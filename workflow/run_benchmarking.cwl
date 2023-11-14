cwlVersion: v1.2
class: Workflow
id: run_benchmarking
doc: This CWL workflow convert fasta to SDF and can filter based on filter string to run RTG over all the sample vcf provide in test_folder using consensus folder. It can also plot different filters(optional) 
requirements:
- class: StepInputExpressionRequirement
- class: InlineJavascriptRequirement 
inputs:
#rtg tool
  test_folder: { doc: provide folder containing test vcf file with index files, type: Directory}
  gold_standard_folder_path: { doc: provide folder containing consensus vcf file with index files, type: Directory }
  ref_file: { doc: provide reference file in fasta format, type: 'File?' }
  ram: { doc: provide ram (in GB) based on number of test files, type: 'int?', default: 14 } 
  output_file_name: { doc: provide output file name, type: string }
  filter_string: { doc: (optional) provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, type: 'string?', default: '' }
  cores: { doc: provide cores to run samples in multiprocessing, type: 'int?', default: 8 }

#plotting
  disable_plotting: {type: boolean, default: True, doc: "Set to true to disable plotting tool" }
  plot_feature: { doc: provide bcftool format like filter_string example- %DP, type: 'string?', default: '%DP' }
  sample_manifest: { doc: provide sample with experimental strategy, type: 'File?' }
  plot_start: { doc: start point for the plot, default: "0", type: 'string' }
  plot_end: { doc: cut point for the plot, default: "1", type: 'string' }
  plot_bin_size: { doc: bin size for the plot, default: "0.1", type: 'string' }
  filter_name: { doc: provide filter name, type: 'string?',default: "filter" }

outputs:
 benchmarking_tsv: { type: File, doc: benchmarking output in tsv format, outputSource: run_RTG/output_tsv }
 average_result: { type: File, doc: average benchmarking results , outputSource: run_RTG/output_mean }
 rtg_results: { type: Directory, doc: directory containing output for all the samples from RTG, outputSource: run_RTG/results_dir }
 plot_WGS: { type: 'File?', doc: plot for WGS samples , outputSource: plots/WGS_png}
 plot_WXS: { type: 'File?', doc: plot for WXS samples, outputSource: plots/WXS_png }
 
 
steps:
 convert_reference:
    run: ../tools/convert_reference.cwl
    in:
       ref_file: ref_file
    out:
       [ ref_SDF ]
 run_RTG:
    run: ../tools/run_rtg.cwl
    in:
       test_folder: test_folder
       ref_folder: convert_reference/ref_SDF
       gold_standard_folder_path_tool: gold_standard_folder_path
       filter_string: filter_string
       output_file_name: output_file_name
       ram: ram
       cores: cores
    out:
       [ output_tsv, output_mean, results_dir, filter_folder]  
 plots:
    run: ../tools/plotting.cwl
    when : $(inputs.disable_tool != true)
    in:
      disable_tool: disable_plotting
      input_folder: run_RTG/results_dir
      filter_string: plot_feature
      sample_manifest: sample_manifest 
      plot_start_tool: plot_start
      plot_end_tool: plot_end
      plot_bin_size_tool: plot_bin_size
      plot_name: output_file_name
      filter_name: filter_name
    out: [WGS_png,WXS_png]             

