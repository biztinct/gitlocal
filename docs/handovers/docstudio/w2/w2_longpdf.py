# DOCSTUDIO W2: page-by-page check of the long report PDF the QA login made in the browser walk
# (saved built report id from env RID), made again here as the QA login; nothing stored; rolled back.
import base64, io, os, re
from PyPDF2 import PdfReader
try:
    qa = env['res.users'].browse(6672)
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=[qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]))
    P = q['pb.report.pdf']; rid = int(os.environ['RID'])
    o = P.open('pb.report.definition', rid)
    r = P.download('pb.report.definition', rid, o['look'])
    raw = base64.b64decode(r['data'])
    pages = [re.sub(r'\s+', ' ', p.extract_text() or '') for p in PdfReader(io.BytesIO(raw)).pages]
    nums = [len(re.findall(r'Page \d+ of \d+', t)) for t in pages]
    print('PROBE rows', r['rows'], 'pages', len(pages), 'seconds', r['seconds'],
          'pages with rows', sum(1 for t in pages if len(t) > 400),
          'pages with exactly one page number', sum(1 for n in nums if n == 1),
          'pages with Printed on', sum(1 for t in pages if 'Printed on' in t),
          'shortest page chars', min(len(t) for t in pages))
    open(os.environ.get('OUT','/tmp/w2_long.pdf'),'wb').write(raw)
    print('PROBE tail p1', pages[0][-160:])
finally:
    env.cr.rollback()
