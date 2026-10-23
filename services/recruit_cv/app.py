"""Private CV extraction service. No document storage and no external AI calls."""
import hmac
import io
import json
import os
import re
import zipfile
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

CONTRACT = 'payobook-cv-v1'
MAX_BYTES = 5 * 1024 * 1024
_converter = None
_nlp = None
_lock = Lock()


@asynccontextmanager
async def lifespan(app):
    global _converter, _nlp
    if len(os.environ.get('RECRUIT_CV_KEY', '')) < 32:
        raise RuntimeError('Set RECRUIT_CV_KEY to a random value of at least 32 characters')
    from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    import spacy
    options = PdfPipelineOptions(do_ocr=True, generate_parsed_pages=True)
    _converter = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.IMAGE],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                        InputFormat.IMAGE: ImageFormatOption(pipeline_options=options)})
    _converter.initialize_pipeline(InputFormat.PDF)
    _nlp = spacy.blank('xx')
    yield


app = FastAPI(title='Payobook CV extraction', lifespan=lifespan, docs_url=None, redoc_url=None)


def authorize(header):
    expected = os.environ.get('RECRUIT_CV_KEY', '')
    if not expected or not hmac.compare_digest(header or '', 'Bearer ' + expected):
        raise HTTPException(401, 'Unauthorized')


def document_text(result):
    """Recover physical lines only when they preserve Docling's reading order.

    The layout model can combine a simple CV into one paragraph. Parsed OCR/PDF
    line cells retain its section boundaries. Never substitute cell order for
    the model's reading order when columns/tables make the two disagree.
    """
    text = result.document.export_to_text(traverse_pictures=True)
    lines = '\n'.join(cell.text for page in result.pages for cell in page.cells if cell.text.strip())
    normalise = lambda value: re.sub(r'\s+', ' ', value).strip()
    return lines if lines and normalise(lines) == normalise(text) else text


def structure(text, skills, nlp):
    """Evidence-led extraction; unrecognised employment stays reviewable text.

    No demographic inference, ranking or automatic suitability decisions.
    Skill matches use exact token phrases, not substring matches (R vs HR).
    """
    from spacy.matcher import PhraseMatcher
    matcher = PhraseMatcher(nlp.vocab, attr='LOWER')
    vocabulary = {str(s['id']): str(s['name']) for s in skills if s.get('name')}
    for key, name in vocabulary.items():
        matcher.add(key, [nlp.make_doc(name)])
    document = nlp(text[:200000])
    matched = sorted({int(nlp.vocab.strings[match]) for match, _, _ in matcher(document)})
    sections = {'experience': [], 'education': []}
    section = None
    headings = {
        'experience': r'^(work experience|professional experience|employment(?: history)?|experience|kinh nghiệm(?: làm việc)?|pengalaman(?: kerja)?)\s*[:：]?$',
        'education': r'^(education|qualifications|học vấn|trình độ học vấn|pendidikan)\s*[:：]?$',
    }
    for raw in text.splitlines():
        line = raw.strip(' #\t')
        found = next((key for key, pattern in headings.items() if re.match(pattern, line, re.I)), None)
        if found:
            section = found
        elif re.match(r'^(skills|languages|references|certifications|kỹ năng|keahlian)\s*:?', line, re.I):
            section = None
        elif section and line:
            sections[section].append(line)
    return {'text': text[:200000], 'skill_ids': matched,
            'experience': '\n'.join(sections['experience'])[:20000],
            'education': '\n'.join(sections['education'])[:10000],
            'review_note': 'Review extracted sections and skill matches against the original CV. Missing sections are left blank.'}


@app.get('/health')
def health(authorization: str = Header(default='')):
    authorize(authorization)
    return {'contract': CONTRACT, 'ready': bool(_converter and _nlp)}


@app.post('/extract')
def extract(file: UploadFile = File(...), skills: str = Form('[]'), authorization: str = Header(default='')):
    authorize(authorization)
    if not _lock.acquire(blocking=False):
        raise HTTPException(429, 'Another CV is being processed. Try again shortly.')
    try:
        data = file.file.read(MAX_BYTES + 1)
        suffix = os.path.splitext(file.filename or '')[1].lower()
        if len(data) > MAX_BYTES or suffix not in ('.pdf', '.docx', '.png', '.jpg', '.jpeg'):
            raise HTTPException(422, 'Use a PDF, DOCX or image of at most 5 MB.')
        if suffix == '.docx':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = archive.infolist()
                if len(members) > 2000 or sum(m.file_size for m in members) > 40 * 1024 * 1024:
                    raise HTTPException(422, 'This Word document is too large when expanded.')
        try:
            vocabulary = json.loads(skills)
            if not isinstance(vocabulary, list) or len(vocabulary) > 5000 or any(
                not isinstance(s, dict) or not isinstance(s.get('id'), int) or
                not isinstance(s.get('name'), str) or len(s['name']) > 500 for s in vocabulary):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid skill vocabulary') from None
        from docling.datamodel.base_models import DocumentStream
        result = _converter.convert(DocumentStream(name='cv' + suffix, stream=io.BytesIO(data)),
                                    max_num_pages=30, max_file_size=MAX_BYTES)
        text = document_text(result)
        if not text.strip():
            raise HTTPException(422, 'No readable text was found. Review the original document.')
        return {'contract': CONTRACT, **structure(text, vocabulary, _nlp)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'The CV could not be processed. Review the original document.') from None
    finally:
        _lock.release()
        file.file.close()
