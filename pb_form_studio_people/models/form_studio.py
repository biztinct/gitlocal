# -*- coding: utf-8 -*-
"""The employee record as a Form builder host (FS-2).

THE HOST CONTRACT (FS1_REPORT.md §5) item 1: one host, `employee_detail`,
on `hr.employee` ONLY (never `hr.version` / `hr.employee.public`,
FS_HOST_FACTS §F). Its sections mirror the side panel: the panel's own tabs
are LOCKED sections (drawn by the screen, no field can be placed there) and
three OPEN sections make up the new "Company details" tab. The same
published layout drives the panel tab, the full page and the "Company
details" page on Full details (item 5, the engine's native-view sync).

Nothing here runs at install: the native page is registered the first time a
layout of this record type is published or a field of it deleted.
"""
from odoo import api, models
from odoo.exceptions import AccessError

HOST = 'employee_detail'
MODEL = 'hr.employee'
#: The native form that "Full details" opens (FS_HOST_FACTS §A.1).
NATIVE_VIEW = 'hr.view_employee_form'

#: The side panel's gate (`pb_employee_vault/models/pb_people_360.py:16-19, 28-31`).
HR_GROUPS = ('om_hr_payroll.group_hr_payroll_user', 'hr.group_hr_user')

# ----------------------------------------------------------------- R14
#: The standard boxes HR sees on the employee screens after the TIDY-E clean-up:
#: the KEEP rows of the audit's verdict table (`pb_employee_form_tidy/tests/
#: data/form_box_verdicts.csv` on branch tidy-e), minus lists, pictures,
#: computed summaries and per-weekday places — boxes a person cannot hold one
#: value in. Missing fields on a database are skipped at run time.
STANDARD_FIELDS = (
    'name', 'work_email', 'work_phone', 'mobile_phone', 'company_id', 'department_id',
    'job_id', 'job_title', 'parent_id', 'hrbp_user_id', 'buddy_id', 'employee_id',
    'address_id', 'work_location_id', 'departure_reason_id', 'departure_description',
    'departure_date', 'additional_note', 'private_email', 'private_phone', 'bank_name',
    'pb_other_name_holder', 'legal_name', 'pb_legal_first_name', 'pb_legal_last_name',
    'birthday', 'birthday_public_display', 'place_of_birth', 'country_of_birth', 'sex',
    'emergency_contact', 'emergency_phone', 'visa_no', 'visa_expire', 'permit_no',
    'work_permit_expiration_date', 'has_work_permit', 'country_id', 'identification_id',
    'ssnid', 'passport_id', 'passport_expiration_date', 'private_street', 'private_street2',
    'private_city', 'private_state_id', 'private_zip', 'private_country_id',
    'distance_home_work', 'distance_home_work_unit', 'marital', 'spouse_complete_name',
    'spouse_birthdate', 'children', 'certificate', 'study_field', 'id_card',
    'driving_license', 'contract_date_start', 'contract_date_end', 'wage', 'employee_type',
    'pb_probation_state', 'contract_type_id', 'structure_type_id', 'resource_calendar_id',
    'user_id', 'payroll_country', 'tz', 'hr_responsible_id', 'expense_manager_id',
    'leave_manager_id', 'attendance_manager_id', 'hourly_cost', 'pin', 'barcode',
    'pb_clock_code', 'ruleset_id', 'pb_fixed_term_before', 'pb_fixed_term_months_before',
    'pb_rehire', 'pb_rehire_note', 'date_of_joining', 'pb_blood_type', 'pb_religion',
    'pb_job_level', 'pb_permanent_address', 'pb_visa_status', 'pb_leave_policy_id',
)
#: Types a standard box may have to be offered at all (one value per person).
STANDARD_TTYPES = ('char', 'text', 'integer', 'float', 'monetary', 'boolean', 'date',
                   'datetime', 'selection', 'many2one')

#: R14 locked list, by kind. Each kind is one plain reason on screen.
PORTAL_CONTRACT = ('contract_id', 'contract_date_start', 'contract_date_end',
                   'contract_type_id', 'structure_type_id', 'resource_calendar_id',
                   'employee_type', 'pb_probation_state', 'first_contract_date',
                   'date_of_joining', 'departure_reason_id', 'departure_description',
                   'departure_date', 'pb_fixed_term_before', 'pb_fixed_term_months_before',
                   'pb_rehire', 'pb_rehire_note', 'pb_rehire_by', 'pb_rehire_on', 'ruleset_id',
                   'pb_leave_policy_id')
PORTAL_ORG = ('company_id', 'department_id', 'job_id', 'job_title', 'job_title_text',
              'parent_id', 'coach_id', 'hrbp_user_id', 'buddy_id', 'pb_job_level',
              'address_id', 'work_location_id')
PORTAL_ACCESS = ('user_id', 'pin', 'barcode', 'badge_ids', 'pb_clock_code', 'employee_id',
                 'hr_responsible_id', 'leave_manager_id', 'expense_manager_id',
                 'attendance_manager_id', 'work_contact_id', 'work_email')
PORTAL_COUNTRY = ('payroll_country', 'pbfs_country_of_work_id')
PORTAL_TAX = ('vietnam_tax_code', 'pb_npwp_number', 'pb_in_pan_number', 'pb_id_ptkp_status',
              'pb_in_tax_regime', 'pb_sg_shg_fund', 'pb_vn_tax_resident', 'subject_to_pit',
              'vn_residency_status')
#: Already changed by the employee through My details' own flows:
#: `pb_me_details` (`models/detail_request.py:46-72`: ID papers, marital
#: status, photo) and `pb_me_portal`'s profile change request
#: (`models/pb_profile_change_request.py:41-46`: phone, email, address,
#: emergency contact). Offered once, there.
MY_DETAILS_PAPERS = ('identification_id', 'passport_id', 'passport_expiration_date',
                     'permit_no', 'work_permit_expiration_date', 'marital', 'image_1920')
MY_DETAILS_PROFILE = ('private_phone', 'private_email', 'private_street',
                      'emergency_contact', 'emergency_phone')
#: R19 (2026-11-20) — boxes that became reachable when the engine learned to
#: write the personal boxes Odoo 19 keeps on `hr.version` (`_pbfs_portal_
#: writes_through`), and that must STILL stay HR's. Checked against every
#: reader in the repository (FS_FOLLOWUP1B_REPORT.md §R19):
#: * the rest of the home address — `pb_hr_govt/models/report_base.py:175-261`
#:   (Vietnamese social-insurance files) and `pb_form_lines/models/reader.py:
#:   214-282`, `render_sg.py:183` (government tax forms) print it; its first
#:   line is already the My details profile request's (`MY_DETAILS_PROFILE`).
PORTAL_ADDRESS = ('private_street2', 'private_city', 'private_zip', 'private_state_id',
                  'private_country_id')
#: R25 (owner, 2026-11-20) — closed again: the spouse is recorded on My
#: details › Family (a family member the pay team confirms), not here.
PORTAL_SPOUSE = ('spouse_complete_name', 'spouse_birthdate')
#: R26 (owner, 2026-11-20) — may be changed on My Payobook, but HR ALWAYS
#: approves ("Saves at once" refused). Add a box here to make it sensitive.
PORTAL_SENSITIVE = ('pb_blood_type', 'pb_religion')
#: * `ssnid`, `legal_name`, `additional_note`, `children`, `tz` — one plain
#:   reason each, in `_pbfs_portal_locked` (time zone: read by
#:   `pb_hr_payroll_formula/models/employee_work_timezone.py:76-106`).


def page_titles():
    """The Full details page title per language. Plain data on purpose: the
    engine stores it on its own record and puts it in the page it writes."""
    return {'en_US': 'Company details', 'vi_VN': 'Thông tin công ty',
            'id_ID': 'Detail perusahaan'}


class PbFormStudio(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------ host
    @api.model
    def _pbfs_hosts(self):
        hosts = super()._pbfs_hosts()
        if MODEL not in self.env:
            return hosts
        _ = self.env._
        locked = _('Drawn by the side panel itself. Fields cannot be placed here.')
        hosts[HOST] = {
            'model': MODEL,
            'title': _('Employee'),
            'icon': 'user',
            # Host order = the side panel's tab order; ids are stable forever.
            'sections': [
                {'id': 'profile', 'title': _('Profile'), 'icon': 'user', 'tone': 'teal',
                 'kind': 'locked',
                 'note': _('Wage, department, manager and contract dates. %s', locked)},
                {'id': 'personal', 'title': _('Personal'), 'icon': 'idCard', 'tone': 'blue',
                 'kind': 'locked',
                 'note': _('Identity, contact and family details. %s', locked)},
                {'id': 'job', 'title': _('Job'), 'icon': 'briefcase', 'tone': 'blue',
                 'kind': 'locked',
                 'note': _('Position, team and place of work. %s', locked)},
                {'id': 'pay', 'title': _('Pay & tax'), 'icon': 'banknote', 'tone': 'green',
                 'kind': 'locked',
                 'note': _('Tax, insurance and bank details. %s', locked)},
                {'id': 'custom', 'title': _('Company details'), 'icon': 'sparkles',
                 'tone': 'brand', 'kind': 'open'},
                {'id': 'job_more', 'title': _('More about the job'), 'icon': 'briefcase',
                 'tone': 'amber', 'kind': 'open'},
                {'id': 'person_more', 'title': _('More about the person'), 'icon': 'user',
                 'tone': 'teal', 'kind': 'open'},
                {'id': 'documents', 'title': _('Documents'), 'icon': 'fileText', 'tone': 'brand',
                 'kind': 'locked',
                 'note': _('Uploaded documents, by kind. %s', locked)},
                {'id': 'resume', 'title': _('Résumé'), 'icon': 'award', 'tone': 'blue', 'kind': 'locked', 'note': _('Experience, skills and certifications.')},
                {'id': 'settings', 'title': _('Settings'), 'icon': 'settings', 'tone': 'slate', 'kind': 'locked', 'note': _('Account and employee settings.')},
                {'id': 'timeline', 'title': _('Timeline'), 'icon': 'history', 'tone': 'brand',
                 'kind': 'locked',
                 'note': _('Every change to this person, newest first. %s', locked)},
            ],
            'default_layout': {'custom': [], 'job_more': [], 'person_more': []},
            # Standard fields stay where the panel draws them (R8: look-only).
            'std_fields': [],
            'custom_section': 'custom',
            # R10 — Country of Work (FIELD_AUDIT_FACTS §6), as a country record.
            'country_field': 'pbfs_country_of_work_id',
            'country_view_field': 'pbfs_country_of_work_id',
            'copy_custom': False,
            'native_views': [NATIVE_VIEW],
            # R14: the employee record can be offered on My Payobook, field by field.
            'portal': True,
            'standard_fields': self._pbfs_people_standard_fields(),
        }
        return hosts

    @api.model
    def _pbfs_people_standard_fields(self):
        Model = self.env[MODEL]
        # FS-16: a box that must stay off the screens (`_pbfs_std_comeback`:
        # the old Bank box, the record's Contract Type / Pay Category) is not
        # offered anywhere in the Form builder either.
        stay = self._pbfs_std_comeback(MODEL)
        return [n for n in STANDARD_FIELDS
                if n in Model._fields and Model._fields[n].type in STANDARD_TTYPES
                and n not in stay]

    # ------------------------------------------------------------ R14 hooks
    @api.model
    def _pbfs_people_formula_names(self):
        """Every employee field a pay formula can read: the formula input
        catalogue (`pb_hr_payroll_formula/models/application_domain_sources.py:19-49`,
        plus the first hop of its related sources), the tax sources of
        `pb_me_tax` (`models/formula_sources.py:34-41`), and custom fields
        marked "Use in pay formulas". Each module only where installed."""
        names = set()
        if 'hr.formula.config' in self.env:
            try:
                from odoo.addons.pb_hr_payroll_formula.models import application_domain_sources as ads
                # R19: boxes the catalogue lists but never hands to a payslip
                # (`PAYROLL_EXCLUDED_FIELDS`, application_domain_sources.py:38,
                # refused at :274) are not "read by a pay formula".
                names |= set(ads.EMPLOYEE_FIELDS) - set(getattr(ads, 'PAYROLL_EXCLUDED_FIELDS', ()))
                names |= {hops[0] for hops in ads.RELATED_FIELDS.values()}
            except ImportError:
                pass
            try:
                from odoo.addons.pb_me_tax.models.formula_sources import TAX_SOURCES
                names |= {spec[2] for spec in TAX_SOURCES.values() if len(spec) > 2}
            except ImportError:
                pass
        for name, meta in self._pbfs_meta(MODEL).items():
            if meta.custom and meta.formula_ok:
                names.add(name)
        return names

    @api.model
    def _pbfs_portal_hidden(self, model):
        """R14 / R16: never shown on My Payobook — the wage and every STANDARD
        pay figure. A custom money field may be shown (R16); the engine never
        lets the employee change an amount."""
        out = dict(super()._pbfs_portal_hidden(model) or {})
        if model != MODEL:
            return out
        reason = self.env._('Pay figures are never shown on My Payobook.')
        Model = self.env[MODEL]
        custom = set(self._pbfs_custom_names(MODEL))
        for name, field in Model._fields.items():
            if name in custom:
                continue
            if field.type == 'monetary' or name in ('wage', 'hourly_cost', 'contract_wage'):
                out.setdefault(name, reason)
        return out

    @api.model
    def _pbfs_portal_sensitive(self, model):
        """R26: blood type and religion — the employee may propose a change,
        HR always approves it."""
        out = dict(super()._pbfs_portal_sensitive(model) or {})
        if model == MODEL:
            reason = self.env._('Sensitive detail — HR always approves')
            for name in PORTAL_SENSITIVE:
                if name in self.env[MODEL]._fields:
                    out.setdefault(name, reason)
        return out

    @api.model
    def _pbfs_portal_locked(self, model):
        """R14: may be shown, never changed by the employee. One plain reason
        per field; the first that applies wins."""
        out = dict(super()._pbfs_portal_locked(model) or {})
        if model != MODEL:
            return out
        _ = self.env._
        Model = self.env[MODEL]
        rows = []
        if 'pb.me.detail.request' in self.env:
            rows.append((MY_DETAILS_PAPERS, _('Already on My details: the employee changes it there.')))
        if 'pb.profile.change.request' in self.env:
            rows.append((MY_DETAILS_PROFILE, _('Already on My details: the employee changes it there.')))
        rows += [
            # R25 (owner, 2026-11-20): the spouse boxes go back to HR; the
            # employee adds a husband or wife on My details › Family.
            (PORTAL_SPOUSE, _('Changed through My details › Family')),
            (PORTAL_COUNTRY, _('Country of Work decides which rules apply. Only HR changes it.')),
            (PORTAL_TAX, _('Tax numbers and status are changed through Tax details.')),
            (tuple(n for n in Model._fields if 'bank' in n or n in (
                'account_number', 'pb_other_name_holder')),
             _('Bank details are changed through the bank change request.')),
            (PORTAL_CONTRACT, _('Part of the contract. Only HR changes it.')),
        ]
        # FS-10: say what really reads it ("Used by pay formula: <scheme>"),
        # the same words as the Form builder's lock; a field a formula merely
        # could read says so — it may still be hidden from the screens.
        used = self._pbfs_std_used_reasons(MODEL)
        rows += [((name,), _('%s Only HR changes it.', reason)) for name, reason in used.items()]
        rows += [
            (tuple(self._pbfs_people_formula_names()),
             _('A pay formula can read it, so only HR changes it.')),
            (PORTAL_ORG, _('Company, team, manager and job are set by HR.')),
            (PORTAL_ACCESS, _('Login and access details are set by HR.')),
            # R19: still HR's (reasons and readers: PORTAL_ADDRESS above).
            (PORTAL_ADDRESS, _('Government forms are filled from the home address, so only HR '
                               'changes it.')),
            (('ssnid',), _('Social security numbers are set by HR.')),
            (('legal_name',), _('The legal name must match the ID papers, so only HR changes '
                                'it.')),
            (('additional_note',), _("This is HR's own note about the person.")),
            (('children',), _('Children who count for tax are added on My details, under '
                              'Family, where the pay team confirms them.')),
            (('tz',), _('The time zone follows the place of work and is used to count '
                        'working time, so only HR changes it.')),
        ]
        for names, reason in rows:
            for name in names:
                if name in Model._fields:
                    out.setdefault(name, reason)
        return out

    # ------------------------------------------------------------ gates
    @api.model
    def _pbfs_people_is_hr(self):
        """The side panel's own gate: HR, payroll or the administrator."""
        user = self.env.user
        return self.env.su or user._is_admin() or any(user.has_group(g) for g in HR_GROUPS)

    @api.model
    def render(self, host_key, record_id):
        """The employee host answers HR only, like the side panel it feeds —
        a line manager, an employee or a portal user gets nothing, even with
        a hand-made request."""
        if host_key == HOST and not self._pbfs_people_is_hr():
            raise AccessError(self.env._('Only HR can see these details.'))
        return super().render(host_key, record_id)

    @api.model
    def pbfs_people_full_form(self, view_id=False):
        """R22: may this person see the "Form builder" button on the form view
        `view_id`? Yes only for THE Full details form (`NATIVE_VIEW`) and only
        through the side panel wand's own gate (`can_edit`, R2 — the
        administrator). Never raises: the button is simply not drawn. Opening
        the Form builder stays refused by the engine for anybody else
        (`get_studio` / `publish` → `_pbfs_check_admin`)."""
        if not self.can_edit(HOST):
            return False
        try:
            view_id = int(view_id or 0)
        except (TypeError, ValueError):
            return False
        view = self.env.ref(NATIVE_VIEW, raise_if_not_found=False)
        return bool(view and view_id and view.id == view_id)

    # ------------------------------------------------------------ native page
    @api.model
    def _pbfs_people_register_native(self):
        """Make sure the engine knows the Full details form of this host.
        A registration only: the page itself is written by the engine, and
        only when a custom field is placed (THE HOST CONTRACT item 5)."""
        if not self.env.ref(NATIVE_VIEW, raise_if_not_found=False):
            return False
        Native = self.env['pb.form.native.view'].sudo()
        rec = Native.search([('model', '=', MODEL), ('parent_xmlid', '=', NATIVE_VIEW)], limit=1)
        if not rec:
            rec = Native.create({'model': MODEL, 'parent_xmlid': NATIVE_VIEW, 'host_key': HOST,
                                 'titles': page_titles()})
        return rec

    @api.model
    def _pbfs_resync_native(self, model, exclude=()):
        # Called by the engine on every publish and BEFORE every field delete
        # (FS1-6): the employee page is registered just in time, so install
        # stays silent and the very first publish already writes the page.
        if model == MODEL:
            self._pbfs_people_register_native()
        return super()._pbfs_resync_native(model, exclude=exclude)
