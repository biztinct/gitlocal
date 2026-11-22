# -*- coding: utf-8 -*-
"""The report builder's registry: what a row can be, and what it can show.

A SUBJECT answers "What is each row?" — people, contracts, time off
requests… Each one names its base model, the link to the employee (so the
"About the person" fields can be added to its rows), the company and
department paths the reader's scope narrows on, the dates the period picker
can use, and a CURATED field list with plain labels. Nothing outside this
registry ever reaches the ORM: a spec that names a key this file does not
know is refused (`pb.report.builder._clean_spec`).

Labels are built INSIDE the methods, with `self.env._`, so they are
translated for the reader (a literal inside a module-level dict is never
translated — DOCSTUDIO FACTS §1).

Other modules extend the registry by overriding `_pbrb_subjects` (add or
change a subject) or `_pbrb_counts` (add a "Counts from other areas"
column), calling `super()` first.

A subject is only listed when its model exists on this database (the probe
pattern: no dependency beyond `hr`), and a field only when its path
resolves on this database — a module that is not installed costs a field,
never an error.
"""
from odoo import api, models

#: The one pay field the builder offers (handover §2): contract pay. It is
#: shown only to the pay groups (`pb.report.builder._pay_ok`).
PAY_GROUP = 'om_hr_payroll.group_hr_payroll_manager'


class PbReportBuilderSubjects(models.AbstractModel):
    _name = 'pb.report.builder'
    _description = 'Report builder'
    _inherit = ['pb.group.scoped']

    # ================================================================ people
    @api.model
    def _pbrb_people_fields(self):
        """(key, path, label, extra) of the People subject — also the "About
        the person" list of every subject that links to an employee."""
        _ = self.env._
        return [
            ('name', 'name', _("Name"), dict()),
            ('department', 'department_id', _("Department"), dict()),
            ('job', 'job_id', _("Job position"), dict()),
            ('job_title', 'job_title', _("Job title"), dict()),
            ('manager', 'parent_id', _("Manager"), dict()),
            ('company', 'company_id', _("Company"), dict()),
            ('country_of_work', 'payroll_country', _("Country of Work"), dict()),
            ('location', 'work_location_id', _("Location"), dict()),
            ('employee_type', 'employee_type', _("Employee type"), dict()),
            ('contract_type', 'contract_id.contract_type_id', _("Contract type"), dict()),
            ('start_date', 'first_contract_date', _("Start date"), dict()),
            ('leaving_date', 'departure_date', _("Leaving date"), dict()),
            ('leaving_reason', 'departure_reason_id', _("Why they left"), dict()),
            ('active', 'active', _("Still working here"), dict()),
            ('work_email', 'work_email', _("Work email"), dict()),
            ('work_mobile', 'mobile_phone', _("Work mobile"), dict()),
            ('gender', 'sex', _("Gender"), dict()),
            ('birthday', 'birthday', _("Date of birth"), dict()),
            ('nationality', 'country_id', _("Nationality"), dict()),
            ('id_number', 'identification_id', _("ID number"), dict()),
        ]

    # ============================================================== subjects
    @api.model
    def _pbrb_subjects(self):
        """{key: subject}. Raw: NOT narrowed to the reader — the facade does
        that (`_subjects_for_reader`). Models absent here are left out."""
        _ = self.env._
        out = {}

        def add(key, **subject):
            if subject['model'] in self.env:
                subject['key'] = key
                out[key] = subject

        add('people', hint=_("One row per person, with counts from other areas"), label=_("People"), icon='users', model='hr.employee',
            employee_path='', company_path='company_id', department_path='department_id',
            dates=[('start_date', 'first_contract_date', _("Start date"), None),
                   ('leaving_date', 'departure_date', _("Leaving date"), None)],
            date_optional=True, archived=True, own_host='hr.employee', counts=True,
            fields=self._pbrb_people_fields(),
            why=_("You cannot see people. Ask your administrator for HR access."))

        add('contracts', hint=_("One row per contract"), label=_("Contracts"), icon='fileText', model='hr.contract',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('date_start', 'date_start', _("Start date"), None),
                   ('date_end', 'date_end', _("End date"), None),
                   ('trial_end', 'trial_date_end', _("End of trial"), None)],
            own_host='hr.contract',
            fields=[
                ('reference', 'name', _("Contract"), dict()),
                ('employee', 'employee_id', _("Employee"), dict()),
                ('department', 'department_id', _("Department"), dict()),
                ('job', 'job_id', _("Job position"), dict()),
                ('company', 'company_id', _("Company"), dict()),
                ('contract_type', 'contract_type_id', _("Contract type"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('date_start', 'date_start', _("Start date"), dict()),
                ('date_end', 'date_end', _("End date"), dict()),
                ('trial_end', 'trial_date_end', _("End of trial"), dict()),
                ('working_hours', 'resource_calendar_id', _("Working hours"), dict()),
                ('pay', 'wage', _("Contract pay"),
                 dict(pay=True, currency=('employee_id.pb_paid_by_id.currency_id',
                                          'company_id.currency_id'))),
            ],
            why=_("You cannot see contracts. Ask your administrator for contract access."))

        add('time_off', hint=_("One row per time off request"), label=_("Time off requests"), icon='umbrella', model='hr.leave',
            employee_path='employee_id', company_path='employee_company_id',
            department_path='employee_id.department_id',
            dates=[('from', 'request_date_from', _("First day"), None),
                   ('to', 'request_date_to', _("Last day"), None)],
            fields=[
                ('employee', 'employee_id', _("Employee"), dict()),
                ('kind', 'holiday_status_id', _("Kind of leave"), dict()),
                ('from', 'request_date_from', _("First day"), dict()),
                ('to', 'request_date_to', _("Last day"), dict()),
                ('days', 'number_of_days', _("Days"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('reason', 'private_name', _("Reason given"), dict()),
            ],
            why=_("You cannot see time off requests. Ask your administrator for "
                  "time off access."))

        add('attendance', hint=_("One row per check in"), label=_("Attendance"), icon='clock', model='hr.attendance',
            employee_path='employee_id', company_path='employee_id.company_id',
            department_path='employee_id.department_id',
            dates=[('check_in', 'check_in', _("Check in"), None)],
            fields=[
                ('employee', 'employee_id', _("Employee"), dict()),
                ('check_in', 'check_in', _("Check in"), dict()),
                ('check_out', 'check_out', _("Check out"), dict()),
                ('hours', 'worked_hours', _("Hours worked"), dict()),
                ('extra_hours', 'overtime_hours', _("Extra hours"), dict()),
            ],
            why=_("You cannot see attendance. Ask your administrator for "
                  "attendance access."))

        add('open_roles', hint=_("One row per role being hired for"), label=_("Open roles"), icon='briefcase',
            model='pb.hiring.requisition', employee_path=None, company_path='company_id',
            department_path='department_id',
            dates=[('opened_on', 'opened_on', _("Opened on"), None),
                   ('wanted_by', 'target_start_date', _("Wanted by"), None),
                   ('closed_on', 'closed_on', _("Closed on"), None)],
            fields=[
                ('reference', 'name', _("Reference"), dict()),
                ('role', 'title', _("Role"), dict()),
                ('department', 'department_id', _("Department"), dict()),
                ('company', 'company_id', _("Company"), dict()),
                ('country', 'country_id', _("Country"), dict()),
                ('headcount', 'headcount', _("How many people"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('wanted_by', 'target_start_date', _("Wanted by"), dict()),
                ('opened_on', 'opened_on', _("Opened on"), dict()),
                ('closed_on', 'closed_on', _("Closed on"), dict()),
                ('recruiter', 'recruiter_id', _("Recruiter"), dict()),
                ('days_open', 'days_open', _("Days open"), dict()),
                ('applicants', 'applicant_count', _("Applicants"), dict()),
            ],
            why=_("You cannot see open roles. Ask your administrator for Hiring access."))

        add('applicants', hint=_("One row per applicant"), label=_("Applicants"), icon='userPlus', model='hr.applicant',
            employee_path=None, company_path='company_id', department_path='department_id',
            dates=[('applied_on', 'create_date', _("Applied on"), None),
                   ('hired_on', 'date_closed', _("Hire date"), None)],
            fields=[
                ('name', 'partner_name', _("Name"), dict()),
                ('job', 'job_id', _("Job position"), dict()),
                ('open_role', 'pb_requisition_id', _("Open role"), dict()),
                ('stage', 'stage_id', _("Stage"), dict()),
                ('status', 'application_status', _("Status"), dict()),
                ('department', 'department_id', _("Department"), dict()),
                ('company', 'company_id', _("Company"), dict()),
                ('applied_on', 'create_date', _("Applied on"), dict()),
                ('hired_on', 'date_closed', _("Hire date"), dict()),
                ('source', 'source_id', _("Source"), dict()),
                ('recruiter', 'user_id', _("Recruiter"), dict()),
            ],
            why=_("You cannot see Applicants. Ask your administrator for Hiring access."))

        add('assets', hint=_("One row per asset"), label=_("Assets"), icon='laptop', model='pb.asset',
            employee_path='current_employee_id', company_path='company_id',
            department_path='current_employee_id.department_id',
            dates=[('bought_on', 'purchase_date', _("Bought on"), None),
                   ('warranty_end', 'warranty_end', _("Warranty ends"), None)],
            fields=[
                ('code', 'code', _("Asset code"), dict()),
                ('name', 'name', _("What it is"), dict()),
                ('category', 'category_id', _("Category"), dict()),
                ('kind', 'kind', _("Kind"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('holder', 'current_employee_id', _("Held by"), dict()),
                ('company', 'company_id', _("Company"), dict()),
                ('country', 'country_id', _("Country"), dict()),
                ('serial', 'serial', _("Serial number"), dict()),
                ('bought_on', 'purchase_date', _("Bought on"), dict()),
                ('warranty_end', 'warranty_end', _("Warranty ends"), dict()),
                ('cost', 'cost', _("Cost"), dict()),
            ],
            why=_("You cannot see assets. Ask your administrator for Assets access."))

        add('training', hint=_("One row per course someone was put on"), label=_("Training"), icon='graduationCap',
            model='pb.training.assignment', employee_path='employee_id',
            company_path='company_id', department_path='employee_id.department_id',
            dates=[('assigned_on', 'assigned_on', _("Put on it"), None),
                   ('due', 'due_date', _("To be finished by"), None),
                   ('finished_on', 'completed_on', _("Finished on"), None)],
            fields=[
                ('employee', 'employee_id', _("Employee"), dict()),
                ('course', 'channel_id', _("Course"), dict()),
                ('status', 'state', _("How far it has got"), dict()),
                ('why', 'reason', _("Why"), dict()),
                ('assigned_on', 'assigned_on', _("Put on it"), dict()),
                ('due', 'due_date', _("To be finished by"), dict()),
                ('finished_on', 'completed_on', _("Finished on"), dict()),
                ('score', 'score', _("Test score"), dict()),
            ],
            why=_("You cannot see training. Ask your administrator for Learning access."))

        add('expenses', hint=_("One row per expense claim"), label=_("Expense claims"), icon='receipt', model='pb.expense.claim',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('sent_on', 'submitted_on', _("Sent on"), None),
                   ('decided_on', 'decided_on', _("Decided on"), None),
                   ('paid_on', 'paid_on', _("Paid on"), None)],
            fields=[
                ('reference', 'name', _("Reference"), dict()),
                ('employee', 'employee_id', _("Employee"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('total', 'total', _("Total"), dict()),
                ('receipts', 'receipt_count', _("Receipts"), dict()),
                ('sent_on', 'submitted_on', _("Sent on"), dict()),
                ('decided_on', 'decided_on', _("Decided on"), dict()),
                ('paid_on', 'paid_on', _("Paid on"), dict()),
                ('company', 'company_id', _("Company"), dict()),
            ],
            why=_("You cannot see expense claims. Ask your administrator for "
                  "Expenses access."))

        add('goals', hint=_("One row per goal sheet"), label=_("Goals"), icon='target', model='pb.goal.set',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('deadline', 'deadline', _("Deadline"), None),
                   ('created_on', 'create_date', _("Created on"), None)],
            fields=[
                ('sheet', 'name', _("Goal sheet"), dict()),
                ('employee', 'employee_id', _("Employee"), dict()),
                ('year', 'cycle_id', _("Goal year"), dict()),
                ('department', 'department_id', _("Department"), dict()),
                ('manager', 'manager_employee_id', _("Manager"), dict()),
                ('status', 'state', _("Status"), dict()),
                ('goals', 'goal_count', _("Goals"), dict()),
                ('progress', 'progress', _("How far along"), dict()),
                ('deadline', 'deadline', _("Deadline"), dict()),
            ],
            why=_("You cannot see goals. Ask your administrator for Talent access."))
        return out

    # ============================================== counts from other areas
    @api.model
    def _pbrb_counts(self):
        """Columns a list of PEOPLE can carry, worked out per person for the
        chosen period with ONE `_read_group` on the other model each, as the
        reader. `agg`: '__count', '<field>:sum', or 'days' (distinct days)."""
        _ = self.env._
        out = []

        def add(key, **count):
            if count['model'] in self.env:
                count['key'] = key
                out.append(count)

        add('leave_days', label=_("Time off days taken"), model='hr.leave',
            employee='employee_id', domain=[('state', '=', 'validate')],
            date='request_date_from', agg='number_of_days:sum')
        add('days_attended', label=_("Days attended"), model='hr.attendance',
            employee='employee_id', domain=[], date='check_in', agg='days')
        add('assets_held', label=_("Assets held now"), model='pb.asset',
            employee='current_employee_id', domain=[('state', '=', 'assigned')],
            date=None, agg='__count')
        add('training_done', label=_("Training finished"), model='pb.training.assignment',
            employee='employee_id', domain=[('state', '=', 'done')],
            date='completed_on', agg='__count')
        add('open_claims', label=_("Expense claims still open"), model='pb.expense.claim',
            employee='employee_id', domain=[('state', 'in', ('submitted', 'approved'))],
            date=None, agg='__count')
        add('goals_set', label=_("Goals set"), model='pb.goal.set',
            employee='employee_id', domain=[], date='create_date', agg='goal_count:sum')
        return out
