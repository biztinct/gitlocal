# -*- coding: utf-8 -*-
"""Z05 — the spreadsheet importer, against a workbook of the real shape.

The fixture is BUILT here rather than read off disk: the real RIZE workbook
lives outside any module and a suite that needs a file nobody ships is a suite
that passes on one machine. Every row, every column heading and every awkward
cell in it is copied verbatim from that workbook (`RIZE/VIETNAM/
Zoho_Payroll_Vietnam_Final_Configuration_and_Data_Setup_Pack_COMPLETED.xlsx`,
sheet "Approval Matrix"), including the three lines of preamble above the
header row and the joint approvers.
"""

import base64
import io

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.pb_approval_config.models import matrix_import as mi

from .common import MatrixCase

HEADER = ['Stage', 'Transaction / Object', 'Maker Role', 'Reviewer Role',
          'Final Approver Role', 'Named Approver', 'Backup / Delegate',
          'Threshold / Limit', 'SLA', 'Setup Status', 'Evidence / Control']

ROWS = [
    ['1.0', 'Employee master changes', 'HR Ops', 'HR Reviewer', 'HR Lead',
     'Nithya (HR Manager)', 'Monica (Finance Manager)', 'None',
     '1 working day', 'Ready', 'Import report + change evidence'],
    ['2.0', 'Salary/contract changes', 'HR Ops', 'HR Reviewer',
     'HR + Finance', 'Nithya (HR) + Monica (Finance)',
     'Nguyen Thi Phuong Thao', 'None (unified)', '1 working day', 'Ready',
     'Approved letter/contract'],
    ['3.0', 'Timesheet and leave', 'Employee/Manager', 'Line Manager', 'HR',
     'Nithya (HR Manager)', 'Respective Line Manager', 'None',
     'By Day 15 cut-off', 'Ready', 'Approved timesheet'],
    ['4.0', 'Overtime', 'Employee/Manager', 'Line Manager',
     'Functional Manager', 'Nithya (HR) + Monica (Finance)',
     'Respective Line Manager', '<=200 h/person/year', 'By Day 15', 'Ready',
     'Approved hours and reason'],
    ['5.0', 'Incentive/bonus', 'Functional Owner', 'HR/Payroll',
     'Functional Manager + Finance', 'Nithya (HR) + Monica (Finance)',
     'Nguyen Thi Phuong Thao', 'None', 'By Day 15', 'Ready',
     'Scheme result and approval'],
    ['6.0', 'Draft payroll run', 'Payroll Preparer', 'HR Reviewer', 'HR Lead',
     'Nithya (HR Manager)', 'Monica (Finance Manager)', 'None',
     '1 working day', 'Ready', 'Control report + variance'],
    ['7.0', 'Funding and payroll journal', 'Payroll/Finance',
     'Finance Reviewer', 'Finance Controller', 'Monica (Finance Manager)',
     'Nithya (HR Manager)', 'None', '1 working day', 'Ready',
     'Funding tie-out + JE'],
    ['8.0', 'Bank file creation', 'Payroll/Finance Maker', 'Bank Checker',
     'Authorized Signatory', 'Nithya + Monica + Thao (joint)',
     'Joint authorizers', 'None', 'On/before penultimate working day',
     'Ready', 'Bank control total'],
    ['9.0', 'Bank payment release', 'Bank Maker', 'Bank Checker',
     'Authorized Signatory', 'Nithya + Monica + Thao (joint)',
     'Per bank mandate', 'Per bank mandate',
     'On/before penultimate working day', 'Ready',
     'Bank release confirmation'],
    ['10.0', 'Reopen / off-cycle payroll', 'Payroll Preparer',
     'HR + Finance Review', 'Country/Finance Approver',
     'Nithya + Monica (joint)', 'Nguyen Thi Phuong Thao', 'None',
     'Case-by-case', 'Ready', 'Exception approval and audit'],
]


def _workbook(sheet_name=mi.SHEET_NAME, rows=None, header=None):
    """The fixture file, as base64, in the shape the real one has."""
    import openpyxl
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = sheet_name
    sheet.append(['PAYROLL APPROVAL & AUTHORIZATION MATRIX'])
    sheet.append([])
    sheet.append(['Roles are proposed from the implementation workshop.'])
    sheet.append(header or HEADER)
    for row in (ROWS if rows is None else rows):
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return base64.b64encode(buffer.getvalue())


@tagged('post_install', '-at_install')
class TestP7Import(MatrixCase):

    def _run(self):
        return self.as_admin('pb.approval.matrix.import').run(
            _workbook(), self.company.id)

    # ------------------------------------------------------------ Z05
    def test_z05a_ten_rows_become_ten_drafts(self):
        result = self._run()
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['made']), 10,
                         "every row in the sheet should land")
        self.assertEqual(result['drafts'], 10,
                         "every row should make a draft route")
        self.assertEqual(result['published'], 0,
                         "the importer publishes nothing, ever")

    def test_z05b_every_row_is_recognised(self):
        result = self._run()
        self.assertEqual(result['unrecognised'], [],
                         "the ten rows of the standard sheet are all known")
        keys = sorted(row['process_key'] for row in result['made'])
        self.assertEqual(keys, sorted([
            'master', 'paychange', 'timesheet', 'overtime', 'awards',
            'payrun', 'journal', 'bankfile', 'release', 'reopen']))

    def test_z05c_a_joint_cell_becomes_two_signatures(self):
        """"HR + Finance" is two people, not one step wearing the word."""
        result = self._run()
        pay = [r for r in result['made'] if r['process_key'] == 'paychange'][0]
        roles = [s['role'] for s in pay['steps']]
        self.assertIn('hr_lead', roles)
        self.assertIn('finance', roles)
        version = self.env['biz.approval.workflow.version'].browse(
            pay['version_id'])
        self.assertEqual(version.status, 'draft')
        self.assertEqual(len(version.definition['steps']), 2)

    def test_z05d_a_line_manager_is_a_manager_step_not_a_role(self):
        result = self._run()
        row = [r for r in result['made'] if r['process_key'] == 'timesheet'][0]
        version = self.env['biz.approval.workflow.version'].browse(
            row['version_id'])
        modes = [s['who'].get('mode') for s in version.definition['steps']]
        self.assertIn('manager', modes,
                      '"Line Manager" is the person\'s own manager')

    def test_z05e_named_people_are_proposals_never_accounts(self):
        result = self._run()
        self.assertTrue(result['people'], "the names should come back")
        for person in result['people']:
            self.assertEqual(person['state'], 'proposed')
            self.assertFalse(person['user_id'],
                             "no account is ever guessed from a name")
        names = {p['name_text'] for p in result['people']}
        self.assertIn('Nithya (HR Manager)', names)
        self.assertIn('Monica (Finance)', names,
                      'a joint cell proposes each person separately')

    def test_z05f_the_sla_is_read_where_it_can_be(self):
        result = self._run()
        by_key = {r['process_key']: r for r in result['made']}
        self.assertEqual(by_key['master']['due']['kind'], 'working_days')
        self.assertEqual(by_key['master']['due']['days'], 1)
        self.assertEqual(by_key['timesheet']['due']['kind'], 'calendar_day')
        self.assertEqual(by_key['timesheet']['due']['day'], 15)
        self.assertIsNone(by_key['reopen']['due'],
                          '"Case-by-case" is not a date')
        self.assertTrue(any('Case-by-case' in w
                            for w in by_key['reopen']['warnings']),
                        'and it says so rather than inventing one')

    def test_z05g_a_threshold_is_a_note_and_never_a_condition(self):
        result = self._run()
        overtime = [r for r in result['made']
                    if r['process_key'] == 'overtime'][0]
        self.assertIn('200 h/person/year', overtime['threshold_note'])
        version = self.env['biz.approval.workflow.version'].browse(
            overtime['version_id'])
        for step in version.definition['steps']:
            self.assertIsNone(step.get('condition'),
                              'a limit never becomes a silent condition')

    def test_z05h_an_unknown_row_lands_under_other_request(self):
        rows = [['11.0', 'Something nobody has heard of', 'X', 'HR Lead',
                 'HR Lead', '', '', 'None', '1 working day', 'Ready', '']]
        result = self.as_admin('pb.approval.matrix.import').run(
            _workbook(rows=rows), self.company.id)
        self.assertEqual(result['made'][0]['process_key'], 'generic')
        self.assertEqual(result['unrecognised'],
                         ['Something nobody has heard of'])

    def test_z05i_a_workbook_with_no_such_sheet_says_so(self):
        with self.assertRaises(UserError):
            self.as_admin('pb.approval.matrix.import').run(
                _workbook(sheet_name='Something Else'), self.company.id)

    def test_z05j_preview_writes_nothing(self):
        before = self.env['biz.approval.workflow'].search_count([
            ('company_id', '=', self.company.id)])
        answer = self.as_admin('pb.approval.matrix.import').preview(
            _workbook())
        self.assertEqual(len(answer['rows']), 10)
        self.assertEqual(
            self.env['biz.approval.workflow'].search_count(
                [('company_id', '=', self.company.id)]), before)

    def test_z05k_a_proposed_person_becomes_a_responsibility_when_chosen(self):
        result = self._run()
        person = [p for p in result['people']
                  if p['role_key'] == 'hr_lead'][0]
        self.as_admin('pb.approval.matrix.import').resolve_person(
            person['id'], self.hr.id)
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_hr_lead.id),
            ('scope_key', '=', '')], limit=1)
        self.assertEqual(held.user_id, self.hr)
        left = self.as_admin('pb.approval.matrix.import').proposed_people(
            self.company.id)
        self.assertNotIn(person['id'], [p['id'] for p in left])

    def test_z05l_setting_up_approvals_is_the_gate(self):
        with self.assertRaises(Exception):
            self.env['pb.approval.matrix.import'].with_user(
                self.asker).with_company(self.company).run(
                    _workbook(), self.company.id)

    # ------------------------------------------- the synonym tables alone
    def test_z05m_the_synonyms_answer_what_the_sheet_says(self):
        self.assertEqual(mi.match_process('Bank file creation'), 'bankfile')
        self.assertEqual(mi.match_role('Finance Controller'),
                         'finance_controller')
        self.assertEqual(mi.match_role('Finance Reviewer'), 'finance')
        self.assertEqual(mi.match_role('Respective Line Manager'), 'manager')
        self.assertIsNone(mi.match_role('None'))
        self.assertEqual(mi.split_joint('Nithya + Monica + Thao (joint)'),
                         ['Nithya', 'Monica', 'Thao'])
        self.assertEqual(mi.split_joint('HR/Payroll'), ['HR/Payroll'],
                         'a slash is one team\'s name, never two signatures')
