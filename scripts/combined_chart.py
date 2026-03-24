#!/usr/bin/env python3

import itertools
import argparse
import pandas as pd
import plotly.express as px

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

def ensure_color_map_from_palette(color_map: dict, keys, palette=None) -> dict:
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

def build_metrics(parquet_df_path, stratification="WholeGenome"):
    dataset = parquet_df_path.split(".")[0]
    df = pd.read_parquet(parquet_df_path)
    wgs = df[(~df.TOOL.str.contains("mpileup")) & (df.STRATIFICATION == stratification)]

    tmp_counts = list()
    for name, group in wgs.groupby(by=["TOOL", "SUBSET", "STATUS"], observed=True):
        tmp_counts.append((*name, len(group)))

    tmp_metrics = list()
    counts = pd.DataFrame.from_records(tmp_counts, columns=("TOOL", "SUBSET", "METRIC", "COUNT"))
    for tool, subset in itertools.product(wgs.TOOL.unique().tolist(), wgs.SUBSET.unique().tolist()):
        tp_baseline = next(iter(counts[(counts.TOOL == tool) & (counts.SUBSET == subset) & (counts.METRIC == "TP_baseline")].COUNT), 0)
        tp_call = next(iter(counts[(counts.TOOL == tool) & (counts.SUBSET == subset) & (counts.METRIC == "TP_call")].COUNT), 0)
        fp = next(iter(counts[(counts.TOOL == tool) & (counts.SUBSET == subset) & (counts.METRIC == "FP")].COUNT), 0)
        fn = next(iter(counts[(counts.TOOL == tool) & (counts.SUBSET == subset) & (counts.METRIC == "FN")].COUNT), 0)

        total_calls_count = tp_call + fp
        total_baseline_count = tp_baseline + fn

        precision = 0.0 if total_calls_count == 0 else 100 * (tp_call / total_calls_count)
        sensitivity = 0.0 if total_baseline_count == 0 else 100 * (tp_baseline / total_baseline_count)

        sum_pr = precision + sensitivity
        mul_pr = precision * sensitivity
        f1_score = 0.0 if sum_pr == 0 else (2 * mul_pr) / sum_pr

        tmp_metrics.append((dataset, tool, subset, "Precision", precision))
        tmp_metrics.append((dataset, tool, subset, "Sensitivity", sensitivity))
        tmp_metrics.append((dataset, tool, subset, "F1_Score", f1_score))
        
    return pd.DataFrame.from_records(tmp_metrics, columns=("DATASET", "TOOL", "SUBSET", "METRIC", "PERCENT"))

def main():
    parser = argparse.ArgumentParser("make_reports", description="Make benchmarking reports for a dataset given its dataframe")
    parser.add_argument("--brotli_dirs", nargs="+", help="List of directories containing brotli files to process.")
    parser.add_argument("--output_basename", help="Basename for output files")

    args = parser.parse_args()
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
            text=f"{','.join(list(df.METRIC.unique()))} metrics across all datasets",
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
