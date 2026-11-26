# DOCSTUDIO close-out D: the "download only, cannot file" guard of the contract panel on the LIVE code,
# with synthetic users made inside the transaction and ROLLED BACK (nothing left). payobook only.
#  A  a synthetic HR officer reads the contract, may file (today's roles), and a no-role user is refused
#     (A2 test 11 shape);
#  B  the same HR officer with document CREATE taken away for every group they hold (inside the
#     transaction): the sheet says can_file False with the sentence, download works, and the server
#     method contract_document_save REFUSES (A2's read-only reader path);
#  C  the sample-wording note never in the PDF (A2 test 16 shape).
import base64
from odoo.exceptions import UserError
def p(*a): print('PROBE', *a)
try:
    comp = env['res.company'].browse(5)
    k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False), ('company_id', '=', 5)], order='id', limit=1)
    def mk(login, groups):
        gids = [env.ref('base.group_user').id] + [env.ref(g).id for g in groups]
        return env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO CD guard ' + login, 'login': 'demo.cd.guard.%s@example.invalid' % login,
            'company_id': comp.id, 'company_ids': [(6, 0, [comp.id])], 'group_ids': [(6, 0, gids)]})
    hr = mk('hr', ['hr.group_hr_user', 'hr_contract.group_hr_contract_manager'])
    nobody = mk('nobody', [])
    # a reader who may also see pay (so the download is not blocked by the pay rule)
    pr = mk('pay', ['pb_hr_payroll_base.group_payroll_base_officer', 'hr_contract.group_hr_contract_manager', 'om_hr_payroll.group_hr_payroll_manager'])
    P = lambda u: env(user=u.id, context=dict(env.context, allowed_company_ids=[comp.id]))['pb.contracts']
    # A
    d = P(hr).contract_document(k.id)
    try:
        P(nobody).contract_document(k.id); nob = 'NOT refused'
    except UserError as e:
        nob = 'refused (%s)' % str(e)[:70]
    p('A hr officer: button', P(hr).contract_document_available(k.id), 'preview', d.get('ok'), 'can_file', d.get('can_file'),
      '| no-role user', nob, 'button', P(nobody).contract_document_available(k.id))
    # B
    acc = env['ir.model.access'].sudo().search([('model_id.model', '=', 'pb.employee.document'), ('perm_create', '=', True),
                                                ('group_id', 'in', pr.all_group_ids.ids)])
    p('B document create rows held by the reader', len(acc), ', '.join(sorted(set(a.name for a in acc))))
    acc.write({'perm_create': False})
    env.registry.clear_cache()
    env.invalidate_all()
    d2 = P(pr).contract_document(k.id)
    pdf = P(pr).contract_document_pdf(k.id)
    sv = P(pr).contract_document_save(k.id)
    p('B read-only reader: preview', d2.get('ok'), 'can_file', d2.get('can_file'), 'sentence', (d2.get('file_msg') or '')[:90],
      '| download', bool(pdf.get('ok')) and base64.b64decode(pdf['data'])[:5] == b'%PDF-',
      '| server filing refused', not sv.get('ok'), (sv.get('msg') or '')[:90])
    # C
    pdf_txt = base64.b64decode(pdf['data']) if pdf.get('ok') else b''
    try:
        from PyPDF2 import PdfReader
        import io
        txt = ' '.join((pg.extract_text() or '') for pg in PdfReader(io.BytesIO(pdf_txt)).pages)
    except Exception as e:
        txt = 'unreadable %s' % e
    p('C sample note on screen', d2.get('sample_wording'), '| in the PDF', any(w in txt for w in ('Sample wording', 'lawyer', 'Nội dung mẫu', 'luật sư')))
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:200])
finally:
    env.cr.rollback()
    env.registry.clear_cache()
    p('rolled back')
