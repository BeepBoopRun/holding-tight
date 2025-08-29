import io
import sys
import os
import subprocess as sb
from pathlib import Path
from typing import Any, NamedTuple
import tempfile

import requests
from vmd import molecule, atomsel
from Bio import Blast

BLASTP_PATH = os.path.abspath("./blast/ncbi-blast-2.17.0+/bin/blastp")
BLASTDB_PATH = os.path.abspath("./blast/blast_db")

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

ONE_TO_THREE = {v: k for k,v in THREE_TO_ONE.items()}


class VMDFiles(NamedTuple):
    topology: Path
    trajectory: Path




def filetype(file: Path) -> str:
    filetype = file.suffix[1:]
    if filetype == "cms":
        filetype = "mae"
        return filetype
    return filetype


def get_sequence_chains(topology_file: Path, trajectory_file: Path) -> dict[str, dict[int, str]]:
    molid = molecule.load(filetype(topology_file), str(topology_file))
    molecule.read(molid, filetype(trajectory_file), str(trajectory_file))

    protein = atomsel("protein", molid=molid)
    structure = {}
    for chain, resname, residue_id in zip(
        protein.chain, protein.resname, protein.resid
    ):
        if chain not in structure:
            structure[chain] = {}
        structure[chain][residue_id] = THREE_TO_ONE.get(resname, "X")
    return structure


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
        print("GET CONTACTS:", line.strip())

    process.wait()
    print("GET CONTACTS: Done!")


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


def get_residues_extended(uniprot_identifier: str) -> list[dict[Any, Any]] | None:
    url = GPCRDB_RESIDUES_EXTENDED_ENDPOINT + uniprot_identifier
    response = requests.post(url)
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

def blast_sequence(seq: str) -> Blast.HSP | None:
    results_file = tempfile.NamedTemporaryFile(suffix=".xml")
    job = sb.run(
        [BLASTP_PATH, "-query", "-", "-db", BLASTDB_PATH, "-out", results_file.name, "-outfmt", "5", "-max_target_seqs", "1"],
        capture_output=True,
        input=seq.encode(),
    )
    if job.returncode != 0:
        print(f"Getting accession number failed! Input: {seq}")
        return None
    # read the outputfile, return alignment
    blast_record: Blast.Record = Blast.read(results_file)
    for alignments in blast_record:
        for alignment in alignments:
            return alignment
    return None

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

def extract_uniprot_ident(target_description: str) -> str:
    return target_description.split("|")[1]

def make_translation_dict_from_alignment(named_atoms: list[tuple[str, str, str]], alignment: Blast.HSP ) -> dict[tuple[str, str, int], list[str]] | None:
    named_atoms.sort(key=lambda x: int(x[2]))
    ident = extract_uniprot_ident(alignment.target.description)
    residue_info = get_residues_extended(ident)
    if residue_info is None:
        print("REQUEST FAILED!", flush=True)
        return None
    # Alignment object uses 1 based indexing for coordinates, gpcrdb does not!!
    if alignment.coordinates is None:
        print("NO COORDINATES IN ALIGNMENT!", flush=True)
        return None

    # creates a list of tuples, where first element is the start index and second is the end index
    target_slices = list(zip(alignment.coordinates[0][::2], alignment.coordinates[0][1::2]))
    query_slices = list(zip(alignment.coordinates[1][::2], alignment.coordinates[1][1::2]))

    result = {}
    for qs, ts in zip(query_slices, target_slices):
        keys = named_atoms[qs[0]-1 : qs[1]-1]
        values = residue_info[ts[0]-1 : ts[1]-1]
        for k,v in zip(keys,values):
            value = v.get("display_generic_number", "")
            result[k] = value if value is not None else ""
    return result


def create_translation_dict2(topology: Path, trajectory: Path) -> dict[tuple[str, str, str], str] | None:
    print("TRANSLATION DIC 2 CREATOR", flush=True)
    seq_chains = get_sequence_chains(topology, trajectory)
    result_dict = {}
    for chain in seq_chains:
        seq = "".join([res_name[1] for res_name in sorted(seq_chains[chain].items())])
        alignment = blast_sequence(seq)
        if alignment is None:
            print("FAILED TO GET ALIGNMENT!", flush=True)
            return None
        named_atoms = []
        for idx in seq_chains[chain]:
            # create (chain, residue_name, residue_idx) triplets
            named_atoms.append((chain, ONE_TO_THREE[seq_chains[chain][idx]], str(idx)))
        chain_dict = make_translation_dict_from_alignment(named_atoms, alignment)
        if chain_dict is None:
            print("FAILED TO GET CHAIN_DICT!", flush=True)
            return None
        # merge results from each chain
        result_dict = {**result_dict, **chain_dict}
    return result_dict



if __name__ == "__main__":
    files = get_files_maestro(
        Path(
            "/home/zcrank/pan/dev/user_uploads/17a1ed8c-301d-4e61-8073-bd774799e52c"
        ).absolute()
    )
    if files is None:
        print("Couldn't find necesarry files!")
        sys.exit(1)
    print(create_translation_dict2(files.topology, files.trajectory))

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
