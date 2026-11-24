# DOCSTUDIO W2: owner ruling "view-only people on a contract can download but not file", on live payobook,
# with a throw-away login made inside the transaction for each candidate role and ROLLED BACK (no login
# is left behind). Prints PROBE lines only.
import base64
def p(*a): print('PROBE', *a)
try:
    comp = env['res.company'].browse(5)
    k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False), ('company_id', '=', 5)], order='id', limit=1)
    for label, groups in (('payroll officer only', ['pb_hr_payroll_base.group_payroll_base_officer']),
                          ('HR officer only', ['hr.group_hr_user'])):
        gids = [env.ref('base.group_user').id] + [env.ref(g).id for g in groups]
        u = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO W2 view-only probe', 'login': 'demo.w2.viewonly.%s@example.invalid' % len(label),
            'company_id': comp.id, 'company_ids': [(6, 0, [comp.id])], 'group_ids': [(6, 0, gids)]})
        e = env(user=u.id, context=dict(env.context, allowed_company_ids=[comp.id]))
        C = e['pb.contracts']
        d = C.contract_document(k.id)
        pdf = C.contract_document_pdf(k.id)
        sv = C.contract_document_save(k.id)
        p(label, 'button', C.contract_document_available(k.id), 'preview', d.get('ok'), 'can_file', d.get('can_file'),
          'file message', bool(d.get('file_msg')), 'pay blocked', d.get('pay_blocked'),
          'download', pdf.get('ok') and base64.b64decode(pdf['data'])[:5] == b'%PDF-' or pdf.get('msg'),
          'filing refused', not sv.get('ok'), (sv.get('msg') or '')[:90])
finally:
    env.cr.rollback()
    p('rolled back')
