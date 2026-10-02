# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = ['hr.employee']

    division = fields.Char(string='Division')
    # ============================================ the source system's own key
    #
    # An employee that arrived from a connected system needs ONE identifier
    # that is stable, unique, and that nobody can point a field mapping at.
    # `employee_id`, `barcode` and `identification_id` are all mappable, and on
    # ABM the scheme's declared mappings point every one of them at the ID CARD
    # number — so two people who share a blank or duplicated card number became
    # one employee, and the feed's own key (Zoho's `11382`) was overwritten the
    # moment `_update_employee_from_raw_data` ran.
    #
    # Scoped by connector, because "0442" from one system and "0442" from
    # another are different people.
    pb_source_ref = fields.Char(
        string='Source System Reference', index=True, copy=False,
        help="Identifies this employee in the system they were imported from, "
             "as <connection id>:<their code>. Set by the import and used to "
             "recognise the same person on every later run, so records are "
             "updated instead of duplicated.")

    position_name = fields.Char(string='Position')
    job_title_text = fields.Char(string='Job Title')
    date_of_joining = fields.Date(string='Date of Joining')
    overtime_status = fields.Char(string='Overtime Status', default='')
    fire_prevention_officer = fields.Char(string='Fire Prevention Officer', default='')
    tham_gia_bhxh = fields.Char(string='Tham gia BHXH', default='')
    level_of_health_compensation = fields.Char(string='Level of Health Compensation', default='')
    subject_to_pit = fields.Char(string='Subject to PIT', default='')
    trade_union_participation = fields.Char(string='Trade Union Participation', default='')
    funeral_fund_participation = fields.Char(string='Funeral Fund Participation', default='')
    female_excluding_pregnant = fields.Char(string='Female Excluding Pregnant', default='')
    osh_worker_code = fields.Char(string='OSH Worker Code', default='')
    insurance_code = fields.Char(string='Insurance Code', default='')
    trade_union_fee_code = fields.Char(string='Trade Union Fee Code', default='')
    basic_overtime_electricity = fields.Char(string='Basic Overtime Electricity', default='')
    bd_phsk = fields.Char(string='BD PHSK', default='')
    deduction_of_funeral_money = fields.Char(string='Deduction of Funeral Money', default='')
    different_subjects = fields.Char(string='Different Subjects', default='')
    legal_entity_pays_salary = fields.Char(string='Legal Entity Pays Salary', default='')
    bank_name = fields.Char(string='Bank', default='')
    account_number = fields.Char(string='Account Number', default='')
