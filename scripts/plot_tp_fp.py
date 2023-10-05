import os
import gzip
import pandas as pd
import subprocess
import numpy
from matplotlib import pyplot as plt
import argparse

# coding=utf8
# Initialize parser
parser = argparse.ArgumentParser()

# Adding argument
parser.add_argument("-i", "--input_folder", help="input RTG folder")
parser.add_argument("-f", "--filter", help="filter to analysis")

# Read arguments from command line
args = parser.parse_args()
folder_name=args.input_folder
filter=args.filter

def vcf_to_pandas(file):
    vcf_data=[]
    upper_header=[]
    with gzip.open(file, 'rt') as f:
        for line in f:
            line=line.split("\n")[0]
            if line.startswith("#CHROM"):
                header=line.split("\t")
            if not line.startswith("#"):
                calls=line.split("\t")
                vcf_data.append(calls)
    return pd.DataFrame(vcf_data,columns=header)

def vcf_filter_extract(file):
    cmd_bcftools="bcftools query -f'"+filter + " \n' "+file
    result = subprocess.run(cmd_bcftools, shell=True, capture_output=True, text=True, check=True)
    return result.stdout.split() # return filter value as a list

def extract_filter(folder_name,file_target,manifest_sample,sample_type):
    data_list=[]
    for folder in os.listdir(folder_name):
        sample_id=folder.replace("_rtg","")
        folder_address=folder_name+"/"+folder
        for i in os.listdir(folder_address):
            if i==file_target and manifest_sample[sample_id]==sample_type:
                i=folder_address+"/"+file_target
                print(i)
                data_list.append(vcf_filter_extract(i))
                break    
    return [item for sublist in data_list for item in sublist]
            
file_target="tp.vcf.gz"
sample_type="WGS"
manifest_sample=pd.read_csv("input/benchmarking_without_filters.tsv",sep='\t',usecols=["sample_id","experimental_strategy"])
manifest_sample=manifest_sample.set_index('sample_id').T.to_dict('records')
#print(manifest_sample)
data_tp=pd.DataFrame(extract_filter(folder_name,file_target,manifest_sample[0],sample_type),columns=["filter"])
print(data_tp)

data_tp["filter"]=data_tp["filter"].astype('int')
frequency_table_tp=data_tp['filter'].value_counts(bins=list(range(0,200,10)))
frequency_table_tp=frequency_table_tp.sort_index()
frequency_table_tp.index=frequency_table_tp.index.astype(str)

title="Plot for filter: "+filter+ " "+sample_type+" samples"
plt.figure(figsize=(20,8))
plt.bar(frequency_table_tp.index, frequency_table_tp.values)
plt.xticks(fontsize=7)
plt.title(title)
plt.xlabel("Range")
plt.ylabel("Number of True Positives")
plt.savefig('tp.png')

file_target="fp.vcf.gz"
folder_name="results_rtg"
data_fp=pd.DataFrame(extract_filter(folder_name,file_target,manifest_sample[0],sample_type),columns=["filter"])
data_fp["filter"]=data_fp["filter"].astype('int')
frequency_table_fp=data_fp['filter'].value_counts(bins=list(range(0,200,10)))
frequency_table_fp=frequency_table_fp.sort_index()
frequency_table_fp.index=frequency_table_fp.index.astype(str)

plt.figure(figsize=(20,8))
plt.bar(frequency_table_fp.index, frequency_table_fp.values)
plt.xticks(fontsize=7)
plt.title(title)
plt.xlabel("Range")
plt.ylabel("Number of False Positives")
plt.savefig('fp.png')
