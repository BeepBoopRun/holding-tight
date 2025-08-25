import requests
import sys
import os
import subprocess as sb
from pathlib import Path
from typing import NamedTuple
import subprocess as sb

from vmd import molecule, atomsel

BLASTP_PATH = os.path.abspath("../blast/ncbi-blast-2.17.0+/bin/blastp")
BLASTDB_PATH = os.path.abspath("../blast/blast_db")

DYNAMIC_CONTACTS_PATH = os.path.abspath("getcontacts/get_dynamic_contacts.py")
CURRENT_INTERPRETER_PATH = sys.executable
CORES_AVAILABLE = "12"
GPCRDB_NUMBERING_ENDPOINT = (
    "https://gpcrdb.org/services/structure/assign_generic_numbers"
)
GPCRDB_RESIDUES_EXTENDED_ENDPOINT = "https://gpcrdb.org/services/residues/extended/"

THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASH": "0",  # no idea
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLU": "E",
    "GLN": "Q",
    "GLY": "G",
    "HIS": "H",
    "HIE": "H",  # unsure
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "UNK": "X",
}

def get_uniprot_identifier(seq: str) -> str | None:
    job = sb.run([BLASTP_PATH, "-query", "-", "-db", BLASTDB_PATH, "-max_target_seqs", "1"], capture_output=True, input=seq.encode())
    if job.returncode != 0:
        print(f"Getting accession number failed! Input: {seq}")
        return None
    for line in job.stdout.decode().splitlines():
        if line.startswith(">"):
            return line.strip()[1:].split("|")[1]
    return None

def filetype(file: Path) -> str:
    filetype = file.suffix[1:]
    if filetype == "cms":
        filetype = "mae"
        return filetype
    return filetype

def get_sequence2(topology_file: Path, trajectory_file: Path) -> str:
    molid = molecule.load(filetype(topology_file), str(topology_file))
    molecule.read(molid, filetype(trajectory_file), str(trajectory_file))

    protein = atomsel("protein", molid=molid)
    residues = [None] * (max(protein.residue) + 1)
    for (chain, resname, residue_id, atom_name) in zip(protein.chain, protein.resname, protein.residue, protein.name):
        residues[residue_id] = THREE_TO_ONE.get(resname, "X")
    return "".join(residues)

class VMDFiles(NamedTuple):
    topology: Path
    trajectory: Path


def get_files_maestro(directory: Path) -> VMDFiles | None:
    print(f"Directory: {directory}")

    top_candidates: list[Path] = []
    trj_candidates: list[Path] = []

    for file in directory.rglob("*"):
        if file.suffix == ".cms":
            top_candidates.append(file)
        elif file.suffix == ".dtr":
            trj_candidates.append(file)

    if not top_candidates or not trj_candidates:
        print("Needed files not found in given directory!")
        return None

    chosen_top = None
    chosen_trj = None

    for candidate in top_candidates:
        if candidate.name.endswith("out.cms"):
            chosen_top = candidate
            break
    if chosen_top is None:
        chosen_top = sorted(top_candidates)[0]

    for candidate in trj_candidates:
        if candidate.name == "clickme.dtr":
            chosen_trj = candidate
            break
    if chosen_trj is None:
        chosen_trj = sorted(trj_candidates)[0]

    if chosen_top is None or chosen_trj is None:
        return None

    return VMDFiles(chosen_top, chosen_trj)


def get_files_dir(directory: Path) -> VMDFiles | None:
    top = None
    trj = None
    for file in directory.iterdir():
        if file.suffix in [".pdb", ".psf"] and top is None:
            top = file
        elif file.suffix in [".dcd", ".xtc", ".trr"] and trj is None:
            trj = file
        if top is not None and trj is not None:
            return VMDFiles(top, trj)
    return None


def get_interactions(topology_file: Path, trajectory_file: Path, outfile: Path):
    process = sb.Popen(
        [
            CURRENT_INTERPRETER_PATH,
            DYNAMIC_CONTACTS_PATH,
            "--trajectory",
            trajectory_file,
            "--topology",
            topology_file,
            "--itypes",
            "all",
            "--output",
            outfile,
            "--sele2",
            "ligand",
            "--cores",
            CORES_AVAILABLE,
        ],
        stdout=sb.PIPE,
        stderr=sb.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None

    for line in process.stdout:
        print("Output:", line.strip())  # or parse percentage here

    process.wait()
    print("Done!")


def get_pdb(topology_file: Path, trajectory_file: Path, outfile: Path):
    molid = molecule.load(filetype(topology_file), str(topology_file))
    molecule.read(molid, filetype(trajectory_file), str(trajectory_file))

    sel = atomsel("all", molid=molid)
    sel.write("pdb", str(outfile))


def get_numbering(pdb_file: Path, outfile: Path):
    with open(pdb_file, "rb") as f:
        files = {"pdb_file": f}
        response = requests.post(GPCRDB_NUMBERING_ENDPOINT, files=files)

    if response.ok:
        with open(outfile, "wb") as f:
            f.write(response.content)
    else:
        print(
            f"Failed to fetch numbering! Error {response.status_code}: {response.text}"
        )


def get_residues_extended(uniprot_identifier: str) -> str|None:
    url = GPCRDB_RESIDUES_EXTENDED_ENDPOINT + uniprot_identifier
    print(url)
    response = requests.post(url)
    print(response)
    if response.ok:
        return response.json()
    return None


def create_translation_dict(
    numbered_pdb: Path,
) -> dict[tuple[str, str, str], list[str]]:
    trans_dict = {}
    with open(numbered_pdb, "r") as f:
        print("File open...")
        for line in f.readlines():
            if line[0:4] != "ATOM":
                continue
            atom_name = line[12:15].strip()
            residue_name = line[17:20].strip()
            sequence_number = line[22:26].strip()
            chain = line[21]
            atom_identifier = (chain, residue_name, sequence_number)
            if atom_name == "N":
                BW_number = line[61:66].strip()
                if (
                    float(BW_number) <= 0
                    or float(BW_number) >= 8.1
                    or float(BW_number) == 0
                ):
                    continue
                if atom_identifier in trans_dict:
                    trans_dict[atom_identifier][0] = BW_number
                else:
                    trans_dict[atom_identifier] = [BW_number, None]
            if atom_name == "CA":
                GPCRDB_number = line[61:66].strip()
                if (
                    float(GPCRDB_number) <= -8.1
                    or float(GPCRDB_number) >= 8.1
                    or float(GPCRDB_number) == 0
                ):
                    continue
                if float(GPCRDB_number) > 0:
                    GPCRDB_number = GPCRDB_number.replace(".", "x")
                else:
                    GPCRDB_number = str(
                        round(abs(-float(GPCRDB_number) + 0.001), 3)
                    ).replace(".", "x")
                if atom_identifier in trans_dict:
                    trans_dict[atom_identifier][1] = GPCRDB_number
                else:
                    trans_dict[atom_identifier] = [None, GPCRDB_number]
    return trans_dict


def get_sequence(pdb: Path):
    with open(pdb, "r") as f:
        next(f)
        sequence: list[tuple[int, str]] = []
        for line in f.readlines():
            if line[0:4] != "ATOM":
                continue
            atom_name = line[12:15].strip()
            if not atom_name == "CA":
                continue
            residue_name = line[17:20].strip()
            residue_name_single = THREE_TO_ONE[residue_name]
            sequence_number = int(line[22:26].strip())
            res_info = (sequence_number, residue_name_single)
            if res_info not in sequence:
                sequence.append(res_info)
    return sequence


if __name__ == "__main__":
    files = get_files_maestro(Path("/home/zcrank/pan/dev/user_uploads/173cd575-f48f-43a4-98c2-7b9e746ee6fd/0").absolute())
    if files is None:
        print("Couldn't find necesarry files!")
        sys.exit(1)
    seq = get_sequence2(files.topology, files.trajectory)
    ident = get_uniprot_identifier(seq)
    if ident is None:
        print("Couldn't identify the structure!")
        sys.exit(1)
    residue_info = get_residues_extended(ident)
    print(residue_info)
    
    # get_pdb(files.topology, files.trajectory, outfile=NUMBERED_PATH.absolute())
    # get_numbering(NUMBERED_PATH, outfile=Path("./numbered_out.pdb"))
    # out = create_translation_dict(Path("./numbered_out.pdb"))
    # print(out)
   #  sequence = get_sequence(NUMBERED_PATH)
   #  aa_seq = ""
   #  for seq, res in sequence:
   #     aa_seq += res
   #  print(aa_seq)
   #  gpcrdb_num = get_residues_extended("4dkl")
   #  if gpcrdb_num is None:
   #      print("Something went wrong with GPCRDB call!!")
   #      sys.exit(1)
   #  aa_seq_gpcrdb = ""
   #  for res_info in gpcrdb_num:
   #      aa_seq_gpcrdb += res_info["amino_acid"]
   #  print(aa_seq_gpcrdb)
