# -*- coding: utf-8 -*-
"""Shared fixture: one company, the people of the privacy matrix, one case
run all the way to an issued letter, a draft letter, a note, a file."""

import base64

from odoo.tests import new_test_user


def groups_if(env, *xmlids):
    """Comma list of the groups that exist on this database."""
    return ','.join(x for x in xmlids if env.ref(x, raise_if_not_found=False))


def make_fixture(cls):
    env = cls.env
    cls.company = env.company
    vn = env.ref('base.vn', raise_if_not_found=False)
    if vn and not cls.company.country_id:
        cls.company.country_id = vn
    cls.company_b = env['res.company'].create({'name': 'DEMO Conduct Co B'})
    cls.dept = env['hr.department'].create({'name': 'DEMO Conduct Dept',
                                            'company_id': cls.company.id})
    Emp = env['hr.employee']

    def user(login, groups, companies=None):
        companies = companies or cls.company
        return new_test_user(env, login=login, groups=groups,
                             company_id=companies[0].id,
                             company_ids=[(6, 0, companies.ids)])

    G = groups_if
    cls.u_named = user('s9b_named', G(env, 'base.group_user', 'hr.group_hr_user',
                                      'pb_conduct.group_conduct_user'),
                       cls.company | cls.company_b)
    cls.u_head = user('s9b_head', G(env, 'base.group_user', 'pb_conduct.group_conduct_head'))
    # W3-A (ruling CD1): a SECOND named person, who gives the second sign-off
    cls.u_named2 = user('s9b_named2', G(env, 'base.group_user', 'pb_conduct.group_conduct_user'))
    cls.u_hr = user('s9b_hr', G(env, 'base.group_user', 'hr.group_hr_user'))
    cls.u_hr_mgr = user('s9b_hrmgr', G(env, 'base.group_user', 'hr.group_hr_manager'))
    cls.u_life = user('s9b_life', G(env, 'base.group_user', 'pb_lifecycle.group_lifecycle_user',
                                    'pb_lifecycle.group_lifecycle_manager',
                                    'pb_lifecycle.group_lifecycle_admin'))
    cls.u_pay = user('s9b_pay', G(env, 'base.group_user', 'om_hr_payroll.group_hr_payroll_user',
                                  'om_hr_payroll.group_hr_payroll_manager',
                                  'pb_hr_payroll_base.group_payroll_base_officer'))
    cls.u_admin = user('s9b_admin', G(env, 'base.group_user', 'base.group_system',
                                      'hr.group_hr_manager'))
    # The Tenant administrator role, exactly as seeded on this database.
    role = env.ref('pb_vendor_access.role_tenant_administrator', raise_if_not_found=False)
    cls.u_tenant = user('s9b_tenant', 'base.group_user')
    if role:
        cls.u_tenant.sudo().write({'group_ids': [(4, g.id) for g in role.group_ids]})
    cls.u_manager = user('s9b_mgr', 'base.group_user')
    cls.u_subject_portal = new_test_user(env, login='s9b_subject', groups='base.group_portal',
                                         company_id=cls.company.id)
    cls.u_other_portal = new_test_user(env, login='s9b_other', groups='base.group_portal',
                                       company_id=cls.company.id)
    cls.u_subject2_internal = user('s9b_subject2', 'base.group_user')

    cls.e_manager = Emp.create({'name': 'DEMO Mina Manager', 'company_id': cls.company.id,
                                'department_id': cls.dept.id, 'user_id': cls.u_manager.id})
    cls.e_subject = Emp.create({'name': 'DEMO Sam Subject', 'company_id': cls.company.id,
                                'department_id': cls.dept.id, 'parent_id': cls.e_manager.id,
                                'user_id': cls.u_subject_portal.id})
    cls.e_other = Emp.create({'name': 'DEMO Olive Other', 'company_id': cls.company.id,
                              'department_id': cls.dept.id, 'user_id': cls.u_other_portal.id})
    cls.e_subject2 = Emp.create({'name': 'DEMO Ian Internal', 'company_id': cls.company.id,
                                 'department_id': cls.dept.id,
                                 'user_id': cls.u_subject2_internal.id})
    cls.e_named_self = Emp.create({'name': 'DEMO Nora Named', 'company_id': cls.company.id,
                                   'user_id': cls.u_named.id})
    cls.e_named2 = Emp.create({'name': 'DEMO Nick Second', 'company_id': cls.company.id,
                               'user_id': cls.u_named2.id})
    cls.e_b = Emp.create({'name': 'DEMO Bea CompanyB', 'company_id': cls.company_b.id})

    cls.reason = env.ref('pb_conduct.reason_attendance')
    F = env['pb.conduct'].with_user(cls.u_named).with_context(
        allowed_company_ids=cls.company.ids)
    cls.F = F
    F2 = env['pb.conduct'].with_user(cls.u_named2).with_context(
        allowed_company_ids=cls.company.ids)
    cls.F2 = F2

    # ---- the main case, all the way to an issued decision letter (the
    #      written warning gets its second sign-off from the second person)
    cid = F.create_case({'employee_id': cls.e_subject.id, 'reason_id': cls.reason.id,
                         'summary': 'SECRET-SUMMARY late 9 times in May',
                         'incident_date': '2026-05-31', 'raised_by': 'Shift lead'})['id']
    cls.case = env['pb.conduct.case'].browse(cid)
    F.add_note(cid, 'investigation', 'SECRET-NOTE timesheets checked')
    F.add_file(cid, 'evidence.txt', base64.b64encode(b'SECRET-FILE').decode())
    F.move(cid, 'plan_hearing', {'hearing_date': '2026-06-10 03:00:00', 'place': 'Room 2',
                                 'attendees': 'Sam, union rep, HR lead'})
    F.move(cid, 'invite')
    cls.invite = cls.case.letter_ids.filtered(lambda l: l.kind == 'invite')
    F.issue_letter(cls.invite.id)
    F.move(cid, 'hearing_held', {'held_on': '2026-06-10',
                                 'minutes': 'SECRET-MINUTES Sam said the bus was late'})
    F.move(cid, 'decide', {'outcome': 'written', 'summary': 'A written warning for lateness.'})
    cls.decision = cls.case.letter_ids.filtered(lambda l: l.kind == 'written')
    F.move(cid, 'ask_signoff')
    F2.move(cid, 'confirm_signoff')

    # ---- a second case with a DRAFT letter the employee must never see
    cid2 = F.create_case({'employee_id': cls.e_subject.id, 'reason_id': cls.reason.id,
                          'summary': 'Second matter'})['id']
    cls.case2 = env['pb.conduct.case'].browse(cid2)
    F.move(cid2, 'invite')
    cls.draft = cls.case2.letter_ids
    cls.draft.write({'title': 'SECRET-DRAFT-TITLE'})

    # ---- a case about an employee with an internal login
    cid3 = F.create_case({'employee_id': cls.e_subject2.id, 'reason_id': cls.reason.id,
                          'summary': 'Internal login matter'})['id']
    cls.case3 = env['pb.conduct.case'].browse(cid3)

    # ---- a case ABOUT the named HR person (opened by the head)
    H = env['pb.conduct'].with_user(cls.u_head).with_context(allowed_company_ids=cls.company.ids)
    cls.case_self = env['pb.conduct.case'].browse(H.create_case({
        'employee_id': cls.e_named_self.id, 'reason_id': cls.reason.id,
        'summary': 'About Nora herself'})['id'])

    # ---- a case in company B
    FB = env['pb.conduct'].with_user(cls.u_named).with_context(
        allowed_company_ids=(cls.company_b | cls.company).ids)
    cls.case_b = env['pb.conduct.case'].browse(FB.with_context(
        allowed_company_ids=[cls.company_b.id, cls.company.id]).create_case({
            'employee_id': cls.e_b.id, 'reason_id': cls.reason.id,
            'summary': 'Company B matter'})['id'])

    cls.file_att = env['ir.attachment'].sudo().search(
        [('res_model', '=', 'pb.conduct.case'), ('res_id', '=', cls.case.id)])
    cls.vault_doc = cls.decision.document_id
    env.flush_all()
