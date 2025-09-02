from pathlib import Path

from django.utils import timezone
from django.conf import settings
from huey.contrib.djhuey import db_task
import plotly.express as px
import pandas as pd
import plotly.graph_objects as go

from .models import Submission, SubmissionTask, SubmittedForm
from .contacts import (
    get_interactions,
    get_numbering,
    get_pdb,
    create_translation_dict_by_pdb,
    create_translation_dict_by_blast,
)

PAGE_BG_COLOR = "#e5e7eb"
COMMON_LAYOUT = dict(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=PAGE_BG_COLOR)

INTERACTION_TYPES_LONG = {
    "sb": "Salt bridges",
    "pc": "Pi-cation",
    "ps": "Pi-stacking",
    "ts": "T-stacking",
    "vdw": "van der Waals",
    "hbbb": "BB–BB H-bond",
    "hbsb": "BB–SC H-bond",
    "hbss": "SC–SC H-bond",
    "wb": "Water-med. H-bond",
    "wb2": "Ext. water-med. H-bond",
    "hblb": "Lig.–BB H-bond",
    "hbls": "Lig.–SC H-bond",
    "lwb": "Lig.–water H-bond",
    "lwb2": "Lig.–ext. water H-bond",
}


def save_file(file_handle, path_to_save_location: Path):
    with open(path_to_save_location, "wb+") as destination:
        for chunk in file_handle.chunks():
            destination.write(chunk)


def find_interactions(submission: Submission):
    print(submission, flush=True)
    results_dir = submission.get_results_directy()
    results_dir.mkdir(exist_ok=True)
    print("Preparing to run GetContacts...", flush=True)
    for form in submission.submittedform_set.all():
        files = form.get_trajectory_files()
        file_id = str(form.form_id)
        get_interactions(
            topology_file=files.topology,
            trajectory_file=files.trajectory,
            outfile=results_dir / f"result{file_id}.tsv",
        )
    print("All GetContacts calls finished!", flush=True)

    submission.finished_at = timezone.now()
    submission.save()


def prepare_numbering_pdb(submission: Submission):
    results_dir = submission.get_results_directy()
    results_dir.mkdir(exist_ok=True)
    for form in submission.submittedform_set.all():
        files = form.get_trajectory_files()
        file_id = str(form.form_id)
        get_pdb(
            topology_file=files.topology,
            trajectory_file=files.trajectory,
            outfile=results_dir / f"top{file_id}.pdb",
        )
        get_numbering(
            pdb_file=results_dir / f"top{file_id}.pdb",
            outfile=results_dir / f"num_top{file_id}.pdb",
        )
    print("Numbering PDB files complete", flush=True)


def load_getcontacts_csv(file: Path | str) -> pd.DataFrame:
    with open(file, newline="") as csvfile:
        for _ in range(2):
            next(csvfile)

        df = pd.read_csv(
            csvfile,
            names=[
                "Frame",
                "Interaction",
                "Atom 1",
                "Atom 2",
                "Atom 3",
                "Atom 4",
            ],
            delimiter="\t",
            header=None,
        )
        return df


def create_getcontacts_table(get_contacts_df: pd.DataFrame) -> str:
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(get_contacts_df.columns), line_color=PAGE_BG_COLOR
                ),
                cells=dict(
                    values=[
                        get_contacts_df[col].apply(
                            lambda x: "-" if x is None or pd.isna(x) else x
                        )
                        for col in get_contacts_df.columns
                    ],
                    line_color=PAGE_BG_COLOR,
                ),
            )
        ]
    )
    fig.update_traces(columnwidth=[100, 300])
    fig.update_layout(COMMON_LAYOUT)
    table = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displaylogo": False, "responsive": True},
    )
    return table


def create_interaction_area_graph(get_contacts_df: pd.DataFrame) -> str:
    interaction_count = (
        get_contacts_df.groupby(["Frame", "Interaction"])
        .agg(Count=("Atom 1", "count"))
        .reset_index()
    )
    print(interaction_count, flush=True)
    fig = px.area(
        interaction_count,
        x="Frame",
        y="Count",
        title="Interaction counts",
        line_group="Interaction",
        color="Interaction",
    )
    fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="linear"))
    fig.update_layout(COMMON_LAYOUT)
    graph = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displaylogo": False, "responsive": True},
    )
    return graph


def analyse_submission(submission: Submission):
    results_path = submission.get_results_directy()
    group_data = {"status": "TO BE ADDED!"}
    runs_data = []

    for form in submission.submittedform_set.all():
        run_data = {}
        file_id = str(form.form_id)
        df = load_getcontacts_csv(results_path / f"result{file_id}.tsv")
        df["Interaction"] = df["Interaction"].apply(lambda x: INTERACTION_TYPES_LONG[x])
        if submission.common_numbering:
            files = form.get_trajectory_files()
            dic = create_translation_dict_by_pdb(results_path / f"num_top{file_id}.pdb")

            def get_numbering_pdb(row):
                assert dic is not None
                for atom in ["Atom 1", "Atom 2"]:
                    key = tuple(row[atom].split(":")[0:3])
                    if key in dic:
                        return dic[key][1]

            df["PDB numbering"] = df.apply(get_numbering_pdb, axis=1)
            print(df, flush=True)

            dic = create_translation_dict_by_blast(files.topology, files.trajectory)

            def get_numbering_blast(row):
                assert dic is not None
                for atom in ["Atom 1", "Atom 2"]:
                    key = tuple(row[atom].split(":")[0:3])
                    if key in dic:
                        return dic[key]

            df["BLAST numbering"] = df.apply(get_numbering_blast, axis=1)
            run_data["interaction_graph"] = create_interaction_area_graph(df)
        run_data["table"] = create_getcontacts_table(df)
        run_data["value"] = form.value
        runs_data.append(run_data)

    return (group_data, runs_data)


def queue_task(submission: Submission, task_type: SubmissionTask.TaskType):
    task = SubmissionTask.objects.create(
        submission=submission, status="P", task_type=task_type
    )
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
    except Exception as e:
        print(f"Interaction tasks failed! Error: {e}")
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
    except Exception as e:
        print(f"Numbering tasks failed! Error: {e}")
        task.status = "F"
        task.save()
        return
    task.status = "S"
    task.save()
