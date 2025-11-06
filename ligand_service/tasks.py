from pathlib import Path
import json
import logging
import functools

from django.utils import timezone
from huey.contrib.djhuey import db_task, task
import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
import xmltodict
import numpy as np
import pandas as pd

from .contacts import (
    get_trajectory_frame_count,
    create_translation_dict_by_blast,
    get_interactions_from_trajectory,
)

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


PAGE_BG_COLOR = "#e5e7eb"
COMMON_LAYOUT = dict(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=PAGE_BG_COLOR)
COMMON_LAYOUT_TABLE = dict(
    margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor=PAGE_BG_COLOR
)
LIGAND_DETECTION_THRESHOLD = 0.7
INCHIKEY_TO_NAME_JSON_PATH = Path("./chebi/inchikey_to_name.json")
INCHIKEY_TO_CHEBIID_JSON_PATH = Path("./chebi/inchikey_to_chebiID.json")

INTERACTION_TYPE_RENAME = {}


def save_file(file_handle, path_to_save_location: Path):
    with open(path_to_save_location, "wb+") as destination:
        for chunk in file_handle.chunks():
            destination.write(chunk)


def extract_data_from_plip_results(
    results_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    frames_data = {
        "frame": [],
        "interaction_type": [],
        "residue_chain": [],
        "residue_name": [],
        "residue_number": [],
        "lig_residue_chain": [],
        "lig_residue_name": [],
        "lig_residue_number": [],
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
                            frames_data["frame"].append(int(dir.stem[5:]))
                            frames_data["interaction_type"].append(interaction_type)
                            frames_data["residue_chain"].append(value["reschain"])
                            frames_data["residue_number"].append(value["resnr"])
                            frames_data["residue_name"].append(value["restype"])
                            frames_data["lig_residue_chain"].append(
                                value["reschain_lig"]
                            )
                            frames_data["lig_residue_name"].append(value["resnr_lig"])
                            frames_data["lig_residue_number"].append(
                                value["restype_lig"]
                            )
    frame_df = pd.DataFrame(frames_data)
    ligand_df = pd.DataFrame(ligand_info)
    ligand_df.drop_duplicates(inplace=True)
    return frame_df, ligand_df


def create_getcontacts_table(get_contacts_df: pd.DataFrame) -> str:
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=list(get_contacts_df.columns),
                    line_color=PAGE_BG_COLOR,
                    height=25,
                ),
                cells=dict(
                    values=[
                        get_contacts_df[col].apply(
                            lambda x: "-" if x is None or pd.isna(x) else x
                        )
                        for col in get_contacts_df.columns
                    ],
                    line_color=PAGE_BG_COLOR,
                    height=25,
                ),
            )
        ]
    )
    fig.update_traces(columnwidth=[100, 300])
    fig.update_layout(COMMON_LAYOUT_TABLE)
    table = fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )
    return table


def create_interaction_area_graph(contacts_df: pd.DataFrame) -> str:
    print(contacts_df.columns.values, flush=True)
    interaction_count = (
        contacts_df.groupby(["frame", "interaction_type"])
        .agg(Count=("residue_number", "count"))
        .reset_index()
    )
    print(interaction_count, flush=True)
    fig = px.area(
        interaction_count,
        x="frame",
        y="Count",
        title="Interaction counts",
        line_group="interaction_type",
        color="interaction_type",
    )
    fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="linear"))
    fig.update_layout(COMMON_LAYOUT)
    graph = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displaylogo": False, "responsive": True},
    )
    return graph


def hex2rgba(hexcol, a):
    return f"rgba({int(hexcol[1:3], 16)},{int(hexcol[3:5], 16)},{int(hexcol[5:7], 16)},{a})"


def create_time_resolved_map(contacts_df: pd.DataFrame) -> str:
    sub_df = contacts_df[
        ["frame", "residue_name", "residue_number", "interaction_type"]
    ]
    sub_df["residue_label"] = (
        sub_df["residue_name"].astype(str) + "_" + sub_df["residue_number"].astype(str)
    )

    residues = sorted(
        sub_df["residue_label"].unique(), key=lambda s: int(s.split("_")[-1])
    )
    frames = np.arange(sub_df["frame"].min(), sub_df["frame"].max() + 1)

    types = [
        "water_bridges",
        "hydrophobic_interactions",
        "pi_stacks",  # UWAGA: może zmienimy na pi_pi_stacking?
        "pi_cation_interactions",
        "hydrogen_bonds",
        "halogen_bonds",
        "salt_bridges",
    ]

    colors = [
        "#B0B0B0",
        "#8da0cb",
        "#66c2a5",
        "#a6d854",
        "#ffd92f",
        "#fc8d62",
        "#e78ac3",
    ]

    counts = (
        sub_df.groupby(["residue_label", "frame", "interaction_type"])
        .size()
        .rename("n")
        .reset_index()
    )
    counts = counts.pivot_table(
        index=["residue_label", "frame"],
        columns="interaction_type",
        values="n",
        fill_value=0,
    )
    counts = counts.reindex(columns=types, fill_value=0)
    counts = counts.reindex(
        pd.MultiIndex.from_product(
            [residues, frames], names=["residue_label", "frame"]
        ),
        fill_value=0,
    )

    vals = counts.values.reshape(len(residues), len(frames), len(types))

    fig = go.Figure()

    hovertemplate = (
        "Residue: %{y}<br>"
        "Frame: %{x}<br>"
        "water_bridges: %{customdata[0]}<br>"
        "hydrophobic_interactions: %{customdata[1]}<br>"
        "pi_stacks: %{customdata[2]}<br>"
        "pi_cation_interactions: %{customdata[3]}<br>"
        "hydrogen_bonds: %{customdata[4]}<br>"
        "halogen_bonds: %{customdata[5]}<br>"
        "salt_bridges: %{customdata[6]}<extra></extra>"
    )

    for k, t in enumerate(types):
        presence = (vals[..., k] > 0).astype(float)
        fig.add_trace(
            go.Heatmap(
                z=presence,
                x=frames,
                y=residues,
                zmin=0,
                zmax=1,
                showscale=False,
                showlegend=False,
                colorscale=[
                    [0.0, hex2rgba(colors[k], 0.0)],
                    [1.0, hex2rgba(colors[k], 1.0)],
                ],
                name=t,
                legendgroup=t,
                customdata=vals,
                hovertemplate=hovertemplate,
            )
        )

    for k, t in enumerate(types):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(color=colors[k], size=10),
                name=t,
                legendgroup=t,
                showlegend=True,
                hoverinfo="skip",
            )
        )

    fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type="linear"))
    fig.update_layout(
        COMMON_LAYOUT,
        plot_bgcolor=PAGE_BG_COLOR,
        xaxis_title="Frame",
        yaxis_title="Residue",
        height=700,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)

    graph = fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )
    return graph


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
    df = out[0]
    ligand_df = out[1]
    dic, scores = create_translation_dict_by_blast(top_file, traj_file)
    run_data["name"] = top_file.parent.name
    run_data["alignment_scores"] = scores

    def get_numbering_blast(row):
        assert dic is not None
        key = (
            row["residue_chain"],
            row["residue_name"],
            str(row["residue_number"]),
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


def _reslabel(name, num):
    return f"{name}-{num}"


def _resnum_key(label):
    try:
        return int(str(label).split("-")[-1])
    except Exception:
        return 1e9


def contact_fraction_matrix(
    group_df: pd.DataFrame, itype: str | None = None
) -> pd.DataFrame:
    df = group_df.copy()

    df["ResidueLabel"] = [
        _reslabel(rn, rr) for rn, rr in zip(df["residue_name"], df["residue_number"])
    ]
    total_frames = (
        df.groupby("Simulation name")["frame"].nunique().rename("total_frames")
    )

    if itype is not None:
        df = df[df["interaction_type"] == itype]

    df["frame"] = pd.to_numeric(df["frame"], errors="coerce")
    df = df.dropna(subset=["frame", "Simulation name", "ResidueLabel"])

    pres = (
        df[["Simulation name", "ResidueLabel", "frame"]]
        .drop_duplicates()
        .groupby(["Simulation name", "ResidueLabel"])
        .agg(frames_with_contact=("frame", "nunique"))
        .reset_index()
    )

    pres = pres.merge(total_frames, on="Simulation name", how="left")

    pres["FractionPercent"] = 100.0 * pres["frames_with_contact"] / pres["total_frames"]

    mat = pres.pivot(
        index="Simulation name", columns="ResidueLabel", values="FractionPercent"
    ).fillna(0.0)

    mat = mat[sorted(mat.columns, key=_resnum_key)]

    return mat


def plot_contact_fraction_heatmap(
    group_df: pd.DataFrame,
    title_prefix: str = "Contact fraction per residue",
    colorscale: str = "magma_r",
):
    # ALTERNATYWNIE colorscale "magma_r"??????

    types = [t for t in pd.unique(group_df["interaction_type"]) if pd.notna(t)]
    types_sorted = sorted(types)

    mats = {"All types": contact_fraction_matrix(group_df, None)}
    for t in types_sorted:
        mats[t] = contact_fraction_matrix(group_df, t)

    all_sims = sorted(set().union(*[set(m.index) for m in mats.values()]))
    all_res = sorted(
        set().union(*[set(m.columns) for m in mats.values()]), key=_resnum_key
    )

    for k in mats:
        mats[k] = mats[k].reindex(index=all_sims, columns=all_res, fill_value=0.0)

    init_key = "All types"
    Z0 = mats[init_key].values
    X = all_res
    Y = all_sims

    fig = go.Figure(
        data=go.Heatmap(
            z=Z0,
            x=X,
            y=Y,
            zmin=0,
            zmax=100,
            colorscale=colorscale,
            colorbar=dict(
                title=dict(
                    text="% of trajectory",
                    side="right",  # po prawej stronie, ale domyślnie góra → my to poprawimy
                ),
                tickfont=dict(size=10),
                xpad=10,
            ),
            hovertemplate="Simulation: %{y}<br>Residue: %{x}<br>Fraction: %{z:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        paper_bgcolor=PAGE_BG_COLOR,
        title=f"{title_prefix} — {init_key}",
        xaxis_title="Residue",
        yaxis_title="Simulation",
        xaxis=dict(tickangle=270),
    )

    buttons = []
    for key in [init_key] + types_sorted:
        buttons.append(
            dict(
                label=key,
                method="update",
                args=[
                    {"z": [mats[key].values]},
                    {"title": {"text": f"{title_prefix} — {key}"}},
                ],
            )
        )

    fig.update_xaxes(tickangle=45)

    fig.update_layout(
        updatemenus=[
            dict(
                type="dropdown",
                buttons=buttons,
                x=1.02,
                y=1.15,
                xanchor="left",
                yanchor="top",
                bgcolor=PAGE_BG_COLOR,
                bordercolor="lightgray",
            )
        ]
    )

    fig_html = fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )
    return fig_html


IDENTIFIER_COLUMN = "Simulation name"


def plot_correlation_heatmap(
    df: pd.DataFrame,
    colorscale: str = "magma_r",
):
    sims_exp_data = df[df.columns[-3:]].drop_duplicates().reset_index(drop=True)
    sims_frame_data = df[df.columns[:-3].to_list() + [IDENTIFIER_COLUMN]]
    sims_frame_data["residue"] = (
        sims_frame_data["residue_name"]
        + "-"
        + sims_frame_data["residue_number"].astype(str)
    )

    interactions_by_sim = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "interaction_type"])["frame"]
        .count()
        .reset_index()
    )
    interactions_by_sim_residue = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "residue"])["frame"]
        .count()
        .reset_index()
    )
    interactions_by_sim_residue_type = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "residue", "interaction_type"])[
            "frame"
        ]
        .count()
        .reset_index()
    )

    interactions_with_exp = interactions_by_sim.merge(sims_exp_data.iloc[:, :-1])
    EXP_DATA_COLUMN = interactions_with_exp.columns.to_list()[-1]

    correlations = {}
    wide_df = interactions_by_sim_residue.pivot_table(
        index=["Simulation name"], columns="residue", values="frame"
    ).reset_index()
    wide_df = wide_df.merge(sims_exp_data.iloc[:, :-1])
    corrs = wide_df.corr(numeric_only=True)[EXP_DATA_COLUMN].sort_values(
        ascending=False
    )
    correlations["Overall"] = corrs

    for interaction in interactions_by_sim_residue_type["interaction_type"].unique():
        wide_df = (
            interactions_by_sim_residue_type[
                interactions_by_sim_residue_type["interaction_type"] == interaction
            ]
            .pivot_table(index=["Simulation name"], columns="residue", values="frame")
            .reset_index()
        )
        wide_df = wide_df.merge(sims_exp_data.iloc[:, :-1])
        corrs = wide_df.corr(numeric_only=True)[EXP_DATA_COLUMN].sort_values(
            ascending=False
        )
        corrs.drop(EXP_DATA_COLUMN, inplace=True)
        correlations[interaction] = corrs

    corrs_df = pd.DataFrame(correlations)
    corrs_df.drop(EXP_DATA_COLUMN, inplace=True)
    corrs_df.sort_index(key=lambda x: x.str.split("-").str[1].astype(int), inplace=True)
    corrs_df.fillna("", inplace=True)

    fig = go.Figure(
        data=go.Heatmap(
            z=corrs_df.T.values,
            x=corrs_df.index,
            y=corrs_df.columns.to_list(),
            zmin=-1,
            zmax=1,
            colorscale="magma_r",
            colorbar=dict(
                title=dict(
                    text="Correlation",
                    side="right",
                ),
                tickfont=dict(size=10),
                xpad=10,
            ),
            hovertemplate="Residue: %{x}<br>Correlation: %{z}<extra></extra>",
        )
    )

    fig.update_layout(
        paper_bgcolor=PAGE_BG_COLOR,
        title=f"Correlation between number of interactions and {EXP_DATA_COLUMN.lower()}",
        xaxis_title="Residue",
        yaxis_title="Interaction type",
        xaxis=dict(tickangle=270),
    )

    fig.update_xaxes(tickangle=45)

    fig_html = fig.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )

    return fig_html


def analyse_group(results_dirs: list[Path], group_result_dir: Path):
    sims_data = []
    for dir in results_dirs:
        print("RESULT DIR:", dir)
        print([x for x in dir.iterdir()], flush=True)
        with open(dir / "run_data.json") as f:
            raw = f.read()
            data = json.loads(raw)
            sims_data.append(data)

    interactions = []
    for dir in results_dirs:
        print("RESULT DIR:", dir)
        print([x for x in dir.iterdir()], flush=True)
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
        interaction_correlation_map = plot_correlation_heatmap(group_df)
        group_data["interaction_correlation_map"] = interaction_correlation_map

    print("WRITING GROUP DATA", flush=True)
    with open(group_result_dir / "group_data.json", "w") as f:
        json.dump(group_data, f)
    print("COMPLETED WRITING GROUP DATA", flush=True)

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
