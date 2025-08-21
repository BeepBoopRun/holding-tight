import requests 
import json
from pathlib import Path
import subprocess



receptor_json_filepath = Path("./receptor_list.json").absolute()

if not receptor_json_filepath.is_file():
    r = requests.get("https://gpcrdb.org/services/receptorlist/", headers={"accept": "application/json"})
    receptors_json = r.json()
    with open(receptor_json_filepath, 'w') as f:
        json.dump(receptors_json, f)
else:
    print("Receptors json file already exists, using available file...")

receptor_fasta_filepath = Path("./receptors.fasta").absolute()
if not receptor_fasta_filepath.is_file():
    with open(receptor_fasta_filepath, 'w') as f_fasta:
        with open(receptor_json_filepath, 'r') as f_json:
            for receptor in json.loads(f_json.read()):
                f_fasta.write(f">{receptor["accession"]}\n{receptor["sequence"]}\n")
else:
    print("Receptor fasta file already exists, using available file...")

makeblastdb_path = Path("./ncbi-blast-2.17.0+/bin/makeblastdb").absolute()
subprocess.run([makeblastdb_path, "-in",  "receptors.fasta", "-dbtype", "prot", "-out", "blast_db"])
