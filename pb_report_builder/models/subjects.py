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
            ('name', 'name', _("Name"), {}),
            ('department', 'department_id', _("Department"), {}),
            ('job', 'job_id', _("Job position"), {}),
            ('job_title', 'job_title', _("Job title"), {}),
            ('manager', 'parent_id', _("Manager"), {}),
            ('company', 'company_id', _("Company"), {}),
            ('country_of_work', 'payroll_country', _("Country of Work"), {}),
            ('location', 'work_location_id', _("Location"), {}),
            ('employee_type', 'employee_type', _("Employee type"), {}),
            ('contract_type', 'contract_id.contract_type_id', _("Contract type"), {}),
            ('start_date', 'first_contract_date', _("Start date"), {}),
            ('leaving_date', 'departure_date', _("Leaving date"), {}),
            ('leaving_reason', 'departure_reason_id', _("Why they left"), {}),
            ('active', 'active', _("Still working here"), {}),
            ('work_email', 'work_email', _("Work email"), {}),
            ('work_mobile', 'mobile_phone', _("Work mobile"), {}),
            ('gender', 'sex', _("Gender"), {}),
            ('birthday', 'birthday', _("Date of birth"), {}),
            ('nationality', 'country_id', _("Nationality"), {}),
            ('id_number', 'identification_id', _("ID number"), {}),
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

        add('people', label=_("People"), icon='users', model='hr.employee',
            employee_path='', company_path='company_id', department_path='department_id',
            dates=[('start_date', 'first_contract_date', _("Start date")),
                   ('leaving_date', 'departure_date', _("Leaving date"))],
            date_optional=True, archived=True, own_host='hr.employee', counts=True,
            fields=self._pbrb_people_fields(),
            why=_("You cannot see people. Ask your administrator for HR access."))

        add('contracts', label=_("Contracts"), icon='fileText', model='hr.contract',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('date_start', 'date_start', _("Start date")),
                   ('date_end', 'date_end', _("End date")),
                   ('trial_end', 'trial_date_end', _("End of trial"))],
            own_host='hr.contract',
            fields=[
                ('reference', 'name', _("Contract"), {}),
                ('employee', 'employee_id', _("Employee"), {}),
                ('department', 'department_id', _("Department"), {}),
                ('job', 'job_id', _("Job position"), {}),
                ('company', 'company_id', _("Company"), {}),
                ('contract_type', 'contract_type_id', _("Contract type"), {}),
                ('status', 'state', _("Status"), {}),
                ('date_start', 'date_start', _("Start date"), {}),
                ('date_end', 'date_end', _("End date"), {}),
                ('trial_end', 'trial_date_end', _("End of trial"), {}),
                ('working_hours', 'resource_calendar_id', _("Working hours"), {}),
                ('pay', 'wage', _("Contract pay"),
                 {'pay': True, 'currency': 'company_id.currency_id'}),
            ],
            why=_("You cannot see contracts. Ask your administrator for contract access."))

        add('time_off', label=_("Time off requests"), icon='umbrella', model='hr.leave',
            employee_path='employee_id', company_path='employee_company_id',
            department_path='employee_id.department_id',
            dates=[('from', 'request_date_from', _("First day")),
                   ('to', 'request_date_to', _("Last day"))],
            fields=[
                ('employee', 'employee_id', _("Employee"), {}),
                ('kind', 'holiday_status_id', _("Kind of leave"), {}),
                ('from', 'request_date_from', _("First day"), {}),
                ('to', 'request_date_to', _("Last day"), {}),
                ('days', 'number_of_days', _("Days"), {}),
                ('status', 'state', _("Status"), {}),
                ('reason', 'private_name', _("Reason given"), {}),
            ],
            why=_("You cannot see time off requests. Ask your administrator for "
                  "time off access."))

        add('attendance', label=_("Attendance"), icon='clock', model='hr.attendance',
            employee_path='employee_id', company_path='employee_id.company_id',
            department_path='employee_id.department_id',
            dates=[('check_in', 'check_in', _("Check in"))],
            fields=[
                ('employee', 'employee_id', _("Employee"), {}),
                ('check_in', 'check_in', _("Check in"), {}),
                ('check_out', 'check_out', _("Check out"), {}),
                ('hours', 'worked_hours', _("Hours worked"), {}),
                ('extra_hours', 'overtime_hours', _("Extra hours"), {}),
            ],
            why=_("You cannot see attendance. Ask your administrator for "
                  "attendance access."))

        add('open_roles', label=_("Open roles"), icon='briefcase',
            model='pb.hiring.requisition', employee_path=None, company_path='company_id',
            department_path='department_id',
            dates=[('opened_on', 'opened_on', _("Opened on")),
                   ('wanted_by', 'target_start_date', _("Wanted by")),
                   ('closed_on', 'closed_on', _("Closed on"))],
            fields=[
                ('reference', 'name', _("Reference"), {}),
                ('role', 'title', _("Role"), {}),
                ('department', 'department_id', _("Department"), {}),
                ('company', 'company_id', _("Company"), {}),
                ('country', 'country_id', _("Country"), {}),
                ('headcount', 'headcount', _("How many people"), {}),
                ('status', 'state', _("Status"), {}),
                ('wanted_by', 'target_start_date', _("Wanted by"), {}),
                ('opened_on', 'opened_on', _("Opened on"), {}),
                ('closed_on', 'closed_on', _("Closed on"), {}),
                ('recruiter', 'recruiter_id', _("Recruiter"), {}),
                ('days_open', 'days_open', _("Days open"), {}),
                ('applicants', 'applicant_count', _("Applicants"), {}),
            ],
            why=_("You cannot see open roles. Ask your administrator for Hiring access."))

        add('applicants', label=_("Applicants"), icon='userPlus', model='hr.applicant',
            employee_path=None, company_path='company_id', department_path='department_id',
            dates=[('applied_on', 'create_date', _("Applied on")),
                   ('hired_on', 'date_closed', _("Hire date"))],
            fields=[
                ('name', 'partner_name', _("Name"), {}),
                ('job', 'job_id', _("Job position"), {}),
                ('open_role', 'pb_requisition_id', _("Open role"), {}),
                ('stage', 'stage_id', _("Stage"), {}),
                ('status', 'application_status', _("Status"), {}),
                ('department', 'department_id', _("Department"), {}),
                ('company', 'company_id', _("Company"), {}),
                ('applied_on', 'create_date', _("Applied on"), {}),
                ('hired_on', 'date_closed', _("Hire date"), {}),
                ('source', 'source_id', _("Source"), {}),
                ('recruiter', 'user_id', _("Recruiter"), {}),
            ],
            why=_("You cannot see Applicants. Ask your administrator for Hiring access."))

        add('assets', label=_("Assets"), icon='laptop', model='pb.asset',
            employee_path='current_employee_id', company_path='company_id',
            department_path='current_employee_id.department_id',
            dates=[('bought_on', 'purchase_date', _("Bought on")),
                   ('warranty_end', 'warranty_end', _("Warranty ends"))],
            fields=[
                ('code', 'code', _("Asset code"), {}),
                ('name', 'name', _("What it is"), {}),
                ('category', 'category_id', _("Category"), {}),
                ('kind', 'kind', _("Kind"), {}),
                ('status', 'state', _("Status"), {}),
                ('holder', 'current_employee_id', _("Held by"), {}),
                ('company', 'company_id', _("Company"), {}),
                ('country', 'country_id', _("Country"), {}),
                ('serial', 'serial', _("Serial number"), {}),
                ('bought_on', 'purchase_date', _("Bought on"), {}),
                ('warranty_end', 'warranty_end', _("Warranty ends"), {}),
                ('cost', 'cost', _("Cost"), {}),
            ],
            why=_("You cannot see assets. Ask your administrator for Assets access."))

        add('training', label=_("Training"), icon='graduationCap',
            model='pb.training.assignment', employee_path='employee_id',
            company_path='company_id', department_path='employee_id.department_id',
            dates=[('assigned_on', 'assigned_on', _("Put on it")),
                   ('due', 'due_date', _("To be finished by")),
                   ('finished_on', 'completed_on', _("Finished on"))],
            fields=[
                ('employee', 'employee_id', _("Employee"), {}),
                ('course', 'channel_id', _("Course"), {}),
                ('status', 'state', _("How far it has got"), {}),
                ('why', 'reason', _("Why"), {}),
                ('assigned_on', 'assigned_on', _("Put on it"), {}),
                ('due', 'due_date', _("To be finished by"), {}),
                ('finished_on', 'completed_on', _("Finished on"), {}),
                ('score', 'score', _("Test score"), {}),
            ],
            why=_("You cannot see training. Ask your administrator for Learning access."))

        add('expenses', label=_("Expense claims"), icon='receipt', model='pb.expense.claim',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('sent_on', 'submitted_on', _("Sent on")),
                   ('decided_on', 'decided_on', _("Decided on")),
                   ('paid_on', 'paid_on', _("Paid on"))],
            fields=[
                ('reference', 'name', _("Reference"), {}),
                ('employee', 'employee_id', _("Employee"), {}),
                ('status', 'state', _("Status"), {}),
                ('total', 'total', _("Total"), {}),
                ('receipts', 'receipt_count', _("Receipts"), {}),
                ('sent_on', 'submitted_on', _("Sent on"), {}),
                ('decided_on', 'decided_on', _("Decided on"), {}),
                ('paid_on', 'paid_on', _("Paid on"), {}),
                ('company', 'company_id', _("Company"), {}),
            ],
            why=_("You cannot see expense claims. Ask your administrator for "
                  "Expenses access."))

        add('goals', label=_("Goals"), icon='target', model='pb.goal.set',
            employee_path='employee_id', company_path='company_id',
            department_path='employee_id.department_id',
            dates=[('deadline', 'deadline', _("Deadline")),
                   ('created_on', 'create_date', _("Created on"))],
            fields=[
                ('sheet', 'name', _("Goal sheet"), {}),
                ('employee', 'employee_id', _("Employee"), {}),
                ('year', 'cycle_id', _("Goal year"), {}),
                ('department', 'department_id', _("Department"), {}),
                ('manager', 'manager_employee_id', _("Manager"), {}),
                ('status', 'state', _("Status"), {}),
                ('goals', 'goal_count', _("Goals"), {}),
                ('progress', 'progress', _("How far along"), {}),
                ('deadline', 'deadline', _("Deadline"), {}),
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
