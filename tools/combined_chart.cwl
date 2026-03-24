cwlVersion: v1.2
class: CommandLineTool
id: combined_chart
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
  - entryname: combined_chart.py
    entry:
      $include: ../scripts/combined_chart.py
baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    echo "$(inputs.parquets.map( function(e) { return e.path }).join(' '))" | xargs -n 1 tar xf
- position: 10
  shellQuote: false   
  valueFrom: >-
    && python combined_chart.py --brotli_dirs *brotli --output_basename $(inputs.output_basename)
inputs:
  parquets:  { type: "File[]", doc: "TAR files containing brotli_dirs" }
  output_basename: { type: "string", doc: "Basename for output files" }
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
outputs:
  html:
    type: File[]
    outputBinding:
      glob: "*.html"
