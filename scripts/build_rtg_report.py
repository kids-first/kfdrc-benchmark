#!/usr/bin/env python3

import argparse
import itertools
import sys

# pip install cyvcf2
import cyvcf2

HEADER_COLUMNS = ["CHROM", "POS", "REF", "ALT", "SCORE", "STATUS", "CALL_WEIGHT", "TOOL", "SUBSET", "STRATIFICATION"]
POSSIBLE_STRATIFICATIONS = ["WholeGenome", "Homopolymer", "TandemRepeat", "Satellite", "LowMappability", "SegDup", "DifficultRegion", "EasyRegion"]


def get_record_status(record):
    value = record.INFO.get("BASE", False)
    if value:
        return f"{value}_baseline" if value == "TP" else value
    value = record.INFO["CALL"]
    return f"{value}_call" if value == "TP" else value


def process_rtg_vcf(vcf_path, tool, out_wf):
    is_base_vcf = "baseline.vcf.gz" in vcf_path

    for record in cyvcf2.Reader(vcf_path):
        status = get_record_status(record)
        if status == "IGN" or status == "OUT":
            continue

        chrom = record.CHROM
        pos = record.POS
        ref = record.REF
        alt = ",".join(record.ALT)
        score = -1.0 if is_base_vcf else record.QUAL
        call_weight = -1.0 if is_base_vcf else record.INFO.get("CALL_WEIGHT", 1.0)
        all_subsets = ["Combined", "SNV" if record.is_snp else "InDel"]
        all_stratifications = ["WholeGenome"] + record.INFO["STRATIFICATIONS"].split(",")

        for subset, stratification in itertools.product(all_subsets, all_stratifications):
            print("\t".join([chrom, str(pos), ref, alt, str(score), status, str(call_weight), tool, subset, stratification]), file=out_wf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("build_report_df", description="Build benchmarking report dataframe")
    parser.add_argument("--sample_name", required=True, help="Basename for output files, without extension")
    parser.add_argument("--tool_name", required=True, help="Name of tool being processed for the benchmarking report")
    parser.add_argument("--call_vcf", required=True, help="Path to a single call vcf to process instead of globbing for RTG vcfeval results in the root directory")
    parser.add_argument("--baseline_vcf", required=True, help="Path to a single baseline vcf to process instead of globbing for RTG vcfeval results in the root directory")
    args = parser.parse_args()

    tmp_tsv_path = f"{args.sample_name}_{args.tool_name}.tsv"

    print(f"Creating temporary tsv file {tmp_tsv_path} to write dataframe for {args.sample_name}", file=sys.stderr)
    with open(tmp_tsv_path, "w") as out_wf:
        print("\t".join(HEADER_COLUMNS), file=out_wf)
        for vcf_path in [args.call_vcf, args.baseline_vcf]:
            print(f"Processing {vcf_path} for {args.sample_name}", file=sys.stderr)
            process_rtg_vcf(vcf_path, args.tool_name, out_wf)
