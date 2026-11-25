# DOCSTUDIO PDFFIX phase 2: every PDF report of our modules, one record each, with whichever engine
# this process finds on PATH. Rolled back; nothing stored. Env: OUT. Prints PROBE <report> <pages|skip>.
import os, io
from PyPDF2 import PdfReader
OUT = os.environ['OUT']; os.makedirs(OUT, exist_ok=True)
SKIP = {'pb_report_pdf.report_table', 'pb_doc_studio.report_doc_letter'}   # proven in phase 1
R = env['ir.actions.report'].sudo()
reps = R.search([('report_type', '=', 'qweb-pdf')])
for rep in reps:
    xid = rep.get_external_id().get(rep.id, '')
    mod = xid.split('.')[0]
    if not mod.startswith(('pb', 'om', 'biz')) or rep.report_name in SKIP:
        continue
    try:
        Model = env[rep.model].sudo()
        rec = Model.search([], order='id desc', limit=1) if Model._auto else Model.browse()
        if not rec:
            print('PROBE', xid, 'skip no record', flush=True); continue
        with env.cr.savepoint():
            pdf, _x = R._render_qweb_pdf(rep, res_ids=rec.ids)
        n = len(PdfReader(io.BytesIO(pdf)).pages)
        open(os.path.join(OUT, xid.replace('.', '__') + '.pdf'), 'wb').write(pdf)
        print('PROBE', xid, rep.model, rec.id, 'pages', n, flush=True)
    except Exception as e:                                   # noqa: BLE001
        print('PROBE', xid, 'skip', type(e).__name__, str(e)[:120].replace('\n', ' '), flush=True)
env.cr.rollback(); print('PROBE rolled back')
