#!/usr/bin/env python3
"""
Workflow orchestrator for tumor/normal benchmarking on Seven Bridges.

Stages:
- downsample
- align
- somatic
- consensus
- benchmark
"""

import argparse
import copy
import csv
import json
import logging
from urllib.parse import urlparse
import sevenbridges as sbg
from sevenbridges.http.error_handlers import rate_limit_sleeper, maintenance_sleeper
import sys
import time

# ----------------------------
# Seven Bridges API caches
# ----------------------------

_FILE_CACHE: dict[str, object] = {}
_TASK_CACHE: dict[str, object] = {}
_APP_CACHE: dict[str, object] = {}

VALID_START_FROM = {
    "downsample",
    "align",
    "somatic",
    "benchmark",
}

TASK_DONE = "COMPLETED"

class ManifestValidationError(Exception):
    pass

def get_file(api, file_id):
    if not file_id:
        return None
    if file_id not in _FILE_CACHE:
        _FILE_CACHE[file_id] = api.files.get(file_id)
    return _FILE_CACHE[file_id]


def get_task(api, task_id):
    if not task_id:
        return None
    if task_id not in _TASK_CACHE:
        _TASK_CACHE[task_id] = api.tasks.get(task_id)
    return _TASK_CACHE[task_id]


def get_app(api, app_id):
    if not app_id:
        return None
    if app_id not in _APP_CACHE:
        _APP_CACHE[app_id] = api.apps.get(app_id)
    return _APP_CACHE[app_id]

def is_valid_url(s: str) -> bool:
    try:
        parsed = urlparse(s)
        return all([parsed.scheme in ("http", "https"), parsed.netloc])
    except Exception:
        return False

def is_valid_id(file_id, api):
    try:
        get_file(api, file_id)
        return True
    except Exception:
        return False

def tsv_to_manifest_json(tsv_path):
    manifest = {}

    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row_num, row in enumerate(reader, start=1):
            run_id = f"{row.get('tumor_biospecimen')}-{row.get('normal_biospecimen')}.{row.get('alignment_type', 'BWA')}-{row.get('somatic_type', 'KFsomatic')}"
            start_from = row.get("start_from")

            entry = {
                "downsample": {
                    "tumor": {"inputs": {}, "task_id": None},
                    "normal": {"inputs": {}, "task_id": None},
                },
                "align": {
                    "tumor": {"inputs": {}, "task_id": None},
                    "normal": {"inputs": {}, "task_id": None},
                },
                "somatic": {
                    "inputs": {},
                    "task_id": None,
                },
                "consensus": {
                    "inputs": {},
                    "task_id": None,
                },
                "call_vcf": row.get("call_vcf"),
                "truth_vcf": row.get("truth_vcf"),
                "align_type": row.get("alignment_type"),
                "somatic_type": row.get("somatic_type"),
                "tumor_biospecimen": row.get("tumor_biospecimen"),
                "normal_biospecimen": row.get("normal_biospecimen"),
                "start_from": row.get("start_from"),
                "run_id": run_id
            }

            tumor_bam = row.get("tumor_bam")
            normal_bam = row.get("normal_bam")

            if start_from == "downsample":
                entry["downsample"]["tumor"]["inputs"]["bam_url"] = tumor_bam
                entry["downsample"]["normal"]["inputs"]["bam_url"] = normal_bam

            elif start_from == "align":
                entry["align"]["tumor"]["inputs"]["input_bam_list"] = [tumor_bam]
                entry["align"]["normal"]["inputs"]["input_bam_list"] = [normal_bam]

            elif start_from == "somatic":
                entry["somatic"]["inputs"]["input_tumor_aligned"] = tumor_bam
                entry["somatic"]["inputs"]["input_normal_aligned"] = normal_bam

            manifest[row_num] = entry

    return manifest

def safe_get_path(entry: dict, *path: str):
    """Safely fetch nested dict values."""
    for key in path:
        if not isinstance(entry, dict):
            return None
        entry = entry.get(key)
    return entry

def validate_manifest_files(manifest: dict, api) -> None:
    """
    manifest: output of tsv_to_manifest_json()
    api: sevenbridges.Api instance
    """
    errors = []

    for row_num, entry in manifest.items():

        # File URLs
        file_urls = []
        file_urls.append(safe_get_path(entry, "downsample", "tumor", "inputs", "bam_url"))
        file_urls.append(safe_get_path(entry, "downsample", "normal", "inputs", "bam_url"))
        for furl in file_urls:
            if furl and not is_valid_url(furl):
                errors.append(f"[Manifest {row_num=}] Invalid URL: {furl}")

        # File IDs
        file_ids = []
        file_ids.extend(safe_get_path(entry, "align", "tumor", "inputs", "input_bam_list") or [])
        file_ids.extend(safe_get_path(entry, "align", "normal", "inputs", "input_bam_list") or [])
        file_ids.append(safe_get_path(entry, "somatic", "inputs", "input_tumor_aligned"))
        file_ids.append(safe_get_path(entry, "somatic", "inputs", "input_normal_aligned"))
        file_ids.append(safe_get_path(entry, "call_vcf"))
        file_ids.append(safe_get_path(entry, "truth_vcf"))
        for fid in file_ids:
            if fid and not is_valid_id(fid, api):
                errors.append(f"[Manifest {row_num=}] Invalid FILE ID: {fid=}")

    if errors:
        raise ManifestValidationError("\n".join(errors))

def validate_required_fields(manifest: dict) -> None:
    """
    Validates presence of required fields in the manifest JSON
    based on the value of `start_from`.
    """

    errors = []

    for row_num, entry in manifest.items():
        prefix = f"[Manifest {row_num=}]"

        # ---- Always required ----
        required_fields = (
            "tumor_biospecimen",
            "normal_biospecimen",
            "truth_vcf",
            "start_from",
        )

        for field in required_fields:
            if not entry.get(field):
                errors.append(f"{prefix} Missing required field: {field}")

        start_from = entry.get("start_from")
        if start_from not in VALID_START_FROM:
            errors.append(
                f"{prefix} Invalid or unsupported start_from value: {start_from}"
            )
            continue

        # ---- start_from–specific rules ----
        if start_from == "downsample":
            for sample in ("tumor", "normal"):
                bam_url = safe_get_path(entry, "downsample", sample, "inputs", "bam_url")
                if not bam_url:
                    errors.append(
                        f"{prefix} Missing downsample {sample} bam_url"
                    )

        elif start_from == "align":
            for sample in ("tumor", "normal"):
                bam_list = safe_get_path(entry, "align", sample, "inputs", "input_bam_list")
                if not bam_list:
                    errors.append(
                        f"{prefix} Missing align {sample} input_bam_list"
                    )

        elif start_from == "somatic":
            somatic_inputs = safe_get_path(entry, "somatic", "inputs") or {}

            if not somatic_inputs.get("input_tumor_aligned"):
                errors.append(
                    f"{prefix} Missing somatic input_tumor_aligned"
                )
            if not somatic_inputs.get("input_normal_aligned"):
                errors.append(
                    f"{prefix} Missing somatic input_normal_aligned"
                )
            if not entry.get("align_type"):
                errors.append(f"{prefix} Missing align_type")

        elif start_from == "benchmark":
            if not entry.get("call_vcf"):
                errors.append(
                    f"{prefix} Missing call_vcf"
                )
            if not entry.get("align_type"):
                errors.append(f"{prefix} Missing align_type")
            if not entry.get("somatic_type"):
                errors.append(f"{prefix} Missing somatic_type")

        else:
            errors.append(
                f"{prefix} Invalid or unsupported start_from value: {start_from}"
            )

    if errors:
        raise ManifestValidationError("\n".join(errors))

def create_downsample_payload(
    *,
    entry,
    inputs,
    role,
    input_copy,
    api,
) -> dict:
    input_copy.update({
        "bam_url": inputs.get("bam_url"),
        "target_coverage": 60 if role == "tumor" else 30,
    })
    return input_copy

def create_align_payload(
    *,
    entry,
    inputs,
    role,
    input_copy,
    api,
) -> dict:
    bam_list = [
        get_file(api, fid).path
        for fid in inputs.get("input_bam_list", [])
    ]

    biospecimen = (
        entry["tumor_biospecimen"]
        if role == "tumor"
        else entry["normal_biospecimen"]
    )

    input_copy.update({
        "input_bam_list": bam_list,
        "output_basename": f"{biospecimen}.BWA",
        "biospecimen_name": biospecimen,
        "run_hs_metrics": False,
        "run_wgs_metrics": True,
        "run_agg_metrics": True,
        "run_sex_metrics": True,
        "run_gvcf_processing": False,
    })
    return input_copy

def create_somatic_payload(
    *,
    entry,
    inputs,
    role,
    input_copy,
    api,
) -> dict:
    tumor_aligned = get_file(api, inputs.get("input_tumor_aligned"))
    normal_aligned = get_file(api, inputs.get("input_normal_aligned"))

    input_copy.update({
        "input_tumor_aligned": tumor_aligned,
        "input_normal_aligned": normal_aligned,
        "input_tumor_name": entry["tumor_biospecimen"],
        "input_normal_name": entry["normal_biospecimen"],
        "output_basename": (
            f"{entry['tumor_biospecimen']}."
            f"{entry['align_type']}-KFsomatic"
        ),
        "gatk_filter_expression": [
            "gnomad_3_1_1_AF != '.' && gnomad_3_1_1_AF > 0.001 && gnomad_3_1_1_FILTER=='PASS'",
            f"vc.getGenotype('{entry['normal_biospecimen']}').getDP() <= 7",
        ],
        "gatk_filter_name": [
            "GNOMAD_AF_HIGH",
            "NORM_DP_LOW",
        ],
        "wgs_or_wxs": "WGS",
        "run_amplicon_architect": False,
        "run_cnvkit": False,
        "run_controlfreec": False,
        "run_gatk_cnv": False,
        "run_manta": False,
        "run_theta2": False,
        "run_lancet": True,
        "run_mutect2": True,
        "run_strelka2": True,
        "run_vardict": True,
    })
    return input_copy

def create_consensus_payload(
    *,
    entry,
    inputs,
    role,
    input_copy,
    api,
) -> dict:
    input_copy.update({
        "lancet_vcf": get_file(api, inputs.get("lancet_vcf")),
        "mutect2_vcf": get_file(api, inputs.get("mutect2_vcf")),
        "strelka2_vcf": get_file(api, inputs.get("strelka2_vcf")),
        "vardict_vcf": get_file(api, inputs.get("vardict_vcf")),
        "cram": get_file(api, inputs.get("cram")),
        "input_tumor_name": entry["tumor_biospecimen"],
        "input_normal_name": entry["normal_biospecimen"],
        "output_basename": (
            f"{entry['tumor_biospecimen']}."
            f"{entry['align_type']}."
            f"{entry['somatic_type']}"
        ),
        "gatk_filter_expression": [
            "gnomad_3_1_1_AF != '.' && gnomad_3_1_1_AF > 0.001 && gnomad_3_1_1_FILTER=='PASS'",
            f"vc.getGenotype('{entry['normal_biospecimen']}').getDP() <= 7",
        ],
        "gatk_filter_name": [
            "GNOMAD_AF_HIGH",
            "NORM_DP_LOW",
        ],
    })
    return input_copy

def create_benchmark_payload(
    *,
    group_key,
    grouped_entries,
    input_copy,
    api,
):
    tumor_biospecimen, truth_vcf = group_key

    call_vcfs = []
    tool_names = []
    for entry in grouped_entries:
        call_vcfs.append(get_file(api, entry["call_vcf"]))
        tool_names.append(f"{entry.get('align_type')}-{entry.get('somatic_type')}")

    input_copy.update({
        "baseline": get_file(api, truth_vcf),
        "calls": call_vcfs,
        "tool_name": tool_names,
        "sample_name": tumor_biospecimen,
    })

    return input_copy

def ensure_step_struct(entry: dict, step: str, roles=None):
    """
    Ensure that the workflow state contains the required structure
    for a given step and optional roles.

    This initializes missing dictionaries for the step and, if roles
    are provided, ensures each role has an associated 'inputs' map.
    Existing data is preserved.

    Args:
        entry (dict): Mutable workflow state for a single run.
        step (str): Workflow step name (e.g. "downsample", "align").
        roles (iterable[str] | None): Optional roles (e.g. ["tumor", "normal"])
            for paired-sample steps.
    """
    entry.setdefault(step, {})
    if roles:
        for role in roles:
            entry[step].setdefault(role, {})
            entry[step][role].setdefault("inputs", {})

def ensure_task(
    *,
    run_id: str,
    entry: dict,
    step: str,
    role=str|None,
    draft_task_id: str,
    payload_fn: callable,
    biospecimen: str,
    api: sbg.Api,
):
    """
    Ensure that a task exists for a given workflow step (and optional role).

    If a task_id is already present in the workflow state, it is returned.
    Otherwise, a new task is created using the provided draft task and
    payload builder, the task_id is stored back into the workflow entry,
    and the new task_id is returned.

    This function is idempotent and safe to call repeatedly.

    Args:
        run_id (str): Workflow run identifier (used for logging).
        entry (dict): Mutable workflow state for this run.
        step (str): Workflow step name (e.g. "downsample", "align").
        role (str | None): Optional role ("tumor", "normal") for paired steps.
        draft_task_id (str): Backend draft task/template identifier.
        payload_fn (callable): Payload builder following the unified
            signature (entry, inputs, role, input_copy, api) -> dict.
        biospecimen (str): Biospecimen name used when creating the task.
        api: Backend API client.

    Returns:
        str: Task ID of the existing or newly created task.
    """
    node = entry[step] if role is None else entry[step][role]

    if node.get("task_id"):
        return node["task_id"]

    logging.info(f"[{run_id}] Creating {step} task ({role or 'single'})")
    draft = get_task(api, draft_task_id)
    input_copy = copy_inputs(draft, api)

    payload = payload_fn(
        entry=entry,
        inputs=node.get("inputs", {}),
        role=role,
        input_copy=input_copy,
        api=api,
    )

    task_id = create_task(biospecimen, payload, draft, api)
    node["task_id"] = task_id
    return task_id

def resolve_sb_files(x, api):
    if isinstance(x, list): return [resolve_sb_files(v, api) for v in x]
    if isinstance(x, dict):
        if x.get("class") == "File":
            p = x.get("path")
            return get_file(api, p) if isinstance(p, str) else x
        return {k: resolve_sb_files(v, api) for k, v in x.items()}
    return x

def copy_inputs(draft_task, api) -> dict:
    incopy = copy.deepcopy(draft_task.inputs.copy())
    for key, value in incopy.items():
        incopy[key] = resolve_sb_files(value, api)
    return incopy

def create_task(prefix, payload, draft_task, api) -> str:
    if getattr(api, "_dry_run", False):
        logging.info(f"[DRY RUN] Would create task {get_app(api, draft_task.app).name} with: {prefix=}")
        return "DRY_RUN_TASK_ID"
    task = api.tasks.create(
        name=f"{prefix} {get_app(api, draft_task.app).name} {time.strftime('%Y%m%d_%H%M%S')}",
        project=draft_task.project,
        app=draft_task.app,
        inputs=payload,
        run=False
    )
    return task.id

def handle_downsample(run_id, entry, api, args):
    ensure_step_struct(entry, "downsample", ["tumor", "normal"])
    ensure_step_struct(entry, "align", ["tumor", "normal"])

    tumor_task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="downsample",
        role="tumor",
        draft_task_id=args.downsample_draft_task,
        payload_fn=create_downsample_payload,
        biospecimen=entry["tumor_biospecimen"],
        api=api,
    )

    normal_task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="downsample",
        role="normal",
        draft_task_id=args.downsample_draft_task,
        payload_fn=create_downsample_payload,
        biospecimen=entry["normal_biospecimen"],
        api=api,
    )

    tumor_task = get_task(api, tumor_task_id)
    normal_task = get_task(api, normal_task_id)

    if tumor_task.status == normal_task.status == TASK_DONE:
        logging.info(f"[{run_id}] Downsample completed → align")

        entry["align"]["tumor"]["inputs"]["input_bam_list"] = [
            tumor_task.outputs["output"]["path"]
        ]
        entry["align"]["normal"]["inputs"]["input_bam_list"] = [
            normal_task.outputs["output"]["path"]
        ]
        return None

    logging.info(
        f"[{run_id}] Waiting on downsample: "
        f"tumor={tumor_task.status}, normal={normal_task.status}"
    )
    return "downsample"

def handle_align(run_id, entry, api, args):
    ensure_step_struct(entry, "align", ["tumor", "normal"])
    ensure_step_struct(entry, "somatic")

    tumor_task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="align",
        role="tumor",
        draft_task_id=args.alignment_draft_task,
        payload_fn=create_align_payload,
        biospecimen=entry["tumor_biospecimen"],
        api=api,
    )

    normal_task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="align",
        role="normal",
        draft_task_id=args.alignment_draft_task,
        payload_fn=create_align_payload,
        biospecimen=entry["normal_biospecimen"],
        api=api,
    )

    tumor_task = get_task(api, tumor_task_id)
    normal_task = get_task(api, normal_task_id)

    if tumor_task.status == normal_task.status == TASK_DONE:
        logging.info(f"[{run_id}] Align completed → somatic")

        entry["somatic"]["inputs"] = {
            "input_tumor_aligned": tumor_task.outputs["cram"]["path"],
            "input_normal_aligned": normal_task.outputs["cram"]["path"],
        }
        entry["align_type"] = "BWA"
        return None

    logging.info(
        f"[{run_id}] Waiting on align: "
        f"tumor={tumor_task.status}, normal={normal_task.status}"
    )
    return "align"

def handle_somatic(run_id, entry, api, args):
    ensure_step_struct(entry, "somatic")
    ensure_step_struct(entry, "consensus")

    task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="somatic",
        role=None,
        draft_task_id=args.somatic_draft_task,
        payload_fn=create_somatic_payload,
        biospecimen=entry["tumor_biospecimen"],
        api=api,
    )

    task = get_task(api, task_id)

    if task.status != TASK_DONE:
        logging.info(f"[{run_id}] Waiting on somatic: {task.status}")
        return "somatic"

    def pick_vcf(outputs):
        return next(
            o["path"]
            for o in outputs
            if o.get("basename", "").endswith("vcf.gz")
        )

    entry["consensus"]["inputs"] = {
        "lancet_vcf": pick_vcf(task.outputs["lancet_protected_outputs"]),
        "mutect2_vcf": pick_vcf(task.outputs["mutect2_protected_outputs"]),
        "strelka2_vcf": pick_vcf(task.outputs["strelka2_protected_outputs"]),
        "vardict_vcf": pick_vcf(task.outputs["vardict_protected_outputs"]),
        "cram": task.inputs["input_tumor_aligned"]["path"],
    }
    entry["somatic_type"] = "KFsomatic"

    logging.info(f"[{run_id}] Somatic completed → consensus")
    return None

def handle_consensus(run_id, entry, api, args):
    ensure_step_struct(entry, "consensus")

    task_id = ensure_task(
        run_id=run_id,
        entry=entry,
        step="consensus",
        role=None,
        draft_task_id=args.consensus_draft_task,
        payload_fn=create_consensus_payload,
        biospecimen=entry["tumor_biospecimen"],
        api=api,
    )

    task = get_task(api, task_id)

    if task.status != TASK_DONE:
        logging.info(f"[{run_id}] Waiting on consensus: {task.status}")
        return "consensus"

    entry["call_vcf"] = next(
        o["path"]
        for o in task.outputs["annotated_protected_outputs"]
        if o.get("basename", "").endswith("vcf.gz")
    )

    logging.info(f"[{run_id}] Consensus completed → benchmark")
    return None

def handle_benchmark(run_id, *_):
    logging.info(f"[{run_id}] Ready for benchmarking.")
    return "benchmark"

def handle_benchmark_aggregate(status, api, args):
    """
    Runs once when all runs are ready for benchmarking.
    Groups entries by (tumor_biospecimen, truth_vcf)
    and launches benchmark tasks.
    """
    groups = {}

    for entry in status.values():
        key = (
            entry["tumor_biospecimen"],
            entry["truth_vcf"],
        )
        groups.setdefault(key, []).append(entry)

    for group_key, entries in groups.items():
        tumor, truth_vcf = group_key
        task_key = f"{tumor}-{truth_vcf}"

        # Idempotence: store benchmark task IDs at top-level
        bench_tasks = status.setdefault("_benchmark_tasks", {})
        if task_key in bench_tasks:
            continue

        logging.info(
            f"[benchmark] Creating benchmark task for "
            f"tumor={tumor}, truth={truth_vcf}"
        )

        draft = get_task(api, args.benchmark_draft_task)
        input_copy = copy_inputs(draft, api)

        payload = create_benchmark_payload(
            group_key=group_key,
            grouped_entries=entries,
            input_copy=input_copy,
            api=api,
        )

        task_id = create_task(
            prefix=f"benchmark {tumor}",
            payload=payload,
            draft_task=draft,
            api=api,
        )

        bench_tasks[task_key] = task_id


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--manifest",  help="Manifest to create the status JSON")
    parser.add_argument("--status", help="Status JSON file to orchestrate benchmarking")
    parser.add_argument("--downsample_draft_task", default="c9513481-d896-4390-8cef-23ef1c9a8a58", help="Downsample draft task to use for task creation")
    parser.add_argument("--alignment_draft_task", default="0b04b976-6aea-47e6-8657-887eb7866fe2", help="Alignment draft task to use for task creation")
    parser.add_argument("--somatic_draft_task", default="779b6ede-9c5d-473c-9f47-348852712c8e", help="Somatic draft task to use for task creation")
    parser.add_argument("--consensus_draft_task", default="03afd8ee-cae7-4f8d-ba5e-6798f1df3cfb", help="Consensus draft task to use for task creation")
    parser.add_argument("--benchmark_draft_task", default="f4d1048e-45ad-4548-aea1-f9378069b06f", help="Benchmark draft task to use for task creation")
    parser.add_argument("--api_profile", default="cavatica", help="Name of profile to access SBG")
    parser.add_argument("--dry_run", action="store_true", help="Do not draft task. Only dump input JSON")
    args = parser.parse_args()

    if not (args.manifest or args.status):
        parser.error("One of --manifest or --status must be set")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="benchmark.log", filemode="a")

    c = sbg.Config(profile=args.api_profile)
    api = sbg.Api(config=c, error_handlers=[rate_limit_sleeper, maintenance_sleeper])
    api._dry_run = args.dry_run

    if args.manifest:
        logging.info(f"Processing manifest {args.manifest}...")
        manifest = tsv_to_manifest_json(args.manifest)
        try:
            validate_required_fields(manifest)
            validate_manifest_files(manifest, api)
        except ManifestValidationError as e:
            logging.error(e)
            sys.exit(1)
        # Now that we've validated the manifest, we can replace the row_num keys with run_id keys for easier orchestration in the next steps
        new_manifest = {}
        for row_num, entry in manifest.items():
            run_id = entry["run_id"]
            if run_id in new_manifest:
                logging.error(f"Duplicate run_id {run_id}")
                sys.exit(1)
            new_manifest[run_id] = entry

        manifest = new_manifest
        with open(f"status.json", "w") as f:
            logging.info(f"Saving initial status to status.json...")
            print(json.dumps(manifest, indent=2), file=f)
        return

    with open(args.status, 'r') as f:
        status = json.load(f)

    STEP_HANDLERS = {
        "downsample": handle_downsample,
        "align": handle_align,
        "somatic": handle_somatic,
        "consensus": handle_consensus,
        "benchmark": handle_benchmark,
    }
    NEXT_STEP = {
        "downsample": "align",
        "align": "somatic",
        "somatic": "consensus",
        "consensus": "benchmark",
        "benchmark": "benchmark",
    }

    VALID_STEPS = set(NEXT_STEP)

    for run_id, entry in status.items():
        entry.setdefault("current_step", entry.get("start_from"))
        step = entry["current_step"]

        logging.info(f"[{run_id}] Current step: {step}")
        handler = STEP_HANDLERS.get(step)
        if not handler:
            logging.error(f"[{run_id}] No handler defined for step: {step}")
            sys.exit(1)

        result = handler(run_id, entry, api, args)

        if result is None:
            entry["current_step"] = NEXT_STEP[step]
        else:
            entry["current_step"] = result

        if entry["current_step"] not in VALID_STEPS:
            logging.error(f"[{run_id}] Invalid workflow step: {entry['current_step']}")
            sys.exit(1)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    with open(f"status_{timestamp}.json", "w") as f:
        logging.info(f"Saving updated status to status_{timestamp}.json...")
        print(json.dumps(status, indent=2), file=f)

    logging.info(f"Checking to see if all runs are ready for benchmarking...")
    all_ready = all(
        entry.get("current_step") == "benchmark"
        for entry in status.values()
    )

    if all_ready:
        logging.info("All runs ready → launching benchmark aggregation")
        handle_benchmark_aggregate(status, api, args)
    else:
        logging.info("Not all runs are ready for benchmarking yet. Wait for tasks to complete and re-run the orchestrator.")

if __name__ == "__main__":
    main()