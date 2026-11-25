# DOCSTUDIO PDFFIX: render the same documents with whichever PDF engine this shell process finds
# first on its PATH (the run script sets PATH, nothing else changes). Nothing is stored: every
# record made here (saved report, Explorer view) is rolled back at the end.
# Env: OUT (folder for the PDFs), DB (database name), PROBE_UID (payobook QA login, default 6672).
# Prints PROBE lines: engine, per document: file, bytes.
import base64, os, traceback
from odoo.addons.base.models import ir_actions_report as IAR

OUT = os.environ['OUT']
DB = os.environ.get('DB') or env.cr.dbname
os.makedirs(OUT, exist_ok=True)


def p(*a):
    print('PROBE', *a, flush=True)


def save(name, raw):
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(raw)
    p(name, 'bytes', len(raw), 'pdf', raw[:5] == b'%PDF-')


def save_b64(name, res):
    if res.get('ok'):
        save(name, base64.b64decode(res['data']))
        if 'odoo' in (res.get('name') or '').lower():
            p(name, 'VENDOR WORD IN FILE NAME', res.get('name'))
    else:
        p(name, 'FAILED', res.get('msg'))


def step(name, fn):
    try:
        fn()
    except Exception as e:                                   # noqa: BLE001
        traceback.print_exc()
        p(name, 'ERROR', type(e).__name__, str(e)[:300])
        env.cr.rollback()


try:
    w = IAR._wkhtml()
    p('engine', w.bin, w.version, 'patched' if w.is_patched_qt else 'UNPATCHED')
except Exception as e:                                       # noqa: BLE001
    p('engine info', type(e).__name__, e)

Report = env['ir.actions.report']


def payslips():
    Slip = env['hr.payslip'].sudo()
    dom = [('state', 'in', ('done', 'verify', 'paid')), ('line_ids', '!=', False)]
    if DB == 'payobook':
        dom.append(('company_id', '=', 5))
    slips = Slip.search(dom, order='date_to desc, id desc', limit=3)
    if not slips:
        slips = Slip.search([('line_ids', '!=', False)], order='id desc', limit=3)
    p('payslip ids', slips.ids, 'scheme document', [bool(s.formula_config_id.payslip_document) if 'formula_config_id' in s else None for s in slips])
    if not slips:
        return
    themed = env.ref('pb_hr_payroll_formula.action_report_payslip_themed', raise_if_not_found=False)
    if themed:
        pdf, _x = Report.sudo()._render_qweb_pdf(themed, res_ids=slips[:1].ids)
        save('payslip_themed.pdf', pdf)
        if len(slips) > 1:
            pdf, _x = Report.sudo().with_context(pb_payrun_print=True, discard_logo_check=True)._render_qweb_pdf(
                themed, res_ids=slips.ids)
            save('payslip_run3.pdf', pdf)
    std = env.ref('om_hr_payroll.action_report_payslip', raise_if_not_found=False)
    if std:
        pdf, _x = Report.sudo()._render_qweb_pdf(std, res_ids=slips[:1].ids)
        save('payslip_standard.pdf', pdf)


def letters():
    qa = env['res.users'].browse(int(os.environ.get('PROBE_UID') or 6672)) if DB == 'payobook' else env.user
    cids = [qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=cids))
    DS = q['pb.doc.studio']
    cert = env.ref('pb_me_letters.letter_template_employment_cert', raise_if_not_found=False)
    exp = env.ref('pb_lifecycle.letter_template_experience', raise_if_not_found=False)
    people = DS.people('')
    emps = env['hr.employee'].sudo().browse([x['id'] for x in people])
    vn = emps.filtered(lambda e: e.company_id.country_id.code == 'VN')[:1] or emps[:1]
    p('letter person company country', vn.company_id.country_id.code, 'letterhead', (cert.pbds_page or {}).get('letterhead') if cert else None)
    if cert:
        save_b64('letter_cert_vi_clean.pdf', DS.sample_pdf(cert.id, {}, vn.id, 'vi_VN'))
        save_b64('letter_cert_en_clean.pdf', DS.sample_pdf(cert.id, {}, vn.id, 'en_US'))
        if DB == 'payobook':
            for font in ('classic', 'friendly', 'modern'):
                save_b64('letter_cert_vi_%s.pdf' % font, DS.sample_pdf(
                    cert.id, {'page': dict(cert.pbds_page or {}, font=font)}, vn.id, 'vi_VN'))
            save_b64('letter_cert_vi_plain_paper.pdf', DS.sample_pdf(
                cert.id, {'page': dict(cert.pbds_page or {}, letterhead=False)}, vn.id, 'vi_VN'))
    if exp and DB == 'payobook':
        base = str(exp.with_context(lang='en_US').body_html or '')
        extra = ''.join('<p><strong>Paragraph %d.</strong> This sentence checks that every word of a long '
                        'letter reaches the page, with <strong>bold words</strong> in the middle and a '
                        'plain ending word number %d.</p>' % (i, i) for i in range(1, 31))
        save_b64('letter_long_en_clean.pdf', DS.sample_pdf(exp.id, {'body': base + extra}, vn.id, 'en_US'))
        save_b64('letter_long_en_classic.pdf', DS.sample_pdf(
            exp.id, {'body': base + extra, 'page': dict(exp.pbds_page or {}, font='classic')}, vn.id, 'en_US'))
    # a letter already stored (made before this programme), printed again — nothing saved
    if DB == 'payobook':
        old = env['pb.hr.letter'].sudo().search([], order='id asc', limit=1)
        if old:
            rep = env.ref('pb_lifecycle.action_report_hr_letter', raise_if_not_found=False)
            if rep:
                pdf, _x = Report.sudo()._render_qweb_pdf(rep, res_ids=old.ids)
                save('letter_stored_lifecycle.pdf', pdf)


def contract():
    qa = env['res.users'].browse(int(os.environ.get('PROBE_UID') or 6672))
    cids = [qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=cids))
    k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False),
                                           ('company_id', '=', qa.company_id.id)], order='id', limit=1)
    if k:
        save_b64('contract_document.pdf', q['pb.contracts'].contract_document_pdf(k.id))


def reports():
    qa = env['res.users'].browse(int(os.environ.get('PROBE_UID') or 6672))
    cids = [qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=cids))
    P = q['pb.report.pdf']
    RB = q['pb.report.builder']
    ex = {e['key']: e for e in RB.examples()}
    pick = ex.get('mix') or next(iter(ex.values()))
    spec = dict(pick['spec'])
    spec['columns'] = list(spec['columns']) + [c for c in ('job', 'country_of_work', 'manager')
                                                if c not in spec['columns']]
    try:
        card = RB.save_report('PDFFIX probe', spec, False)
    except Exception:                                        # noqa: BLE001
        card = RB.save_report('PDFFIX probe', pick['spec'], False)
    o = P.open('pb.report.definition', card['id'])
    r = P.download('pb.report.definition', card['id'], o['look'])
    save_b64('report_long.pdf', r)
    p('report rows', r.get('rows'), 'seconds', r.get('seconds'), 'columns', len(o.get('columns') or []))
    sumspec = ex.get('country_contract')
    if sumspec:
        card2 = RB.save_report('PDFFIX probe short', sumspec['spec'], False)
        o2 = P.open('pb.report.definition', card2['id'])
        save_b64('report_short.pdf', P.download('pb.report.definition', card2['id'], o2['look']))
        look = dict(o2['look'], letterhead=False) if 'letterhead' in o2['look'] else None
        if look:
            save_b64('report_short_plain_paper.pdf', P.download('pb.report.definition', card2['id'], look))
    v = q['pb.explorer.view'].pbx_save('PDFFIX probe view', {'measure': 'net', 'dimension': 'department_id'}, False)
    ov = P.open('pb.explorer.view', v['id'])
    save_b64('explorer.pdf', P.download('pb.explorer.view', v['id'], ov['look']))


try:
    step('payslips', payslips)
    step('letters', letters)
    if DB == 'payobook':
        step('contract', contract)
        step('reports', reports)
finally:
    env.cr.rollback()
    p('rolled back')
