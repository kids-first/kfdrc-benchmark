cwlVersion: v1.2
class: CommandLineTool
id: rtg_format
doc: converts reference to SDF required for rtg
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: pgc-images.sbgenomics.com/danmiller/rtg-core:3.13
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: $(inputs.cpu)
  ramMin: $(inputs.ram * 1000)
baseCommand: []
arguments:
- position: 1
  shellQuote: false
  valueFrom: >-
    outdir=$(inputs.tool_name)
    && rtg vcfeval -o $outdir --sample $(inputs.baseline_sample),$(inputs.calls_sample)
- position: 10
  shellQuote: false   
  valueFrom: >-
    && find $outdir -type f -name '*.vcf.gz*' -exec bash -c '
    for f do
      d=\$(basename "\$(dirname "$f")")
      b=\$(basename "$f")
      mv -n -- "$f" "\$(dirname "\$(dirname "$f")")/\${d}_\${b}"
    done
    ' bash {} +
    

inputs:
  template: { type: "Directory", inputBinding: { position: 2, prefix: "--template" }, doc: "Reference to convert to SDF" }
  baseline: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 2, prefix: "--baseline" }, doc: "VCF file containing baseline variants" }
  calls: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 2, prefix: "--calls" }, doc: "VCF file containing called variants" }
  bed_regions: { type: "File?", inputBinding: { position: 2, prefix: "--bed-regions" }, doc: "if set, only read VCF records that overlap the ranges contained in the specified BED file" }
  evaluation_regions: { type: "File?", inputBinding: { position: 2, prefix: "--evaluation-regions" }, doc: "if set, evaluate within regions contained in the supplied BED file, allowing transborder matches. To be used for truth-set high-confidence regions or other regions of interest where region boundary effects should be minimized" }
  
  tool_name: { type: "string" }
  baseline_sample: { type: "string" }
  calls_sample: { type: "string" }
  extra_args: { type: "string?", inputBinding: { position: 2, shellQuote: false }}
  cpu: { type: "int?", default: 1, inputBinding: { position: 2, prefix: "--threads" }}
  ram: { type: "int?", default: 8 }
 
outputs:
  baseline_vcf:
    type: 'File?'
    secondaryFiles: [{pattern: ".tbi", required: true}]
    outputBinding:
      glob: "*baseline.vcf.gz"
  calls_vcf:
    type: 'File?'
    secondaryFiles: [{pattern: ".tbi", required: true}]
    outputBinding:
      glob: "*calls.vcf.gz"
  combined:
    type: 'File?'
    outputBinding:
      glob: "*_weighted_roc.tsv.gz"
  indel:
    type: 'File?'
    outputBinding:
      glob: "*_indel_roc.tsv.gz"
  snp:
    type: 'File?'
    outputBinding:
      glob: "*_snp_roc.tsv.gz"
