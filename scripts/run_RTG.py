import pandas as pd
import os
import subprocess
import re
import argparse
import warnings
import sys
from pandarallel import pandarallel

"""
Script to filter and run rtg tool to benchmark only tumor calls with provided normal vcfs

command line: python3.11 scripts/run_RTG.py -i tumor_files -c consenus_files -f 'FORMAT/DP>30 | FORMAT/AF>0.5' -o test -r /home/ubuntu/mount/tumor_only_benchmarking/reference/human

author: Saksham Phul(phuls@chop.edu)
"""


def map_sample_id_with_file(path):
    """
    This function builds a manifest using test_folder by extracting sample id from test file and mapping it with consensus file. It return the data for all the
    files as a pandas dataframe
    """

    bcftools_samples = "bcftools query -l "
    sample_id_files = []

    filelist = os.listdir(path)
    for file in filelist:
        if file.endswith("vcf.gz"):
            file_path = path + "/" + file
            cmd_samples = bcftools_samples + file_path
            samples_vcf = (
                subprocess.check_output(cmd_samples, shell=True).decode("utf-8").strip()
            )
            if re.search("\n", samples_vcf):
                for sample in samples_vcf.split("\n"):
                    sample_id_files.append([sample, file_path])
            else:
                sample_id_files.append([samples_vcf, file_path])

    return pd.DataFrame(sample_id_files, columns=["sample_id", "file_path"])


def run_rtg(sample_id, tumor_only_file, consensus_only_files, ref_file, filter_string):
    """
    This function can filter VCFs based on filter string (in bcftool format) and will run rtg to return result as confusion matrix/F1 scores
    """

    # Check that VCFs exist
    if not os.path.isfile(consensus_only_files) or not os.path.isfile(tumor_only_file):
        print(
            f"Warning: Skipping RTG run for {sample_id} - cannot find either tumor or consensus file",
            file=sys.stderr,
        )
        return [None, None, None, None, None, None, None, None]

    # Check that VCFs have TBI indexes
    index_file_consensus_only = consensus_only_files + ".tbi"
    index_file_tumor_only = tumor_only_file + ".tbi"
    if not os.path.isfile(index_file_consensus_only) or not os.path.isfile(
        index_file_tumor_only
    ):
        print(
            f"Warning: Skipping RTG run for {sample_id} - cannot find index file {index_file_consensus_only} or {index_file_tumor_only}",
            file=sys.stderr,
        )
        return [None, None, None, None, None, None, None, None]

    if len(filter_string) > 0:  # run with filter string provided

        cmd_filter = (
            "bcftools view -Oz --thread 4 "
            f"-i '{filter_string}' "
            f"-o filtered_vcfs/{sample_id}.filtered.vcf.gz "
            f"{tumor_only_file} "
            "&& "
            f"tabix filtered_vcfs/{sample_id}.filtered.vcf.gz "
        )
        print(cmd_filter,file=sys.stderr)

        subprocess.run(cmd_filter, shell=True)
        path_filtered_files=os.getcwd()+"/"+"filtered_vcfs/"+sample_id+".filtered.vcf.gz"
        cmd = (
            "rtg vcfeval "
            f"--baseline={consensus_only_files}  "
            f"--sample={sample_id} "
            f"--calls {path_filtered_files} "
            f"--template {ref_file} "
            "--all-records "
            "--no-roc "
            f"--output results_rtg/{sample_id}_rtg"
        )
    else:  # run without the filter
        cmd = (
            "rtg vcfeval "
            f"--baseline={consensus_only_files} "
            f"--sample={sample_id} "
            f"--calls {tumor_only_file} "
            f"--template {ref_file} "
            "--all-records "
            "--no-roc "
            f"--output results_rtg/{sample_id}_rtg"
        )
    # Run RTG on proper inputs
    print("Running RTG on: ", sample_id, file=sys.stderr)
    output = subprocess.check_output(cmd, shell=True).decode("utf-8").strip()

    return output.split("\n")[-1].split()


def clean_filename(row):
    """
    Remove abs path and return just the file name
    """
    return row.split("/")[-1]


def main():
    # Initialize parser
    parser = argparse.ArgumentParser()

    # Adding optional argument
    parser.add_argument(
        "-i",
        "--test_folder_path",
        help="provide folder containing test vcf file with index files",
    )
    parser.add_argument(
        "-c",
        "--consensus_folder_path",
        help="provide folder containing consensus vcf file with index files",
    )
    parser.add_argument(
        "-r", "--ref_folder_sdf", help="provide reference file in fasta format"
    )
    parser.add_argument(
        "-t",
        "--workers",
        help="provide cores to run samples in multiprocessing",
        type=int,
        default=8,
    )
    parser.add_argument(
        "-f", "--filter", help="provide filter string in bcftool format", default=""
    )
    parser.add_argument("-o", "--output_file_name", help="provide output file name")

    # suppress pandas future warnings
    warnings.simplefilter(action="ignore", category=FutureWarning)

    args = parser.parse_args()

    pandarallel.initialize(
        nb_workers=int(int(args.workers) / 2)
    )  # divide by 2 for load balancing as rtg tool will utilize multi processing for single run

    consensus_path = args.consensus_folder_path
    tumor_only_path = args.test_folder_path
    ref_file = args.ref_folder_sdf
    filter_string = args.filter

    tumor_only_manifest = map_sample_id_with_file(
        tumor_only_path
    )  # map files with sample ID, test vcf files and return a list
    tumor_only_manifest = tumor_only_manifest.drop_duplicates(
        subset=["sample_id"], keep="first"
    )  # drop duplicate if multiple file exist with same sample Id
    consensus_only_manifest = map_sample_id_with_file(
        consensus_path
    )  # map files with sample ID, consensus files and return a list
    consensus_only_manifest = consensus_only_manifest.drop_duplicates(
        subset=["sample_id"], keep="first"
    )  # drop duplicate if multiple file exist with same sample Id

    tumor_consensus_sample_ID = pd.merge(
        tumor_only_manifest, consensus_only_manifest, on=["sample_id"], how="inner"
    )

    tumor_consensus_sample_ID = tumor_consensus_sample_ID.rename(
        columns={"file_path_x": "test_input_file", "file_path_y": "reference_file"}
    )

    tumor_consensus_sample_ID = tumor_consensus_sample_ID.sort_values(
        "sample_id", ascending=False
    )

    if len(filter_string) > 0:  # check if filter string is provided or not
        subprocess.run("mkdir filtered_vcfs", shell=True)  # make a folder to store filter vcfs
        
    tumor_consensus_sample_ID["result"] = tumor_consensus_sample_ID.parallel_apply(
        lambda row: run_rtg(
            row["sample_id"],
            row["test_input_file"],
            row["reference_file"],
            ref_file,
            filter_string,
        ),
        axis=1,
    )

    tumor_consensus_sample_ID[
        [
            "Threshold",
            "True-pos-baseline",
            "True-pos-call",
            "False-pos",
            "False-neg",
            "Precision",
            "Sensitivity",
            "F-measure",
        ]
    ] = pd.DataFrame(
        tumor_consensus_sample_ID.result.tolist(), index=tumor_consensus_sample_ID.index
    )

    tumor_consensus_sample_ID = tumor_consensus_sample_ID.drop(
        ["result", "Threshold"], axis=1
    )
    tumor_consensus_sample_ID = tumor_consensus_sample_ID[
        [
            "sample_id",
            "Precision",
            "Sensitivity",
            "F-measure",
            "True-pos-baseline",
            "True-pos-call",
            "False-pos",
            "False-neg",
            "test_input_file",
            "reference_file",
        ]
    ]

    tumor_consensus_sample_ID["test_input_file"] = tumor_consensus_sample_ID[
        "test_input_file"
    ].apply(clean_filename)
    tumor_consensus_sample_ID["reference_file"] = tumor_consensus_sample_ID[
        "reference_file"
    ].apply(clean_filename)

    if not args.output_file_name.endswith(".tsv"):
        output_mean = args.output_file_name + "_mean.tsv"
        output_file = args.output_file_name + ".tsv"

    else:
        output_file = args.output_file_name
        tmp_list = output_file.split(".")
        output_mean = tmp_list[0] + "_mean.tsv"

    tumor_consensus_sample_ID["Filter_string"] = filter_string
    # write output file
    tumor_consensus_sample_ID.to_csv(output_file, sep="\t", index=False)

    tumor_consensus_sample_ID = (
        tumor_consensus_sample_ID.dropna()
    )  # drop nan if any to compute average of all the samples

    tumor_consensus_sample_ID = tumor_consensus_sample_ID.astype(
        {
            "Precision": float,
            "Sensitivity": float,
            "F-measure": float,
            "True-pos-baseline": int,
            "True-pos-call": int,
            "False-pos": int,
            "False-neg": int,
        }
    )

    mean_results_df = tumor_consensus_sample_ID[
        [
            "Precision",
            "Sensitivity",
            "F-measure",
            "True-pos-baseline",
            "True-pos-call",
            "False-pos",
            "False-neg",
        ]
    ].mean()  # compute mean

    mean_results_df = mean_results_df.round(3)
    mean_results_df["No. of samples"] = len(tumor_consensus_sample_ID.index)
    mean_results_df["Filter_string"] = filter_string
    mean_results_df = mean_results_df.to_frame(name="Average_results")

    # write average results
    mean_results_df.to_csv(output_mean, sep="\t", index=True)


if __name__ == "__main__":
    main()
