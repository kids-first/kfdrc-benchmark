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
    rtg format
    -o $(inputs.output_name ? inputs.output_name : inputs.reference.nameroot)


inputs:
  reference: { type: "File", inputBinding: { position: 9 }, doc: "Reference to convert to SDF" }
  output_name: { type: "string?", doc: "Name for SDF directory"}
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
 
outputs:
  sdf:
    type: Directory
    outputBinding:
      glob: "$(inputs.output_name ? inputs.output_name : inputs.reference.nameroot)"
    doc: Reference SDF 
