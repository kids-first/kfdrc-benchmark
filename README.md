# D3b Bixu VCF benchmarking workflow

Benchmarking workflow computes confusion matrix with f1 score for target VCFs using provided gold standard VCF files. It can also filter calls by providing bcftool like string (Ex `DP > 10`). Additionally, it can prepare stacked bar plots with true positives, false positives together for specific numerical filters.

### Repo Description

This workflow have 3 CWL based tools. The description for these tools are as follows:

- Convert_reference_SDF: This converts fasta file into sdf format required for RTG as an input.

- Run_rtg_tools: User have to provide all the target vcf files in a folder and all the gold standard in another folder. This tool will create a manifest using target vcfs by pulling sample id from vcf header and will aim to look for corresponding gold standard vcfs.  This tool can also filter target vcfs if filter string is provided. Filtering is optional, and once calls are filtered, RTG tool computes the confusion matrix on new filtered vcfs or target vcfs (depends if filter string is provided or not) using the gold standard provided.

- Bar plots: This tool takes rtg_results folder as input that contains tp.vcf.gz & fp.vcf.gz for all desered samples and manifest for samples that informs this tool about experimental strategy. This tool will loop over all the sample folders and will pull TPs & FPs. furthur, it will plot stack bar plots for WGS and WXS 

Here is figure that depicts skeleton of this workflow

![Benchmarking schematic](https://github.com/kids-first/kfdrc-benchmark/tree/main/docs/Benchmarking_wf_schematic.png)

### Inputs

```
convert_reference_sdf
  ref_file: { doc: provide reference file in fasta format, type: 'File?' } 

RTG Tool
  test_folder: { doc: provide folder containing test vcf file with index files, type: Directory }
  consensus_folder_path: { doc: provide folder containing consensus vcf file with index files, type: Directory }
  ram: { doc: provide ram (in GB) based on number of test files, type: 'int?', default: 14 } 
  output_file_name: { doc: provide output file name, type: string }
  filter_string: { doc: (optional) provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, type: 'string?', default: '' }
  cores: { doc: provide cores to run samples in multiprocessing, type: 'int?', default: 8 }

Bar Plots
  disable_plotting: {type: boolean, default: True, doc: "Set to true to disable plotting tool" }
  plot_feature: { doc: provide bcftool format like filter_string example- %DP, type: 'string?', default: '%DP' }
  sample_manifest: { doc: provide sample with experimental strategy, type: 'File?' }
  plot_range: {doc: Provide start end and bin size in the same order Example- 0 200 10 for depth,default: ["0","200","10"] , type: 'string[]' }
  filter_name: { doc: provide filter name, type: 'string?', default: "filter" }

```

### Outputs
```
RTG Tool
 benchmarking_tsv: { type: File, doc: benchmarking output in tsv format, outputSource: run_RTG/output_tsv }
 average_result: { type: File, doc: average benchmarking results , outputSource: run_RTG/output_mean }
 rtg_results: { type: Directory, doc: directory containing output for all the samples from RTG, outputSource: run_RTG/results_dir }

Bar Plots 
 plot_WGS: { type: 'File?', doc: plot for WGS samples , outputSource: plots/WGS_png}
 plot_WXS: { type: 'File?', doc: plot for WXS samples, outputSource: plots/WXS_png }
```

### More details

Test [run 1](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/tasks/260d89bd-5581-4d69-a1f1-afc3673e7277/)
Benchmarking docker:[link](https://github.com/d3b-center/bixtools/blob/master/tumor-only-benchmarking/1.0.0/Dockerfile)

Plotting tool also lives independently to provide flexibility and save cost for analysis if required. Here is the [link to app](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/apps/filter_plotting/12) & [link to test run](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/tasks/98fcf1b6-97ce-44e0-9075-a90ba7dc3c38/)