from pathlib import Path

from django.utils import timezone
from django.conf import settings
from huey.contrib.djhuey import db_task
from .models import Submission

from .contacts import *

from huey.contrib.djhuey import HUEY, task
HUEY.flush()

def analyse_submission(submission: Submission):
    sub_id = str(submission.id)
    sub_path = Path(settings.MEDIA_ROOT).joinpath(sub_id)
    results_dir = sub_path.joinpath("results")
    results_dir.mkdir(exist_ok=True)
    print("READING CONTACT PATTERNS", flush=True)
    for form in submission.submittedform_set.all():
        dir_id = str(form.form_id)
        dir_path = Path(sub_path, dir_id)
        if form.file_input == "M":
            print(f"Encountered maestro dir with id: {dir_id}", flush=True)
            files = get_files_maestro(dir_path)
            if files is None:
                continue
        elif form.file_input == "T":
            print(f"Encountered topology and trajectory directory with id: {dir_id}", flush=True)
            files = get_files_dir(dir_path)
            if files is None:
                continue
        else:
            continue
        get_interactions(topology_file=files.topology, trajectory_file=files.trajectory, outfile=results_dir / f"result{dir_id}.tsv")
    print("ALL CONTACT PATTERNS DONE!", flush=True)

    submission.finished_at = timezone.now()
    submission.save()

def prepare_numbering(submission: Submission):
    sub_id = str(submission.id)
    sub_path = Path(settings.MEDIA_ROOT).joinpath(sub_id)
    results_dir = sub_path.joinpath("results")
    results_dir.mkdir(exist_ok=True)
    print("CREATING PDB FILES, NUMERING THEM!", flush=True)
    for form in submission.submittedform_set.all():
        dir_id = str(form.form_id)
        dir_path = Path(sub_path, dir_id)
        if form.file_input == "M":
            print(f"Encountered maestro dir with id: {dir_id}", flush=True)
            files = get_files_maestro(dir_path)
            if files is None:
                continue
        elif form.file_input == "T":
            print(f"Encountered topology and trajectory directory with id: {dir_id}", flush=True)
            files = get_files_dir(dir_path)
            if files is None:
                continue
        else:
            continue
        get_pdb(topology_file=files.topology, trajectory_file=files.trajectory, outfile=results_dir / f"top{dir_id}.pdb")
        get_numbering(pdb_file=results_dir / f"top{dir_id}.pdb", outfile=results_dir / f"num_top{dir_id}.pdb")
    print("ALL PDB'S NUMBERED!", flush=True)


@db_task()
def queue_submission(submission: Submission):
    analyse_submission(submission)

@task()
def queue_numbering(submission: Submission):
    prepare_numbering(submission)
