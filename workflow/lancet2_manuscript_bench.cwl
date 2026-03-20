cwlVersion: v1.2
class: Workflow
id: lancet2_manuscript_bench
requirements:
- class: StepInputExpressionRequirement
- class: InlineJavascriptRequirement 
- class: MultipleInputFeatureRequirement
- class: ScatterFeatureRequirement
inputs:
  baseline: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}]}
  stratification_bed: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}] }
  evaluation_bed: { type: "File?" }
  reference: { type: "File" }
  reference_fai: { type: "File" }
  vcfeval_extra_args: { type: "string?", default: "--all-records --ref-overlap --output-mode annotate --vcf-score-field QUAL" }
  sample_name: { type: "string" }
  calls: { type: "File[]", secondaryFiles: [{pattern: ".tbi", required: true}] }
  tool_name: { type: "string[]", doc: "Tool names corresponding to each of the calls." }

outputs:
  report_htmls: { type: 'File[]', outputSource: make_rtg_report/htmls } 
 
steps:
  rtg_format:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/rtg_format.cwl
    in:
      reference: reference
    out: [sdf]
  fai_to_bed:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/fai_to_bed.cwl
    when: $(inputs.evaluation_bed == null)
    in:
      evaluation_bed: evaluation_bed
      fai: reference_fai
    out: [bed]
  bcftools_pare_bed:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/bcftools_pare_bed.cwl
    in:
      bed:
        source: [fai_to_bed/bed, evaluation_bed]
        pickValue: first_non_null
      vcf: baseline
    out: [pared_bed]
  bcftools_annotate:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/bcftools_annotate.cwl
    scatter: [vcf]
    in:
      vcf: calls
      annotations: stratification_bed
      output_filename:
        valueFrom: '$(inputs.vcf.basename.replace(/.vcf.gz$/, "stratified.vcf.gz"))'
      extra_args:
        valueFrom: >-
          --include 'FILTER="PASS"' --merge-logic STRATIFICATIONS:unique --columns CHROM,FROM,TO,STRATIFICATIONS --header-line '##INFO=<ID=STRATIFICATIONS,Number=.,Type=String,Description="GIAB stratifications">'
    out: [annotated]
  rtg_vcfeval:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/rtg_vcfeval.cwl
    scatter: [calls, tool_name]
    scatterMethod: dotproduct
    in:
      template: rtg_format/sdf
      baseline: baseline
      calls: bcftools_annotate/annotated
      bed_regions: bcftools_pare_bed/pared_bed
      baseline_sample:
        valueFrom: "ALT"
      calls_sample:
        valueFrom: "ALT"
      tool_name: tool_name
      extra_args: vcfeval_extra_args
    out: [baseline_vcf, calls_vcf]
  build_rtg_report:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/build_rtg_report.cwl
    scatter: [call_vcf, baseline_vcf, tool_name]
    scatterMethod: dotproduct
    in:
      call_vcf: rtg_vcfeval/calls_vcf
      baseline_vcf: rtg_vcfeval/baseline_vcf
      sample_name: sample_name
      tool_name: tool_name
    out: [report]
  make_rtg_report:
    hints:
      - class: 'sbg:AWSInstanceType'
        value: c7i.2xlarge
    run: ../tools/make_rtg_report.cwl
    in:
      sample_name: sample_name
      truthset:
        source: baseline
        valueFrom: '$(self.basename.replace(/.vcf.gz$/, ""))'
      tsvs: build_rtg_report/report
    out: [htmls]
