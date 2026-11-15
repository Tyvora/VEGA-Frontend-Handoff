"""Independent read-only inspection CLI; no creator or science algorithm called."""
import argparse,json
from .reader import load_package

def main():
    parser=argparse.ArgumentParser();parser.add_argument('path');args=parser.parse_args()
    package=load_package(args.path)
    print(json.dumps({'capability':package.metadata['capability'],'decision':package.decision,'arrays':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in package.arrays.items()}},indent=2))
if __name__=='__main__':main()
