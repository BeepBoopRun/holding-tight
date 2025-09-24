from ftplib import FTP
import gzip
import json
from pathlib import Path


from rdkit.Chem import inchi

ftp = FTP("ftp.ebi.ac.uk")
ftp.login()
ftp.cwd("pub/databases/chebi/Flat_file_tab_delimited")
chebi_dir = Path("./chebi").absolute()
chebi_dir.mkdir(exist_ok=True)
print("Downloading files from ChEBI...")

try:
    with open(chebi_dir / "compounds.tsv.gz", "wb") as fp:
        ftp.retrbinary("RETR compounds.tsv.gz", fp.write)
    with open(chebi_dir / "chebiId_inchi.tsv", "wb") as fp:
        ftp.retrbinary("RETR chebiId_inchi.tsv", fp.write)

    inchikey_to_chebiID = {}
    chebiID_to_name = {}
    with open(chebi_dir / "chebiId_inchi.tsv") as f:
        for line in f.readlines()[1:]:
            cols = line.split("\t")
            inchikey = inchi.InchiToInchiKey(cols[1])
            inchikey_to_chebiID[inchikey] = cols[0]

    with gzip.open(chebi_dir / "compounds.tsv.gz", encoding="cp1252", mode="rt") as f:
        for line in f.readlines()[1:]:
            cols = line.split("\t")
            if cols[5] == "null":
                continue
            chebiID_to_name[cols[0]] = cols[5]

    inchikey_to_name = {}
    for inchikey, chebiID in inchikey_to_chebiID.items():
        name = chebiID_to_name.get(chebiID, None)
        if name is None:
            continue
        inchikey_to_name[inchikey] = name

    with open(chebi_dir / "inchikey_to_chebiID.json", "w") as f:
        json.dump(inchikey_to_chebiID, f)
    print("SUCCESS: InChiKey to chebiID dictionary successfuly created!")

    with open(chebi_dir / "inchikey_to_name.json", "w") as f:
        json.dump(inchikey_to_name, f)
    print("SUCCESS: InChiKey to compound name dictionary successfuly created!")

except Exception as e:
    print(f"FAILURE: Failed to prepare data from ChEBI. Error: {e}")
