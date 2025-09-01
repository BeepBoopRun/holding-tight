from pathlib import Path
import uuid

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.conf import settings

from .models import Submission, SubmissionTask
from .forms import FileInputFormSet, InputDetails
from .models import SubmittedForm
from .tasks import queue_task

from .contacts import (
    create_translation_dict_by_pdb,
    create_translation_dict_by_vmd,
    get_files_dir,
    get_files_maestro,
)

PAGE_BG_COLOR = "#e5e7eb"


def submit(request):
    formset = FileInputFormSet(prefix="submit")
    details = InputDetails()
    return render(
        request, "submit/index.html", {"formset": formset, "details_form": details}
    )


def handle_uploaded_file(file_handle, path_to_save_location: Path):
    with open(path_to_save_location, "wb+") as destination:
        for chunk in file_handle.chunks():
            destination.write(chunk)


def form(request):
    if request.method == "POST":
        formset = FileInputFormSet(request.POST, request.FILES, prefix="submit")
        details_form = InputDetails(request.POST)

        user_email = None
        compare_by_residue = None
        name_VOI = None

        if details_form.is_valid():
            user_email = details_form.cleaned_data["email"]
            compare_by_residue = details_form.cleaned_data["compare_by_residue"]
            name_VOI = details_form.cleaned_data["name_VOI"]

        submission_id = uuid.uuid4()
        submission_path = Path(settings.MEDIA_ROOT).joinpath(str(submission_id))
        submission_path.mkdir(parents=True)

        submission = Submission.objects.create(
            id=submission_id,
            email=user_email,
            common_numbering=(not compare_by_residue),
            name_VOI=name_VOI,
        )
        submission.save()
        for idx, form in enumerate(formset):
            if not form.is_valid():
                print("INVALID FORM!!".center(20, "-"), flush=True)
                print(form.errors, flush=True)
                break
            form_path = submission_path.joinpath(str(idx))
            print(f"FORM {idx}")
            if form.cleaned_data["choice"] == "MaestroDir":
                file_input = SubmittedForm.FILE_INPUT_TYPES.MAESTRO_DIR
                for file in form.cleaned_data["file"]:
                    path = form_path.joinpath(
                        form.cleaned_data["paths"][file.name]
                    ).parents[0]
                    path.mkdir(parents=True, exist_ok=True)
                    filename = "_".join(file.name.split("_")[2:])
                    handle_uploaded_file(
                        file_handle=file, path_to_save_location=path / filename
                    )
            elif form.cleaned_data["choice"] == "TopTrjPair":
                file_input = SubmittedForm.FILE_INPUT_TYPES.TOPTRJ_PAIR
                for file in form.cleaned_data["file"]:
                    form_path.mkdir(exist_ok=True)
                    handle_uploaded_file(
                        file_handle=file,
                        path_to_save_location=form_path / file.name,
                    )
            SubmittedForm.objects.create(
                form_id=idx,
                submission=submission,
                file_input=file_input,
                value=form.cleaned_data["value"],
                name=form.cleaned_data["name"],
            ).save()
    queue_task(submission, task_type=SubmissionTask.TaskType.INTERACTIONS)

    if not compare_by_residue:
        queue_task(submission, task_type=SubmissionTask.TaskType.NUMBERING)

    return HttpResponseRedirect(f"/search/{submission_id}")


def redirect_to_submit(request):
    return HttpResponseRedirect("/submit")


def render_about(request):
    return render(request, "about.html")


def empty_search(request):
    return render(request, "search/empty.html")


def search(request, job_id):
    try:
        job_id = uuid.UUID(job_id)
        submission = Submission.objects.get(id=job_id)
    except Exception:
        return render(
            request,
            "search/empty.html",
            {"status": "Job ID does not exist!", "job_id": job_id},
        )

    tasks = SubmissionTask.objects.filter(submission=submission)
    if not all([task.status == SubmissionTask.TaskStatus.SUCCESS for task in tasks]):
        return render(
            request,
            "search/ongoing.html",
            {"job_id": job_id, "tasks": tasks},
        )

    sub_id = str(submission.id)
    results_path = Path(settings.MEDIA_ROOT).joinpath(sub_id, "results")

    data = []
    for form in submission.submittedform_set.all():
        file_id = str(form.form_id)
        sub_id = str(submission.id)
        sub_path = Path(settings.MEDIA_ROOT).joinpath(sub_id)
        dir_path = Path(sub_path, file_id)
        with open(results_path.joinpath(f"result{file_id}.tsv"), newline="") as csvfile:
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
            if submission.common_numbering:
                if form.file_input == "M":
                    files = get_files_maestro(dir_path)
                elif form.file_input == "T":
                    files = get_files_dir(dir_path)
                if files is None:
                    continue
                dic = create_translation_dict_by_pdb(
                    results_path / f"num_top{file_id}.pdb"
                )

                def get_numbering_pdb(row):
                    assert dic is not None
                    for atom in ["Atom 1", "Atom 2"]:
                        key = tuple(row[atom].split(":")[0:3])
                        if key in dic:
                            return dic[key][1]

                df["PDB numbering"] = df.apply(get_numbering_pdb, axis=1)
                print(df, flush=True)
                dic = create_translation_dict_by_vmd(files.topology, files.trajectory)

                def get_numbering_api(row):
                    assert dic is not None
                    for atom in ["Atom 1", "Atom 2"]:
                        key = tuple(row[atom].split(":")[0:3])
                        if key in dic:
                            return dic[key]

                df["BLAST numbering"] = df.apply(get_numbering_api, axis=1)

            if form.name is not None and form.name != "":
                run_name = f'"{form.name}"'
            else:
                run_name = file_id

            layout_config = dict(
                margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=PAGE_BG_COLOR
            )
            fig = go.Figure(
                data=[
                    go.Table(
                        header=dict(values=list(df.columns), line_color=PAGE_BG_COLOR),
                        cells=dict(
                            values=[
                                df[col].apply(
                                    lambda x: "-" if x is None or pd.isna(x) else x
                                )
                                for col in df.columns
                            ],
                            height=25,
                            line_color=PAGE_BG_COLOR,
                        ),
                    )
                ]
            )
            fig.update_layout(layout_config)
            plotly_table = fig.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                config={"displaylogo": False, "responsive": True},
            )

            interaction_count = (
                df.groupby(["Frame", "Interaction"])
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
            fig.update_layout(layout_config)
            plotly_graph = fig.to_html(
                full_html=False,
                include_plotlyjs="cdn",
                config={"displaylogo": False, "responsive": True},
            )
            data.append(
                (
                    run_name,
                    form.value,
                    plotly_table,
                    plotly_graph,
                )
            )

    return render(
        request,
        "search/found.html",
        {
            "job_id": job_id,
            "data": data,
            "name_VOI": submission.name_VOI,
        },
    )
