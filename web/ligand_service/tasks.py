from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
import functools
import shutil
import pandas as pd
import xmltodict

from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from django.conf import settings

from ligand_service.models import Simulation

from .contacts import (
    get_trajectory_frame_count,
    create_translation_dict_by_blast,
    get_interactions_from_trajectory,
)

from .graphs import (
    plot_contact_fraction_heatmap,
    plot_correlation_covariance_heatmaps,
    create_getcontacts_table,
    create_interaction_area_graph,
    create_time_resolved_map,
)

LIGAND_DETECTION_THRESHOLD = 0.7
INCHIKEY_TO_NAME_JSON_PATH = Path("./chebi/inchikey_to_name.json")
INCHIKEY_TO_CHEBIID_JSON_PATH = Path("./chebi/inchikey_to_chebiID.json")

INTERACTION_TYPE_RENAME = {
    "hydrophobic_interactions": "Hydrophobic",
    "hydrogen_bonds": "Hydrogen bond",
    "water_bridges": "Water bridge",
    "salt_bridges": "Salt bridge",
    "pi_stacks": "Pi-pi stacking",
    "pi_cation_interactions": "Pi-cation",
    "halogen_bonds": "Halogen bond",
    "metal_complexes": "Metal complex",
}

logger = logging.getLogger(__name__)


def log_exceptions(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled exception in {func.__name__}: {e}")
            raise

    return wrapper


def save_file(file_handle, path_to_save_location: Path):
    with open(path_to_save_location, "wb+") as destination:
        for chunk in file_handle.chunks():
            destination.write(chunk)


def extract_data_from_plip_results(
    results_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    frames_data = {
        "Frame": [],
        "Interaction type": [],
        "Residue chain": [],
        "Residue name": [],
        "Residue number": [],
        "Ligand residue chain": [],
        "Ligand residue name": [],
        "Ligand residue number": [],
    }
    ligand_info = {
        "frames_seen": [],
        "name": [],
        "ligtype": [],
        "smiles": [],
        "inchikey": [],
        # "img": [],
    }
    logger.info("Extracting data from plip results...")
    for dir in sorted(results_dir.iterdir(), key=lambda x: (len(str(x)), x)):
        if not dir.is_dir():
            continue
        with open(dir / "report.xml") as f:
            file_contents = f.read()
            out = xmltodict.parse(file_contents)
            binding_sites = out["report"]["bindingsite"]
            # handling of instance, where there is only one binding site
            if not isinstance(binding_sites, list):
                binding_sites = [binding_sites]
            for binding_site in binding_sites:
                if binding_site["@has_interactions"] == "False":
                    logger.info(f"Skipping binding_site: {binding_site}")
                    continue
                ident = binding_site["identifiers"]
                interactions = binding_site["interactions"]
                inchikey = ident["inchikey"]
                if inchikey in ligand_info["inchikey"]:
                    idx = ligand_info["inchikey"].index(inchikey)
                    ligand_info["frames_seen"][idx] += 1
                else:
                    logger.info(f"Adding new ligand: {inchikey}")
                    ligand_info["frames_seen"].append(1)
                    ligand_info["name"].append(ident["longname"])
                    ligand_info["ligtype"].append(ident["ligtype"])
                    ligand_info["smiles"].append(ident["smiles"])
                    ligand_info["inchikey"].append(inchikey)

                # mol = Chem.MolFromSmiles(ident["smiles"])
                # logger.info(f"Molecule created from SMILES")
                # if mol is not None:
                #     img = Draw.MolToImage(mol, size=(300, 300))
                #     logger.info(f"Image created from mol")
                #     buffer = BytesIO()
                #     img.save(buffer, format="PNG")
                #     img_str = base64.b64encode(buffer.getvalue()).decode()
                #     inlined_image = (
                #         f'<img src="data:image/png;base64,{img_str}">'
                #     )
                #     ligand_info["img"].append(inlined_image)
                # else:
                #     ligand_info["img"].append("")

                for interaction_type in interactions:
                    for contacts_lists in interactions[interaction_type] or []:
                        contacts = interactions[interaction_type][contacts_lists]
                        # handling of instance where there is only one interaction of given type,
                        # xmltodict doesn't make a list in this case, it just provides the value
                        if not isinstance(contacts, list):
                            contacts = [contacts]
                        for value in contacts:
                            frames_data["Frame"].append(int(dir.stem[5:]))
                            frames_data["Interaction type"].append(
                                INTERACTION_TYPE_RENAME[interaction_type]
                            )
                            frames_data["Residue chain"].append(value["reschain"])
                            frames_data["Residue number"].append(value["resnr"])
                            frames_data["Residue name"].append(value["restype"])
                            frames_data["Ligand residue chain"].append(
                                value["reschain_lig"]
                            )
                            frames_data["Ligand residue number"].append(
                                value["resnr_lig"]
                            )
                            frames_data["Ligand residue name"].append(
                                value["restype_lig"]
                            )
    frame_df = pd.DataFrame(frames_data)
    ligand_df = pd.DataFrame(ligand_info)
    ligand_df.drop_duplicates(inplace=True)
    return frame_df, ligand_df


inchikey_to_name = {}
inchikey_to_chebiID = {}

if (
    not INCHIKEY_TO_CHEBIID_JSON_PATH.is_file()
    or not INCHIKEY_TO_NAME_JSON_PATH.is_file()
):
    print(
        "Files from ChEBI are not available, please run 'python manage.py getchebi' before starting the server."
    )
else:
    with open(INCHIKEY_TO_NAME_JSON_PATH) as f:
        inchikey_to_name = json.load(f)
    with open(INCHIKEY_TO_CHEBIID_JSON_PATH) as f:
        inchikey_to_chebiID = json.load(f)


def analyse_simulation(
    top_file: Path, traj_file: Path, plip_dir: Path, results_dir: Path
):
    run_data = {}
    out = extract_data_from_plip_results(plip_dir)
    if out is None:
        return
    shutil.rmtree(plip_dir)
    df = out[0]
    ligand_df = out[1]
    dic, scores = create_translation_dict_by_blast(top_file, traj_file)
    run_data["name"] = top_file.parent.name
    run_data["alignment_scores"] = scores

    def get_numbering_blast(row):
        assert dic is not None
        key = (
            row["Residue chain"],
            row["Residue name"],
            str(row["Residue name"]),
        )
        if key in dic:
            return dic[key]

    df["Aligned numbering"] = df.apply(get_numbering_blast, axis=1)
    run_data["interaction_graph"] = create_interaction_area_graph(df)
    results_dir.mkdir(exist_ok=True, parents=True)
    df.to_csv(
        path_or_buf=(results_dir / "interactions.csv"),
        index=False,
    )

    ligands_arr = []
    for ligand in ligand_df.to_dict(orient="records"):
        simulation_frame_count = get_trajectory_frame_count(top_file, traj_file)
        if ligand["frames_seen"] / simulation_frame_count < LIGAND_DETECTION_THRESHOLD:
            print(
                f"Skipping ligand below threshold, seen in {ligand['frames_seen']} out of {simulation_frame_count}",
                flush=True,
            )
            continue
        id = inchikey_to_chebiID.get(ligand["inchikey"], None)
        name = inchikey_to_name.get(ligand["inchikey"], None)
        ligands_arr = run_data.get("ligands", [])
        ligands_arr.append(
            {
                "id": id,
                "name": name,
                "img": ligand.get("img", ""),
                "frames_seen": ligand["frames_seen"],
                "smiles": ligand["smiles"],
                "inchikey": ligand["inchikey"],
            }
        )

    run_data["ligands"] = ligands_arr

    run_data["table"] = create_getcontacts_table(df)
    run_data["map"] = create_time_resolved_map(df)

    with open(results_dir / "run_data.json", "w") as f:
        json.dump(run_data, f)

    print("Analysis finished! Results available at: ", results_dir, flush=True)

    return run_data


def analyse_group(results_dirs: list[Path], group_result_dir: Path):
    sims_data = []
    for dir in results_dirs:
        with open(dir / "run_data.json") as f:
            raw = f.read()
            data = json.loads(raw)
            sims_data.append(data)

    interactions = []
    for dir in results_dirs:
        with open(dir / "interactions.csv") as f:
            interactions.append(
                (
                    dir.name,
                    pd.read_csv(f),
                )
            )

    with open(group_result_dir / "exp_data.csv") as f:
        exp_data = pd.read_csv(f)

    prepared_dfs = []
    for id, df in interactions:
        sim_name = exp_data.loc[
            exp_data["Simulation ID"] == id, "Simulation name"
        ].iloc[0]
        if len(exp_data.columns.tolist()) > 2:
            value_name = exp_data.columns.tolist()[2]
            value = exp_data.loc[exp_data["Simulation ID"] == id, value_name].iloc[0]
            df[value_name] = value
        df["Simulation name"] = sim_name
        df["Simulation ID"] = id
        prepared_dfs.append(df)

    group_df = pd.concat(prepared_dfs)
    group_df.to_csv(group_result_dir / "group.csv", index=False)

    interaction_freq_map = plot_contact_fraction_heatmap(group_df)

    group_data = {
        "exp_data": exp_data.to_dict(orient="split", index=False),
        "interaction_freq_map": interaction_freq_map,
    }

    if len(exp_data.columns) > 2:
        interaction_correlation_map, interaction_covariance_map = (
            plot_correlation_covariance_heatmaps(group_df)
        )
        group_data["interaction_correlation_map"] = interaction_correlation_map
        group_data["interaction_covariance_map"] = interaction_covariance_map

    with open(group_result_dir / "group_data.json", "w") as f:
        json.dump(group_data, f)

    return None


@task()
def start_simulation(
    top_file: Path, traj_file: Path, work_dir: Path, results_dir: Path
):
    # setup for using only specific frames
    print("Starting the simulation!", flush=True)
    frame_count = get_trajectory_frame_count(top_file, traj_file)
    frames = [x for x in range(frame_count)]
    plip_dir = work_dir / "plip"
    frames_dir = work_dir / "frames"
    get_interactions_from_trajectory(top_file, traj_file, plip_dir, frames_dir, frames)
    analyse_simulation(top_file, traj_file, plip_dir, results_dir)
    return len(frames)


example_results_dir = settings.BASE_DIR / "example_results"
example_results_dirnames = []
if example_results_dir.is_dir():
    example_results_dirnames = [dir.name for dir in example_results_dir.iterdir()]


def remove_unused_sim_files(sim_files_dir: Path):
    stat = sim_files_dir.stat()
    last_modified_time = datetime.fromtimestamp(stat.st_ctime)
    if datetime.now() - last_modified_time < timedelta(hours=4):
        return
    try:
        sim = Simulation.objects.get(sim_id=sim_files_dir.name)
        status = sim.get_analysis_status()
        if (
            status != "Queueing"
            and status != "Queued"
            and not status.startswith("Running")
        ):
            shutil.rmtree(sim_files_dir)
            print(f"Removing directory: {sim_files_dir}", flush=True)
    except:
        shutil.rmtree(sim_files_dir)


@periodic_task(crontab(day="*/1"))
def clean_user_uploads():
    print("Running routine cleanup...")
    uploads_dir = settings.BASE_DIR / "user_uploads"
    analysis_dirs = []
    user_dirs = []
    for dir in uploads_dir.iterdir():
        if dir.name in example_results_dirnames:
            continue

        if dir.is_file() and dir.suffix == ".log":
            continue

        if "-" in dir.name:
            analysis_dirs.append(dir)
        else:
            user_dirs.append(dir)

    print("User directories: ", user_dirs)
    print("Analysis directories: ", analysis_dirs)
    for user_dir in user_dirs:
        for subdir in user_dir.iterdir():
            for sim_dir in subdir.iterdir():
                remove_unused_sim_files(sim_dir)
