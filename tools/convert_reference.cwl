cwlVersion: v1.2
class: CommandLineTool
id: convert_reference
label: convert_reference_SDF
doc: converts reference from fasta to SDF required for rtg
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: pgc-images.sbgenomics.com/d3b-bixu/tumor-only-benchmarking:1.0.0
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: 4
  ramMin: 8
baseCommand: [ rtg ]
arguments:
- position: 1
  valueFrom: >-
    format -o human_ref $(inputs.ref_file.path)	
  shellQuote: false   

inputs:
 ref_file: { doc: provide popmax cutoff for rare disease, type: File }
 
outputs:
 ref_SDF:
  type: Directory
  outputBinding:
   glob: "human_ref"
  doc: Fasta file converted to SDF format
