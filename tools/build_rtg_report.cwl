cwlVersion: v1.2
class: CommandLineTool
id: build_rtg_report
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: pgc-images.sbgenomics.com/danmiller/python3.13-lancet:0.0.1
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: $(inputs.cpu)
  ramMin: $(inputs.ram * 1000)
- class: InitialWorkDirRequirement
  listing:
  - entryname: build_rtg_report.py
    entry:
      $include: ../scripts/build_rtg_report.py
baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    python build_rtg_report.py

inputs:
  call_vcf: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 2, prefix: "--call_vcf" }, doc: "Call VCF produced by rtg vcfeval" }
  baseline_vcf: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 2, prefix: "--baseline_vcf" }, doc: "Baseline VCF produced by rtg vcfeval" }
  sample_name: { type: "string", inputBinding: { position: 2, prefix: "--sample_name" }, doc: "Name of sample being benchmarked." }
  tool_name: { type: "string", inputBinding: { position: 2, prefix: "--tool_name" }, doc: "Name of tool being processed for the benchmarking report." }
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
 
outputs:
  report:
    type: File
    outputBinding:
      glob: "*.tsv"
