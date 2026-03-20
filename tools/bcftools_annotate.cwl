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
baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    bcftools annotate -Oz --write-index=tbi

inputs:
  vcf: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 9 }}
  annotations: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}], inputBinding: { position: 2, prefix: "--annotations" } }
  output_filename: { type: "string", inputBinding: { position: 2, prefix: "--output" } }
  extra_args: { type: "string?", inputBinding: { position: 2, shellQuote: false } }
  cpu: { type: "int?", default: 1, inputBinding: { position: 2, prefix: "--threads" }}
  ram: { type: "int?", default: 2 }
 
outputs:
  annotated:
    type: File
    secondaryFiles: [{pattern: ".tbi", required: true}]
    outputBinding:
      glob: "*.vcf.gz"
