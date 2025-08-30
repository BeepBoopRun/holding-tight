import requests
import json
from pathlib import Path
import subprocess

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prepares blastdb, using GPCRdb database"

    def handle(self, *args, **options):
        receptor_json_filepath = Path("blast/receptor_list.json").absolute()
        r = requests.get(
            "https://gpcrdb.org/services/receptorlist/",
            headers={"accept": "application/json"},
        )
        receptors_json = r.json()
        with open(receptor_json_filepath, "w") as f:
            json.dump(receptors_json, f)

        receptor_fasta_filepath = Path("blast/receptors.fasta").absolute()
        with open(receptor_fasta_filepath, "w") as f_fasta:
            with open(receptor_json_filepath, "r") as f_json:
                for receptor in json.loads(f_json.read()):
                    f_fasta.write(
                        f">{receptor['accession']}|{receptor['entry_name']}\n{receptor['sequence']}\n"
                    )

        job = subprocess.run(
            [
                "makeblastdb",
                "-in",
                "./blast/receptors.fasta",
                "-dbtype",
                "prot",
                "-out",
                "./blast/blast_db",
            ],
            capture_output=True,
        )
        self.stdout.write(job.stdout.decode())
        if job.returncode != 0:
            self.style.ERROR(f"Creating blastdb failed! Stdout: {job.stderr.decode()}")

        self.stdout.write(self.style.SUCCESS("Blastdb successfuly created!"))
