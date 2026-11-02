# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee 360 — the read-only detail tabs (Personal · Job · Pay & tax).

The drawer's Profile tab is a summary; these tabs carry the rest of the
employee record so HR rarely has to leave the roster. Read-only by owner
ruling (2026-11-02): editing goes through the drawer's "Full details" button,
which opens the complete employee form.

One table (``_SPEC``) drives everything. Each row names a field on
``hr.employee`` (Odoo 19 mirrors the hr.version fields there as related
fields, so one model covers both). Rows whose field is missing on this
database, or that the reader may not see (``fields_get`` already drops
group-restricted fields), are skipped — the spec is safe on every tenant
whatever country packs are installed.

Display rules:
  * a plain row shows "—" when empty, so HR sees what is missing;
  * an ``opt`` row is hidden when empty (rarely-used extras);
  * a group with a ``gate`` country (VN / ID statutory) is shown only when the
    person is paid or recorded in that country, or any of its rows is filled;
    inside it every row shows, booleans as Yes / No;
  * a group with no visible row is dropped.
Money is masked the same way as the Profile tab: only payroll managers get
the number (two-tier serialization, never CSS hiding).
"""

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# (field, label or None to use the field's own label, opt)
_SPEC = [
    ('personal', 'identity', _lt("Identity"), 'idCard', None, [
        ('legal_name', _lt("Legal name"), True),
        ('pb_legal_first_name', _lt("Legal given name"), True),
        ('pb_legal_last_name', _lt("Legal family name"), True),
        ('birthday', _lt("Date of birth"), False),
        ('place_of_birth', _lt("Place of birth"), False),
        ('sex', _lt("Gender"), False),
        ('marital', _lt("Marital status"), False),
        ('country_id', _lt("Nationality"), False),
        ('pb_religion', _lt("Religion"), True),
        ('pb_blood_type', _lt("Blood type"), True),
    ]),
    ('personal', 'papers', _lt("ID papers"), 'stamp', None, [
        ('identification_id', _lt("ID number"), False),
        ('passport_id', _lt("Passport number"), False),
        ('visa_no', _lt("Visa number"), True),
        ('visa_expire', _lt("Visa expires"), True),
        ('permit_no', _lt("Work permit number"), True),
        ('vietnam_work_permit_number', _lt("Work permit number"), True),
        ('permit_expire', _lt("Work permit expires"), True),
    ]),
    ('personal', 'contact', _lt("Personal contact"), 'mail', None, [
        ('private_email', _lt("Personal email"), False),
        ('private_phone', _lt("Personal phone"), False),
        ('_home_address', _lt("Home address"), False),
        ('vietnam_temporary_address', _lt("Temporary address"), True),
        ('km_home_work', _lt("Home to work (km)"), True),
    ]),
    ('personal', 'family', _lt("Family and emergency"), 'heart', None, [
        ('spouse_complete_name', _lt("Spouse"), True),
        ('children', _lt("Dependent children"), True),
        ('vietnam_dependents_count', _lt("Dependants for tax"), True),
        ('emergency_contact', _lt("Emergency contact"), False),
        ('emergency_phone', _lt("Emergency phone"), False),
        ('vietnam_emergency_contact_name', _lt("Emergency contact name"), True),
        ('vietnam_emergency_contact_phone', _lt("Emergency contact phone"), True),
        ('vietnam_emergency_contact_relationship', _lt("Relationship"), True),
    ]),
    ('personal', 'education', _lt("Education"), 'award', None, [
        ('certificate', _lt("Education level"), True),
        ('study_field', _lt("Field of study"), True),
        ('study_school', _lt("School"), True),
    ]),

    ('job', 'role', _lt("Role"), 'briefcase', None, [
        ('job_title', _lt("Job title"), False),
        ('job_id', _lt("Job position"), False),
        ('pb_job_level', _lt("Job level"), True),
        ('department_id', _lt("Department"), False),
        ('division', _lt("Division"), True),
        ('pb_grade', _lt("Grade"), True),
        ('employee_type', _lt("Employee type"), False),
        ('pb_performance_rating', _lt("Performance rating"), True),
    ]),
    ('job', 'people', _lt("Reporting"), 'users', None, [
        ('parent_id', _lt("Manager"), False),
        ('coach_id', _lt("Coach"), True),
        ('buddy_id', _lt("Buddy"), True),
        ('hrbp_user_id', _lt("HR partner"), True),
        ('user_id', _lt("App login"), True),
    ]),
    ('job', 'workplace', _lt("Workplace"), 'mapPin', None, [
        ('work_location_id', _lt("Work location"), False),
        ('address_id', _lt("Work address"), False),
        ('resource_calendar_id', _lt("Working hours"), False),
        ('pb_leave_policy_id', _lt("Leave policy"), True),
        ('work_email', _lt("Work email"), False),
        ('work_phone', _lt("Work phone"), False),
        ('mobile_phone', _lt("Work mobile"), True),
        ('employee_id', _lt("Employee number"), True),
        ('barcode', _lt("Badge ID"), True),
    ]),
    ('job', 'dates', _lt("Key dates"), 'calendar', None, [
        ('date_of_joining', _lt("Joined"), False),
        ('first_contract_date', _lt("First contract"), True),
        ('contract_date_start', _lt("Current contract from"), False),
        ('contract_date_end', _lt("Current contract until"), False),
        ('pb_probation_state', _lt("Trial period"), True),
        ('trial_date_end', _lt("Trial period ends"), True),
        ('departure_date', _lt("Leaving date"), True),
        ('departure_reason_id', _lt("Reason for leaving"), True),
    ]),

    ('pay', 'setup', _lt("Pay setup"), 'banknote', None, [
        ('wage', _lt("Monthly wage"), False),
        ('hourly_cost', _lt("Hourly cost"), True),
        ('structure_type_id', _lt("Salary structure type"), False),
        ('pb_paid_by_id', _lt("Paid by"), False),
        ('pb_paid_by_advance_id', _lt("Advance paid by"), True),
        ('payroll_country', _lt("Payroll country"), False),
    ]),
    ('pay', 'bank', _lt("Bank"), 'creditCard', None, [
        ('bank_account_id', _lt("Bank account"), True),
        ('bank_name', _lt("Bank"), False),
        ('account_number', _lt("Account number"), False),
        ('vietnam_bank_name', _lt("Bank name"), True),
        ('vietnam_bank_branch', _lt("Bank branch"), True),
        ('vietnam_bank_account_number', _lt("Bank account number"), True),
        ('vietnam_bank_account_name', _lt("Account holder"), True),
    ]),
    ('pay', 'vn', _lt("Vietnam tax and insurance"), 'shield', 'VN', [
        ('vietnam_tax_code', _lt("Personal tax code"), False),
        ('pb_vn_tax_resident', _lt("Tax resident"), False),
        ('vn_residency_status', _lt("Residency status"), False),
        ('vn_tax_regime', _lt("Tax regime"), False),
        ('subject_to_pit', _lt("Subject to personal income tax"), False),
        ('pb_vn_tax_commitment', _lt("Signed the single-employer tax commitment"), False),
        ('vietnam_social_insurance_number', _lt("Social insurance number"), False),
        ('insurance_code', _lt("Insurance code"), False),
        ('pb_vn_in_insurance', _lt("In the statutory insurance scheme"), False),
        ('vn_si_enrolled', _lt("Social insurance (SI)"), False),
        ('vn_hi_enrolled', _lt("Health insurance (HI)"), False),
        ('vn_ui_enrolled', _lt("Unemployment insurance (UI)"), False),
        ('vn_si_enrollment_status', _lt("Insurance enrolment status"), False),
        ('pb_vn_union_member', _lt("Union member"), False),
        ('vn_work_region', _lt("Minimum-wage region"), False),
        ('pb_vn_is_local', _lt("Local employee"), False),
        ('vietnam_work_permit_type', _lt("Work authorisation"), False),
    ]),
    ('pay', 'id', _lt("Indonesia tax and insurance"), 'shield', 'ID', [
        ('pb_npwp_number', _lt("NPWP tax number"), False),
        ('pb_bpjs_employment_number', _lt("BPJS employment number"), False),
        ('pb_bpjs_health_number', _lt("BPJS health number"), False),
        ('pb_family_card_number', _lt("Family card number"), False),
    ]),
]

_MONEY_FIELDS = ('wage', 'hourly_cost')
_HOME_ADDRESS = ('private_street', 'private_street2', 'private_city',
                 'private_state_id', 'private_zip', 'private_country_id')


class PbPeople(models.AbstractModel):
    _inherit = 'pb.people'

    def _e360_value(self, emp, name, meta, unmask):
        """Display text for one field, or None when it is empty."""
        if name == '_home_address':
            parts = []
            for f in _HOME_ADDRESS:
                if f in meta:
                    v = emp[f]
                    v = v.display_name if hasattr(v, '_name') else v
                    if v:
                        parts.append(str(v).strip())
            return ', '.join(p for p in parts if p) or None
        info = meta[name]
        ftype = info.get('type')
        v = emp[name]
        if ftype == 'boolean':
            return _("Yes") if v else _("No")
        if ftype == 'many2one':
            return v.display_name or None if v else None
        if ftype == 'selection':
            return dict(info.get('selection') or []).get(v) or None if v else None
        if ftype in ('date', 'datetime'):
            return str(v)[:10] if v else None
        if ftype == 'monetary':
            if not unmask:
                return _("Visible to payroll managers only")
            if not v:
                return None
            cur = emp.company_id.currency_id or self.env.company.currency_id
            return '%s%s' % (cur.symbol or '', '{:,.0f}'.format(v))
        if ftype == 'integer':
            return str(v) if v else None
        if v in (False, None):
            return None
        v = str(v).strip()
        return v or None

    def _e360_gate(self, emp, meta, country):
        codes = set()
        if 'payroll_country' in meta and emp.payroll_country:
            codes.add(str(emp.payroll_country).upper())
        if 'country_id' in meta and emp.country_id:
            codes.add((emp.country_id.code or '').upper())
        return country in codes

    @api.model
    def _e360_details(self, emp, unmask):
        """{'personal': [group, …], 'job': […], 'pay': […]} for the drawer."""
        names = {f for *_x, rows in _SPEC for f, _l, _o in rows}
        names |= set(_HOME_ADDRESS)
        meta = emp.fields_get(
            [n for n in names if n in emp._fields],
            attributes=['type', 'selection'])
        if any(f in meta for f in _HOME_ADDRESS):
            meta['_home_address'] = {'type': 'char'}

        tabs = {'personal': [], 'job': [], 'pay': []}
        for tab, key, title, icon, gate, rows in _SPEC:
            vals = []
            for name, label, opt in rows:
                if name not in meta:
                    continue
                try:
                    value = self._e360_value(emp, name, meta, unmask)
                except AccessError:
                    continue
                if name in _MONEY_FIELDS and not unmask and opt:
                    continue
                is_bool = meta[name].get('type') == 'boolean'
                filled = (value is not None and not is_bool) or (is_bool and emp[name])
                vals.append((name, str(label), value, opt, filled))
            if gate:
                if not (self._e360_gate(emp, meta, gate)
                        or any(v[4] for v in vals)):
                    continue
                shown = vals
            else:
                shown = [v for v in vals if v[2] is not None or not v[3]]
            if not shown:
                continue
            tabs[tab].append({
                'key': key, 'title': str(title), 'icon': icon,
                'rows': [{'key': n, 'label': lbl, 'value': val,
                          'empty': val is None} for n, lbl, val, _o, _f in shown],
                'filled': sum(1 for v in shown if v[2] is not None),
            })
        return tabs
