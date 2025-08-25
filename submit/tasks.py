from pathlib import Path
from re import sub

from django.utils import timezone
from django.conf import settings
from huey.contrib.djhuey import db_task
from .models import Submission, SubmissionTask

from .contacts import (
    get_files_maestro,
    get_files_dir,
    get_interactions,
    get_numbering,
    get_pdb,
)


def find_interactions(submission: Submission):
    print(submission, flush=True)
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
            print(
                f"Encountered topology and trajectory directory with id: {dir_id}",
                flush=True,
            )
            files = get_files_dir(dir_path)
            if files is None:
                continue
        else:
            # unreachable
            assert False
        get_interactions(
            topology_file=files.topology,
            trajectory_file=files.trajectory,
            outfile=results_dir / f"result{dir_id}.tsv",
        )
    print("ALL CONTACT PATTERNS DONE!", flush=True)

    submission.finished_at = timezone.now()
    submission.save()


def prepare_numbering_pdb(submission: Submission):
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
            print(
                f"Encountered topology and trajectory directory with id: {dir_id}",
                flush=True,
            )
            files = get_files_dir(dir_path)
            if files is None:
                continue
        else:
            # unreachable
            assert False
        get_pdb(
            topology_file=files.topology,
            trajectory_file=files.trajectory,
            outfile=results_dir / f"top{dir_id}.pdb",
        )
        get_numbering(
            pdb_file=results_dir / f"top{dir_id}.pdb",
            outfile=results_dir / f"num_top{dir_id}.pdb",
        )
    print("ALL PDB'S NUMBERED!", flush=True)

def queue_task(submission: Submission, task_type: SubmissionTask.TaskType):
    task = SubmissionTask.objects.create(submission=submission, status="P", task_type=task_type)
    if task_type == SubmissionTask.TaskType.INTERACTIONS:
        queue_interactions(task)
    elif task_type == SubmissionTask.TaskType.NUMBERING:
        queue_numbering(task)
    else: 
        # unreachable
        assert False


# could be written better to make less db calls

@db_task()
def queue_interactions(task: SubmissionTask):
    task.status = "R"
    task.save()
    try:
        find_interactions(task.submission)
    except:
        task.status = "F"
        task.save()
        return
    task.status = "S"
    task.save()
    

@db_task()
def queue_numbering(task: SubmissionTask):
    task.status = "R"
    task.save()
    try:
        prepare_numbering_pdb(task.submission)
    except:
        task.status = "F"
        task.save()
        return
    task.status = "S"
    task.save()
