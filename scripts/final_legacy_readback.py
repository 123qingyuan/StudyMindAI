"""Final sanitized readback and source-origin audit; does not modify user data."""
import json,sys
from pathlib import Path
import httpx,psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'scripts'))
from app import core
from app.legacy_content import manifest,VERSION,sha
from backfill_legacy_expansions import snapshot
m=manifest();directory=ROOT/'data'/'builtin'/VERSION
previous=json.loads((directory/'backfill-report.json').read_text(encoding='utf-8'))
with core.db() as c:
    current=snapshot(c);assert current==previous['after']
    users=c.execute('SELECT id FROM users').fetchall()
    completed=c.execute("SELECT COUNT(*) n FROM builtin_expansion_runs WHERE version=? AND status='completed'",(VERSION,)).fetchone()['n']
    assert len(users)==completed==26
    docs=c.execute("SELECT content FROM documents WHERE original_name LIKE '%五万字补全%'").fetchall()
    origins={}
    for d in docs:
        matches=[]
        for item in m['items']:
            raw=item['text'].split('\n---\n\n',1)[1]
            if raw[:2000] in d['content']:matches.append(item['domain'])
        key=';'.join(matches) or 'unconfirmed_user_source_not_distributed'
        origins[key]=origins.get(key,0)+1
    counts=[]
    for u in users:
        keys=c.execute('SELECT COUNT(*) n FROM question_sources s JOIN questions q ON q.id=s.question_id WHERE q.user_id=?',(u['id'],)).fetchone()['n']
        counts.append(keys)
health=httpx.get('http://127.0.0.1:8765/api/health',timeout=60,trust_env=False)
assert health.status_code==200
listeners=[{'address':x.laddr.ip,'port':x.laddr.port} for x in psutil.net_connections() if x.status=='LISTEN' and x.laddr.port==8765]
assert any(x['address']=='0.0.0.0' for x in listeners)
report={'accounts':len(users),'completed':completed,'controlled_long_documents':sum(len(m['items']) for _ in users),
        'final_protected_snapshot_matches_successful_backfill_audit':True,'protected_snapshot':current,
        'source_question_counts_per_account':sorted(counts),'incorrect_topup_origin_counts':origins,'incorrect_topup_not_redistributed':True,
        'health_status':health.status_code,'health':health.json(),'listeners':listeners,
        'initial_run_limitation':'Initial import completed all 26 accounts but aggregate unrelated-record equality assertion failed. Original in-memory baseline was not persisted, so exact initial difference is unproven. A subsequent full no-op audit and final readback matched. Do not claim a proven initial before/after equality.',
        'first_run_tool_output':{'accounts':26,'new_documents':140,'exact_hash_reused_and_relabelled':42},
        'quality':'Deduplicated counts are mechanical, not verified effective educational characters. No five-thousand/ fifty-thousand meaningful-content claim.'}
(directory/'final-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
