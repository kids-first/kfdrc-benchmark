import gzip
import pandas as pd
import io
import argparse


def read_vcf(path):
    with (gzip.open if path.endswith("gz") else open)(path, "rt") as f:    # for compressed files
        lines = [l for l in f if not l.startswith('##')]
    return pd.read_csv(
        io.StringIO(''.join(lines)),
        dtype={'#CHROM': str, 'POS': int, 'ID': str, 'REF': str, 'ALT': str,
               'QUAL': str, 'FILTER': str, 'INFO': str},
        sep='\t'
    ).rename(columns={'#CHROM': 'CHROM'})

def operation_row(row): ## to find SNVs & Indels or put some logic 
    row['logic']=False
    if len(row['REF']) > 1:
        row['logic']=True
    elif len(row['ALT']) > 1:
         row['logic']=True
    return row['logic']  


parser = argparse.ArgumentParser(description='Benchmark vcf with gold standard')
parser.add_argument('-i','--sample_ID')
parser.add_argument('-s', '--gold_standard') 
parser.add_argument('-c', '--sample_vcf')  
args = parser.parse_args()

sample_id=args.sample_ID
truth_file=args.gold_standard
sample_file=args.sample_vcf
gold_standard=read_vcf(truth_file)
sample_calls=read_vcf(sample_file)

'''
Apply logic to a vcf row
'''
# sample_calls['logic'] = None
# sample_calls['logic']=sample_calls.apply(operation_row,axis=1)
# sample_calls=sample_calls[sample_calls['logic']]


'''
use pandas merge to compare calls on 'CHROM','POS','REF','ALT' for vcfs 
extract TP FP FN
and compute f1 score, precision, and sensitivity
'''
merge_TP=pd.merge(sample_calls, gold_standard, on=['CHROM','POS','REF','ALT'], how='inner')
TP_calls=merge_TP.shape[0]
FP=sample_calls.shape[0]-TP_calls
FN=gold_standard.shape[0]-TP_calls
f1=round(TP_calls/(TP_calls+0.5*(FP+FN)),2)
precision=round(TP_calls/(TP_calls+FP),2)
sensitivity=round(TP_calls/(TP_calls+FN),2)
'''
Print results
'''
print("Total consensus calls: ", sample_calls.shape[0])
print("Total gold standard calls: ", gold_standard.shape[0])
print("| sample_id | True Positive | False Positive | False Negative | F1 Score | Precision | sensitivity |")
print("| "+sample_id+"| ",TP_calls,"| ",FP,"| ",FN,"| ",f1,"|",precision,"|",sensitivity,"|")


