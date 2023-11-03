# D3b Bixu VCF benchmarking workflow

The D3b Bixu VCF Benchmarking Workflow uses RTG Tools and BCFtools to generate benchmark statistics and a Matplotlib-based tool to plot tool performance and/or fidelity. This workflow computes confusion matrix with F1 score for target VCFs using provided gold standard VCF files. It can also filter calls using [BCFtools-style filtering expression](https://samtools.github.io/bcftools/bcftools.html#expressions) (-i flag argument for ex `DP > 10`). Additionally, it can prepare stacked bar plots with true positives (TP) and false positives (FP) together for specific numerical filters.

### CWL Workflow and Tools

The D3b Bixu VCF Benchmarking Workflow is composed of three Common Workflow Language (CWL) tools:

- convert_reference_SDF: converts the contents of a FASTA file into the RTG Sequence Data File (SDF) format

- run_rtg_tool: User have to provide all the target VCF files in a folder and all the gold standard files in another folder. This tool will create a manifest using target VCFs by pulling sample id from VCF header and will aim to look for corresponding gold standard VCFs. This tool can optionally filter target VCFs if a filter string is provided. Finally, RTG Tools computes the confusion matrix comparing the, optionally-filtered, target VCFs against their associated gold standard VCFs.

- Bar plots: This tool take s rtg_results folder as input that contains tp.vcf.gz & fp.vcf.gz for all desired samples, plot feature (Example: `[%DP ]`) and a manifest for samples that informs this tool about experimental strategy. This tool will loop over all the sample folders and will pull TPs & FPs. Further, it will plot stack bar plots for WGS and WXS separately.

Plotting tool also lives independently to provide flexibility and save cost for analysis if required. Here is the link to [plotting tool](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/apps/filter_plotting) 

### Deployment

This workflow is also deployed on cavatica and can be access as an [app](https://cavatica.sbgenomics.com/u/d3b-bixu/kf-tumor-only-wf-dev/apps/benchmarking_RTG_tool) 

Here is figure that depicts skeleton of this workflow

![Benchmarking schematic](https://github.com/kids-first/kfdrc-benchmark/tree/main/docs/Benchmarking_wf_schematic.png)

### Inputs

```
convert_reference_sdf
  ref_file: provide reference file in fasta format

RTG Tool
  test_folder: provide folder containing test vcf file with index files,
  gold_standard_folder_path: provide folder containing gold standard vcf files with their index files
  ram: provide ram (in GB) based on number of test files, default: 14 
  output_file_name: provide output file name
  filter_string: (optional) provide bcftool format filter_string example- INFO/DP>30 && INFO/AD>1, default: ''
  cores: provide cores to run samples in multiprocessing, default: 8

Bar Plots
  disable_plotting: "Set to true to disable plotting tool", default: True
  plot_feature: provide bcftool format like filter_string example- %DP , default: '%DP'
  sample_manifest: Provide sample with experimental strategy
  plot_range: Provide start end and bin size in the same order Example- 0 200 10 for depth, default: ["0","200","10"] 
  filter_name: provide filter name
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

### More details

- [Benchmarking docker](https://github.com/d3b-center/bixtools/blob/master/tumor-only-benchmarking/1.0.0/Dockerfile):

Prebuilt Docker image is available through Command Line Interface (CLI):
```
docker pull pgc-images.sbgenomics.com/d3b-bixu/tumor-only-benchmarking:1.0.0
```
- ![Workflow Test Run](https://github.com/kids-first/kfdrc-benchmark/tree/main/docs/Test_run_wf.png) 
- ![Test run](https://github.com/kids-first/kfdrc-benchmark/tree/main/docs/Test_run_plotting_tool.png)
