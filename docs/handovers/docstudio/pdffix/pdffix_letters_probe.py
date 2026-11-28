# DOCSTUDIO PDFFIX phase 2: every shipped letter wording x 4 fonts x en/vi through the designer's
# "sample PDF" (nothing filed), on the engine this process finds first on PATH. With CURE=1 the
# space cure (doc_common.pdf_body + pre-wrap) is patched in for this process only. Rolled back.
# Env: OUT, CURE, DC (path to the new doc_common.py when CURE=1)
import base64, os, importlib.util
from markupsafe import Markup
OUT = os.environ['OUT']; os.makedirs(OUT, exist_ok=True)
if os.environ.get('CURE') == '1':
    spec = importlib.util.spec_from_file_location('pdffix_dc', os.environ['DC'])
    dc = importlib.util.module_from_spec(spec); spec.loader.exec_module(dc)
    from odoo.addons.pb_doc_studio.models import doc_studio as ds, doc_report as dr
    ds.PAGE_CSS = ds.PAGE_CSS + "\n.pbds-pdf .pbds-body { white-space: pre-wrap; }\n"
    orig = dr.ReportDocLetter._get_report_values

    def patched(self, docids, data=None):
        v = orig(self, docids, data)
        v['pages'] = [dict(p, body=dc.pdf_body(p.get('body'))) for p in v['pages']]
        return v
    dr.ReportDocLetter._get_report_values = patched
    print('PROBE cure patched in', flush=True)
try:
    qa = env['res.users'].browse(6672)
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=[qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]))
    DS = q['pb.doc.studio']
    emps = env['hr.employee'].sudo().browse([x['id'] for x in DS.people('')])
    vn = emps.filtered(lambda e: e.company_id.country_id.code == 'VN')[:1] or emps[:1]
    tmpls = env['pb.letter.template'].sudo().search([('company_id', '=', False)], order='id')
    for t in tmpls:
        for font in ('clean', 'friendly', 'modern', 'classic'):
            for lang in ('en_US', 'vi_VN'):
                try:
                    r = DS.sample_pdf(t.id, {'page': dict(t.pbds_page or {}, font=font)}, vn.id, lang)
                except Exception as e:                       # noqa: BLE001
                    print('PROBE', t.id, font, lang, 'skip', type(e).__name__, flush=True); env.cr.rollback(); continue
                if r.get('ok'):
                    open(os.path.join(OUT, 't%d_%s_%s.pdf' % (t.id, font, lang[:2])), 'wb').write(base64.b64decode(r['data']))
                else:
                    print('PROBE', t.id, font, lang, 'refused', r.get('msg'), flush=True)
    print('PROBE templates', len(tmpls), flush=True)
finally:
    env.cr.rollback(); print('PROBE rolled back')
