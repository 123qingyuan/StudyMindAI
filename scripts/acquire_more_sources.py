import requests,json,concurrent.futures
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'data/open_sources'; D=P/'opendsa';D.mkdir(exist_ok=True)
paths=json.loads((P/'opendsa_tree.json').read_text())
folders={'AlgAnal','Sorting','Search','Binary','General','List','Hash','Graph','Design','Background','RecurTutor','Recursion','Indexing','SeniorAlgAnal','NP','Bounds'}
selected=[x for x in paths if x.startswith('Exercises/') and x.split('/')[1] in folders and x.endswith('.html') and not any(s in x for s in ['Summ','PRO','FIB'])]
def one(path):
    out=D/path.replace('/','__')
    if out.exists():return
    r=requests.get('https://raw.githubusercontent.com/OpenDSA/OpenDSA/master/'+path,timeout=90);r.raise_for_status();out.write_bytes(r.content)
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:list(ex.map(one,selected))
for name,url in [('OPENDSA_LICENSE','https://raw.githubusercontent.com/OpenDSA/OpenDSA/master/MIT-license.txt'),('medmcqa_validation.parquet','https://huggingface.co/datasets/openlifescienceai/medmcqa/resolve/main/data/validation-00000-of-00001.parquet'),('MEDMCQA_README.md','https://huggingface.co/datasets/openlifescienceai/medmcqa/raw/main/README.md')]:
 r=requests.get(url,timeout=180);r.raise_for_status();(P/name).write_bytes(r.content)
print('Downloaded',len(selected),'OpenDSA files and MedMCQA validation')
