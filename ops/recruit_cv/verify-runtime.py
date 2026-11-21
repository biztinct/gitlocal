"""Synthetic acceptance checks against the running private service.

Run with its RECRUIT_CV_KEY in the environment. Generates documents/images in
memory only, sends no candidate data, prints no key or raw document content.
"""
import concurrent.futures
import io
import json
import os
import time

import requests
from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

URL = os.environ.get('RECRUIT_CV_URL', 'http://127.0.0.1:18080').rstrip('/')
HEADERS = {'Authorization': 'Bearer ' + os.environ['RECRUIT_CV_KEY']}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
CASES = {
    'en': ['Synthetic Candidate', 'Work experience', 'Agronomist at Synthetic Farms', 'January 2021 - March 2025', 'Skills', 'Python SQL', 'Education', 'Bachelor of Agriculture 2020'],
    'vi': ['Ứng viên kiểm thử', 'Kinh nghiệm làm việc', 'Kỹ sư tại Synthetic Farms', 'tháng 1/2021 đến tháng 3/2025', 'Kỹ năng', 'Python SQL', 'Học vấn', 'Đại học nông nghiệp 2020'],
    'id': ['Kandidat Sintetis', 'Pengalaman kerja', 'Insinyur di Synthetic Farms', 'Januari 2021 sampai Maret 2025', 'Keahlian', 'Python SQL', 'Pendidikan', 'Sarjana Pertanian 2020'],
}
pdfmetrics.registerFont(TTFont('CVUnicode', FONT))


def document(kind, lines, pages=1):
    blob = io.BytesIO()
    if kind == 'docx':
        doc = Document()
        for line in lines:
            doc.add_paragraph(line)
        doc.save(blob)
        return blob.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if kind == 'pdf':
        page = canvas.Canvas(blob)
        for _ in range(pages):
            page.setFont('CVUnicode', 13)
            for index, line in enumerate(lines):
                page.drawString(50, 790 - index * 34, line)
            page.showPage()
        page.save()
        return blob.getvalue(), 'application/pdf'
    scan = Image.new('RGB', (1600, 1400), 'white')
    draw = ImageDraw.Draw(scan)
    font = ImageFont.truetype(FONT, 34)
    for index, line in enumerate(lines):
        draw.text((70, 60 + index * 110), line, font=font, fill='black')
    scan.save(blob, format='PNG')
    return blob.getvalue(), 'image/png'


def extract(kind, lines, pages=1):
    data, mime = document(kind, lines, pages)
    return requests.post(URL + '/extract', headers=HEADERS,
        files={'file': ('synthetic.' + kind, data, mime)},
        data={'skills': json.dumps([{'id': 1, 'name': 'Python'}, {'id': 2, 'name': 'SQL'}, {'id': 3, 'name': 'R'}])}, timeout=185)


def main():
    assert requests.get(URL + '/health', timeout=10).status_code == 401
    assert requests.get(URL + '/health', headers=HEADERS, timeout=10).json()['ready']
    results = []
    for language, lines in CASES.items():
        for kind in ('docx', 'pdf', 'png'):
            started = time.monotonic()
            response = extract(kind, lines)
            response.raise_for_status()
            result = response.json()
            assert result['contract'] == 'payobook-cv-v1'
            assert result['skill_ids'] == [1, 2], (language, kind, 'skills')
            assert '2020' in result['education'], (language, kind, 'education')
            assert result['employment'], (language, kind, 'employment')
            job = result['employment'][0]
            assert job['employer'] == 'Synthetic Farms', (language, kind, 'employer')
            assert (job['start'], job['end']) == ('2021-01', '2025-03'), (language, kind, 'dates', job['start'], job['end'])
            row = {'language': language, 'format': kind, 'seconds': round(time.monotonic()-started, 2), 'result': 'pass'}
            results.append(row)
            print(json.dumps(row), flush=True)
    # A realistic multi-page document exercises pipeline queue/memory bounds.
    response = extract('pdf', CASES['en'], pages=10)
    response.raise_for_status()
    assert response.json()['employment']
    print('Ten-page PDF: pass', flush=True)
    # Parallel arrivals must not run two conversions or leak an internal exception.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: extract('pdf', CASES['en'], pages=3).status_code, range(2)))
    assert sorted(statuses) == [200, 429], statuses
    print('Concurrent admission: one accepted, one retryable', flush=True)
    assert requests.get(URL + '/health', headers=HEADERS, timeout=10).json()['ready']
    print(json.dumps({'synthetic_cases': results, 'concurrency': statuses, 'health_after': 'ready'}))

if __name__ == '__main__':
    main()
