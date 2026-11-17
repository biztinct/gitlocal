# -*- coding: utf-8 -*-
"""WDGAP DM1 — look-only check of the Renew dialog for the DM1 demo contracts.

Runs AS THE QA LOGIN (uid from DM1_QA_UID, default 6672 on payobook) inside
`odoo-bin shell`, no password used, and ROLLS BACK at the end: nothing is
saved. For each DM1 contract it opens the contract the way the Contracts
screen does (`pb.contracts.get_contract_detail`), checks "Renew" is offered,
and asks the Renew dialog for its ready-filled values (`get_defaults`).

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < dm1_qa_check.py
"""
import os

EXPECT = {
    'DEMO Nguyễn Thu Hà': ('definite', 'permanent'),
    'DEMO Trần Minh Quân': ('definite', 'permanent'),
    'DEMO Lê Ngọc Lan': ('definite', ''),
    'DEMO Phạm Quang Huy': ('definite', ''),
    'DEMO Võ Bích Yến': ('seasonal', ''),
    'DEMO Hoàng Đức Bảo': ('indefinite', 'permanent'),
}
env = env  # noqa: F821
uid = int(os.environ.get('DM1_QA_UID') or 6672)
company = env['hr.formula.config'].sudo().search(
    [('code', '=', 'DEMO_RETAIL_END')], limit=1).company_id
qa = env(user=uid, context=dict(env.context, allowed_company_ids=[company.id],
                                lang='en_US'))
contracts = env['hr.contract'].sudo().search(
    [('employee_id.name', 'in', list(EXPECT)), ('company_id', '=', company.id)],
    order='id')
ok = 0
for con in contracts:
    name = con.employee_id.name
    detail = qa['pb.contracts'].get_contract_detail(con.id)
    actions = [a.get('method') for a in (detail.get('next_actions') or [])]
    d = qa['pb.people.contract.wizard'].get_defaults(con.employee_id.id, con.id)
    pre = d.get('prefill') or {}
    kinds = {k['key']: k['label'] for k in d.get('vn_kinds') or []}
    treats = {k['key']: k['label'] for k in d.get('pay_treatments') or []}
    want = EXPECT[name]
    good = (pre.get('vn_kind'), pre.get('pay_treatment') or '') == want \
        and pre.get('vn_kind_show') and pre.get('pay_treatment_show') \
        and 'renew' in actions
    ok += bool(good)
    print('DM1 QA | %s | %s | Renew offered: %s | Kind of contract (Vietnam) = %s | '
          'Payroll treatment (Vietnam) = %s | %s' % (
              con.id, name, 'renew' in actions,
              kinds.get(pre.get('vn_kind'), pre.get('vn_kind')),
              treats.get(pre.get('pay_treatment') or '', pre.get('pay_treatment')),
              'PASS' if good else 'FAIL (expected %s)' % (want,)))
print('DM1 QA | %s of %s as expected (as uid %s)' % (ok, len(contracts), uid))
env.cr.rollback()
print('DM1 QA | rolled back')
