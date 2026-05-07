#!/usr/bin/env python3

import argparse
import concurrent.futures
import itertools
import os
import sys

# pip install "pandas[performance,parquet]" fastparquet
# import numpy as np
import pandas as pd
# pip install plotly
import plotly.express as px


# https://coolors.co/00a86b-cd5c5c-b2beb5-40826d
TP_CALL_COLOR = "#00a86b"
TP_BASELINE_COLOR = "#40826d"
FP_COLOR = "#cd5c5c"
FN_COLOR = "#b2beb5"

TOOLS_COLOR_MAP = {
    "deepsomatic": "rgb(127, 60, 141)",
    "lancet2": "rgb(17, 165, 121)",
    "lancet1": "rgb(165, 170, 153)",
    "mutect2": "rgb(242, 183, 1)",
    "strelka": "rgb(231, 63, 116)",
    "varnet": "rgb(57, 105, 172)"
}

TOOLS_COLOR_MAP_KF = {
    "BWA-KFsomatic": "rgb(127, 60, 141)",
    "DRAGEN44-KFsomatic": "rgb(17, 165, 121)",
    "DRAGEN44-DRAGEN44": "rgb(165, 170, 153)",
    "DRAGEN44-DRAGEN45": "rgb(242, 183, 1)",
    "DRAGEN45-DRAGEN45": "rgb(231, 63, 116)",
}


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

def build_metrics_df(counts: pd.DataFrame) -> pd.DataFrame:
    """Compute precision, sensitivity, and F1 score from status counts.

    Given a dataframe of per-status counts for each tool and variant subset,
    this function computes standard performance metrics:
    Precision, Sensitivity, and F1 Score. All metric values are expressed
    as percentages.

    Metrics are computed only for observed (tool, subset) combinations, and
    missing status categories are treated as having zero count.

    Args:
        counts: A pandas DataFrame with columns TOOL, SUBSET, METRIC, and COUNT,
            as produced by ``build_counts_df``.

    Returns:
        A pandas DataFrame with columns:
        - TOOL: Tool name
        - SUBSET: Variant subset
        - METRIC: Metric name ("Precision", "Sensitivity", "F1_Score")
        - PERCENT: Metric value expressed as a percentage.
    """
    pivot = (
        counts
        .pivot_table(
            index=["TOOL", "SUBSET"],
            columns="METRIC",
            values="COUNT",
            fill_value=0,
            observed=True,
        )
    )

    rows = []
    for (tool, subset), row in pivot.iterrows():
        tp_baseline = row.get("TP_baseline", 0)
        tp_call = row.get("TP_call", 0)
        fp = row.get("FP", 0)
        fn = row.get("FN", 0)

        total_calls = tp_call + fp
        total_baseline = tp_baseline + fn

        precision = 0.0 if total_calls == 0 else 100 * tp_call / total_calls
        sensitivity = 0.0 if total_baseline == 0 else 100 * tp_baseline / total_baseline
        f1 = 0.0 if (precision + sensitivity) == 0 else 2 * precision * sensitivity / (precision + sensitivity)

        rows.extend([
            (tool, subset, "Precision", precision),
            (tool, subset, "Sensitivity", sensitivity),
            (tool, subset, "F1_Score", f1),
        ])

    return pd.DataFrame(rows, columns=["TOOL", "SUBSET", "METRIC", "PERCENT"])

def plot_metrics_df(
    df: pd.DataFrame,
    category_orders: dict[str, list[str]],
):
    """Create a grouped bar chart of benchmarking metrics.

    Generates a Plotly bar chart visualizing Precision, Sensitivity, and
    F1 Score for each tool, faceted by variant subset. Tool colors are
    assigned deterministically using a predefined color map extended as
    needed from a qualitative palette.

    Args:
        df: A pandas DataFrame containing metric values with columns TOOL,
            SUBSET, METRIC, and PERCENT, as produced by ``build_metrics_df``.
        category_orders: Dictionary specifying the display order for
            categorical axes (e.g., METRIC, TOOL, SUBSET).

    Returns:
        A Plotly Figure representing the metrics bar chart.
    """

    new_color_map = ensure_color_map_from_palette(
        TOOLS_COLOR_MAP_KF,
        df["TOOL"].unique(),
        palette=px.colors.qualitative.Plotly
    )
    legend = dict(orientation="h", xanchor="right", yanchor="bottom", x=0.75, y=-0.15, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.bar(df, x="METRIC", y="PERCENT", color="TOOL", facet_col="SUBSET", barmode="group", facet_col_spacing=0.04,
                 height=840, category_orders=category_orders, color_discrete_map=new_color_map)
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), xaxis=dict(automargin=True),
                      title=dict(text="Precision, Sensitivity and F1 Score metrics", x=0.05, font_size=32, font_color="black"))
    fig.add_annotation(x=-0.03, y=0.5, textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.update_yaxes(ticksuffix="%")
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    return fig


def build_counts_df(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw benchmarking records into status counts.

    Groups the input dataframe by tool, variant subset, and status, and
    computes the number of records in each group. The resulting dataframe
    represents observed counts only (no unobserved combinations are added).

    Args:
        df: A pandas DataFrame containing benchmarking records with at least
            the columns TOOL, SUBSET, and STATUS.

    Returns:
        A pandas DataFrame with columns:
        - TOOL: Tool name
        - SUBSET: Variant subset (e.g., Combined, SNV, InDel)
        - METRIC: Status label (e.g., TP_call, TP_baseline, FP, FN)
        - COUNT: Number of records for each (TOOL, SUBSET, METRIC) combination.
    """
    return (
        df
        .groupby(["TOOL", "SUBSET", "STATUS"], observed=True)
        .size()
        .reset_index(name="COUNT")
        .rename(columns={"STATUS": "METRIC"})
    )


def plot_counts_df(
    df: pd.DataFrame,
    category_orders: dict[str, list[str]]
):
    """Create a grouped bar chart of variant classification counts.

    Generates a Plotly bar chart visualizing the counts of true positives,
    false positives, and false negatives for each tool, faceted by variant
    subset. Tool colors are assigned deterministically using a predefined
    color map extended as needed from a qualitative palette.

    Args:
        df: A pandas DataFrame containing count values with columns TOOL,
            SUBSET, METRIC, and COUNT, as produced by ``build_counts_df``.
        category_orders: Dictionary specifying the display order for
            categorical axes (e.g., METRIC, TOOL, SUBSET).

    Returns:
        A Plotly Figure representing the grouped count bar chart.
    """
    new_color_map = ensure_color_map_from_palette(
        TOOLS_COLOR_MAP_KF,
        df["TOOL"].unique(),
        palette=px.colors.qualitative.Plotly
    )
    legend = dict(orientation="h", xanchor="right", yanchor="bottom", x=0.75, y=-0.15, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.bar(df, x="METRIC", y="COUNT", color="TOOL", facet_col="SUBSET", barmode="group", facet_col_spacing=0.04,
                 height=840, category_orders=category_orders, color_discrete_map=new_color_map)
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), xaxis=dict(automargin=True),
                      title=dict(text="True Positive, False Positive and False Negative counts", x=0.05, font_size=32, font_color="black"))
    fig.add_annotation(x=-0.03, y=0.5, text="Count", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    return fig


def plot_truth_vaf_dist(truth_df):
    legend = dict(orientation="h",  xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.histogram(truth_df, x="TUMOR_VAF", facet_col="SUBSET", barmode="relative", histfunc="count", nbins=100, range_x=[0, 1], facet_col_spacing=0.04,
                       category_orders = {"SUBSET": ["Combined", "SNV", "InDel"]}, color_discrete_sequence=[TP_BASELINE_COLOR], height=480)
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), bargap=0, bargroupgap=0,
                      title=dict(text="Truth Set variant allele frequency distribution", x=0.05, font_size=32, font_color="black"))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.add_annotation(x=-0.03, y=0.5, text="Count", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.35, text="Variant Allele Frequency in the Tumor", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def plot_counts_by_vaf(df, category_orders):
    sub_df = df[~df.STATUS.str.contains("TP_baseline")]
    legend = dict(orientation="h", xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.histogram(sub_df, x="TUMOR_VAF", color="STATUS", facet_col="SUBSET", facet_row="TOOL", barmode="relative", histfunc="count", nbins=100,
                       range_x=[0, 1], facet_col_spacing=0.04, facet_row_spacing=0.025, category_orders=category_orders, height=1280,
                       color_discrete_map={"TP_call": TP_CALL_COLOR, "FP": FP_COLOR, "FN": FN_COLOR})
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), bargap=0, bargroupgap=0,
                      title=dict(text="Count by Status across the variant allele frequency specturm", x=0.05, font_size=32, font_color="black"))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.add_annotation(x=-0.03, y=0.5, text="Count", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.08, text="Variant Allele Frequency in the Tumor", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def plot_precision_by_vaf(df, category_orders):
    legend=dict(orientation="h", xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.histogram(df, x="TUMOR_VAF", color="STATUS", facet_col="SUBSET", facet_row="TOOL", barmode="relative", histfunc="count", barnorm="percent", nbins=100,
                       range_x=[0, 1], range_y=[0, 100], facet_col_spacing=0.04, facet_row_spacing=0.025, category_orders=category_orders, height=1280,
                       color_discrete_map={"TP_call": TP_CALL_COLOR, "FP": FP_COLOR})
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), bargap=0, bargroupgap=0,
                      title=dict(text="Precision across the variant allele frequency specturm", x=0.05, font_size=32, font_color="black"))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.add_annotation(x=-0.03, y=0.5, text="Count per bin normalized as Percentage", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.08, text="Variant Allele Frequency in the Tumor", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def plot_sensitivity_by_vaf(df, category_orders):
    legend=dict(orientation="h", xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.histogram(df, x="TUMOR_VAF", color="STATUS", facet_col="SUBSET", facet_row="TOOL", barmode="relative", histfunc="count", barnorm="percent", nbins=100,
                       range_x=[0, 1], range_y=[0, 100], facet_col_spacing=0.04, facet_row_spacing=0.025, category_orders=category_orders, height=1280,
                       color_discrete_map={"TP_baseline": TP_BASELINE_COLOR, "FN": FN_COLOR})
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), bargap=0, bargroupgap=0,
                      title=dict(text="Sensitivity across the variant allele frequency specturm", x=0.05, font_size=32, font_color="black"))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.add_annotation(x=-0.03, y=0.5, text="Count per bin normalized as Percentage", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.08, text="Variant Allele Frequency in the Tumor", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def build_norm_score_calls_df(df):
    def min_max_scaler(group):
        diff_max_min = group["SCORE"].max() - group["SCORE"].min()
        diff_score_min = group["SCORE"] - group["SCORE"].min()
        group["NORMALIZED_TOOL_SCORE"] = (diff_score_min / diff_max_min).round(2)
        return group

    return df.groupby("TOOL", observed=True).apply(min_max_scaler, include_groups=False).reset_index()


def plot_norm_scores_calls(df, category_orders):
    legend=dict(orientation="h", xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.histogram(df, x="NORMALIZED_TOOL_SCORE", color="STATUS", facet_col="SUBSET", facet_row="TOOL", barmode="relative", histfunc="count",
                       range_x=[0, 1], facet_col_spacing=0.04, facet_row_spacing=0.025, category_orders=category_orders, height=1280,
                       color_discrete_map={"TP_call": TP_CALL_COLOR, "FP": FP_COLOR})
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), bargap=0, bargroupgap=0,
                      title=dict(text="Effectiveness of tool score in distinguishing TPs and FPs", x=0.05, font_size=32, font_color="black"))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.add_annotation(x=-0.03, y=0.5, text="Count", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.08, text="Normalized Tool score", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def build_pr_curve_df(df, baseline_df):
    data = [("SUBSET", "TOOL", "NORMALIZED_TOOL_SCORE", "TP_call", "FP")]
    grouped = df[["NORMALIZED_TOOL_SCORE", "STATUS", "CALL_WEIGHT", "TOOL", "SUBSET"]].groupby(by=["SUBSET", "TOOL"], observed=True)
    for (subset, tool), tmp_group in grouped:
        for _, group in tmp_group.groupby("NORMALIZED_TOOL_SCORE", observed=True):
            tp_count = group[group.STATUS == "TP_call"].CALL_WEIGHT.sum()
            fp_count = group[group.STATUS == "FP"].CALL_WEIGHT.sum()
            if tp_count > 0:
                score_bin = group.NORMALIZED_TOOL_SCORE.unique()[0].round(2)
                data.append((subset, tool, score_bin, tp_count, fp_count))
    
    tmp_df = pd.DataFrame.from_records(data[1:], columns=data[0])
    final_dfs = list()
    for (subset, tool), group in tmp_df.groupby(by=["SUBSET", "TOOL"], observed=True):
        tps = group.loc[::-1, "TP_call"].cumsum()
        fps = group.loc[::-1, "FP"].cumsum()
        base_count = len(baseline_df[(baseline_df.SUBSET == subset) & (baseline_df.TOOL == tool)])
        precision = (tps / (tps + fps)).values
        recall = (tps / base_count).values
        nvals = len(precision)
        series_list = [np.repeat(subset, nvals), np.repeat(tool, nvals), precision, recall]
        final_dfs.append(pd.concat([pd.Series(i) for i in series_list], axis=1).rename(columns={0: "SUBSET", 1: "TOOL", 2: "Precision", 3: "Recall"}))
    return pd.concat(final_dfs, axis=0)


def plot_pr_curve_df(df, category_orders):
    legend = dict(orientation="h", xanchor="right", yanchor="bottom", x=0.75, y=-0.35, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.line(df, x="Recall", y="Precision", color="TOOL", facet_col="SUBSET", range_x=[0, 1], range_y=[0, 1],
                  height=720, category_orders=category_orders, color_discrete_map=TOOLS_COLOR_MAP)
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=150), xaxis=dict(automargin=True),
                      title=dict(text="Precision Recall curves", x=0.05, font_size=32, font_color="black"))
    return fig


def build_upset_df(df):
    df = df[(df.SUBSET != "Combined") & (~df.STATUS.str.contains("TP_call")) & (~df.STATUS.str.contains("FN"))]
    df = df[["CHROM", "POS", "REF", "ALT", "STATUS", "TOOL", "SUBSET"]]

    unstacked_data = list()
    TOOLS = ("deepsomatic", "lancet1", "lancet2", "mutect2", "strelka", "varnet")
    grouped = df.groupby(by=["CHROM", "POS", "REF", "ALT", "SUBSET", "STATUS"], observed=True)
    for (chrom, pos, ref, alt, subset, status), group in grouped:
        status = status.split("_")[0]
        tool_matrix = [1 if tool in group.TOOL.unique() else 0 for tool in TOOLS]
        unstacked_data.append((chrom, pos, ref, alt, subset, status, *tool_matrix))

    upset_data = list()
    tmp_df = pd.DataFrame.from_records(unstacked_data, columns=("CHROM", "POS", "REF", "ALT", "SUBSET", "STATUS", *TOOLS))
    for key, group in tmp_df.groupby(by=["SUBSET", *TOOLS], observed=True):
        subset = key[0]
        one_hot_set = "".join([str(i) for i in key[1:]])

        counts = group.STATUS.value_counts()
        tp_count = counts.get("TP", 0)
        fp_count = counts.get("FP", 0)
        num_calls = tp_count + fp_count
        if num_calls == 0:
            continue

        validation_rate = ((100.0 * tp_count) / num_calls).round(2)
        upset_data.append((subset, one_hot_set, num_calls, tp_count, validation_rate))

    one_hot_mapping = dict()
    short_tool_codes = ["DS", "L1", "L2", "M2", "ST", "VN"]
    upset_df = pd.DataFrame.from_records(upset_data, columns=("SUBSET", "ONE_HOT_SET", "NUM_CALLS", "NUM_VALIDATED", "VALIDATION_RATE"))

    for one_hot_set in itertools.product(range(2), repeat=6):
        key = "".join([str(i) for i in one_hot_set])
        if key not in upset_df.ONE_HOT_SET.unique():
            continue
        val = "_".join([short_tool_codes[idx] for idx, pav in enumerate(one_hot_set) if one_hot_set[idx] == 1])
        one_hot_mapping[key] = val

    upset_df["OVERLAP_GROUP"] = upset_df.ONE_HOT_SET.apply(lambda x: one_hot_mapping[x])
    return upset_df


def plot_validation_rate(df, subset_name):
    legend=dict(orientation="h", xanchor="right", yanchor="bottom", x=0.95, y=1.05, font_size=20, bgcolor="ghostwhite", bordercolor="gray", borderwidth=0.5)
    fig = px.bar(df, x="OVERLAP_GROUP", y=["NUM_CALLS", "NUM_VALIDATED"], text="VALIDATION_RATE", log_y=True, barmode="overlay", height=840, opacity=1,
                 color_discrete_map={"NUM_VALIDATED": "rgb(57, 105, 72)", "NUM_CALLS": "rgb(242, 183, 1)"}, labels={"value": "VALUE", "variable": "VARIABLE"})
    fig.for_each_xaxis(lambda x: x.update(title=""))
    fig.for_each_yaxis(lambda y: y.update(title=""))
    fig.update_layout(legend=legend, font_family="Figtree", font_color="dimgray", font_size=18, margin=dict(t=120), xaxis=dict(automargin=True),
                      title=dict(text=f"{subset_name} validation rate across overlap groups", x=0.05, font_size=32, font_color="black"))
    fig.add_annotation(x=-0.03, y=0.5, text="Count", textangle=-90, xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    fig.add_annotation(x=0.5, y=-0.4, text="Overlap group", xref="paper", yref="paper", font_family="Figtree", font_color="dimgray", font_size=24)
    return fig


def make_stratification_report(stratification, cli_args):
    dataset_name = cli_args.dataset
    truth_name = cli_args.truthset
    sys.stderr.write(f"Starting to write HTML benchmarking report for {dataset_name} {stratification}\n")

    if cli_args.parquet:
        df = pd.read_parquet(cli_args.parquet)
        df = df[(~df.TOOL.str.contains("mpileup")) & (df.STRATIFICATION == stratification)]
    else:
        dfs = []
        for tsv_path in cli_args.tsvs:
            tmp_df = pd.read_csv(tsv_path, sep="\t")
            tmp_df = tmp_df[(~tmp_df.TOOL.str.contains("mpileup")) & (tmp_df.STRATIFICATION == stratification)]
            dfs.append(tmp_df)
        df = pd.concat(dfs, ignore_index=True)

    counts = build_counts_df(df)
    metrics = build_metrics_df(counts)

#    calls = df[(~df.STATUS.str.contains("TP_baseline")) & (~df.STATUS.str.contains("FN"))]
#    baseline = df[(~df.STATUS.str.contains("TP_call")) & (~df.STATUS.str.contains("FP"))]
#    scaled_calls = build_norm_score_calls_df(calls)
#    pr_curve = build_pr_curve_df(scaled_calls, baseline)
#    upset_df = build_upset_df(df)

    # Sort tool names by combined F1 score for the current data view
    ALL_TOOLS_ORDERED = metrics[(metrics.SUBSET == "Combined") & (metrics.METRIC == "F1_Score")].sort_values("PERCENT", ascending=False).TOOL.tolist()
    ALL_SUBSETS_ORDERED = ["Combined", "SNV", "InDel"]

#    truthset_mask = (~df.STATUS.str.contains("TP_call")) & (~df.STATUS.str.contains("FP"))

    plots = [
        plot_metrics_df(metrics, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "METRIC": ["F1_Score", "Precision", "Sensitivity"]}),
        plot_counts_df(counts, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "METRIC": ["TP_baseline", "TP_call", "FP", "FN"]}),
#        plot_truth_vaf_dist(df[truthset_mask].drop_duplicates(subset=["CHROM", "POS", "REF", "ALT", "SUBSET"], ignore_index=True)),
#        plot_counts_by_vaf(df, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "STATUS": ["TP_call", "FP", "FN"]}),
#        plot_precision_by_vaf(calls, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "STATUS": ["TP_call", "FP"]}),
#        plot_sensitivity_by_vaf(baseline, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "STATUS": ["TP_baseline", "FN"]}),
#        plot_norm_scores_calls(scaled_calls, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED, "STATUS": ["TP_call", "FP"]}),
#        plot_pr_curve_df(pr_curve, category_orders={"TOOL": ALL_TOOLS_ORDERED, "SUBSET": ALL_SUBSETS_ORDERED}),
#        plot_validation_rate(upset_df[upset_df.SUBSET == "SNV"].sort_values(by=["NUM_CALLS", "VALIDATION_RATE"], ascending=False), "SNV"),
#        plot_validation_rate(upset_df[upset_df.SUBSET == "InDel"].sort_values(by=["NUM_CALLS", "VALIDATION_RATE"], ascending=False), "InDel"),
    ]

    out_report = os.path.join(cli_args.out_dir, f"{dataset_name}_{stratification}.html")
    with open(out_report, "w", encoding="utf-8") as wf:
        wf.write(
f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@600&display=swap" rel="stylesheet">
    <script charset="utf-8" src="https://cdn.plot.ly/plotly-2.34.0.min.js"></script>
    <title>{dataset_name} {stratification} {truth_name} report</title>
</head>
<body style="font-family: Figtree, sans-serif; font-optical-sizing: auto; font-weight: 600; font-style: normal; position: relative;">
    <header style="height: 110px; top: -50px; display: flex; align-items: center; justify-content: center; background-color: #f2f5f7; box-shadow: 0 2px 10px 0 rgba(0,0,0,0.2); margin-bottom: 4vh;">
        <div style="height: 70px; top: 0; display: flex; align-items: center; justify-content: center;">
            <h1 style="font-size: 42px; display: block; margin-right: 5vw;">{dataset_name} {stratification} {truth_name} report</h1>
            <nav style="display: flex; flex-wrap: wrap; justify-content: space-between">
                <a href="{dataset_name}_WholeGenome.html" onclick="window.location.reload(true)" style="margin-left: 20px;">WholeGenome</a>
                <a href="{dataset_name}_EasyRegion.html" onclick="window.location.reload(true)" style="margin-left: 20px;">EasyRegion</a>
                <a href="{dataset_name}_DifficultRegion.html" onclick="window.location.reload(true)" style="margin-left: 20px;">DifficultRegion</a>
                <a href="{dataset_name}_LowMappability.html" onclick="window.location.reload(true)" style="margin-left: 20px;">LowMappability</a>
                <a href="{dataset_name}_TandemRepeat.html" onclick="window.location.reload(true)" style="margin-left: 20px;">TandemRepeat</a>
                <a href="{dataset_name}_Homopolymer.html" onclick="window.location.reload(true)" style="margin-left: 20px;">Homopolymer</a>
                <a href="{dataset_name}_Satellite.html" onclick="window.location.reload(true)" style="margin-left: 20px;">Satellite</a>
                <a href="{dataset_name}_SegDup.html" onclick="window.location.reload(true)" style="margin-left: 20px;">SegDup</a>
            </nav>
        </div>
    </header>
    <main>
""")
        for figure in plots:
            raw_html = figure.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})
            wf.write(raw_html.replace("width:100%;","width:95%; margin:auto;"))
            wf.write("""<div style="margin: 5vh auto; width=100%"><hr/></div>""")
        wf.write("</main></body></html>\n")

    return f"{dataset_name} {stratification}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser("make_reports", description="Make benchmarking reports for a dataset given its dataframe")
    parser.add_argument("-t", "--truthset", required=True, help="Name of truthset to be used in the benchmarking report")
    parser.add_argument("-d", "--dataset", required=True, help="Name of dataset to be used in the benchmarking report")
    parser.add_argument("-p", "--parquet", help="Path to parquet dataframe directory contaning all information for a run")
    parser.add_argument("-o", "--out-dir", default=".", help="Path to existing directory to write the HTML benchmarking reports")
    parser.add_argument("--tsvs", nargs="+", help="Paths to TSV files containing calls and truth information for a run. Columns must be CHROM, POS, REF, ALT, TOOL, STATUS, SUBSET, SCORE")
    args = parser.parse_args()

    POSSIBLE_STRATIFICATIONS = ["WholeGenome", "Homopolymer", "TandemRepeat", "Satellite", "LowMappability", "SegDup", "DifficultRegion", "EasyRegion"]

    dfs = [pd.read_csv(tsv_path, sep="\t") for tsv_path in args.tsvs]
    df = pd.concat(dfs, ignore_index=True)
    df.sort_values(by=["STRATIFICATION", "SUBSET",  "TOOL", "CHROM", "POS", "REF", "ALT"], inplace=True)
    df.to_parquet(f"{args.dataset}.parquet.brotli", compression="brotli", index=False, partition_cols=["STRATIFICATION", "SUBSET", "TOOL"])

    with concurrent.futures.ProcessPoolExecutor() as executor:
        for done_report_name in executor.map(make_stratification_report, POSSIBLE_STRATIFICATIONS, itertools.repeat(args)):
            sys.stderr.write(f"Done writing HTML benchmarking report for {done_report_name}\n")

