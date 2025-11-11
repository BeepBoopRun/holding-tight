from django.db import models

import uuid
from pathlib import Path
from typing import NamedTuple

from huey.contrib.djhuey import HUEY as huey

from .utils import get_user_uploads_dir, get_user_work_dir

from vmd import molecule
from django_prometheus.models import ExportModelOperationsMixin


class TrajectoryFiles(NamedTuple):
    topology: Path
    trajectory: Path


def filetype(file: Path) -> str:
    filetype = file.suffix[1:]
    if filetype == "cms":
        filetype = "mae"
        return filetype
    return filetype


def get_trajectory_frame_count(topology_file: Path, trajectory_file: Path) -> int:
    molid = molecule.load(filetype(topology_file), str(topology_file))
    num_frames = molecule.numframes(molid)
    print("Number of frames before loading trajectory", num_frames)
    molecule.read(
        molid=molid,
        filetype=filetype(trajectory_file),
        filename=str(trajectory_file),
        waitfor=-1,
    )
    count = molecule.numframes(molid) - num_frames
    molecule.delete(molid)
    return count


class Simulation(ExportModelOperationsMixin("simulation"), models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    dirname = models.CharField(max_length=128)
    user_key = models.CharField(max_length=32)
    analysis_task_id = models.UUIDField(null=True, default=None, unique=True)
    frame_count = models.IntegerField(null=True, default=None)
    sim_id = models.UUIDField(null=True, default=uuid.uuid4, unique=True)
    # internal, used for start / delete
    results_id = models.UUIDField(null=True, default=uuid.uuid4, unique=True)
    # shared, used to find and share results

    was_deleted = models.BooleanField(default=False)

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

    def has_failed(self) -> bool | Exception:
        if self.analysis_task_id is None:
            return False
        try:
            if huey.result(str(self.analysis_task_id), preserve=True) is not None:
                return False
        except Exception as e:
            return e
        return False

    # NOTE: Could be remade with huey signals, didn't notice them at the start!
    def get_analysis_status(self) -> str:
        if self.is_not_queued():
            return "Not queued"
        elif self.is_running():
            # TODO: Add runinfo
            files = self.get_trajectory_files()
            frame_count = get_trajectory_frame_count(files.topology, files.trajectory)
            plip_dir = get_user_work_dir(self.user_key) / str(self.sim_id) / "plip"
            if not plip_dir.is_dir():
                return "Queued"
            frames_done = len([x for x in plip_dir.iterdir()])
            if frames_done == 0:
                return "Queued"
            return f"Running {frames_done} / {frame_count} frames"
        elif self.has_failed():
            return "Failure"
        elif self.is_finished():
            return "Finished"
        else:
            return "Unknown"

    def get_sim_dir(self) -> Path:
        return get_user_uploads_dir(self.user_key) / str(self.sim_id)

    def get_trajectory_files(self) -> TrajectoryFiles | None:
        dir = self.get_sim_dir()
        maestro_files = get_files_maestro(dir)
        print("MAESTRO DIR: ", maestro_files)
        if maestro_files is not None:
            return maestro_files
        return get_files_dir(dir)


class GroupAnalysis(ExportModelOperationsMixin("group_analysis"), models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user_key = models.CharField(max_length=32)
    results_id = models.UUIDField(null=True, default=uuid.uuid4)
    sims = models.ManyToManyField(Simulation, related_name="simulations")


class GPCRdbResidueAPI(ExportModelOperationsMixin("GPCRdb_calls"), models.Model):
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
            # creating an empty file is needed, for vmd to load the trajectory
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
