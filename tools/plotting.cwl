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
    #just kill switch to connect the graph
    disable_tool: {type: 'boolean', doc: "bring it here to connect graph"}

    input_folder: { doc: provide RTG folder, type: Directory, inputBinding: { prefix: --input_folder, position: 2} }
    filter_string: { doc: provide filter string for this bcftool cmd-> "bcftools query -f'{your string}'" Example- "%DP" or "%AD{1}/%DP" for vaf,%AF,%GERMQ , type: 'string?', default: '%DP', inputBinding: { prefix: --filter, position: 2 } }
    sample_manifest: { doc: provide sample with experimental strategy, type: File, inputBinding: { prefix: --sample_manifest, position: 2} }
    output_file_name: { doc: provide output file name, type: string, inputBinding: { prefix: --output_file_name, position: 2 } }
    range: {doc: Provide start end and bin size in the same order Example- 0 200 10 for depth, type: 'string[]', inputBinding: { prefix: --interval_list, position: 2} }

outputs:
   WGS_png:
    type: File
    outputBinding:
     glob: $(inputs.output_file_name).WGS.png
    doc: Bar plot for TPs 
   WXS_png:
    type: File
    outputBinding:
     glob: $(inputs.output_file_name).WXS.png
    doc: Bar plot for FPs 