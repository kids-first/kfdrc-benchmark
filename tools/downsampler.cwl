cwlVersion: v1.2
class: CommandLineTool
doc: Downsample a BAM http/s3 to a particualr coverage
requirements:
  - class: ShellCommandRequirement
  - class: DockerRequirement
    dockerPull: 'pgc-images.sbgenomics.com/d3b-bixu/samtools:1.20-parallel'
  - class: ResourceRequirement
    ramMin: $(inputs.ram * 1000)
    coresMin: $(inputs.cpu)
  - class: InlineJavascriptRequirement
  - class: InitialWorkDirRequirement
    listing:
      - entryname: downsample.sh
        entry: >
          #!/usr/bin/env bash

          set -ex

          BAM=$(inputs.bam_url)

          TARGET_COV=$(inputs.target_coverage)

          OUTPUT_FILENAME=$(inputs.bam_url.split('/').pop().replace(/bam$/, inputs.target_coverage + "x.bam"))

          AVG_RL=`samtools view --threads $(Math.min(inputs.cpu,8)) -F 0x904 $BAM \
                  | head -n1000000 \
                  | awk '{sum += length($10); count++} END {print sum/count}'`

          EST_COV=`samtools idxstats $BAM \
                   | awk -F'\t' -v L=$AVG_RL '{mapped+=$3; contig+=$2} END {print mapped*L/contig}'`

          SUBSAMPLE=`awk "BEGIN {print $TARGET_COV/$EST_COV}"`

          echo $BAM > bam_info.log

          samtools idxstats $BAM | \
          awk -F'\t' -v L=$AVG_RL -v S=$SUBSAMPLE '{mapped+=$3; contig+=$2} END {print "Mapped Reads:",mapped,"\tBases Mapped:",mapped*L,"\tEst Coverage:",mapped*L/contig, "\tSubsample Factor:",S}' >> bam_info.log

          set -o pipefail

          samtools collate --threads $(Math.min(inputs.cpu,8)) -O $BAM | \
          samtools view --threads $(Math.min(inputs.cpu,8)) --with-header --subsample $SUBSAMPLE -u | \
          samtools sort --threads $(inputs.cpu) --output-fmt BAM -o $OUTPUT_FILENAME
hints:
  - class: 'sbg:SaveLogs'
    value: downsample.sh
  - class: 'sbg:SaveLogs'
    value: bam_info.log
baseCommand: []
arguments:
  - position: 0
    shellQuote: false
    valueFrom: /bin/bash downsample.sh
inputs:
  bam_url: { type: 'string', doc: "HTTP URL to BAM file" }
  target_coverage: { type: 'int', doc: "Target coverage to take BAM to. Recommend 30 for normal, 60 for tumor" }
  cpu: { type: 'int?', default: 16, doc: "CPUs to allocate to this task" }
  ram: { type: 'int?', default: 128, doc: "GB of RAM to allocate to this task" }
outputs:
  output:
    type: File
    outputBinding:
      glob: '*.bam'
$namespaces:
  sbg: 'https://sevenbridges.com'
