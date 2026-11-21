# FS-16 files probe (odoo-bin shell, REHEARSAL COPIES or local copies; writes nothing that stays:
# rollback at the end). Hashes only — never a name, value or account number.
#   * the Vietnam social-insurance participant list (BHXHDSTK01-DV_595) and the joiners report
#     (TangLaoDong) for this month and last month: md5 of every sheet's cells (the xlsx's own
#     creation time is left out);
#   * one bank file per pay run (the latest 6 runs with paid people): md5 of the file's content
#     (for an xlsx: of every sheet's cells).
import datetime
import hashlib
import io
import json
import zipfile

from dateutil.relativedelta import relativedelta


def md5(b):
    return hashlib.md5(b).hexdigest()[:12]


def xlsx_cells(data):
    """md5 of the workbook's own parts (sheets, shared strings, styles), never its docProps."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return md5(data)
    h = hashlib.md5()
    for name in sorted(z.namelist()):
        if name.startswith('docProps/'):
            continue
        h.update(name.encode())
        h.update(z.read(name))
    return h.hexdigest()[:12]


out = {}
admin = env.ref('base.user_admin')
e = env(user=admin.id, context={'allowed_company_ids': admin.company_ids.ids})
vn_companies = env['res.company'].sudo().search([]).filtered(lambda c: c.country_id.code == 'VN')

# ---- social insurance reports
if 'pb.govt.report.wizard' in env:
    today = datetime.date.today().replace(day=1)
    for company in vn_companies:
        for months_back in (0, 1):
            start = today - relativedelta(months=months_back)
            end = start + relativedelta(months=1, days=-1)
            for kind, ref in (('bhxhdstk01', 'pb_hr_govt.report_bhxhdstk01_xlsx'),
                              ('tang_ld', 'pb_hr_govt.report_tang_ld_xlsx')):
                key = 'si %s c%s %s' % (kind, company.id, start.strftime('%Y-%m'))
                try:
                    with env.cr.savepoint():
                        wiz = e['pb.govt.report.wizard'].with_company(company).create({
                            'company_id': company.id, 'report_type': kind,
                            'date_from': start, 'date_to': end})
                        report = env.ref(ref)
                        data, _fmt = e['ir.actions.report'].with_company(company)._render_xlsx(
                            report.report_name, wiz.ids, data=None) if hasattr(
                            e['ir.actions.report'], '_render_xlsx') else report._render(wiz.ids)
                        out[key] = xlsx_cells(data)
                except Exception as exc:                # noqa: BLE001
                    out[key] = 'ERR %s %s' % (type(exc).__name__, str(exc)[:80])
else:
    out['si'] = 'not installed'

# ---- one bank file per pay run
if 'vietnam.bank.export.wizard' in env:
    Wiz = e['vietnam.bank.export.wizard']
    runs = env['hr.payslip.run'].sudo().search([], order='id desc', limit=40)
    made = 0
    for run in runs:
        if made >= 6:
            break
        slips = run.slip_ids.filtered(lambda s: s.state in ('done', 'paid'))
        if not slips:
            continue
        key = 'bankfile run %s' % run.id
        try:
            with env.cr.savepoint():
                wiz = Wiz.with_company(run.company_id).create({
                    'payslip_run_id': run.id, 'payslip_ids': [(6, 0, slips.ids)],
                    'bank_format': 'generic'})
                res = wiz._generate()
                import base64
                data = base64.b64decode(res['file_b64'])
                out[key] = '%s rows-left-out %s' % (xlsx_cells(data) if data[:2] == b'PK' else md5(data),
                                                    len(res.get('excluded') or []))
                made += 1
        except Exception as exc:                        # noqa: BLE001
            out[key] = 'ERR %s %s' % (type(exc).__name__, str(exc)[:80])
            made += 1
else:
    out['bankfile'] = 'not installed'

print('FILES _seen = Vietnam companies %s, pay runs %s' % (len(vn_companies), env['hr.payslip.run'].sudo().search_count([])))
for k in sorted(out):
    print('FILES %s = %s' % (k, out[k]))
env.cr.rollback()
