# -*- coding: utf-8 -*-
"""UPDATES P3a — a test helper: bank details need a second person.

Fixtures that WRITE bank details (to test what the desk writes, not who
agrees to it) now have the bank part approved by whoever holds its seat —
never the proposer. Everything else about those tests is unchanged.

UPDATES P3c — the platform support login and demo logins are never asked.
On a database where the support login is the company's only Finance holder
(p0clone, the golden template) nobody would hold a seat, so such fixtures
first give the company a Finance holder of their own (`ensure_second_person`).
"""


def ensure_second_person(env, company=None):
    """Make sure `company` has a Finance holder who may approve bank details.
    Writes nothing when it already has one (local test databases: the
    administrator). Returns the holder."""
    company = company or env.company
    Apply = env['pb.records.apply'].sudo()
    holders = Apply._bank_may_ask(Apply._finance_holders(company))
    if holders:
        return holders[:1]
    role = env['biz.approval.role'].sudo().search([('key', '=', 'finance')], limit=1)
    user = env['res.users'].sudo().with_context(
        no_reset_password=True, mail_create_nosubscribe=True).create({
            'name': 'Test bank second person', 'login': 'test.bank.second.%s' % company.id,
            'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [env.ref('base.group_user').id])]})
    Resp = env['biz.approval.responsibility'].sudo()
    row = Resp.search([('company_id', '=', company.id), ('role_id', '=', role.id),
                       ('scope_key', '=', ''), ('active', '=', True)], limit=1)
    if row:
        row.write({'user_id': user.id, 'backup_user_id': False})
    else:
        Resp.create({'company_id': company.id, 'role_id': role.id,
                     'scope_key': '', 'user_id': user.id})
    return user


def approve_bank(env, answer):
    """Approve every waiting bank part of a desk answer as its seat holder.
    Returns the number of parts approved."""
    done = 0
    Apply = env['pb.records.apply'].sudo()
    for part in (answer or {}).get('lanes') or []:
        if part.get('lane') != 'bank' or not part.get('pending'):
            continue
        rec = Apply.browse(part['apply_id'])
        request = rec.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(
            lambda s: s.status == 'open'
            and s.acting_user_id != rec._proposer())[:1]
        assert seat, 'no second person holds a seat on %s' % rec.name
        env['biz.approval.engine'].with_user(seat.acting_user_id).decide(
            request.id, step.key, 'approve')
        done += 1
    return done
