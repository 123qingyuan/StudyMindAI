from pathlib import Path
import json,csv,re,collections
P=Path(__file__).resolve().parents[1]/'data/open_sources'
for p in P.glob('ceval_*.json'):
 r=json.loads(p.read_text(encoding='utf8')); print(p.stem,len(r),dict(collections.Counter(x.get('answer') for x in r)))
for p in P.glob('linkedin_*.md'):print(p.stem,len(re.findall(r'^#### Q',p.read_text(encoding='utf8'),re.M)))
for name in ['computer_science','electrical_engineering','professional_psychology','professional_medicine']:
 rows=list(csv.DictReader((P/('cmmlu_'+name+'.csv')).read_text(encoding='utf8').splitlines()));print(name,len(rows));print('\n'.join(x['Question'] for x in rows[:15]))
r=json.loads((P/'english_train_exercise_dataset.json').read_text(encoding='utf8'));print('english',[(k,str(v)[:350]) for k,v in r.items()])
