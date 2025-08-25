from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings

from .forms import FileInputFormSet, InputDetails
from .models import Submission, SubmittedForm
from .tasks import queue_numbering, queue_submission

from pathlib import Path
import uuid
import shutil


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
        use_common_numbering = None
        name_VOI = None

        if details_form.is_valid():
            user_email = details_form.cleaned_data["email"]
            use_common_numbering = details_form.cleaned_data["use_common_numbering"]
            name_VOI = details_form.cleaned_data["name_VOI"]

        submission_id = uuid.uuid4()
        submission_path = Path(settings.MEDIA_ROOT).joinpath(str(submission_id))
        submission_path.mkdir(parents=True)

        submission = Submission.objects.create(
            id=submission_id,
            email=user_email,
            common_numbering=use_common_numbering,
            name_VOI=name_VOI,
        )
        verified_submission = True
        try:
            for idx, form in enumerate(formset):
                if not form.is_valid():
                    print("INVALID FORM!!".center(20, "-"), flush=True)
                    print(form.errors, flush=True)
                    verified_submission = False
                    break

                form_path = submission_path.joinpath(str(idx))
                print(f"FORM {idx}")

                if form.cleaned_data["choice"] == "MaestroDir":
                    SubmittedForm.objects.create(
                        form_id=idx,
                        submission=submission,
                        file_input="M",
                        value=form.cleaned_data["value"],
                        name=form.cleaned_data["name"],
                    ).save()
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
                    SubmittedForm.objects.create(
                        form_id=idx,
                        submission=submission,
                        file_input="T",
                        value=form.cleaned_data["value"],
                        name=form.cleaned_data["name"],
                    ).save()
                    for file in form.cleaned_data["file"]:
                        form_path.mkdir(exist_ok=True)
                        handle_uploaded_file(
                            file_handle=file,
                            path_to_save_location=form_path / file.name,
                        )

                else:
                    verified_submission = False
                    submission.delete()
                    print(
                        f"Unsupported file input format used: {form.cleaned_data['choice']}"
                    )
                    break
        finally:
            if not verified_submission:
                shutil.rmtree(submission_path)
                return HttpResponse("Bad request!")

    else:
        print("Method other than POST", flush=True)
    print(submission, flush=True)
    submission.save()
    queue_submission(submission)

    if use_common_numbering is True:
        queue_numbering(submission)

    return HttpResponseRedirect(f"/search/{submission_id}")


def search(request):
    return HttpResponse("Response")
