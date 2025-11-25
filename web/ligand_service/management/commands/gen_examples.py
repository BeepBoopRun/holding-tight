import csv
import shutil
from time import sleep
from datetime import datetime
import uuid
import subprocess as sb
from pathlib import Path


from django.core.management.base import BaseCommand, CommandError
from ligand_service import tasks, views
from ligand_service.contacts import get_trajectory_frame_count
from ligand_service.models import GroupAnalysis, Simulation

from ligand_service.utils import (
    get_user_results_dir,
    get_user_uploads_dir,
    get_user_work_dir,
)

EXAMPLE_USER_UUID = "7a872fc4-2f2d-4170-a5d6-f5d8944b3f87"
EXAMPLE_GROUP_UUID = "6eb09d37-a6bd-41b2-b69f-e7126aae0e26"

DIRNAME_TO_EXP_VALUE = {
    "Alvimopan": 2608.88,
    "Buprenorphine": 3750.0,
    "Nalmefene": 206.88,
    "Naloxone": 70.56,
    "Naltrexone": 171.42,
    "Nmethylnaloxone": 49.98,
    "Nmethylnaltrexone": 40.02,
}


class Command(BaseCommand):
    help = "Generates results from example simulations"

    def handle(self, *args, **options):
        sim_dirs = [dir for dir in Path("./example_sims").absolute().iterdir()]
        if len(sim_dirs) == 0:
            raise CommandError("No simulation directories were provided!")
        for sim in Simulation.objects.filter(user_key=EXAMPLE_USER_UUID):
            shutil.rmtree(
                get_user_uploads_dir(EXAMPLE_USER_UUID) / str(sim.sim_id),
                ignore_errors=True,
            )
            shutil.rmtree(
                get_user_work_dir(EXAMPLE_USER_UUID) / str(sim.sim_id),
                ignore_errors=True,
            )
            shutil.rmtree(get_user_results_dir(str(sim.results_id)), ignore_errors=True)

        Simulation.objects.filter(user_key=EXAMPLE_USER_UUID).delete()
        for dir in sim_dirs:
            sim = Simulation(
                dirname=dir.name,
                user_key=EXAMPLE_USER_UUID,
                sim_id=str(uuid.uuid4()),
            )
            shutil.copytree(
                dir,
                get_user_uploads_dir(EXAMPLE_USER_UUID) / sim.sim_id / dir.name,
            )
            files = sim.get_trajectory_files()
            if files is None:
                sim.delete()
                raise CommandError("Incorrect files were supplied!")
            sim.frame_count = get_trajectory_frame_count(
                files.topology, files.trajectory
            )
            sim.save()
            (get_user_work_dir(EXAMPLE_USER_UUID) / str(sim.sim_id)).mkdir(
                exist_ok=True, parents=True
            )
            (get_user_results_dir(sim.results_id)).mkdir(exist_ok=True, parents=True)
            views.start_sim_task(sim, EXAMPLE_USER_UUID)

        sims = Simulation.objects.filter(user_key=EXAMPLE_USER_UUID)

        # start plip worker
        workers = []
        for i in range(8):
            worker = sb.Popen(
                [
                    "python",
                    "manage.py",
                    "run_huey",
                ]
            )
            workers.append(worker)

        toc = datetime.now()
        while True:
            tic = datetime.now()
            status_list = [sim.get_analysis_status() for sim in sims]
            print(f"Elapsed time: {tic - toc} Current state: {status_list}")
            if all([status == "Finished" for status in status_list]):
                break
            if any([status == "Failed" for status in status_list]):
                raise CommandError("Simulation analysis failed!")
            sleep(5)

        for worker in workers:
            worker.kill()

        analysis = GroupAnalysis.objects.create(
            user_key=EXAMPLE_USER_UUID,
            results_id=EXAMPLE_GROUP_UUID,
        )
        analysis.sims.set(sims)
        group_result_id = analysis.results_id

        dirnames = [sim.dirname for sim in sims]

        parsed_data = {
            "Simulation name": dirnames,
            "Simulation ID": [sim.results_id for sim in sims],
            "Residence Time": [DIRNAME_TO_EXP_VALUE[dirname] for dirname in dirnames],
        }

        results_dirs = [get_user_results_dir(sim.results_id) for sim in sims]
        group_result_dir = get_user_results_dir(str(group_result_id))
        for dir in results_dirs + [group_result_dir]:
            dir.mkdir(parents=True, exist_ok=True)

        with open(group_result_dir / "exp_data.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow([key for key in parsed_data.keys()])
            for idx in range(len(sims)):
                print(idx, flush=True)
                writer.writerow([value[idx] for (key, value) in parsed_data.items()])

        tasks.analyse_group(results_dirs, group_result_dir)

        for dir in results_dirs + [group_result_dir]:
            shutil.copytree(dir, Path("./example_results") / dir.name)
