cwlVersion: v1.2
class: CommandLineTool
id: plot_tp_fp
label: bar_plots 
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
    filter_string: { doc: provide filter string for this bcftool cmd-> "bcftools query -f'your string'" Example- "%DP" or "%AD(curly brackets)1/%DP" for vaf %AF %GERMQ , type: 'string?', default: '%DP', inputBinding: { prefix: --filter, position: 2 } }
    sample_manifest: { doc: provide sample with experimental strategy, type: File, inputBinding: { prefix: --sample_manifest, position: 2} }
    plot_name: { doc: provide output file name, type: string, inputBinding: { prefix: --output_file_name, position: 2 } }
    plot_start_tool: { doc: start point for the plot, type: 'string',inputBinding: { prefix: --plot_start, position: 2 } }
    plot_end_tool: { doc: end point for the plot, type: 'string', inputBinding: { prefix: --plot_end, position: 2 } }
    plot_bin_size_tool: { doc: bin size for the plot, type: 'string', inputBinding: { prefix: --plot_bin_size, position: 2 } }
    filter_name: { doc: provide filter name, type: 'string?',default: "filter", inputBinding: { prefix: --filtername, position: 2 } }

outputs:
   WGS_png:
    type: File
    outputBinding:
     glob: "*.WGS.png"
    doc: Bar plot for TPs 
   WXS_png:
    type: File
    outputBinding:
     glob: "*.WXS.png"
    doc: Bar plot for FPs 