import sys
import os
import subprocess as sb
from pathlib import Path
from typing import Any
import tempfile
import re

import requests
from vmd import molecule, atomsel
from Bio import SearchIO

from .models import GPCRdbResidueAPI

BLASTP_PATH = "blastp"
BLASTDB_PATH = Path("blast/blast_db").absolute()

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

ONE_TO_THREE = {v: k for k, v in THREE_TO_ONE.items()}

def filetype(file: Path) -> str:
    filetype = file.suffix[1:]
    if filetype == "cms":
        filetype = "mae"
        return filetype
    return filetype


def get_sequence_chains(
    topology_file: Path, trajectory_file: Path
) -> dict[str, dict[int, str]]:
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
    try:
        cached_request = GPCRdbResidueAPI.objects.get(
            uniprot_identifier=uniprot_identifier
        )
        print("Returning cached response...", flush=True)
        return cached_request.response_json
    except Exception:
        url = GPCRDB_RESIDUES_EXTENDED_ENDPOINT + uniprot_identifier
        print(f"Calling GPCRdb: {url}")
        response = requests.post(url)
        if response.ok:
            print("Call successful", flush=True)
            response_json = response.json()
            GPCRdbResidueAPI.objects.create(
                uniprot_identifier=uniprot_identifier, response_json=response_json
            ).save()
            return response_json
        print(f"Call failed: {response.status_code}", flush=True)
    return None


def create_translation_dict_by_pdb(
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


def blast_sequence(seq: str) -> SearchIO.HSP | None:
    print("Starting blast with seq:", seq, flush=True)
    results_file = tempfile.NamedTemporaryFile(suffix=".xml")
    job = sb.run(
        [
            BLASTP_PATH,
            "-query",
            "-",
            "-db",
            BLASTDB_PATH,
            "-out",
            results_file.name,
            "-outfmt",
            "5",
            "-max_target_seqs",
            "1",
        ],
        capture_output=True,
        input=seq.encode(),
    )
    if job.returncode != 0:
        print("Sequence blast failed!")
        print(f"Stderr: {job.stderr.decode()}", flush=True)
        return None
    else:
        print("Blast successful")
    # read the outputfile, return alignment
    blast_qresult: SearchIO.QueryResult = SearchIO.read(results_file, "blast-xml")
    for hit in blast_qresult:
        for hsp in hit:
            return hsp
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


def create_translation_dict_by_blast(
    topology: Path, trajectory: Path
) -> dict[tuple[str, str, str], str] | None:
    seq_chains = get_sequence_chains(topology, trajectory)
    result_dict = {}
    for chain in seq_chains:
        seq = "".join([res_name[1] for res_name in sorted(seq_chains[chain].items())])
        alignment = blast_sequence(seq)
        if alignment is None:
            print("FAILED TO GET ALIGNMENT!", flush=True)
            continue
        named_atoms = []
        for idx in seq_chains[chain]:
            # create (chain, residue_name, residue_idx) triplets
            # for consistency with getcontacts lib
            named_atoms.append((chain, ONE_TO_THREE[seq_chains[chain][idx]], str(idx)))
            # sort by residue_idx
        named_atoms.sort(key=lambda x: int(x[2]))
        ident = extract_uniprot_ident(alignment.hit_id)
        residue_info = get_residues_extended(ident)
        if residue_info is None:
            print(
                f"Failed to get info from GPCRdb API, requested uniprot identifier: {ident}",
                flush=True,
            )
            continue
        # creates a list of tuples, where first element is the start index and second is the end index
        # (start idx, end idx)
        target_slices = list(zip(alignment.hit_range[::2], alignment.hit_range[1::2]))
        query_slices = list(
            zip(alignment.query_range[::2], alignment.query_range[1::2])
        )
        print(target_slices, flush=True)
        print(query_slices, flush=True)
        chain_result = {}
        for qs, ts in zip(query_slices, target_slices):
            keys = named_atoms[qs[0] : qs[1]]
            values = []
            for idx in range(ts[0], ts[1]):
                for amino_acid in residue_info:
                    # sequence_number starts from 1, while coordinates start from 0
                    if amino_acid["sequence_number"] == idx + 1:
                        values.append(amino_acid)
                        break
            for k, v in zip(keys, values):
                # compare amino acids
                if k[1] != ONE_TO_THREE[v["amino_acid"]]:
                    print(
                        f"MAPING MISMATCH: {k} : {ONE_TO_THREE[v['amino_acid']]}",
                        flush=True,
                    )
                value = v.get("display_generic_number", "")
                chain_result[k] = (
                    re.sub(r"(\.\d*)", "", value)
                    if value is not None
                    else v["protein_segment"]
                )
        for atom in named_atoms:
            if atom not in chain_result:
                print(f"ATOM NOT MAPPED! {atom}", flush=True)
        # merge results from each chain
        result_dict = {**result_dict, **chain_result}
    return result_dict if len(result_dict) > 0 else None
