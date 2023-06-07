import pandas as pd
import os
import subprocess
import re
from pandarallel import pandarallel
import argparse
import warnings
import sys

#look into https://stackoverflow.com/questions/26784164/pandas-multiprocessing-apply

# Initialize parser
parser = argparse.ArgumentParser()

# Adding optional argument
parser.add_argument("-i", "--test_folder_path", help="provide sample vcf file")
parser.add_argument("-c", "--consensus_folder_path", help="provide sample ID for germline vcf")
parser.add_argument("-r", "--ref_folder_sdf", help="Frequency cutoff for popmax")
parser.add_argument("-t", "--workers", help="Frequency cutoff for popmax")
parser.add_argument("-o", "--output_file_name", help="Frequency cutoff for popmax")

# suppress pandas future warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

args = parser.parse_args()

pandarallel.initialize(nb_workers=int(int(args.workers)/2))

consensus_path=args.consensus_folder_path
tumor_only_path=args.test_folder_path 
ref_file=args.ref_folder_sdf

def map_sample_id_with_file(path):
    bcftools_samples = "bcftools query -l "
    exe=('vcf.gz')
    sample_id_files=[]

    filelist=os.listdir(path) 
    for file in filelist:
        if file.endswith(exe):
            file_path=path+"/"+file
            cmd_samples=bcftools_samples+file_path
            samples_vcf = (subprocess.check_output(cmd_samples, shell=True).decode("utf-8").strip())
            if re.search('\n',samples_vcf):
                for sample in samples_vcf.split('\n'):
                    sample_id_files.append([sample,file_path])
                continue
            else:    
                sample_id_files.append([samples_vcf,file_path])    
    
    return pd.DataFrame(sample_id_files,columns=['sample_id','file_path'])

def run_rtg(sample_id,tumor_only_file,consensus_only_files,ref_file):
    
    if os.path.isfile(consensus_only_files) and os.path.isfile(tumor_only_file):
        index_file_tumor_only=tumor_only_file+'.tbi'
        index_file_consensus_only=consensus_only_files+'.tbi'
#        if os.path.isdir(ref_file.dir):
        if os.path.isfile(consensus_only_files) and os.path.isfile(tumor_only_file) and os.path.isfile(index_file_consensus_only) and os.path.isfile(index_file_tumor_only) : # run only when tumor only and consensus file exist     
            print('Running RTG on: ',sample_id,file=sys.stderr)
            cmd='rtg vcfeval --baseline='+consensus_only_files+' --sample='+sample_id +' -c '+ tumor_only_file + ' -t '+ref_file+' -o results/'+sample_id+'_rtg'
            output=subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
            
            return output.split('\n')[-1].split()
    else:
        print('Warning: Skipping RTG run for',sample_id,'- cannot find either tumor or consensus files with their index files',file=sys.stderr)
        return [None,None,None,None,None,None,None,None]

tumor_only_manifest=map_sample_id_with_file(tumor_only_path)
consensus_only_manifest=map_sample_id_with_file(consensus_path )

tumor_consensus_sample_ID=pd.merge(tumor_only_manifest,consensus_only_manifest,on=['sample_id'],how='inner')
tumor_consensus_sample_ID=tumor_consensus_sample_ID.rename(columns={'file_path_x':'test_input_file','file_path_y':'reference_file'})

tumor_consensus_sample_ID=tumor_consensus_sample_ID.sort_values('sample_id',ascending=False)
tumor_consensus_sample_ID['result']=tumor_consensus_sample_ID.parallel_apply(lambda row : run_rtg(row['sample_id'],row['test_input_file'],row['reference_file'],ref_file),axis=1)

tumor_consensus_sample_ID[['Threshold','True-pos-baseline','True-pos-call','False-pos','False-neg','Precision','Sensitivity','F-measure']]=pd.DataFrame(tumor_consensus_sample_ID.result.tolist(),index=tumor_consensus_sample_ID.index)

tumor_consensus_sample_ID=tumor_consensus_sample_ID.drop(['result','Threshold'],axis=1)
tumor_consensus_sample_ID=tumor_consensus_sample_ID[['sample_id','Precision','Sensitivity','F-measure','True-pos-baseline','True-pos-call','False-pos','False-neg','test_input_file','reference_file']]

#tumor_consensus_sample_ID['result']=tumor_consensus_sample_ID.apply(lambda row : run_rtg(row['sample_id'],row['tumor_only_file'],row['consensus_only_files'],ref_file),axis=1)
if not args.output_file_name.endswith(".tsv"):
    output_file=args.output_file_name+".tsv"
else:
    output_file=args.output_file_name    
tumor_consensus_sample_ID.to_csv(output_file,sep='\t',index=False)
