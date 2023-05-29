import pandas as pd
import os
import subprocess
import re
from pandarallel import pandarallel

#add to docker bcftools & pandarallel
#run python3.11 -m pip install -U decorator && python3.11 -m pip install -U psutil

#look into https://stackoverflow.com/questions/26784164/pandas-multiprocessing-apply

pandarallel.initialize(nb_workers=8)

tumor_only_path = '/home/ubuntu/mount/samples_tumor_only_benchmarking/public_tumor_only'
consensus_path = '/home/ubuntu/mount/samples_tumor_only_benchmarking/public_consensus'

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

tumor_only_manifest=map_sample_id_with_file(tumor_only_path)
consensus_only_manifest=map_sample_id_with_file(consensus_path )

tumor_consensus_sample_ID=pd.merge(tumor_only_manifest,consensus_only_manifest,on=['sample_id'],how='inner')
tumor_consensus_sample_ID=tumor_consensus_sample_ID.rename(columns={'file_path_x':'tumor_only_file','file_path_y':'consensus_only_files'})

#tumor_consensus_sample_ID.to_csv("manifest.tsv",sep='\t',index=False)
def run_rtg(sample_id,tumor_only_file,consensus_only_files):
    
    if os.path.isfile(consensus_only_files) and os.path.isfile(tumor_only_file):
        print(sample_id)
        cmd='/home/ubuntu/tools/RTG/rtg-tools-3.12.1/rtg vcfeval --baseline='+consensus_only_files+' --sample='+sample_id +' -c '+ tumor_only_file + ' -t /home/ubuntu/mount/tumor_only_benchmarking/reference/human -o results/'+sample_id
        output=subprocess.check_output(cmd, shell=True).decode("utf-8").strip()
        
        return output.split('\n')[-1].split()
    else:
        return False

tumor_consensus_sample_ID=tumor_consensus_sample_ID.sort_values('sample_id',ascending=False)
tumor_consensus_sample_ID['result']=tumor_consensus_sample_ID.parallel_apply(lambda row : run_rtg(row['sample_id'],row['tumor_only_file'],row['consensus_only_files']),axis=1)
tumor_consensus_sample_ID.to_csv("manifest.tsv",sep='\t',index=False)

#    --output-mode=split \
header_string='Threshold  True-pos-baseline  True-pos-call  False-pos  False-neg  Precision  Sensitivity  F-measure'
header=header_string.split('\n')[0].split()

#Threshold  True-pos-baseline  True-pos-call  False-pos  False-neg  Precision  Sensitivity  F-measure
#result=result.split()
#df.columns=headers
#print(tumor_consensus_sample_ID)