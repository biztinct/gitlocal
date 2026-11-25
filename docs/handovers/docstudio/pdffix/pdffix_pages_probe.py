# DOCSTUDIO PDFFIX-2: page counts of every shipped wording (en + vi) and a real contract document,
# in one of three modes, nothing stored (rolled back):
#   MODE=base  - the code as it was before the switch (phase-1/2 PDF changes taken out in-process),
#                run it with the OLD engine on PATH;
#   MODE=live  - the code as it is live;
#   MODE=fix   - the new code: DC (doc_common.py), DR (doc_report.py values), TPL (doc_report.xml
#                templates page_frame + report_doc_letter swapped in), DPI ('' or a number).
import base64, io, os, importlib.util
from markupsafe import Markup
from lxml import etree
from PyPDF2 import PdfReader
OUT = os.environ['OUT']; os.makedirs(OUT, exist_ok=True)
MODE = os.environ['MODE']
from odoo.addons.pb_doc_studio.models import doc_studio as ds, doc_report as dr
orig = dr.ReportDocLetter._get_report_values
if MODE == 'base':
    ds.PAGE_CSS = ds.PAGE_CSS.replace('.pbds-pdf .pbds-body { white-space: pre-wrap; }', '')
    def patched(self, docids, data=None):
        v = orig(self, docids, data)
        v.pop('data_report_margin_top', None); v.pop('data_report_header_spacing', None)
        raw = (data or {}).get('pbds_sample')
        if raw:
            v['pages'] = raw
        return v
    dr.ReportDocLetter._get_report_values = patched
elif MODE == 'fix':
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    dc = load('pdffix_dc', os.environ['DC'])
    ds.PAGE_CSS = ds.PAGE_CSS + '\n.pbds-pdf .pbds-keep { page-break-inside: avoid; }\n'
    DPI = os.environ.get('DPI')
    def patched(self, docids, data=None):
        raw = (data or {}).get('pbds_sample')
        v = orig(self, docids, data)
        src = raw or v['pages']
        out = []
        for p in src:
            head, tail = dc.pdf_split(p.get('body'))
            out.append(dict(p, body=head, body_tail=tail))
        v['pages'] = out
        if DPI == 'contract':
            if any('pbdc-' in '%s%s' % (p.get('body') or '', p.get('body_tail') or '') for p in out):
                v['data_report_dpi'] = 100
        elif DPI:
            v['data_report_dpi'] = int(DPI)
        return v
    dr.ReportDocLetter._get_report_values = patched
    root = etree.parse(os.environ['TPL']).getroot()
    for tid in ('page_frame', 'report_doc_letter'):
        node = next(t for t in root.iter('template') if t.get('id') == tid)
        arch = etree.Element('t', {'t-name': 'pb_doc_studio.' + tid}); arch.text = node.text
        for c in node:
            arch.append(c)
        env.ref('pb_doc_studio.' + tid).sudo().write({'arch_db': etree.tostring(arch, encoding='unicode')})
    env.registry.clear_cache('templates')


def info(raw):
    pages = PdfReader(io.BytesIO(raw)).pages
    last = ' '.join((pages[-1].extract_text() or '').split())
    return len(pages), len(last), last[:60]


try:
    qa = env['res.users'].browse(6672) if env.cr.dbname == 'payobook' else env.user
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=[qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]))
    DS = q['pb.doc.studio']
    emps = env['hr.employee'].sudo().browse([x['id'] for x in DS.people('')])
    vn = emps.filtered(lambda e: e.company_id.country_id.code == 'VN')[:1] or emps[:1]
    for t in env['pb.letter.template'].sudo().search([('company_id', '=', False)], order='id'):
        for lang in ('en_US', 'vi_VN'):
            try:
                with env.cr.savepoint():
                    r = DS.sample_pdf(t.id, {}, vn.id, lang)
            except Exception:                                # noqa: BLE001
                offs = DS.offers('') if hasattr(DS, 'offers') else []
                try:
                    with env.cr.savepoint():
                        r = DS.sample_pdf(t.id, {}, offs[0]['id'], lang) if offs else {}
                except Exception as e:                       # noqa: BLE001
                    print('PROBE', t.id, lang, 'skip', type(e).__name__, flush=True); continue
            if not r.get('ok'):
                print('PROBE', t.id, lang, 'refused', flush=True); continue
            raw = base64.b64decode(r['data'])
            open(os.path.join(OUT, 't%d_%s.pdf' % (t.id, lang[:2])), 'wb').write(raw)
            n, lc, lt = info(raw)
            print('PROBE t%d %s %s pages %d lastpage_chars %d | %s' % (t.id, lang[:2], (t.with_context(lang='en_US').name or '')[:28], n, lc, lt), flush=True)
    exp = env.ref('pb_lifecycle.letter_template_experience', raise_if_not_found=False)
    if exp:
        base = str(exp.with_context(lang='en_US').body_html or '')
        extra = ''.join('<p><strong>Paragraph %d.</strong> This sentence checks that every word of a long '
                        'letter reaches the page, with <strong>bold words</strong> in the middle and a '
                        'plain ending word number %d.</p>' % (i, i) for i in range(1, 31))
        r = DS.sample_pdf(exp.id, {'body': base + extra}, vn.id, 'en_US')
        if r.get('ok'):
            raw = base64.b64decode(r['data']); open(os.path.join(OUT, 'long_letter.pdf'), 'wb').write(raw)
            print('PROBE long_letter pages %d lastpage_chars %d | %s' % info(raw), flush=True)
    if 'pb.contracts' in env:
        for k in env['hr.contract'].sudo().search([('state', '=', 'open'), ('company_id', '=', qa.company_id.id)], order='id', limit=1):
            r = q['pb.contracts'].contract_document_pdf(k.id)
            if r.get('ok'):
                raw = base64.b64decode(r['data']); open(os.path.join(OUT, 'contract_real.pdf'), 'wb').write(raw)
                print('PROBE contract_real pages %d lastpage_chars %d | %s' % info(raw), flush=True)
finally:
    env.cr.rollback(); print('PROBE rolled back')
