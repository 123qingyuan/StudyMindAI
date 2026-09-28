"""Read-only all-account chunk/search audit; no vector clients or models."""
import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app import core
from app.legacy_content import manifest,VERSION,sha
from app.document.parser import Page,chunks
from app.rag.store import retrieve,_CLIENTS,_MODELS

async def main():
    m=manifest();result=[]
    with core.db() as c:users=c.execute('SELECT id FROM users ORDER BY id').fetchall()
    for n,u in enumerate(users,1):
        items=[]
        with core.db() as c:
            rows=c.execute('SELECT s.item_key,d.id,d.content,l.knowledge_base_id FROM builtin_expansion_sources s JOIN documents d ON d.id=s.document_id JOIN document_links l ON l.document_id=d.id WHERE s.user_id=? AND s.version=?',(u['id'],VERSION)).fetchall()
            base=c.execute("SELECT COUNT(*) n FROM documents WHERE user_id=? AND original_name LIKE '[内置] %'",(u['id'],)).fetchone()['n']
            assert base==24
            for item in m['items']:
                d=next(d for d in rows if d['item_key']==item['key'])
                assert sha(d['content'])==item['sha256']
                actual=c.execute('SELECT page,ordinal,content FROM document_chunks WHERE document_id=? AND user_id=? ORDER BY ordinal',(d['id'],u['id'])).fetchall()
                assert actual==list(chunks([Page(1,item['text'],'text')]))
                hits,mode,warning=await retrieve(m['label'],u['id'],d['knowledge_base_id'])
                assert mode=='keyword' and any(h['document_id']==d['id'] for h in hits)
                items.append({'key':item['key'],'chunks':len(actual),'hash_match':True,'keyword_hit':True})
        result.append({'account':n,'base_documents':base,'long_documents':items})
        print(json.dumps({'account':n,'verified':len(items)},ensure_ascii=False),flush=True)
    assert not _CLIENTS and not _MODELS
    out=ROOT/'data'/'builtin'/VERSION/'all-account-search-report.json'
    out.write_text(json.dumps({'accounts':len(users),'qdrant_clients_opened':0,'embedding_models_opened':0,'results':result},ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(out))

if __name__=='__main__':asyncio.run(main())
