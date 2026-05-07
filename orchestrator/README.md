# Benchmarking Assistant

This script is a stateful workflow orchestrator for running tumor/normal variant‑calling pipelines on Seven Bridges and then benchmarking the resulting callsets in an aggregated, biologically meaningful way. It consumes a TSV manifest describing paired tumor/normal samples and their desired starting point, validates all required inputs and file references, and materializes a structured JSON “status” document that tracks progress. Each run advances deterministically through the pipeline stages—downsample, align, somatic, consensus, and benchmark—with idempotent task creation, explicit step transitions, robust validation, and aggressive caching of files, tasks, and apps to minimize API calls. The workflow is resumable: re‑running the script safely reconciles existing task state and continues only where work remains.

Once all individual runs reach the per‑sample benchmark‑ready state, the script performs a final global fan‑in benchmarking step. In this stage, it groups all runs by (tumor_biospecimen, truth_vcf) and submits one benchmark task per group. Each benchmark task compares multiple callsets—collected across different align_type and somatic_type combinations—against a shared truth set, passing the aligned list of call VCFs and tool identifiers as a single aggregated payload. This design ensures biologically coherent benchmarking, avoids duplicate submissions, and produces reproducible, centralized benchmark results. Overall, the script provides a reliable, efficient, and auditable end‑to‑end orchestration layer from raw inputs through aggregated performance evaluation.

## Modes

The script operates in one of two modes, depending on which input argument is provided.

### Manifest Processing Mode

Used to validate a TSV manifest and generate an initial status JSON.

```
python orchestrate.py --manifest input.tsv
```

This mode:

- Parses the TSV manifest
- Validates required fields and file references
- Builds an internal workflow state for each row
- Writes an initial status.json file
- Does not submit tasks

This is always the first step when starting from a TSV.

#### Manifest Example

The below TSV illustrates how to structure the rows for the different starting points of the workflow. Each row in the TSV represents a single logical run for a tumor/normal pair, but the start_from column tells the script where in the pipeline that run should enter. The manifest supports **mixed workflow entry points**; different rows may start at different stages.

```
tumor_biospecimen	normal_biospecimen	truth_vcf_fileId	start_from	tumor_bam	normal_bam	alignment_type	somatic_type	call_vcf
SPP_GT_3-1	SPP_GT_0-1	69c15af5f4fec601ac2e488f	downsample	https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/seqc/Somatic_Mutation_WG/data/SPP/80X/SPP_GT_3-1_1.bwa.dedup.s0.8.bam	https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/seqc/Somatic_Mutation_WG/data/SPP/30X/SPP_GT_0-1_1.bwa.dedup.s0.3.bam
SPP_GT_3-1	SPP_GT_0-1	69c15af5f4fec601ac2e488f	align	69aa16a5ec41af30b9d16193	69a9b6d155b9050ca7234578
SPP_GT_3-1	SPP_GT_0-1	69c15af5f4fec601ac2e488f	somatic	69ab67568a51980591564924	69aa6f5455b9050ca7248490	BWA
SPP_GT_3-1	SPP_GT_0-1	69c15af5f4fec601ac2e488f	benchmark			BWA	KFsomatic	69aefa11ec41af30b9e77efa
```

The first row for SPP_GT_3-1 / SPP_GT_0-1 starts from downsample, providing public BAM URLs for both tumor and normal. When the script parses this row, it initializes a full workflow entry and populates the downsample inputs with those URLs. Subsequent orchestration runs will create and monitor downsampling tasks, automatically feeding their outputs into alignment once complete.

The second and third rows for the same tumor/normal pair demonstrate how the script allows later-stage re‑entry using existing artifacts instead of recomputing earlier steps. The align row supplies Seven Bridges file IDs for BAMs that are already aligned, so the script skips downsampling entirely and begins alignment directly. Likewise, the somatic row starts at somatic calling using pre‑aligned tumor and normal CRAM/BAM file IDs and an explicitly declared alignment_type (BWA). In each case, validation logic ensures that the required inputs for that starting point are present, and the orchestration logic treats these runs independently while preserving consistent metadata such as tumor/normal biospecimen names and truth set references.

The final row illustrates a different interaction pattern: it starts at benchmark. This row assumes that all upstream analysis has already completed and provides a call_vcf produced by a known (alignment_type, somatic_type) combination (BWA/KFsomatic). The script does not schedule any per‑sample computation for this row; instead, it marks the run as benchmark‑ready and captures the callset metadata. When all runs in the status file reach the benchmark step, the script performs a global aggregation phase. At that point, it groups runs by (tumor_biospecimen, truth_vcf)—so all callsets for SPP_GT_3-1 against the same truth VCF are combined—and submits one benchmark task per group. Each benchmark task compares multiple call VCFs simultaneously, labeling them with their corresponding align_type–somatic_type identifiers. This design allows different rows in the TSV to start at different pipeline stages while still contributing coherently to a single, biologically meaningful benchmarking analysis at the end.

#### Manifest Field Reference

Each row in the manifest represents one **logical run** for a tumor/normal pair.  
The `start_from` field determines which subset of fields must be present and where the run enters the workflow.

| Field name | Type | Required when | Description |
|----------|------|---------------|-------------|
| `tumor_biospecimen` | string | **Always** | Identifier for the tumor sample. Used for task naming, grouping runs, and benchmarking aggregation. |
| `normal_biospecimen` | string | **Always** | Identifier for the matched normal sample. Used for alignment and somatic calling. |
| `truth_vcf_fileid` | Seven Bridges file ID | **Always** | File ID for the truth VCF used as the baseline in benchmarking. Runs sharing the same tumor and truth VCF are grouped into the same benchmark task. |
| `start_from` | string | **Always** | Specifies the workflow entry point. Must be one of: `downsample`, `align`, `somatic`, or `benchmark`. |
| `tumor_bam` | URL or file ID | `downsample`, `align`, `somatic` | Meaning depends on `start_from`:<br>• `downsample`: URL to a raw tumor BAM<br>• `align`: Seven Bridges file ID of an unaligned or preprocessed BAM<br>• `somatic`: File ID of an aligned tumor BAM/CRAM |
| `normal_bam` | URL or file ID | `downsample`, `align`, `somatic` | Same semantics as `tumor_bam`, but for the normal sample. |
| `alignment_type` | string | `somatic`, `benchmark` | Label describing the aligner used (e.g. `BWA`). Used for metadata tracking and benchmark tool naming. |
| `somatic_type` | string | `benchmark` | Label describing the somatic calling approach (e.g. `KFsomatic`). Combined with `alignment_type` to form benchmark tool names. |
| `call_vcf_fileid` | Seven Bridges file ID | `benchmark` | File ID of the final callset VCF to be benchmarked against the truth set. |
| `run_id` *(derived)* | string | — | Not provided in the TSV. The script derives this value from `tumor_biospecimen`, `normal_biospecimen`, `alignment_type`, and `somatic_type` to uniquely identify each run in the status JSON. |

### Orchestration/Resume Mode

Used to execute or resume workflow tasks based on an existing status file.

```
python orchestrate.py --status status.json
```

This mode:

- Reads the current workflow state
- Submits missing tasks
- Monitors task completion
- Advances runs through workflow stages
- Writes a timestamped updated status file
- Automatically launches aggregated benchmarking when all runs are ready

This command can be safely re‑run periodically until all work is complete.

#### Draft Task Options

The script uses Seven Bridges draft task IDs to define what application to run and how it should be configured for each workflow stage. A draft task on Seven Bridges is a saved task template that already points to a specific app, project, and baseline configuration. These can point to tasks on Seven Bridges that have been previously run or are still in the DRAFT state. The script clones these templates, injects dynamically built inputs, and creates new runnable tasks from them.

If you are in a fresh project that does not have any of these tasks, you will first need to add the apps to your project and create draft tasks. 

```
--downsample_draft_task <Task ID for downsampling>
--alignment_draft_task <Task ID for alignment>
--somatic_draft_task <Task ID for somatic calling>
--consensus_draft_task <Task ID for consensus generation>
--benchmark_draft_task <Task ID for benchmarking>
```

## Manual Intervention

At the moment the script does not handle processes that fail. If one of the tasks started by the orchestrator experiences a failure, you will need to manually adjust and restart the task. Once you've done that you'll also need to update the status JSON so that it can find the new tasks. Locate the affected run in the status JSON and update the corresponding step’s task_id to the new task ID created by the manual restart. Do not change the current_step unless you are intentionally re‑running or skipping a stage; in most cases, leaving current_step unchanged allows the script to re‑poll task status and advance naturally once completion is detected. After saving the updated status file, rerun the script with --status; it will reconcile the new task state, avoid re‑submission, and continue orchestration from the correct point.

If the failure is sufficiently catastrophic, make a new manifest detailing, for each row, the last point at which you feel comfortable with the results. Perform conversion using --manifest then continue using --status.
