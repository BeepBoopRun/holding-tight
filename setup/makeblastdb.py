import requests
import json
from pathlib import Path
import subprocess

Path("blast").absolute().mkdir(exist_ok=True)
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
print(job.stdout.decode())
if job.returncode != 0:
    print(f"FAILURE: Creating blastdb failed! Stderr: {job.stderr.decode()}")

print("SUCCESS: Blastdb successfuly created!")
