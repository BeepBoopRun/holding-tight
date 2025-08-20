from pathlib import Path
import csv

from django.db.models import ObjectDoesNotExist
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.conf import settings

from submit.models import Submission
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
        submission = Submission.objects.get(id=job_id)
    except ObjectDoesNotExist:
        return render(
            request,
            "ligand_service/search.html",
            {"status": "Job ID does not exist!", "job_id": job_id},
        )

    if submission.finished_at is None:
        return render(
            request,
            "ligand_service/search.html",
            {"status": "Ongoing", "job_id": job_id},
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
            data.append(
                (
                    file_id,
                    form.value,
                    table,
                )
            )

    return render(
        request,
        "ligand_service/search.html",
        {
            "status": "Success",
            "job_id": job_id,
            "data": data,
            "name_VOI": submission.name_VOI,
        },
    )
