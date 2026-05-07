#!/usr/bin/env python3

import argparse
import pandas as pd
import plotly.express as px
from pathlib import Path

TOOLS_COLOR_MAP_KF = {
    "BWA-KFsomatic": "rgb(127, 60, 141)",
    "DRAGEN44-KFsomatic": "rgb(17, 165, 121)",
    "DRAGEN44-DRAGEN44": "rgb(165, 170, 153)",
    "DRAGEN44-DRAGEN45": "rgb(242, 183, 1)",
    "DRAGEN45-DRAGEN45": "rgb(231, 63, 116)",
}

TOOL_ORDER = [
    "BWA-KFsomatic",
    "DRAGEN44-KFsomatic",
    "DRAGEN44-DRAGEN44",
    "DRAGEN44-DRAGEN45",
    "DRAGEN45-DRAGEN45",
]

TP_CALL = "TP_call"
TP_BASE = "TP_baseline"
FP = "FP"
FN = "FN"

def ensure_color_map_from_palette(color_map: dict[str, str], keys, palette=None) -> dict[str, str]:
    """Ensure all keys have distinct colors using a qualitative palette.

    This function extends an existing color map by assigning colors to any
    missing keys from a provided qualitative palette. Colors are chosen in
    a deterministic order, avoiding reuse (case-insensitive). If the palette
    is exhausted, an error is raised.

    Args:
        color_map: Existing mapping from key (e.g., tool name) to color string.
        keys: Iterable of keys that must be present in the output color map.
        palette: Optional list of color strings to use for assignment. If not
            provided, a combined Plotly qualitative palette is used.

    Returns:
        A dictionary mapping all requested keys to unique color strings.

    Raises:
        ValueError: If the palette does not contain enough distinct colors to
            assign all missing keys.
    """
    out = dict(color_map)
    used = {str(c).strip().lower() for c in out.values()}

    if palette is None:
        palette = (
            px.colors.qualitative.Alphabet +
            px.colors.qualitative.Dark24 +
            px.colors.qualitative.Light24 +
            px.colors.qualitative.D3 +
            px.colors.qualitative.G10 +
            px.colors.qualitative.T10
        )

    # de-dup palette (case-insensitive) while preserving order
    seen = set()
    palette = [c for c in palette if not (c.lower() in seen or seen.add(c.lower()))]

    palette_iter = (c for c in palette if c.strip().lower() not in used)

    for k in keys:
        if k in out:
            continue
        try:
            c = next(palette_iter)
        except StopIteration:
            raise ValueError(
                "Ran out of distinct palette colors. Provide a bigger palette or allow generated colors."
            )
        out[k] = c
        used.add(c.strip().lower())

    return out

def build_metrics(brotli_df_path: str, stratification: str = "WholeGenome") -> pd.DataFrame:
    """Compute precision, sensitivity, and F1 score metrics from a parquet file.

    The function reads a parquet dataframe containing benchmarking results,
    filters records by stratification and tool type, and computes standard
    performance metrics (Precision, Sensitivity, F1 Score) for each
    tool/subset combination.

    Metrics are computed using counts of TP_call, TP_baseline, FP, and FN
    records. All metric values are expressed as percentages.

    Args:
        brotli_df_path: Path to a parquet file containing benchmarking data.
        stratification: Genomic stratification to filter on
            (e.g., "WholeGenome", "EasyRegion", "DifficultRegion").

    Returns:
        A pandas DataFrame with one row per metric and columns:
        DATASET, TOOL, SUBSET, METRIC, PERCENT.
    """
    dataset = Path(brotli_df_path).name.split(".parquet", 1)[0]
    df = pd.read_parquet(brotli_df_path)
    wgs = df[(~df.TOOL.str.contains("mpileup")) & (df.STRATIFICATION == stratification)]

    counts = (
        wgs
        .groupby(["TOOL", "SUBSET", "STATUS"], observed=True)
        .size()
        .unstack(fill_value=0)
    )

    tmp_metrics = []
    for (tool, subset), row in counts.iterrows():
        tp_call = row.get(TP_CALL, 0)
        fp = row.get(FP, 0)
        fn = row.get(FN, 0)
        tp_baseline = row.get(TP_BASE, 0)

        total_calls_count = tp_call + fp
        total_baseline_count = tp_baseline + fn

        precision = 0.0 if total_calls_count == 0 else 100 * tp_call / total_calls_count
        sensitivity = 0.0 if total_baseline_count == 0 else 100 * tp_baseline / total_baseline_count

        sum_pr = precision + sensitivity
        f1_score = 0.0 if sum_pr == 0 else (2 * precision * sensitivity) / sum_pr

        tmp_metrics.extend([
            (dataset, tool, subset, "Precision", precision),
            (dataset, tool, subset, "Sensitivity", sensitivity),
            (dataset, tool, subset, "F1_Score", f1_score),
        ])

    return pd.DataFrame.from_records(
        tmp_metrics,
        columns=("DATASET", "TOOL", "SUBSET", "METRIC", "PERCENT")
    )

def main():
    """Generate an interactive benchmarking report from parquet dataframes.

    This function parses command-line arguments, computes benchmarking metrics
    across multiple genomic stratifications and datasets, and generates a
    faceted Plotly scatter plot summarizing Precision, Sensitivity, and F1
    Score for each tool.

    The resulting visualization is written to an HTML file suitable for
    interactive exploration in a web browser.

    Command-line arguments:
        --brotli_dirs: List of parquet dataframe files to process.
        --output_basename: Basename for the output HTML report.

    Raises:
        SystemExit: If required command-line arguments are not provided.
    """
    parser = argparse.ArgumentParser("make_reports", description="Make benchmarking reports for a dataset given its dataframe")
    parser.add_argument("--brotli_dirs", nargs="+", help="List of directories containing brotli files to process.")
    parser.add_argument("--output_basename", help="Basename for output files")

    args = parser.parse_args()
    if not args.brotli_dirs or not args.output_basename:
        parser.error("Both --brotli_dirs and --output_basename are required")

    dfs = []
    stratifications = ["WholeGenome", "EasyRegion", "DifficultRegion"]
    for stratification in stratifications:
        d = pd.concat([build_metrics(p, stratification) for p in args.brotli_dirs], ignore_index=True)
        d["STRATIFICATION"] = stratification
        dfs.append(d)

    df = pd.concat(dfs, ignore_index=True)

    tmp = df[(df.SUBSET == "Combined")].copy()

    new_color_map = ensure_color_map_from_palette(
        TOOLS_COLOR_MAP_KF,
        tmp["TOOL"].unique(),
        palette=px.colors.qualitative.Plotly
    )

    legend = dict(
        orientation="h",
        xanchor="right",
        yanchor="bottom",
        x=0.8,
        y=-0.08,
        font_size=26,
        bgcolor="ghostwhite",
        bordercolor="gray",
        borderwidth=0.5,
    )

    # Rows = samples (DATASET), Columns = stratification
    fig = px.scatter(
        tmp,
        x="METRIC",
        y="PERCENT",
        color="TOOL",
        facet_row="DATASET",
        facet_col="STRATIFICATION",
        height=300 * max(1, tmp["DATASET"].nunique()),
        width=1600,
        range_y=[50, 100],
        color_discrete_map=new_color_map,
        category_orders={
            "METRIC": ["Precision", "Sensitivity", "F1_Score"],
            "STRATIFICATION": stratifications,
            "TOOL": TOOL_ORDER 
        },
    )

    fig.update_layout(
        legend=legend,  # printed once (single figure)
        scattermode="group",
        scattergap=0.6,
        title=dict(
            text=f'{", ".join(["Precision", "Sensitivity", "F1_Score"])} metrics across all datasets',
            x=0.05,
            font_size=48,
            font_color="black",
        ),  # printed once (single figure)
        font_family="Avenir",
        font_color="dimgray",
        font_size=20,
        margin=dict(t=150),
        xaxis=dict(automargin=True),
    )

    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))

    fig.update_traces(
        marker=dict(size=12, symbol="hexagon", line=dict(width=1, color="DarkSlateGrey")),
        selector=dict(mode="markers"),
    )

    fig.for_each_annotation(
        lambda a: a.update(
            text=(
                a.text
                .replace("STRATIFICATION=", "")
                .replace("DATASET=", "")
            )
        )
    )

    with open(f"{args.output_basename}.html", "w") as f:
        f.write(fig.to_html(full_html=True, include_plotlyjs="cdn"))

if __name__ == "__main__":
    main()
