"""Cache complete paginated C-Eval source rows, preserving answer keys."""
import json,requests,concurrent.futures,time
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'data'/'open_sources'
CONFIGS=['chinese_language_and_literature','high_school_biology','college_physics','college_economics','operating_system','education_science','electrical_engineer','probability_and_statistics','law','computer_architecture','computer_network','accountant','advanced_mathematics','college_programming','basic_medicine','civil_servant']
def one(config):
    p=OUT/('ceval_'+config+'.json')
    if p.exists():return config,len(json.loads(p.read_text(encoding='utf8')))
    rows=[];offset=0
    while True:
        for attempt in range(4):
            try:
                r=requests.get('https://datasets-server.huggingface.co/rows',params=dict(dataset='ceval/ceval-exam',config=config,split='test',offset=offset,length=100),timeout=90);r.raise_for_status();j=r.json();break
            except Exception:
                if attempt==3:raise
                time.sleep(3)
        page=j['rows']; rows.extend(x['row'] for x in page);offset+=len(page)
        if not page or offset>=j['num_rows_total']:break
    p.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8');return config,len(rows)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for result in ex.map(one,CONFIGS):print(result,flush=True)
