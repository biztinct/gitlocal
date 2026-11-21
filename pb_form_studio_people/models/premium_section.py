"""A presentation of native fields, never a separate employee write API.

Project the already postprocessed full form: installed view rules, field ACLs,
translations, Form builder labels and modifiers remain authoritative. Full
Details is not modified or cached under the section's key.
"""
from odoo import api, models
from lxml import etree
from odoo.addons.pb_form_studio.models.native_section import project_section_form

# Names are mapped to presentation only. Missing/restricted native fields are
# never recreated. Approved bank details keep their existing dedicated workflow.
SECTIONS = {
    'job': (
        ('Role & organisation', ('department_id', 'job_id', 'job_title', 'employee_type', 'pb_job_level', 'division', 'pb_grade', 'pb_performance_rating')),
        ('Reporting & workplace', ('parent_id', 'coach_id', 'hrbp_user_id', 'buddy_id', 'work_location_id', 'address_id')),
        ('Work contacts', ('work_email', 'work_phone', 'mobile_phone', 'employee_id', 'barcode', 'pb_clock_code')),
        ('Hours & leave', ('resource_calendar_id', 'tz', 'pb_work_timezone_note', 'pb_leave_policy_id', 'pb_policy_full_time_confirmed', 'pb_policy_eligibility_review_ref', 'ruleset_id')),
        ('Usual work location', ('monday_location_id', 'tuesday_location_id', 'wednesday_location_id', 'thursday_location_id', 'friday_location_id', 'saturday_location_id', 'sunday_location_id')),
        ('Key dates', ('date_of_joining', 'first_contract_date', 'contract_id', 'contract_date_start', 'contract_date_end', 'pb_probation_state', 'trial_date_end')),
        ('Approvers', ('hr_responsible_id', 'expense_manager_id', 'leave_manager_id', 'attendance_manager_id')),
        ('Work eligibility', ('pb_safety_group', 'pb_posh_ic_member', 'pb_sg_experienced', 'pb_fixed_term_before', 'pb_fixed_term_months_before')),
        ('Departure', ('departure_reason_id', 'departure_date', 'departure_description', 'pb_rehire', 'pb_rehire_note', 'pb_rehire_by', 'pb_rehire_on')),
        ('Notes', ('additional_note',)),
    ),
    'personal': (
        ('Identity', ('name', 'legal_name', 'pb_legal_first_name', 'pb_legal_last_name', 'birthday', 'birthday_public_display', 'place_of_birth', 'country_of_birth', 'sex', 'country_id', 'pb_religion', 'pb_blood_type')),
        ('Personal contact', ('private_email', 'private_phone', 'private_street', 'private_street2', 'private_city', 'private_state_id', 'private_zip', 'private_country_id', 'pb_permanent_address', 'vietnam_temporary_address', 'distance_home_work', 'distance_home_work_unit')),
        ('ID papers & work permits', ('identification_id', 'ssnid', 'passport_id', 'passport_expiration_date', 'visa_no', 'visa_expire', 'pb_visa_status', 'permit_no', 'work_permit_expiration_date', 'vietnam_work_permit_number', 'has_work_permit')),
        ('Family', ('marital', 'spouse_complete_name', 'spouse_birthdate', 'children')),
        ('Emergency contact', ('emergency_contact', 'emergency_phone', 'vietnam_emergency_contact_name', 'vietnam_emergency_contact_phone', 'vietnam_emergency_contact_relationship')),
        ('Education', ('certificate', 'study_field', 'study_school')),
    ),
    'pay': (
        ('Pay setup', ('payroll_country', 'hourly_cost', 'structure_type_id', 'pb_paid_by_id', 'pb_paid_by_advance_id')),
        ('Payroll settings', ('overtime_status', 'fire_prevention_officer', 'tham_gia_bhxh', 'subject_to_pit', 'insurance_code')),
        ('Indonesia tax & insurance', ('pb_npwp_number', 'pb_family_card_number', 'pb_bpjs_employment_number', 'pb_bpjs_health_number', 'pb_id_ptkp_status')),
        ('India tax & insurance', ('pb_in_pan_number', 'pb_in_tax_regime', 'pb_in_uan_number', 'pb_in_esi_number')),
        ('Singapore tax', ('pb_sg_tax_residency', 'pb_sg_shg_fund')),
        ('Vietnam insurance policy', ('vn_insurance_policy_id', 'vn_work_region', 'vn_exempt_oa_od')),
        ('Vietnam insurance contributions', ('vn_si_enrolled', 'vn_si_enrollment_status', 'vn_si_salary_base', 'vn_hi_enrolled', 'vn_hi_salary_base', 'vn_ui_enrolled', 'vn_ui_salary_base')),
        ('Vietnam tax', ('vn_tax_regime', 'vn_residency_status', 'pb_vn_dependants_check')),
        ('Payroll facts', ('pb_vn_is_local', 'pb_vn_tax_resident', 'pb_vn_tax_commitment', 'pb_vn_in_insurance', 'pb_vn_union_member')),
    ),
    'resume': (),
    'documents': (('ID & licence files', ('id_card', 'driving_license')),),
    'settings': (
        ('Access & attendance', ('user_id', 'pin', 'category_ids')),
        ('Profile', ('image_1920', 'employee_properties')),
    ),
}
SECTION_BLOCKS = {
    'job': (('Organisation chart', "//field[@name='child_ids'][not(ancestor::field)]"),),
    'resume': (
        ('Experience', "//div[@id='o_employee_left']"),
        ('Skills', "//div[@id='o_work_information_right']"),
        ('Certifications', "//page[@name='certification']"),
        ('Badges', "//page[@name='received_badges']"),
        ('Résumé file', "//group[@name='pb_resume_file']"),
    ),
    'pay': (
        ('Tax dependants', "//page[@name='vietnam_tax']//group[.//field[@name='vn_dependent_ids']][not(group)]"),
        ('Tax requests', "//field[@name='pb_tax_request_ids'][not(ancestor::field)]"),
    ),

}
JOB_FIELDS = tuple(name for _, names in SECTIONS['job'] for name in names)



def project_job_form(arch, titles, domains=None):
    groups = [(titles[i] if i < len(titles) else title, names)
              for i, (title, names) in enumerate(SECTIONS['job'])]
    return project_section_form(arch, groups, domains)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        section = options.get('pb_workspace_section')
        if view_type == 'form' and section in SECTIONS:
            result = dict(result)
            result['arch'] = project_section_form(result['arch'],
                [(self.env._(title), names) for title, names in SECTIONS[section]],
                {name: field.get('domain', '') for name, field in
                 self.fields_get(attributes=['domain']).items()},
                [(self.env._(title), xpath) for title, xpath in SECTION_BLOCKS.get(section, ())],
                excluded={name for name, field in self._fields.items()
                          if field.type in ('one2many', 'many2many')
                          and not self.env[field.comodel_name].has_access('read')})
            if section == 'job':
                arch = etree.fromstring(result['arch'])
                for field in arch.xpath(".//section//field[@name='child_ids'][@widget='hr_org_chart']"):
                    field.set('widget', 'pb_premium_org_chart')
                result['arch'] = etree.tostring(arch, encoding='unicode')
        return result
