"""Recover the old seven-domain generator, without importing either retired script.

AST allowlist loads literal constants and the one pure expansion function only.
No main(), app imports, user data, question variants or vector operations execute.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'builtin' / 'legacy-expansion-v1'
LABEL = '[旧版扩展·含重复待整理]'


def literal(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    return ast.literal_eval(node.value)


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def unique_lines(text):
    # Deduplicate normalized non-empty lines, removing incidental section numbers.
    lines = [re.sub(r'^##\s*\d+·', '## ', re.sub(r'\s+', ' ', s).strip()) for s in text.splitlines()]
    return '\n'.join(dict.fromkeys(s for s in lines if s))


def main():
    source = ROOT / 'scripts' / 'expand_course_library.py'
    seed = ROOT / 'scripts' / 'seed_multidisciplinary_library.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'expand_text')
    ns = {'LENS': literal(source, 'LENS'), 'TARGET_CHARS': literal(source, 'TARGET_CHARS')}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), 'exec'), ns)
    libraries = literal(seed, 'LIBRARIES')
    assert len(libraries) == 7
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 'legacy-expansion-v1', 'label': LABEL,
                'source_script': str(source.relative_to(ROOT)), 'source_script_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'seed_source': str(seed.relative_to(ROOT)), 'seed_sha256': hashlib.sha256(seed.read_bytes()).hexdigest(),
                'dedup_method': 'Normalize whitespace per nonempty line; strip numbered ## section prefixes; keep first occurrence. This is a mechanical upper bound, not validated useful curriculum length.',
                'excluded': {'计算机知识体系': 'topup_all_knowledge_bases.py selected the latest user document, not a controlled computer source; never redistributed.'}, 'items': []}
    for i, (domain, topics) in enumerate(libraries.items(), 1):
        raw = ns['expand_text'](domain, topics)
        dedup = len(unique_lines(raw))
        source_chars = len(unique_lines('\n\n'.join(topics.values())))
        notice = (f'{LABEL}\n\n警告：这是之前生成的旧版重复扩展稿，只为保留和分发已有资料。'
                  f'原稿 {len(raw)} 字符；机械去重后 {dedup} 字符（非有效知识字数）；'
                  f'受控基础片段去重后 {source_chars} 字符。大量原文和任务重复，不代表有效五万字教材；内容未经学科专家核验。'
                  '\n来源：scripts/expand_course_library.py 的原 expand_text 与 seed_multidisciplinary_library.py 的 LIBRARIES；未复制任何用户文档。\n\n---\n\n')
        text = notice + raw
        path = DEST / f'{i:02d}.md'
        path.write_bytes(text.encode('utf-8'))
        item = {'key': f'legacy-{i:02d}', 'domain': domain, 'file': path.name,
                'original_name': f'{LABEL} {domain}·旧版综合资料.md',
                'old_name': f'[内置课程扩展] {domain}·五万字综合资料.md',
                'raw_sha256': sha(raw), 'sha256': sha(text), 'raw_chars': len(raw), 'chars': len(text),
                'deduplicated_chars': dedup, 'controlled_source_unique_chars': source_chars,
                'summary': f'{LABEL} 原稿{len(raw)}字符；机械去重{dedup}字符，非有效五万字；仅本地关键词检索。'}
        manifest['items'].append(item)
    (DEST / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
