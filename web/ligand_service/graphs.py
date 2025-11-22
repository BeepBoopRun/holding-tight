import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
import numpy as np

PAGE_BG_COLOR = "#e5e7eb"
COMMON_LAYOUT = dict(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=PAGE_BG_COLOR)
COMMON_LAYOUT_TABLE = dict(
    margin=dict(l=20, r=20, t=20, b=20), paper_bgcolor=PAGE_BG_COLOR
)


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
        contacts_df.groupby(["Frame", "Interaction type"])
        .agg(Count=("Residue number", "count"))
        .reset_index()
    )
    print(interaction_count, flush=True)
    fig = px.area(
        interaction_count,
        x="Frame",
        y="Count",
        title="Interaction counts",
        line_group="Interaction type",
        color="Interaction type",
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
        ["Frame", "Residue name", "Residue number", "Interaction type"]
    ]
    sub_df["residue_label"] = (
        sub_df["Residue name"].astype(str) + "-" + sub_df["Residue number"].astype(str)
    )

    residues = sorted(
        sub_df["residue_label"].unique(), key=lambda s: int(s.split("-")[-1])
    )
    frames = np.arange(sub_df["Frame"].min(), sub_df["Frame"].max() + 1)

    types = [
        "Water bridge",
        "Hydrophobic",
        "Pi-pi stacking",
        "Pi-cation",
        "Hydrogen bond",
        "Halogen bond",
        "Salt bridge",
        "Metal complex",
    ]

    colors = [
        "#B0B0B0",
        "#8da0cb",
        "#66c2a5",
        "#a6d854",
        "#ffd92f",
        "#fc8d62",
        "#e78ac3",
        "#d6bbd3",
    ]

    counts = (
        sub_df.groupby(["residue_label", "Frame", "Interaction type"])
        .size()
        .rename("n")
        .reset_index()
    )
    counts = counts.pivot_table(
        index=["residue_label", "Frame"],
        columns="Interaction type",
        values="n",
        fill_value=0,
    )
    counts = counts.reindex(columns=types, fill_value=0)
    counts = counts.reindex(
        pd.MultiIndex.from_product(
            [residues, frames], names=["residue_label", "Frame"]
        ),
        fill_value=0,
    )

    vals = counts.values.reshape(len(residues), len(frames), len(types))

    fig = go.Figure()

    hovertemplate = (
        "Residue: %{y}<br>"
        "Frame: %{x}<br>"
        "Water bridge: %{customdata[0]}<br>"
        "Hydrophobic: %{customdata[1]}<br>"
        "Pi-pi stacking: %{customdata[2]}<br>"
        "Pi-cation: %{customdata[3]}<br>"
        "Hydrogen bond: %{customdata[4]}<br>"
        "Halogen bond: %{customdata[5]}<br>"
        "Salt bridge: %{customdata[6]}<br>"
        "Metal complex: %{customdata[7]}<extra></extra>"
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
        _reslabel(rn, rr) for rn, rr in zip(df["Residue name"], df["Residue number"])
    ]
    total_frames = (
        df.groupby("Simulation name")["Frame"].nunique().rename("total_frames")
    )

    if itype is not None:
        df = df[df["Interaction type"] == itype]

    df["Frame"] = pd.to_numeric(df["Frame"], errors="coerce")
    df = df.dropna(subset=["Frame", "Simulation name", "ResidueLabel"])

    pres = (
        df[["Simulation name", "ResidueLabel", "Frame"]]
        .drop_duplicates()
        .groupby(["Simulation name", "ResidueLabel"])
        .agg(frames_with_contact=("Frame", "nunique"))
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
    types = [t for t in pd.unique(group_df["Interaction type"]) if pd.notna(t)]
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


def plot_correlation_covariance_heatmaps(
    df: pd.DataFrame,
    colorscale: str = "magma_r",
):
    sims_exp_data = df[df.columns[-3:]].drop_duplicates().reset_index(drop=True)
    sims_frame_data = df[df.columns[:-3].to_list() + [IDENTIFIER_COLUMN]]
    sims_frame_data["residue"] = (
        sims_frame_data["Residue name"]
        + "-"
        + sims_frame_data["Residue number"].astype(str)
    )

    interactions_by_sim = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "Interaction type"])["Frame"]
        .count()
        .reset_index()
    )
    interactions_by_sim_residue = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "residue"])["Frame"]
        .count()
        .reset_index()
    )
    interactions_by_sim_residue_type = (
        sims_frame_data.groupby([IDENTIFIER_COLUMN, "residue", "Interaction type"])[
            "Frame"
        ]
        .count()
        .reset_index()
    )

    interactions_with_exp = interactions_by_sim.merge(sims_exp_data.iloc[:, :-1])
    EXP_DATA_COLUMN = interactions_with_exp.columns.to_list()[-1]

    correlations = {}
    wide_df = interactions_by_sim_residue.pivot_table(
        index=["Simulation name"], columns="residue", values="Frame"
    ).reset_index()
    wide_df = wide_df.merge(sims_exp_data.iloc[:, :-1])
    corrs = wide_df.corr(numeric_only=True)[EXP_DATA_COLUMN].sort_values(
        ascending=False
    )
    correlations["Overall"] = corrs

    for interaction in interactions_by_sim_residue_type["Interaction type"].unique():
        wide_df = (
            interactions_by_sim_residue_type[
                interactions_by_sim_residue_type["Interaction type"] == interaction
            ]
            .pivot_table(index=["Simulation name"], columns="residue", values="Frame")
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

    fig_corr = go.Figure(
        data=go.Heatmap(
            z=corrs_df.T.values,
            x=corrs_df.index,
            y=corrs_df.columns.to_list(),
            zmin=-1,
            zmax=1,
            colorscale="rdylbu_r",
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

    fig_corr.update_layout(
        paper_bgcolor=PAGE_BG_COLOR,
        title=f"Correlation between number of interactions and {EXP_DATA_COLUMN}",
        xaxis_title="Residue",
        yaxis_title="Interaction type",
        xaxis=dict(tickangle=270),
    )

    fig_corr.update_xaxes(tickangle=45)

    fig_corr_html = fig_corr.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )

    covariances = {}
    print(wide_df, flush=True)
    covs = wide_df.cov(numeric_only=True)[EXP_DATA_COLUMN].sort_values(ascending=False)
    covariances["Overall"] = covs
    print(covs, flush=True)

    for interaction in interactions_by_sim_residue_type["Interaction type"].unique():
        wide_df = (
            interactions_by_sim_residue_type[
                interactions_by_sim_residue_type["Interaction type"] == interaction
            ]
            .pivot_table(index=["Simulation name"], columns="residue", values="Frame")
            .reset_index()
        )
        wide_df = wide_df.merge(sims_exp_data.iloc[:, :-1])
        covs = wide_df.cov(numeric_only=True)[EXP_DATA_COLUMN].sort_values(
            ascending=False
        )
        covs.drop(EXP_DATA_COLUMN, inplace=True)
        covariances[interaction] = covs

    covs_df = pd.DataFrame(covariances)
    covs_df.drop(EXP_DATA_COLUMN, inplace=True)
    covs_df.sort_index(key=lambda x: x.str.split("-").str[1].astype(int), inplace=True)
    covs_df.fillna("", inplace=True)

    fig_cov = go.Figure(
        data=go.Heatmap(
            z=covs_df.T.values,
            x=covs_df.index,
            y=covs_df.columns.to_list(),
            zmin=covs_df.min(numeric_only=True).min(),
            zmax=covs_df.max(numeric_only=True).max(),
            colorscale="rdylbu_r",
            colorbar=dict(
                title=dict(
                    text="Covariance",
                    side="right",
                ),
                tickfont=dict(size=10),
                xpad=10,
            ),
            hovertemplate="Residue: %{x}<br>Covariance: %{z}<extra></extra>",
        )
    )

    fig_cov.update_layout(
        paper_bgcolor=PAGE_BG_COLOR,
        title=f"Covariance between number of interactions and {EXP_DATA_COLUMN}",
        xaxis_title="Residue",
        yaxis_title="Interaction type",
        xaxis=dict(tickangle=270),
    )

    fig_cov.update_xaxes(tickangle=45)

    fig_cov_html = fig_cov.to_html(
        include_plotlyjs=False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )

    return fig_corr_html, fig_cov_html
