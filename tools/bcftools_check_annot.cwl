cwlVersion: v1.2
class: CommandLineTool
id: bcftools_annotate
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: staphb/bcftools:1.20
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: $(inputs.cpu)
  ramMin: $(inputs.ram * 1000)
- class: InitialWorkDirRequirement
  listing:
  - entryname: annotate.sh
    entry: |
      #!/usr/bin/env bash
      set -xeuo pipefail
      
      # If the INFO tag is NOT defined in the VCF header, run annotation; otherwise just copy through.
      if bcftools view -h $(inputs.vcf.path) | grep -qE "^##INFO=<ID=STRATIFICATIONS"; then
        cp $(inputs.vcf.path)* . 
      else
        bcftools annotate --write-index=tbi --annotations $(inputs.annotations.path) --merge-logic STRATIFICATIONS:unique --columns CHROM,FROM,TO,STRATIFICATIONS --header-line '##INFO=<ID=STRATIFICATIONS,Number=.,Type=String,Description="GIAB stratifications">' -Oz -o $(inputs.vcf.basename.replace(/vcf.gz$/, "checked.vcf.gz")) $(inputs.vcf.path)
      fi

baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    /bin/bash annotate.sh

inputs:
  vcf: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}]}
  annotations: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}]}
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
 
outputs:
  checked:
    type: File
    secondaryFiles: [{pattern: ".tbi", required: true}]
    outputBinding:
      glob: "*.vcf.gz"
