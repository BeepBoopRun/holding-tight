import shutil
from time import sleep
from django.core.management.base import BaseCommand, CommandError
from ligand_service import views
from ligand_service.contacts import get_trajectory_frame_count
from ligand_service.models import Simulation
import uuid

from pathlib import Path

from ligand_service.utils import (
    get_user_results_dir,
    get_user_uploads_dir,
    get_user_work_dir,
)

EXAMPLE_USER_UUID = "7a872fc4-2f2d-4170-a5d6-f5d8944b3f87"


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
                get_user_uploads_dir(EXAMPLE_USER_UUID) / sim.sim_id,
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

        while True:
            status_list = [sim.get_analysis_status() for sim in sims]
            print("Current state:", status_list)
            if all([status == "Finished" for status in status_list]):
                break
            if any([status == "Failed" for status in status_list]):
                raise CommandError("Simulation analysis failed!")
            sleep(5)
