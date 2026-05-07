#!/usr/bin/env python3

import argparse
import itertools
import sys
import cyvcf2

HEADER_COLUMNS = ["CHROM", "POS", "REF", "ALT", "SCORE", "STATUS", "CALL_WEIGHT", "TOOL", "SUBSET", "STRATIFICATION"]

def get_record_status(record: cyvcf2.Variant) -> str:
    """Derive the benchmarking status for a vcfeval VCF record.

    The status is determined from RTG vcfeval INFO annotations, preferring
    the ``BASE`` field (baseline records) and falling back to the ``CALL``
    field (call records). True positives (``TP``) are suffixed to indicate
    their origin.

    Mapping rules:
      - INFO["BASE"] == "TP"  -> "TP_baseline"
      - INFO["CALL"] == "TP"  -> "TP_call"
      - Other values are returned unchanged.

    Args:
        record: A ``cyvcf2.Variant`` representing a single VCF record.

    Returns:
        A status string such as "TP_call", "FP", "FN", or "IGN".
    """
    base = record.INFO.get("BASE")
    if base:
        return f"{base}_baseline" if base == "TP" else base

    call = record.INFO.get("CALL")
    if call:
        return f"{call}_call" if call == "TP" else call

    return "UNK"


def process_rtg_vcf(vcf_path: str, tool: str, out_wf) -> None:
    """Process an RTG vcfeval VCF and write benchmarking rows to a TSV.

    Each variant record is expanded into multiple output rows by taking the
    Cartesian product of variant subsets ("Combined", "SNV", "InDel") and
    genomic stratifications ("WholeGenome" plus any values in
    INFO["STRATIFICATIONS"]).

    Baseline VCFs are detected heuristically via the filename and assigned
    sentinel values for numeric fields that are only meaningful for call
    VCFs.

    Args:
        vcf_path: Path to a vcfeval call or baseline VCF file.
        tool: Name of the variant calling tool being benchmarked.
        out_wf: Open, writable file handle for TSV output.

    Returns:
        None
    """
    is_base_vcf = "baseline.vcf.gz" in vcf_path


    with cyvcf2.Reader(vcf_path) as reader:
        for record in reader:
            status = get_record_status(record)
            if status in {"IGN", "OUT"}:
                continue

            chrom = record.CHROM
            pos = record.POS
            ref = record.REF
            alt = ",".join(record.ALT) if record.ALT else "."
            score = -1.0 if is_base_vcf else record.QUAL
            call_weight = -1.0 if is_base_vcf else record.INFO.get("CALL_WEIGHT", 1.0)
            all_subsets = ["Combined", "SNV" if record.is_snp else "InDel"]
            raw = record.INFO.get("STRATIFICATIONS", "")
            all_stratifications = ["WholeGenome", *raw.split(",")] if raw else ["WholeGenome"]
            all_stratifications = sorted(set(all_stratifications))

            for subset, stratification in itertools.product(all_subsets, all_stratifications):
                print("\t".join([chrom, str(pos), ref, alt, str(score), status, str(call_weight), tool, subset, stratification]), file=out_wf)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("build_report_df", description="Build benchmarking report dataframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
