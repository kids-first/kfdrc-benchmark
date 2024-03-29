import os
import gzip
import pandas as pd
import subprocess
import numpy as np
from matplotlib import pyplot as plt
import argparse

"""
Script to plot stacked bar plots using FP & TP from rtg result folder

command line: python3.11 scripts/plot_tp_fp.py -i results_rtg -f [%AD{1}/%DP] -m input/sample_manifest.tsv -o plot_name -l 0 1 0.05 -n depth

author: Saksham Phul(phuls@chop.edu)
"""
# coding=utf8


def vcf_to_pandas(file):
    vcf_data = []
    upper_header = []
    with gzip.open(file, "rt") as f:
        for line in f:
            line = line.split("\n")[0]
            if line.startswith("#CHROM"):
                header = line.split("\t")
            if not line.startswith("#"):
                calls = line.split("\t")
                vcf_data.append(calls)
    return pd.DataFrame(vcf_data, columns=header)


def vcf_filter_extract(file, filter):
    cmd_bcftools = "bcftools query -f'" + filter + " \n' " + file
    result = subprocess.run(
        cmd_bcftools, shell=True, capture_output=True, text=True, check=True
    )
    return result.stdout.split()  # return filter value as a list


def extract_filter(folder_name, file_target, manifest_sample, sample_type, filter):
    data_list = []
    for folder in os.listdir(folder_name):
        sample_id = folder.replace("_rtg", "")
        folder_address = folder_name + "/" + folder
        for i in os.listdir(folder_address):
            if i == file_target and manifest_sample[sample_id] == sample_type:
                i = folder_address + "/" + file_target
                data_list.append(vcf_filter_extract(i, filter))
                break
    flat_list = [item for sublist in data_list for item in sublist]  # flatten the list
    clean_list = [item for item in flat_list if item != "."]  # remove "." from filters
    divide_operation_vaf = [
        float(item.split("/")[0]) / float(item.split("/")[1]) if "/" in item else item
        for item in clean_list
    ]  # check for '/' operation to perform division
    return divide_operation_vaf


def create_frequency_table(
    folder_name, file_target, m_sample, sample_type, interval, filter
):
    data = pd.DataFrame(
        extract_filter(folder_name, file_target, m_sample, sample_type, filter),
        columns=["filter"],
    )
    data["filter"] = data["filter"].astype("float")
    frequency_table = data["filter"].value_counts(
        bins=list(np.arange(interval[0], interval[1] + interval[2], interval[2]))
    )
    frequency_table = frequency_table.sort_index()
    frequency_table.index = frequency_table.index.astype(str)
    return frequency_table


def plotting(
    folder_name, m_sample, sample_type, output_file_name, filter_name, interval, filter
):
    frequency_table_tp = create_frequency_table(
        folder_name, "tp.vcf.gz", m_sample, sample_type, interval, filter
    )
    frequency_table_fp = create_frequency_table(
        folder_name, "fp.vcf.gz", m_sample, sample_type, interval, filter
    )

    title = "Plot for filter: " + filter + " " + sample_type + " samples"
    file_name = (
        str(output_file_name) + "." + str(filter_name) + "." + str(sample_type) + ".png"
    )
    plt.figure(figsize=(20, 8))
    plt.bar(frequency_table_fp.index, frequency_table_fp.values, color="b")
    plt.bar(
        frequency_table_tp.index,
        frequency_table_tp,
        bottom=frequency_table_fp,
        color="r",
    )
    plt.xticks(fontsize=6)
    plt.yticks(fontsize=10)
    plt.title(title)
    plt.xlabel("Range")
    plt.legend(["False Positives", "True Positives"])
    plt.ylabel("Number of Calls")
    plt.savefig(file_name)


def main(args):
    folder_name = args.input_folder
    filter = args.filter
    filter_name = args.filtername
    output_file_name = args.output_file_name
    start= args.plot_start
    end= args.plot_end
    bin_size= args.plot_bin_size

    interval=[float(start), float(end), float(bin_size)]
    
    if len(interval) != 3:
        raise Exception(
            "Provide all the 3 numeric(int/float): start, end and bin size. Start < End and bin << (End - Start)"
        )

    manifest_sample = pd.read_csv(
        args.sample_manifest, sep="\t", usecols=["sample_id", "experimental_strategy"]
    )
    manifest_sample = manifest_sample.set_index("sample_id").T.to_dict("records")

    plotting(
        folder_name,
        manifest_sample[0],
        "WGS",
        output_file_name,
        filter_name,
        interval,
        filter,
    )  # plot WGS samples
    plotting(
        folder_name,
        manifest_sample[0],
        "WXS",
        output_file_name,
        filter_name,
        interval,
        filter,
    )  # plot WXS samples

    return 1


if __name__ == "__main__":
    # Initialize parser
    parser = argparse.ArgumentParser()

    # Adding argument
    parser.add_argument(
        "-i", "--input_folder", help="provide RTG folder for all the samples"
    )
    parser.add_argument(
        "-f", "--filter", help="provide bcftool like filter string to analysis"
    )
    parser.add_argument(
        "-m", "--sample_manifest", help="provide sample ID with experimental strategy "
    )
    parser.add_argument("-o", "--output_file_name", help="provide output file name")
    parser.add_argument("-n", "--filtername", help="provide filter name")
    parser.add_argument(
        "-s", "--plot_start", help="Start point for the plot"
    )
    parser.add_argument(
        "-e", "--plot_end", help="End point for the plot"
    )
    parser.add_argument(
        "-b", "--plot_bin_size", help="bin size for the plot"
    )

    # Read arguments from command line
    args = parser.parse_args()
    main(args)
