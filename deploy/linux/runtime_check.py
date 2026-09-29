"""Real OCR, PDF/DOCX, keyword and controlled-content checks (no network)."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--build', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
with tempfile.TemporaryDirectory(prefix='studymind-runtime-') as tmp:
    # Do not touch a deployed database or read backend/.env during this probe.
    os.environ.update(STUDYMIND_TESTING='1', STUDYMIND_DATA_DIR=tmp,
                      STUDYMIND_BUNDLE_ROOT=str(root), EMBEDDING_MODE='keyword')
    os.environ.pop('TEST_DATABASE_URL', None)
    from app.default_content import _manifest, _controlled_documents
    from app.legacy_content import manifest
    bank = _manifest()
    assert len(_controlled_documents()) == 24
    assert len(manifest()['items']) == 7
    from app.document.parser import ocr_image, extract
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not font_path.exists():
        font_path = Path('C:/Windows/Fonts/arial.ttf')
    image = Image.new('RGB', (900, 160), 'white')
    ImageDraw.Draw(image).text((30, 40), 'STUDYMIND 2026', font=ImageFont.truetype(str(font_path), 54), fill='black')
    recognized = ocr_image(image)
    assert 'STUDYMIND' in recognized.upper().replace(' ', ''), repr(recognized)
    import pymupdf
    pdf = pymupdf.open()
    pdf.new_page().insert_text((30, 40), 'StudyMind PDF verification')
    pdf_path = Path(tmp) / 'probe.pdf'
    pdf.save(pdf_path)
    pdf.close()
    assert 'StudyMind' in extract(pdf_path, '.pdf')[0].text
    from docx import Document
    doc = Document()
    doc.add_paragraph('StudyMind DOCX verification')
    doc_path = Path(tmp) / 'probe.docx'
    doc.save(doc_path)
    assert 'StudyMind' in extract(doc_path, '.docx')[0].text
    from sklearn.feature_extraction.text import HashingVectorizer
    assert HashingVectorizer(analyzer='char', ngram_range=(2, 4)).transform(['学习知识']).nnz > 0
    print(json.dumps({'runtime': sys.platform, 'ocr': recognized, 'pdf': 'pass',
                      'docx': 'pass', 'keyword': 'pass', 'subjects': len(bank),
                      'questions': sum(map(len, bank.values())), 'legacy_manifests': 'pass'}))
