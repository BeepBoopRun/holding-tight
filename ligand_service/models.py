from django.db import models
from django.conf import settings

import uuid
from pathlib import Path
from typing import NamedTuple

from huey.contrib.djhuey import HUEY as huey
from .utils import get_user_uploads_dir


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


class UploadedFiles(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    dirname = models.CharField(max_length=128)
    user_key = models.CharField(max_length=32)
    analysis_task_id = models.UUIDField(null=True, default=None)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dirname", "user_key"], name="enforce_unique_directories"
            )
        ]

    def __str__(self):
        return self.dirname

    def is_not_queued(self) -> bool:
        return self.analysis_task_id is None

    def is_running(self) -> bool:
        if self.analysis_task_id is None:
            return False
        try:
            if huey.result(str(self.analysis_task_id), preserve=True) is None:
                return True
        except Exception:
            return False
        return False

    def is_finished(self) -> bool:
        if self.analysis_task_id is None:
            return False
        try:
            if huey.result(str(self.analysis_task_id), preserve=True) is not None:
                return True
        except Exception:
            return False
        return False

    def has_failed(self) -> bool:
        if self.analysis_task_id is None:
            return False
        try:
            if huey.result(str(self.analysis_task_id), preserve=True) is not None:
                return False
        except Exception as e:
            return e
        return False

    def get_analysis_status(self) -> str:
        if self.is_not_queued():
            return "Not queued"
        elif self.is_running():
            # TODO: Add runinfo
            return "Running"
        elif self.has_failed():
            return "Failure"
        elif self.is_finished():
            return "Finished"
        else:
            return "Unknown"

    def get_sim_dir(self):
        return get_user_uploads_dir(self.user_key) / self.dirname

    def get_trajectory_files(self) -> TrajectoryFiles | None:
        dir = self.get_sim_dir()
        maestro_files = get_files_maestro(dir)
        print("MAESTRO DIR: ", maestro_files)
        if maestro_files is not None:
            return maestro_files
        return get_files_dir(dir)


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


def get_files_maestro(dir: Path) -> TrajectoryFiles | None:
    subdirs = [x for x in dir.rglob("*") if x.is_dir()]
    chosen_trj = None
    chosen_top = None
    for subdir in subdirs:
        print(subdir, flush=True)
        if subdir.name.endswith("_trj"):
            trj_stump = subdir / "clickme.dtr"
            open(trj_stump, "w").close()
            chosen_trj = trj_stump
            print("chosen trj!", flush=True)
            break
    for file in dir.rglob("*"):
        if file.is_file() and file.name.endswith("-out.cms"):
            chosen_top = file
            print("chosen top!", flush=True)
            break

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
