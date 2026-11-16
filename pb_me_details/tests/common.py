# -*- coding: utf-8 -*-
"""Fixtures shared by the S6-A My details tests."""
import base64

PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
PDF = b'%PDF-1.4 an ID card scan for a test'


def seat(env, company, role_key, user):
    """Make `user` the holder of `role_key` in `company` (the template's
    holder may be an archived administrator, ledger QF1-W4)."""
    role = env['biz.approval.role'].sudo().search([('key', '=', role_key)], limit=1)
    Resp = env['biz.approval.responsibility'].sudo()
    row = Resp.search([('company_id', '=', company.id), ('role_id', '=', role.id),
                       ('scope_key', '=', ''), ('active', '=', True)], limit=1)
    if row:
        row.write({'user_id': user.id, 'backup_user_id': False})
    else:
        Resp.create({'company_id': company.id, 'role_id': role.id,
                     'scope_key': '', 'user_id': user.id})


def decide(env, record, action='approve', reason=''):
    """Decide the record's active step as its open seat's holder."""
    request = record.sudo().approval_request_id
    step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
    open_seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
    assert open_seat, 'nobody holds a seat on %s' % record.display_name
    user = open_seat.acting_user_id
    env['biz.approval.engine'].with_user(user).with_context(
        allowed_company_ids=[record.company_id.id]).decide(
            request.id, step.key, action, reason)
    env.invalidate_all()
    return user


def users(env, company):
    Users = env['res.users'].with_context(no_reset_password=True)
    common = {'company_id': company.id, 'company_ids': [(6, 0, [company.id])]}
    portal = Users.create(dict(common, name='S6A Details Portal',
                               login='s6a_det_portal', password='s6a_det_portal',
                               group_ids=[(6, 0, [env.ref('base.group_portal').id])]))
    hr = Users.create(dict(common, name='S6A Details HR', login='s6a_det_hr',
                           group_ids=[(6, 0, [env.ref('hr.group_hr_user').id])]))
    pay = Users.create(dict(common, name='S6A Details Pay', login='s6a_det_pay',
                            group_ids=[(6, 0, [
                                env.ref('om_hr_payroll.group_hr_payroll_user').id])]))
    return portal, hr, pay
