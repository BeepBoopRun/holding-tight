from django.db import models
from django.conf import settings

import uuid
from pathlib import Path
from typing import NamedTuple


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True, default=None)
    name_VOI = models.CharField(null=True, blank=True, default=None)
    email = models.EmailField(null=True, blank=True, default=None)
    common_numbering = models.BooleanField()

    def get_main_directory(self):
        return Path(settings.MEDIA_ROOT).joinpath(str(self.id))

    def get_results_directy(self):
        return self.get_main_directory().joinpath("results")


class TrajectoryFiles(NamedTuple):
    topology: Path
    trajectory: Path

class SubmittedForm(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    form_id = models.IntegerField()
    value = models.FloatField()
    name = models.CharField(null=True, blank=True, default=None)

    class FILE_INPUT_TYPES(models.TextChoices):
        MAESTRO_DIR = "M", "MaestroDir"
        TOPTRJ_PAIR = "T", "TopTrjPair"

    file_input = models.CharField(max_length=1, choices=FILE_INPUT_TYPES)

    def get_main_directory(self):
        return self.submission.get_main_directory().joinpath(str(self.form_id))

    def get_trajectory_files(self) -> TrajectoryFiles:
        if self.file_input == SubmittedForm.FILE_INPUT_TYPES.MAESTRO_DIR:
            files = get_files_maestro(self.get_main_directory())
        elif self.file_input == SubmittedForm.FILE_INPUT_TYPES.TOPTRJ_PAIR:
            files = get_files_dir(self.get_main_directory())
        else:
            # unreachable
            assert False
        return files


class SubmissionTask(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)

    class TaskStatus(models.TextChoices):
        PENDING = "P", "Pending"
        RUNNING = "R", "Running"
        FAILED = "F", "Failed"
        SUCCESS = "S", "Success"

    status = models.CharField(max_length=1, choices=TaskStatus)

    class TaskType(models.TextChoices):
        NUMBERING = "N", "Numbering"
        INTERACTIONS = "I", "Calculating interactions"
        ANALYSIS = "A", "Analysing interaction results"

    task_type = models.CharField(max_length=1, choices=TaskType)
    task_progress_info = models.JSONField(default=list, blank=True)

    def get_task_progress_info(self):
        return self.task_progress_info or {}


class GPCRdbResidueAPI(models.Model):
    uniprot_identifier = models.CharField(max_length=12)
    response_json = models.JSONField()



def get_files_maestro(directory: Path) -> TrajectoryFiles | None:
    top_candidates: list[Path] = []
    trj_candidates: list[Path] = []

    for file in directory.rglob("*"):
        if file.suffix == ".cms":
            top_candidates.append(file)
        elif file.suffix == ".dtr":
            trj_candidates.append(file)

    if not top_candidates or not trj_candidates:
        print("Needed files not found in given directory!")
        return None

    chosen_top = None
    chosen_trj = None

    for candidate in top_candidates:
        if candidate.name.endswith("out.cms"):
            chosen_top = candidate
            break
    if chosen_top is None:
        chosen_top = sorted(top_candidates)[0]

    for candidate in trj_candidates:
        if candidate.name == "clickme.dtr":
            chosen_trj = candidate
            break
    if chosen_trj is None:
        chosen_trj = sorted(trj_candidates)[0]

    if chosen_top is None or chosen_trj is None:
        return None

    return TrajectoryFiles(chosen_top, chosen_trj)


def get_files_dir(directory: Path) -> TrajectoryFiles | None:
    top = None
    trj = None
    for file in directory.iterdir():
        if file.suffix in [".pdb", ".psf"] and top is None:
            top = file
        elif file.suffix in [".dcd", ".xtc", ".trr"] and trj is None:
            trj = file
        if top is not None and trj is not None:
            return TrajectoryFiles(top, trj)
    return None
