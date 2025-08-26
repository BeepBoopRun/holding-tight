from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings

from .forms import FileInputFormSet, InputDetails
from .models import Submission, SubmittedForm, SubmissionTask
from .tasks import queue_task

from pathlib import Path
import uuid


def index(request):
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


def search(request):
    return HttpResponse("Response")
