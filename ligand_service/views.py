from pathlib import Path
import csv
import uuid

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.conf import settings

from submit.models import Submission, SubmissionTask
from .tables import ContactsTable, ContactsTableNumbered

from submit.contacts import create_translation_dict


def redirect_to_submit(request):
    return HttpResponseRedirect("/submit")


def render_about(request):
    return render(request, "ligand_service/about.html")


def empty_search(request):
    return render(request, "ligand_service/search_empty.html")


def search(request, job_id):
    try:
        job_id = uuid.UUID(job_id)
        submission = Submission.objects.get(id=job_id)
    except Exception:
        return render(
            request,
            "ligand_service/search.html",
            {"status": "Job ID does not exist!", "job_id": job_id},
        )

    tasks = SubmissionTask.objects.filter(submission=submission)
    if not all([task.status == SubmissionTask.TaskStatus.SUCCESS for task in tasks]):
        return render(
            request,
            "ligand_service/search_ongoing.html",
            {"job_id": job_id, "tasks": tasks},
        )

    sub_id = str(submission.id)
    results_path = Path(settings.MEDIA_ROOT).joinpath(sub_id, "results")

    print("PREPARING TO SHOW CONTACTS", flush=True)
    data = []
    for form in submission.submittedform_set.all():
        file_id = str(form.form_id)
        with open(results_path.joinpath(f"result{file_id}.tsv"), newline="") as csvfile:
            for _ in range(2):
                next(csvfile)

            reader = csv.DictReader(
                csvfile,
                skipinitialspace=True,
                fieldnames=[
                    "frame",
                    "interaction_type",
                    "atom_1",
                    "atom_2",
                    "atom_3",
                    "atom_4",
                ],
                delimiter="\t",
            )
            raw_table = [{k: v for k, v in row.items()} for row in reader]
            if submission.common_numbering:
                dic = create_translation_dict(results_path / f"num_top{file_id}.pdb")
                for row in raw_table:
                    print(row, flush=True)
                    for atom in ["atom_1", "atom_2"]:
                        key = tuple(row[atom].split(":")[0:3])
                        print(key)
                        if key in dic:
                            print(
                                f"KEY: {key} IN THE DIC, VALUE: {dic[key]}", flush=True
                            )
                            row["numbered_residue"] = dic[key][1]
                print(dic, flush=True)
                table = ContactsTableNumbered(raw_table[0:1000])
            else:
                table = ContactsTable(raw_table[0:1000])

            if form.name is not None and form.name != "":
                run_name = form.name
            else:
                run_name = file_id
            data.append(
                (
                    run_name,
                    form.value,
                    table,
                )
            )

    return render(
        request,
        "ligand_service/search_found.html",
        {
            "job_id": job_id,
            "data": data,
            "name_VOI": submission.name_VOI,
        },
    )
