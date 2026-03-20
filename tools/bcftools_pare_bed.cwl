cwlVersion: v1.2
class: CommandLineTool
id: bcftools_pare_bed
requirements:
- class: ShellCommandRequirement
- class: DockerRequirement
  dockerPull: staphb/bcftools:1.20
- class: InlineJavascriptRequirement  
- class: ResourceRequirement
  coresMin: $(inputs.cpu)
  ramMin: $(inputs.ram * 1000)
baseCommand: []
arguments:
- position: 1
  shellQuote: false   
  valueFrom: >-
    bcftools index -s $(inputs.vcf.path) | awk '$3>0{print $1}' > covered_chrs.txt
    && bed=$(inputs.bed.path)
    && case "$bed" in *.gz) zcat -- "$bed" ;; *) cat -- "$bed" ;; esac
    | awk 'BEGIN{FS=OFS="\t"} NR==FNR{ok[$1]=1; next} ($1 in ok){print}' covered_chrs.txt - > $(inputs.bed.basename.replace(/.bed(.gz)?$/, ".pared.bed"))

inputs:
  vcf: { type: "File", secondaryFiles: [{pattern: ".tbi", required: true}]}
  bed: { type: "File" }
  cpu: { type: "int?", default: 1 }
  ram: { type: "int?", default: 2 }
 
outputs:
  pared_bed:
    type: File
    outputBinding:
      glob: "*.bed"
