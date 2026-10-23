"""Run with python -m unittest discover -s services/recruit_cv.

Set RECRUIT_CV_INTEGRATION=1 to load Docling and exercise synthetic PDF/DOCX
and scanned-image CVs. No real candidate data is used.
"""
import io
import os
import unittest
import zipfile
from types import SimpleNamespace
import spacy
from fastapi.testclient import TestClient
import app as service


class ExtractionContract(unittest.TestCase):
    def test_line_recovery_preserves_reading_order(self):
        cells = [SimpleNamespace(text=line) for line in ['Experience', 'Acme', 'Education', 'BSc']]
        document = SimpleNamespace(export_to_text=lambda **kwargs: 'Experience Acme Education BSc')
        result = SimpleNamespace(document=document, pages=[SimpleNamespace(cells=cells)])
        self.assertEqual(service.document_text(result), 'Experience\nAcme\nEducation\nBSc')
        result.pages[0].cells = list(reversed(cells))
        self.assertEqual(service.document_text(result), 'Experience Acme Education BSc')

    def test_skill_token_boundaries_and_sections(self):
        nlp = spacy.blank('xx')
        result = service.structure('Experience\nAcme 2021–2025\nSkills\nHR and Python\nEducation\nBSc 2020',
            [{'id':1,'name':'R'},{'id':2,'name':'Python'}], nlp)
        self.assertEqual(result['skill_ids'],[2])
        self.assertEqual(result['experience'],'Acme 2021–2025')
        self.assertEqual(result['education'],'BSc 2020')

    def test_vietnamese_and_indonesian_sections(self):
        for text in ['Kinh nghiệm làm việc\nAcme\nHọc vấn\nUniversity',
                     'Pengalaman kerja\nAcme\nPendidikan\nUniversity']:
            result = service.structure(text,[],spacy.blank('xx'))
            self.assertEqual(result['experience'],'Acme')
            self.assertEqual(result['education'],'University')

    def test_missing_sections_are_blank(self):
        result=service.structure('No section headings here',[],spacy.blank('xx'))
        self.assertEqual(result['experience'],'')
        self.assertEqual(result['education'],'')

    def test_health_requires_key(self):
        os.environ['RECRUIT_CV_KEY']='synthetic-service-test-key-at-least-32'
        client=TestClient(service.app)
        self.assertEqual(client.get('/health').status_code,401)
        self.assertEqual(client.get('/health',headers={'Authorization':'Bearer incorrect'}).status_code,401)


@unittest.skipUnless(os.environ.get('RECRUIT_CV_INTEGRATION') == '1','Enable synthetic document integration tests explicitly')
class SyntheticDocuments(unittest.TestCase):
    def test_pdf_docx_and_scan(self):
        from reportlab.pdfgen import canvas
        from docx import Document
        from PIL import Image, ImageDraw, ImageFont
        os.environ['RECRUIT_CV_KEY']='synthetic-service-test-key-at-least-32'
        words=['Synthetic Candidate','Work experience','Acme Developer 2021 - 2025',
               'Skills','Python SQL','Education','Bachelor of Science 2020']
        pdf=io.BytesIO(); page=canvas.Canvas(pdf)
        y=780
        for line in words: page.drawString(60,y,line); y-=32
        page.save()
        doc=Document()
        for line in words: doc.add_paragraph(line)
        docx=io.BytesIO(); doc.save(docx)
        scan=Image.new('RGB',(1600,1200),'white'); draw=ImageDraw.Draw(scan)
        font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',36) if os.path.exists('/System/Library/Fonts/Supplemental/Arial.ttf') else ImageFont.load_default(size=36)
        for index,line in enumerate(words): draw.text((80,80+index*100),line,font=font,fill='black')
        png=io.BytesIO(); scan.save(png,format='PNG')
        with TestClient(service.app) as client:
            headers={'Authorization':'Bearer '+os.environ['RECRUIT_CV_KEY']}
            self.assertTrue(client.get('/health',headers=headers).json()['ready'])
            for filename,data,mime in [('cv.pdf',pdf.getvalue(),'application/pdf'),('cv.docx',docx.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),('cv.png',png.getvalue(),'image/png')]:
                response=client.post('/extract',headers=headers,files={'file':(filename,data,mime)},data={'skills':'[{"id":1,"name":"Python"},{"id":2,"name":"SQL"}]'})
                self.assertEqual(response.status_code,200,response.text)
                result=response.json()
                self.assertEqual(result['contract'],'payobook-cv-v1')
                self.assertIn(1,result['skill_ids'],filename)
                self.assertIn('Acme',result['experience'],filename + ': ' + repr(result['text']))
                self.assertIn('2020',result['education'],filename)
                print('Synthetic extraction passed:',filename,flush=True)
            invalid=client.post('/extract',headers=headers,files={'file':('bad.exe',b'invalid','application/octet-stream')})
            self.assertEqual(invalid.status_code,422)
