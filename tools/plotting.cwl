cwlVersion: v1.2
class: CommandLineTool
id: plot_tp_fp
label: bar plot for tp and fp 
doc: This tools maps test files with consensus and runs rtg for samples within test_folder
requirements:
- class: ShellCommandRequirement
- class: InlineJavascriptRequirement 
- class: InitialWorkDirRequirement
  listing:
  - entryname: run_plot
    entry:
      $include: ../scripts/plot_tp_fp.py
hints: 
    DockerRequirement:  
        dockerPull: pgc-images.sbgenomics.com/d3b-bixu/tumor-only-benchmarking:1.0.0
baseCommand: [ python3.11 ]
arguments:
- position: 1
  valueFrom: >-
    run_plot	
  shellQuote: false 

inputs:
    input_folder: { doc: provide RTG folder, type: Directory, inputBinding: { prefix: --input_folder, position: 2} }
    filter_string: { doc: provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, type: 'string?', default: '%DP', inputBinding: { prefix: --filter, position: 2 } }

outputs:
   tp_png:
    type: File
    outputBinding:
     glob: tp.png
    doc: Bar plot for TPs 
   fp_png:
    type: File
    outputBinding:
     glob: fp.png
    doc: Bar plot for FPs 