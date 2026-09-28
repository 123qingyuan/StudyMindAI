"""Download public source snapshots; no database writes."""
from pathlib import Path
import requests,json,concurrent.futures,time
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'open_sources'; OUT.mkdir(exist_ok=True)
def fetch(pair):
    name,url=pair; p=OUT/name
    if p.exists(): return name
    for attempt in range(3):
        try:
            r=requests.get(url,timeout=120);r.raise_for_status();p.write_bytes(r.content);return name
        except Exception:
            if attempt==2: raise
            time.sleep(2)
def main():
    cm=['college_medicine','professional_medicine','anatomy','professional_psychology','computer_security','computer_science','elementary_information_and_technology','management','public_relations','electrical_engineering']
    li=['git/git-quiz.md','java/java-quiz.md','python/python-quiz.md','mysql/mysql-quiz.md','c-(programming-language)/c-(programming-language)-quiz.md','agile-methodologies/agile-methodologies-quiz.md','object-oriented-programming/object-oriented-programming-quiz.md']
    jobs=[('cmmlu_'+x+'.csv','https://raw.githubusercontent.com/haonan-li/CMMLU/master/data/test/'+x+'.csv') for x in cm]
    jobs += [('linkedin_'+x.split('/')[0]+'.md','https://raw.githubusercontent.com/Ebazhanov/linkedin-skill-assessments-quizzes/main/'+x) for x in li]
    jobs += [('CMMLU_README.md','https://huggingface.co/datasets/haonan-li/cmmlu/raw/main/README.md'),('LINKEDIN_LICENSE','https://raw.githubusercontent.com/Ebazhanov/linkedin-skill-assessments-quizzes/main/LICENSE'),('CEVAL_README.md','https://huggingface.co/datasets/ceval/ceval-exam/raw/main/README.md')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for name in ex.map(fetch,jobs): print(name,flush=True)
if __name__=='__main__':main()
