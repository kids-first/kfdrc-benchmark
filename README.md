# D3b Bixu VCF Benchmarking Workflow

The D3b Bixu VCF Benchmarking Workflow uses RTG Tools and BCFtools to generate benchmark statistics and a Matplotlib-based tool to plot tool performance and/or fidelity. This workflow computes confusion matrix with F1 score for target VCFs using provided gold standard VCF files. It can also filter calls using [BCFtools-style filtering expression](https://samtools.github.io/bcftools/bcftools.html#expressions) (-i flag argument for ex `DP > 10`). Additionally, it can prepare stacked bar plots with true positives (TP) and false positives (FP) together for specific numerical filters.

### CWL Workflow and Tools

The D3b Bixu VCF Benchmarking Workflow is composed of three Common Workflow Language (CWL) tools:

1. convert_reference_SDF: converts the contents of a FASTA file into the RTG Sequence Data File (SDF) format

2. run_rtg_tool: User have to provide all the target VCF files in a folder and all the gold standard files in another folder. This tool will create a manifest using target VCFs by pulling sample id from VCF header and will aim to look for corresponding gold standard VCFs. This tool can optionally filter target VCFs if a filter string is provided. Finally, RTG Tools computes the confusion matrix comparing the, optionally-filtered, target VCFs against their associated gold standard VCFs.

3. bar_plots: This tool takes rtg_results folder as input that contains `tp.vcf.gz` & `fp.vcf.gz` for all desired samples, plot feature (Example: `[%DP ]`) and a manifest for samples that informs this tool about experimental strategy. This tool will loop over all the sample folders and will pull TPs & FPs. Further, it will plot stack bar plots for Whole Genome Sequencing (WGS) and Whole Exome Sequencing (WXS) separately.

 To provide flexibility and save cost for analysis, the plotting tool from above can also be run independently. That tool can be found [on CAVATICA](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/apps/filter_plotting).

### Deployment

This workflow is also deployed on cavatica and can be access as an [app](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/apps/benchmarking_RTG_tool) 

Here is figure that depicts skeleton of this workflow

![Benchmarking schematic](https://github.com/kids-first/kfdrc-benchmark/blob/main/docs/Benchmarking_wf_schematic.png)

### Inputs

```
convert_reference_sdf
  ref_file: reference file in FASTA format

RTG Tool
  test_folder: provide folder containing test vcf file with index files,
  gold_standard_folder_path: directory containing gold standard VCFs and their associated indices
  ram: RAM (in GB) to allocate to RTG Tools, default: 14 
  output_file_name: provide output file name
  filter_string: (optional) BCFtools format filter_string example- INFO/DP>30 && INFO/AD>1, default: ''
  cores: provide cores to run samples in multiprocessing, default: 8

Bar Plots
  disable_plotting: Set to true to disable plotting tool, default: True
  plot_feature: bcftool format like filter_string example- %DP , default: '%DP'
  sample_manifest: sample manifest with sample ID and their experimental strategy
  plot_start: start point for the plot, default: '0'
  plot_end: cut point for the plot,  default: '1'
  plot_bin_size: bin size for the plot, default: '0.1'
  filter_name: filter name as annotated in the VCF files
```

### Outputs
```
RTG Tool 
 benchmarking_tsv: benchmarking output in TSV format
 average_result: average benchmarking results 
 rtg_results: directory containing outputs for all the samples from RTG

Bar Plots 
 plot_WGS: plot for WGS samples 
 plot_WXS: plot for WXS samples

```

### Benchmarking Workflow Test Run
![Workflow Test Run](https://github.com/kids-first/kfdrc-benchmark/blob/main/docs/Test_run_wf.png) 

### Plotting Tool Test Run
![Test run](https://github.com/kids-first/kfdrc-benchmark/blob/main/docs/Test_run_plotting_tool.png)

### Workflow Docker

Workflow docker can be found at [Benchmarking docker](https://github.com/d3b-center/bixtools/blob/master/tumor-only-benchmarking/1.0.0/Dockerfile)

Prebuilt docker image is also available through Command Line Interface (CLI):
```
docker pull pgc-images.sbgenomics.com/d3b-bixu/tumor-only-benchmarking:1.0.0
```

### Deploy Workflow on Cavatica

This workflow can be deployed on cavatica using [sbpack](https://github.com/rabix/sbpack) API. Following is the command line that will push workflow to cavatica
```
sbpack cavatica <path-to-project>/<app-name> workflow/run_benchmarking.cwl
```

