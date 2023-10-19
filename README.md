# D3b Bixu VCF benchmarking workflow

Benchmarking workflow computes confusion matrix with f1 score for target VCFs using provided gold standard VCF files. It can also filter calls by providing bcftool like string for ex `DP > 10`. It can also prepare stacked bar plots with True Positives, False Positives together for specific numerical filters.

### Repo Description

This repo is made up of 3 CWL tools. The description for these tools are as follows:

- convert_reference_SDF:
- run_rtg_tools:
- bar plots:

Here is figure that depict structure of this workflow

![Benchmarking schematic](https://github.com/kids-first/kfdrc-benchmark/tree/main/docs/Benchmarking_wf_schematic.png)

### Inputs

```
inputs:
# convert_reference_sdf
  ref_file: { doc: provide reference file in fasta format, type: 'File?' } 
#rtg tool
  test_folder: { doc: provide folder containing test vcf file with index files, type: Directory}
  consensus_folder_path: { doc: provide folder containing consensus vcf file with index files, type: Directory }
  ram: { doc: provide ram (in GB) based on number of test files, type: 'int?', default: 14 } 
  output_file_name: { doc: provide output file name, type: string }
  filter_string: { doc: (optional) provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, type: 'string?', default: '' }
  cores: { doc: provide cores to run samples in multiprocessing, type: 'int?', default: 8 }

#plotting
  disable_plotting: {type: boolean, default: True, doc: "Set to true to disable plotting tool" }
  plot_feature: { doc: provide bcftool format like filter_string example- %DP, type: 'string?', default: '%DP' }
  sample_manifest: { doc: provide sample with experimental strategy, type: 'File?' }
  plot_range: {doc: Provide start end and bin size in the same order Example- 0 200 10 for depth,default: ["0","200","10"] , type: 'string[]' }
  filter_name: { doc: provide filter name, type: 'string?',default: "filter" }

```

### Outputs
```
outputs:
 benchmarking_tsv: { type: File, doc: benchmarking output in tsv format, outputSource: run_RTG/output_tsv }
 average_result: { type: File, doc: average benchmarking results , outputSource: run_RTG/output_mean }
 rtg_results: { type: Directory, doc: directory containing output for all the samples from RTG, outputSource: run_RTG/results_dir }
 plot_WGS: { type: 'File?', doc: plot for WGS samples , outputSource: plots/WGS_png}
 plot_WXS: { type: 'File?', doc: plot for WXS samples, outputSource: plots/WXS_png }
```