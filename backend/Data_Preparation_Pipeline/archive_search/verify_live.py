"""Limited TAP metadata verification; never downloads products."""
import json
from pathlib import Path
import pyvo

def main():
    service=pyvo.dal.TAPService('https://irsa.ipac.caltech.edu/TAP')
    query="SELECT table_name,column_name,datatype,description FROM TAP_SCHEMA.columns WHERE table_name IN ('spherex.artifact','spherex.plane','spherex.observation')"
    result=service.search(query,maxrec=1000)
    rows=[{n:str(row[n]) for n in result.fieldnames} for row in result]
    print(json.dumps(rows,indent=2))
    path=Path(__file__).parent/'tap_schema_verified.json'
    path.write_text(json.dumps({'query':query,'columns':rows},indent=2),encoding='utf-8')
if __name__=='__main__': main()
