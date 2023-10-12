cwlVersion: v1.2
class: CommandLineTool
id: run_rtg
label: run_rtg_tool
doc: This tools maps test files with consensus and runs rtg for samples within test_folder
requirements:
- class: ShellCommandRequirement
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: ${ return inputs.cores }
  ramMin: ${ return inputs.ram * 1000 } 
- class: InitialWorkDirRequirement
  listing:
  - entryname: run_RTG_python
    entry:
      $include: ../scripts/run_RTG.py
  - entryname: input_test_folder
    entry: $(inputs.test_folder)
    writable: true
  - entryname: consensus_folder
    entry: $(inputs.consensus_folder_path)
    writable: true 
hints:  
  DockerRequirement:  
    dockerPull: pgc-images.sbgenomics.com/d3b-bixu/tumor-only-benchmarking:1.0.0
  EnvVarRequirement:
      envDef:
        TMPDIR: "/tmp"    

baseCommand: [ python3.11 ]
arguments:
- position: 1
  valueFrom: >-
    run_RTG_python	
  shellQuote: false      

inputs: 
  test_folder: { doc: provide folder containing test vcf file with index files, type: Directory, inputBinding: { prefix: --test_folder_path, position: 2} }
  consensus_folder_path: { doc: provide folder containing consensus vcf file with index files, type: Directory, inputBinding: { prefix: --consensus_folder_path, position: 2 }  }
  ref_folder: { doc: provide reference file in fasta format, type: 'Directory?', inputBinding: { prefix: --ref_folder_sdf, position: 2 }  }
  ram: { doc: provide ram (in GB) based on number of test files, type: 'int?', default: 8 } 
  filter_string: { doc: provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, type: 'string?', default: '', inputBinding: { prefix: --filter, position: 2 } }
  output_file_name: { doc: provide output file name, type: string, inputBinding: { prefix: --output_file_name, position: 2 } }
  cores: { doc: provide cores to run samples in multiprocessing, type: 'int?', default: 8,inputBinding: { prefix: --worker, position: 2 } }

outputs:
   output_tsv:
    type: File
    outputBinding:
     glob: $(inputs.output_file_name).tsv
    doc: benchmarking output in tsv format
   output_mean:
    type: File
    outputBinding:
     glob: $(inputs.output_file_name)_mean.tsv
    doc: mean benchmarking output for all the samples found in tsv format 
   results_dir:
    type: Directory
    outputBinding:
      glob: "*_results_rtg"
    doc: directory containing output for all the samples from RTG
   filter_folder:
    type: 'Directory?'
    outputBinding:
      glob: "filtered_vcfs"
    doc: directory containing filter vcf files