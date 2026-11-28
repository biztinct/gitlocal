# DOCSTUDIO close-out D: which set of roles lets a person READ a contract (and so print its document)
# but NOT file documents? Throw-away logins made inside the transaction, ROLLED BACK (none left).
# payobook only. Prints PROBE lines only.
import base64
def p(*a): print('PROBE', *a)
CANDS = [
    ('records desk view', ['pb_records.group_records_viewer']),
    ('records desk view + payroll officer', ['pb_records.group_records_viewer', 'pb_hr_payroll_base.group_payroll_base_officer']),
    ('employee manager (contracts)', ['hr_contract.group_hr_contract_employee_manager']),
    ('demo visitor group', ['pb_demo.group_payobook_demo']),
]
try:
    comp = env['res.company'].browse(5)
    k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False), ('company_id', '=', 5)], order='id', limit=1)
    # the existing demo visitor login (uid 8), as it is
    env.cr.execute('SAVEPOINT vo0')
    try:
        dv = env['res.users'].browse(8)
        e = env(user=8, context=dict(env.context, allowed_company_ids=dv.company_ids.ids))
        C = e['pb.contracts']; d = C.contract_document(k.id); pdf = C.contract_document_pdf(k.id) if d.get('ok') else {}
        p('existing demo visitor uid 8 | active', dv.active, 'read contract', e['hr.contract'].has_access('read'), 'button', C.contract_document_available(k.id),
          'preview', d.get('ok'), 'can_file', d.get('can_file'), 'pay blocked', d.get('pay_blocked'),
          'download', bool(pdf.get('ok')) and base64.b64decode(pdf['data'])[:5] == b'%PDF-', 'msg', (d.get('msg') or d.get('file_msg') or '')[:90])
    except Exception as ex:
        p('demo visitor ERROR', type(ex).__name__, str(ex)[:150])
    finally:
        env.cr.execute('ROLLBACK TO SAVEPOINT vo0')
    for i, (label, groups) in enumerate(CANDS):
        env.cr.execute('SAVEPOINT vo')
        try:
            gids = [env.ref('base.group_user').id] + [env.ref(g).id for g in groups if env.ref(g, raise_if_not_found=False)]
            u = env['res.users'].with_context(no_reset_password=True).create({
                'name': 'DEMO CD view-only probe', 'login': 'demo.cd.viewonly.%d@example.invalid' % i,
                'company_id': comp.id, 'company_ids': [(6, 0, [comp.id])], 'group_ids': [(6, 0, gids)]})
            e = env(user=u.id, context=dict(env.context, allowed_company_ids=[comp.id]))
            C = e['pb.contracts']
            av = C.contract_document_available(k.id)
            d = C.contract_document(k.id)
            pdf = C.contract_document_pdf(k.id) if d.get('ok') else {}
            p(label, '| read contract', e['hr.contract'].has_access('read'), 'button', av, 'preview', d.get('ok'),
              'can_file', d.get('can_file'), 'pay blocked', d.get('pay_blocked'),
              'download', bool(pdf.get('ok')) and base64.b64decode(pdf['data'])[:5] == b'%PDF-',
              'msg', (d.get('msg') or d.get('file_msg') or '')[:90])
        except Exception as ex:
            p(label, 'ERROR', type(ex).__name__, str(ex)[:150])
        finally:
            env.cr.execute('ROLLBACK TO SAVEPOINT vo')
finally:
    env.cr.rollback()
    p('rolled back')
