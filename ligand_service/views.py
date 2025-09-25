from pathlib import Path
import uuid
import json
import logging


from django.http import HttpResponseRedirect
from django.http.response import HttpResponseBadRequest
from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse, Http404

from ligand_service.contacts import get_trajectory_frame_count

from .models import Submission, SubmissionTask
from .forms import FileInputFormSet, InputDetails
from .models import SubmittedForm
from .tasks import queue_task

logger = logging.getLogger(__name__)


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
    logger.info(f"Form submission request received, headers: {request.headers}")
    if request.method == "POST":
        logger.info("Form submission method is POST")
        formset = FileInputFormSet(request.POST, request.FILES, prefix="submit")
        details_form = InputDetails(request.POST)

        user_email = None
        compare_by_residue = None
        name_VOI = None

        logger.info("Checking for valid details form...")
        if details_form.is_valid():
            user_email = details_form.cleaned_data["email"]
            compare_by_residue = details_form.cleaned_data["compare_by_residue"]
            name_VOI = details_form.cleaned_data["name_VOI"]
            logger.info("Details form is valid")
        else:
            logger.info("Details form is NOT valid")

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
        logger.info(f"Created a submission object: {submission_id}")
        for idx, form in enumerate(formset):
            if not form.is_valid():
                logger.warning(f"Form {idx} is not valid!: {form.errors}")
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
                value=form.cleaned_data["value"] or 0,
                name=form.cleaned_data["name"],
            ).save()
        queue_task(submission, task_type=SubmissionTask.TaskType.INTERACTIONS)
        queue_task(submission, task_type=SubmissionTask.TaskType.ANALYSIS)
    else:
        logger.warning(
            f"Form submission method is {request.method}, sending BadRequest response"
        )
        return HttpResponseBadRequest()
    logger.info(f"Submission form is valid, redirecting to /search/{submission_id}")
    return HttpResponseRedirect(f"/search/{submission_id}")


def redirect_to_submit(request):
    return HttpResponseRedirect("/submit")


def render_about(request):
    return render(request, "about.html")


def empty_search(request):
    return render(request, "search/empty.html")


def example_submission(request):
    return render(request, "example_submission.html")


def search(request, job_id):
    try:
        job_id = uuid.UUID(job_id)
        submission = Submission.objects.get(id=job_id)
    except Exception:
        return render(
            request,
            "search/empty.html",
            {"message": "Selected JOB ID does not exist!", "job_id": job_id},
        )

    tasks = SubmissionTask.objects.filter(submission=submission)
    if not all([task.status == SubmissionTask.TaskStatus.SUCCESS for task in tasks]):
        results_path = submission.get_results_directy()
        for task in tasks:
            print(task.__dict__, flush=True)
            if (
                task.status != SubmissionTask.TaskStatus.PENDING
                and task.status != SubmissionTask.TaskStatus.FAILED
            ):
                forms_progress_info = []
                for form in submission.submittedform_set.all():
                    files = form.get_trajectory_files()
                    frame_count = get_trajectory_frame_count(
                        files.topology, files.trajectory
                    )
                    file_id = str(form.form_id)
                    processed_frames_dir = (
                        results_path / f"interactions_data_{file_id}" / "results"
                    )
                    frames_processed = 0
                    if processed_frames_dir.is_dir():
                        frames_processed = len(
                            [x for x in processed_frames_dir.iterdir()]
                        )
                    forms_progress_info.append(
                        {f"Form {form.form_id}": f"{frames_processed}/{frame_count} frames"}
                    )
                task.task_progress_info = forms_progress_info
                task.save()

        return render(
            request,
            "search/ongoing.html",
            {"job_id": job_id, "tasks": tasks},
        )

    results_path = submission.get_results_directy()
    filenames = []

    filenames = [None] * len(submission.submittedform_set.all())

    for dir in submission.get_main_directory().iterdir():
        if dir.is_dir() and dir.name != "results":
            filenames[int(dir.name)] = ", ".join([x.name for x in dir.iterdir()])

    with open(results_path / "group_data.json") as f:
        group_data = json.load(f)

    with open(results_path / "runs_data.json") as f:
        runs_data = json.load(f)

    for run, filename in zip(runs_data, filenames):
        run["filename"] = filename

    return render(
        request,
        "search/found.html",
        {
            "job_id": job_id,
            "runs_data": runs_data,
            "group_data": group_data,
            "name_VOI": submission.name_VOI,
            "DEBUG": settings.DEBUG,
        },
    )


def download_file(request, filepath):
    filepath = Path("./user_uploads/" + filepath)
    if filepath.is_file():
        return FileResponse(
            open(filepath, "rb"), as_attachment=True, filename=filepath.name
        )
    else:
        raise Http404("File does not exist")
