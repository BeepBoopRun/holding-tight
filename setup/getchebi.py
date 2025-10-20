from ftplib import FTP
import gzip
import json
import csv
from pathlib import Path

ftp = FTP("ftp.ebi.ac.uk")
ftp.login()
ftp.cwd("pub/databases/chebi/flat_files")
chebi_dir = Path("./chebi").absolute()
chebi_dir.mkdir(exist_ok=True)
print("Downloading files from ChEBI...")

try:
    with open(chebi_dir / "compounds.tsv.gz", "wb") as fp:
        print("Downloading compounds list...")
        ftp.retrbinary("RETR compounds.tsv.gz", fp.write)
    with open(chebi_dir / "structures.tsv.gz", "wb") as fp:
        print("Downloading structures to create chebiID to InChIKey map...")
        ftp.retrbinary("RETR structures.tsv.gz", fp.write)

    inchikey_to_compoundId = {}
    compoundId_to_name = {}
    compoundId_to_chebiID = {}
    with gzip.open(chebi_dir / "structures.tsv.gz", encoding="utf-8", mode="rt") as f:
        f.readline()
        for line in csv.reader(f, delimiter="\t"):
            if line[1] == "" or line[6] == "":
                continue
            #        print("InChIKey:", line[6], "compound_id:", line[1])
            inchikey_to_compoundId[line[6]] = line[1]

    with gzip.open(chebi_dir / "compounds.tsv.gz", encoding="utf-8", mode="rt") as f:
        f.readline()
        for line in csv.reader(f, delimiter="\t"):
            if line[0] == "" or line[6] == "":
                continue
            #        print("compound_id:", line[0], "name:", line[1])
            #        print("compound_id:", line[0], "chebiID:", line[6])
            compoundId_to_name[line[0]] = line[1]
            compoundId_to_chebiID[line[0]] = line[6]

    inchikey_to_name = {}
    for inchikey, compoundId in inchikey_to_compoundId.items():
        name = compoundId_to_name.get(compoundId, None)
        if name is None:
            continue
        inchikey_to_name[inchikey] = name

    inchikey_to_chebiID = {}
    for inchikey, compoundId in inchikey_to_compoundId.items():
        chebiID = compoundId_to_chebiID.get(compoundId, None)
        if chebiID is None:
            continue
        inchikey_to_chebiID[inchikey] = chebiID

    with open(chebi_dir / "inchikey_to_chebiID.json", "w") as f:
        json.dump(inchikey_to_chebiID, f)
    print("SUCCESS: InChiKey to chebiID dictionary successfuly created!")

    with open(chebi_dir / "inchikey_to_name.json", "w") as f:
        json.dump(inchikey_to_name, f)
    print("SUCCESS: InChiKey to compound name dictionary successfuly created!")

except Exception as e:
    print(f"FAILURE: Failed to prepare data from ChEBI. Error: {e}")
