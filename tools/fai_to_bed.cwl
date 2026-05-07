cwlVersion: v1.2
class: CommandLineTool
id: fai_to_bed
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: ubuntu:22.04
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: $(inputs.cpu)
  ramMin: $(inputs.ram * 1000)
baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    awk 'BEGIN{FS=OFS="\t"} {print $1, 0, $2}' $(inputs.fai.path) > fai.bed

inputs:
  fai: { type: "File" }
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
 
outputs:
  bed:
    type: File
    outputBinding:
      glob: "*.bed"
