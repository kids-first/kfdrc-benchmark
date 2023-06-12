cwlVersion: v1.2
class: Workflow
id: run_benchmarking
doc: This CWL workflow convert fasta to SDF and runs RTG over all the sample vcf provide in test_folder using consensus folder
requirements:
- class: StepInputExpressionRequirement
- class: InlineJavascriptRequirement 
inputs:
  test_folder: { doc: provide folder containing test vcf file with index files, type: Directory}
  consensus_folder_path: { doc: provide folder containing consensus vcf file with index files, type: Directory }
  ref_file: { doc: provide reference file in fasta format, type: 'File?' }
  ram: { doc: provide ram (in GB) based on number of test files, type: 'int?', default: 7 } 
  output_file_name: { doc: provide output file name, type: string }
  cores: { doc: provide cores to run samples in multiprocessing, type: 'int?', default: 8 }
outputs:
 benchmarking_tsv: { type: File, doc: benchmarking output in tsv format, outputSource: run_RTG/output_tsv }
 net_result: { type: File, doc: average benchmarking results , outputSource: run_RTG/output_mean }
 rtg_results: { type: Directory, doc: directory containing output for all the samples from RTG, outputSource: run_RTG/results_dir }

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
       consensus_folder_path: consensus_folder_path
       output_file_name: output_file_name
       ram: ram
       cores: cores
    out:
       [ output_tsv, output_mean, results_dir]          

