# -*- coding: utf-8 -*-
"""The one road every arrival travels.

A record can reach Payobook two ways — pushed down the webhook, or lifted out
of a spreadsheet somebody uploaded — and it must not matter which. Both doors
call `process_records`, so a rule that works for the push works for the file,
and a bug found in one is fixed for both. There is exactly one place where an
outside payload becomes a change to an employee, and this is it.

THE SHAPE OF ONE RECORD

    normalise → recognise (duplicate?) → match a person → read the trigger
              → find the rule → do what it says → write it down

Every step of that is recorded on the inbox row, including the steps that
decided to do nothing, because "why did this happen" is the question this
module will be asked and a row that only says "applied" cannot answer it.

WHAT IT WILL NOT DO

`_WHITELIST` is the field-ownership line (blueprint §14, ruling D8) made
mechanical. The connected system owns who a person is; Payobook owns what they
are paid. No arriving payload can write a wage, a bank account, a contract or a
probation date, whatever it contains and whoever sent it — the writer builds its
values from a fixed list and drops everything else on the floor. A leaver's
`departure_date` is filled only when it is EMPTY: HR's own answer to that
question always outranks the connected system's.

ONE SAVEPOINT PER RECORD. A push of two hundred joiners must not be lost
because the hundred-and-first has a department name with a null byte in it. The
bad record rolls back alone, its inbox row is written afterwards (outside the
savepoint that just rolled back, or it would roll back too), and the other
hundred and ninety-nine are committed.
"""

import json
import logging
from datetime import datetime

from odoo import api, fields, models, _

from .event_rule import normalise_value

_logger = logging.getLogger(__name__)

#: The ONLY employee fields an arriving payload may write. Adding to this list
#: moves the ownership line in ruling D8 and is a product decision, not a
#: refactor. Money, banking, contracts, probation, assets and vendors are
#: Payobook's and are absent on purpose.
_WHITELIST = (
    'name',            # who they are
    'work_email',
    'work_phone',
    'job_title',       # the free-text title, never hr.job / salary structure
    'department_id',
    'parent_id',       # their manager
    'sex',             # 'gender' on pre-19 builds — see `_employee_values`
    'gender',
)

#: Identity columns. Not "data" — these are the keys that let the next push find
#: the same person, and they are written by the bridge alone.
_IDENTITY = ('pb_zoho_id', 'employee_id', 'pb_zoho_status')

#: Zoho People spells the same idea several ways depending on the tenant's own
#: form. The spellings on the left of each tuple are the ones this codebase has
#: actually seen (`pb_hr_payroll_formula/integrations/zoho_connector.py`
#: `_parse_employee_record`, `om_hr_payroll/models/hr_zoho.py`); the rest are
#: the export-header variants a file upload brings. Matching is done on a
#: squashed key (lower-case, letters and digits only), so "Date of Joining",
#: "Dateofjoining" and "date_of_joining" are one key, not three.
_ALIASES = {
    'zoho_record_id': ('Zoho_ID', 'recordId', 'Record Id', 'zoho id'),
    'employee_number': ('EmployeeID', 'Employee Id', 'Employee Number',
                        'Employee Code'),
    'name': ('Name', 'Full Name', 'Employee Name', 'full_name_vn'),
    'first_name': ('FirstName', 'First Name'),
    'last_name': ('LastName', 'Last Name'),
    'email': ('EmailID', 'Email', 'Email Address', 'Work Email', 'work_email'),
    'work_phone': ('Work_phone', 'Work Phone', 'Office Phone', 'Extension'),
    'mobile': ('Mobile', 'Mobile Number', 'Mobile Phone'),
    'department': ('Department', 'Department Name'),
    'designation': ('Designation', 'Job Title', 'Position', 'Role'),
    'date_of_joining': ('Dateofjoining', 'Date of Joining', 'Joining Date',
                        'DOJ', 'Date_of_joining'),
    'date_of_exit': ('Dateofexit', 'Date of Exit', 'Last Working Day',
                     'Relieving Date', 'Exit Date', 'LastWorkingDay'),
    'employment_status': ('Employeestatus', 'Employment Status', 'Status',
                          'Employee Status'),
    'reporting_to': ('Reporting_To', 'Reporting To', 'Manager',
                     'Manager Email', 'Reporting Manager'),
    'sex': ('Gender', 'Sex'),
    'location': ('LocationName', 'Location'),
    'event_id': ('event_id', 'eventId', 'Event Id', 'webhook_event_id'),
    'modified_time': ('ModifiedTime', 'Modified Time', 'Last Modified'),
}

#: Zoho writes the whole word; `hr.employee.sex` is a one-letter selection.
_SEX = {'male': 'male', 'm': 'male', 'female': 'female', 'f': 'female',
        'other': 'other'}


def _squash(key):
    return ''.join(ch for ch in str(key or '').lower() if ch.isalnum())


#: Built once, at import: squashed spelling → our key.
_ALIAS_INDEX = {}
for _our_key, _spellings in _ALIASES.items():
    _ALIAS_INDEX[_squash(_our_key)] = _our_key
    for _s in _spellings:
        _ALIAS_INDEX[_squash(_s)] = _our_key


class PbZohoPipeline(models.AbstractModel):
    _name = 'pb.zoho.pipeline'
    _description = 'Arrival Pipeline'

    # ==================================================== normalisation
    @api.model
    def _normalise(self, raw):
        """One arriving record, in Payobook's own words.

        Unknown keys are NOT dropped — they are kept under `_raw`, because the
        audit row stores what actually arrived and the next phase may well need
        a field this one has never heard of.
        """
        rec = {'_raw': raw}
        if not isinstance(raw, dict):
            return rec
        for key, value in raw.items():
            our = _ALIAS_INDEX.get(_squash(key))
            if our and rec.get(our) in (None, '', False):
                rec[our] = value
        if not rec.get('name'):
            parts = [str(rec.get('first_name') or '').strip(),
                     str(rec.get('last_name') or '').strip()]
            rec['name'] = ' '.join(p for p in parts if p)
        for key in ('zoho_record_id', 'employee_number', 'name', 'email',
                    'employment_status', 'reporting_to', 'work_phone',
                    'department', 'designation', 'event_id'):
            if rec.get(key) is not None and rec.get(key) is not False:
                rec[key] = str(rec[key]).strip()
        return rec

    @api.model
    def _to_date(self, value):
        """A date from whatever the sender felt like sending. Never raises."""
        if not value:
            return False
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False
        try:
            return fields.Date.to_date(value)
        except (ValueError, TypeError):
            pass
        for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%d-%b-%Y', '%d %b %Y',
                    '%Y/%m/%d'):
            try:
                return datetime.strptime(str(value), fmt).date()
            except (ValueError, TypeError):
                continue
        _logger.info('pb_zoho_bridge: could not read "%s" as a date', value)
        return False

    # ==================================================== the entry point
    @api.model
    def process_records(self, records, source='webhook', company_id=False):
        """Run every record through the road above. Returns an honest tally.

        `company_id` is passed in rather than read from `self.env.company`
        because the webhook runs with no session at all: the company that owns
        the arrival is the connector's, and guessing it from the environment
        would file a live push under whichever company happens to be first.
        """
        summary = {'received': 0, 'created': 0, 'updated': 0, 'skipped': 0,
                   'review': 0, 'errors': 0, 'onboarding': 0, 'offboarding': 0,
                   'ignored': 0, 'logins': 0}
        company = self.env['res.company'].sudo().browse(company_id) \
            if company_id else self.env.company
        if not company or not company.exists():
            company = self.env.company
        for raw in (records or []):
            summary['received'] += 1
            rec = self._normalise(raw)
            try:
                with self.env.cr.savepoint():
                    self._process_one(rec, source, company, summary)
            except Exception as err:     # noqa: BLE001 - one record, one grave
                _logger.exception('pb_zoho_bridge: record failed')
                summary['errors'] += 1
                # Written AFTER the savepoint has rolled back, on purpose: a row
                # created inside it would be rolled back with the failure and the
                # only record of the problem would be a log line.
                self._log_row(rec, source, company, state='error',
                              action=_('Could not be applied'),
                              error=str(err))
        _logger.info('pb_zoho_bridge: %s', summary)
        return summary

    # ==================================================== one record
    def _process_one(self, rec, source, company, summary):
        Inbox = self.env['pb.zoho.inbox'].sudo()
        event_id = rec.get('event_id') or Inbox.fingerprint(
            {k: v for k, v in rec.items() if k != '_raw'})

        seen = Inbox.already_seen(event_id)
        if seen:
            summary['skipped'] += 1
            self._log_row(rec, source, company, state='skipped',
                          action=_('Already received'), event_id=False,
                          duplicate_of=seen, employee=seen.employee_id)
            return

        employee = self._match_employee(rec)
        if len(employee) > 1:
            summary['review'] += 1
            self._log_row(
                rec, source, company, state='review', event_id=event_id,
                action=_('More than one person could be this record'),
                error=_('%s people match this record: %s. Nothing was changed — '
                        'add an employee number or a work email to tell them '
                        'apart.',
                        len(employee), ', '.join(employee.mapped('name'))))
            return

        status = rec.get('employment_status') or ''
        trigger = self._read_trigger(employee, rec, status)
        rule = self.env['pb.zoho.event.rule'].decide(
            trigger, status, company.id)

        if not rule:
            summary['review'] += 1
            self._log_row(
                rec, source, company, state='review', event_id=event_id,
                employee=employee, trigger=trigger, status=status,
                action=_('No rule covers this yet'),
                error=_('Nobody has told Payobook what "%s" means. Add a rule '
                        'for it and this will be handled automatically next '
                        'time.', status or trigger))
            return

        handler = getattr(self, '_do_%s' % rule.action, None)
        if handler is None:
            summary['review'] += 1
            self._log_row(rec, source, company, state='review',
                          event_id=event_id, employee=employee, rule=rule,
                          trigger=trigger, status=status,
                          action=_('Unknown instruction'))
            return
        handler(rec, source, company, summary, employee, rule, trigger, status,
                event_id)

    def _read_trigger(self, employee, rec, status):
        """Which of the three things happened.

        The status comparison is against what we were told LAST TIME, not
        against Payobook's own idea of employment. Otherwise the first push
        after installing this module would read as a status change for the
        entire workforce and open a journey for every one of them.
        """
        if not employee:
            return 'created'
        if status and normalise_value(status) != normalise_value(
                employee.pb_zoho_status):
            return 'status'
        return 'updated'

    # ==================================================== matching
    def _match_employee(self, rec):
        """Their record id, then their number, then their email, then a name.

        A name is the LAST resort and only when exactly one person has it. Two
        people called Nguyễn Văn An is not an edge case in this product, it is
        Tuesday — so an ambiguous name returns both and the caller files it for
        review rather than picking one.
        """
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        found = Emp._pb_zoho_find(
            zoho_id=rec.get('zoho_record_id'),
            employee_number=rec.get('employee_number'),
            email=rec.get('email'))
        if found:
            return found
        name = (rec.get('name') or '').strip()
        if not name:
            return Emp.browse()
        return Emp.search([('name', '=ilike', name)], limit=2)

    def _match_manager(self, rec, company):
        """The manager named on the record, if we can be sure who it is."""
        raw = rec.get('reporting_to')
        if not raw:
            return self.env['hr.employee'].browse()
        raw = str(raw).strip()
        Emp = self.env['hr.employee'].sudo()
        found = Emp._pb_zoho_find(
            zoho_id=raw if not ('@' in raw) else False,
            employee_number=raw if not ('@' in raw) else False,
            email=raw if '@' in raw else False)
        if len(found) == 1:
            return found
        found = Emp.search([('name', '=ilike', raw)], limit=2)
        return found if len(found) == 1 else Emp.browse()

    def _match_department(self, rec, company):
        """The department by name, created if this company has none yet."""
        label = (rec.get('department') or '').strip()
        if not label:
            return self.env['hr.department'].browse()
        Dept = self.env['hr.department'].sudo()
        found = Dept.search(
            [('name', '=ilike', label),
             '|', ('company_id', '=', False), ('company_id', '=', company.id)],
            limit=1)
        if found:
            return found
        return Dept.create({'name': label, 'company_id': company.id})

    # ==================================================== writing
    def _employee_values(self, rec, company, employee=None):
        """The whitelist, applied. Everything else in the payload is ignored.

        A COSMETIC RENAME IS NOT A CHANGE. "Bui Anh Tam" arriving for a person
        already called "Bùi Anh Tâm " differs by case and spacing alone, and
        overwriting the record with it would churn the chatter of the whole
        workforce on every full push while telling nobody anything.
        """
        vals = {}
        name = (rec.get('name') or '').strip()
        if name:
            current = (employee.name or '').strip() if employee else ''
            if normalise_value(name) != normalise_value(current):
                vals['name'] = name
        if rec.get('email'):
            vals['work_email'] = str(rec['email']).strip()
        if rec.get('work_phone'):
            vals['work_phone'] = str(rec['work_phone']).strip()
        if rec.get('designation'):
            vals['job_title'] = str(rec['designation']).strip()
        dept = self._match_department(rec, company)
        if dept:
            vals['department_id'] = dept.id
        mgr = self._match_manager(rec, company)
        if mgr and (not employee or mgr.id != employee.id):
            vals['parent_id'] = mgr.id
        sex = _SEX.get(normalise_value(rec.get('sex')))
        if sex:
            # Odoo 19 renamed `gender` to `sex`; the legacy staging code in
            # om_hr_payroll still writes the old name. Probe rather than pick,
            # so this keeps working on either build instead of raising.
            Emp = self.env['hr.employee']
            if 'sex' in Emp._fields:
                vals['sex'] = sex
            elif 'gender' in Emp._fields:
                vals['gender'] = sex
        # Identity columns — the keys, not the data.
        if rec.get('zoho_record_id'):
            vals['pb_zoho_id'] = str(rec['zoho_record_id'])
        if rec.get('employee_number'):
            vals['employee_id'] = str(rec['employee_number'])
        if rec.get('employment_status'):
            vals['pb_zoho_status'] = str(rec['employment_status']).strip()
        return {k: v for k, v in vals.items()
                if k in _WHITELIST or k in _IDENTITY}

    def _changed_only(self, employee, vals):
        """Drop the values that already say what the record already says.

        A full push repeats every field of every employee. Writing them back
        unchanged would stamp a modification date and a chatter entry on the
        entire workforce every time the connected system syncs, and the audit
        row would claim an update that changed nothing.
        """
        out = {}
        for key, value in vals.items():
            field = employee._fields.get(key)
            if field is None:
                continue
            current = employee[key]
            if field.type == 'many2one':
                current = current.id if current else False
            if (current or False) != (value or False):
                out[key] = value
        return out

    def _create_or_update(self, rec, company, employee, summary):
        vals = self._employee_values(rec, company, employee)
        if employee:
            vals = self._changed_only(employee, vals)
            if vals:
                employee.sudo().write(vals)
                summary['updated'] += 1
            return employee
        if not vals.get('name'):
            vals['name'] = (rec.get('name') or '').strip() or _('New joiner')
        vals['company_id'] = company.id
        employee = self.env['hr.employee'].sudo().create(vals)
        summary['created'] += 1
        return employee

    # ==================================================== the journey
    def _open_case(self, employee, case_type, anchor_date, company):
        """Start their checklist — unless one is already running.

        Idempotent by state, not by payload: a second push, a re-uploaded
        spreadsheet and a human who started the journey by hand five minutes
        ago all reach the same test, and none of them gives the person two
        joining checklists to work through.
        """
        Case = self.env['pb.journey.case'].sudo()
        running = Case.search([
            ('employee_id', '=', employee.id),
            ('case_type', '=', case_type),
            ('state', 'in', ('draft', 'active', 'on_hold')),
        ], limit=1)
        if running:
            return running, False
        country_id = employee.country_id.id if employee.country_id else False
        template = self.env['pb.journey.template'].sudo().pick_for(
            case_type, country_id, company.id)
        case = Case.create({
            'employee_id': employee.id,
            'case_type': case_type,
            'template_id': template.id if template else False,
            'anchor_date': anchor_date or fields.Date.today(),
            'source': 'zoho',
            'company_id': company.id,
        })
        case.action_open()
        return case, True

    # ==================================================== the login (D6)
    def _auto_create_login(self, employee, company, summary):
        """A portal account, ready and silent.

        Never touches an account that already exists — not the employee's, not
        somebody else's who happens to share the address. A login collision is
        reported, never resolved by force.
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'pb_zoho_bridge.auto_create_logins', '1')
        if str(param).strip() not in ('1', 'true', 'True', 'yes'):
            return False
        email = (employee.work_email or '').strip()
        if not email:
            _logger.info('pb_zoho_bridge: no work email for employee %s — no '
                         'account created', employee.id)
            return False
        if employee.pb_portal_user_id:
            return False
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        existing = Users.search([('login', '=', email)], limit=1)
        if existing:
            employee.sudo().pb_portal_user_id = existing.id
            _logger.info('pb_zoho_bridge: %s already has an account', email)
            return False
        portal = self.env.ref('base.group_portal', raise_if_not_found=False)
        if not portal:
            return False
        user = self.env['res.users'].sudo().with_context(
            no_reset_password=True, mail_create_nosubscribe=True).create({
                'name': employee.name,
                'login': email,
                'email': email,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, [portal.id])],
            })
        employee.sudo().pb_portal_user_id = user.id
        summary['logins'] += 1
        return user

    # ==================================================== extension points
    def _after_onboard(self, case, rec):
        """Called once, right after a joining checklist is opened.

        Deliberately empty. P2 hangs asset issue on it, P3 hangs the buddy and
        the HRBP kick-off on it. `case` is the `pb.journey.case`; `rec` is the
        normalised arrival dict, with the untouched payload under `rec['_raw']`.
        Overrides must never raise: this runs inside the record's savepoint and
        a failure here would discard the journey that just opened.
        """
        return True

    def _after_offboard(self, case, rec):
        """Called once, right after a leaving checklist is opened.

        Same contract as `_after_onboard`: P2 reclaims assets here, P4 adds the
        exit interview. Never raise.
        """
        return True

    # ==================================================== the five actions
    def _do_ignore(self, rec, source, company, summary, employee, rule,
                   trigger, status, event_id):
        summary['ignored'] += 1
        self._log_row(rec, source, company, state='applied', event_id=event_id,
                      employee=employee, rule=rule, trigger=trigger,
                      status=status, action=_('Left alone, as the rule says'))

    def _do_review(self, rec, source, company, summary, employee, rule,
                   trigger, status, event_id):
        summary['review'] += 1
        self._log_row(rec, source, company, state='review', event_id=event_id,
                      employee=employee, rule=rule, trigger=trigger,
                      status=status,
                      action=_('Put aside for someone to look at'),
                      error=_('Nothing was changed. A person needs to decide '
                              'what should happen to this record.'))

    def _do_update(self, rec, source, company, summary, employee, rule,
                   trigger, status, event_id):
        if not employee:
            summary['review'] += 1
            self._log_row(
                rec, source, company, state='review', event_id=event_id,
                rule=rule, trigger=trigger, status=status,
                action=_('Nobody to update'),
                error=_('This record does not match anyone in Payobook, and '
                        'the rule only allows an update.'))
            return
        employee = self._create_or_update(rec, company, employee, summary)
        self._log_row(rec, source, company, state='applied', event_id=event_id,
                      employee=employee, rule=rule, trigger=trigger,
                      status=status, action=_('Record updated'))

    def _do_onboard(self, rec, source, company, summary, employee, rule,
                    trigger, status, event_id):
        was_new = not employee
        employee = self._create_or_update(rec, company, employee, summary)
        if was_new:
            self._auto_create_login(employee, company, summary)
        doj = self._to_date(rec.get('date_of_joining'))
        case, opened = self._open_case(employee, 'onboarding', doj, company)
        if opened:
            summary['onboarding'] += 1
            self._after_onboard(case, rec)
            action = (_('Added and their joining checklist started')
                      if was_new else _('Joining checklist started'))
        else:
            action = _('Record updated — a joining checklist was already running')
        self._log_row(rec, source, company, state='applied', event_id=event_id,
                      employee=employee, rule=rule, trigger=trigger,
                      status=status, action=action, case=case)

    def _do_offboard(self, rec, source, company, summary, employee, rule,
                     trigger, status, event_id):
        if not employee:
            summary['review'] += 1
            self._log_row(
                rec, source, company, state='review', event_id=event_id,
                rule=rule, trigger=trigger, status=status,
                action=_('Nobody to leave'),
                error=_('Payobook has no record of this person, so there is '
                        'nothing to close down.'))
            return
        employee = self._create_or_update(rec, company, employee, summary)
        lwd = self._to_date(rec.get('date_of_exit'))
        # HR's own answer always wins. An exit date already in Payobook was put
        # there by a person who knows something the connected system does not.
        if lwd and not employee.departure_date:
            employee.sudo().write({'departure_date': lwd})
        case, opened = self._open_case(
            employee, 'offboarding', lwd or employee.departure_date, company)
        if opened:
            summary['offboarding'] += 1
            self._after_offboard(case, rec)
            action = _('Their leaving checklist started')
        else:
            action = _('Record updated — a leaving checklist was already running')
        self._log_row(rec, source, company, state='applied', event_id=event_id,
                      employee=employee, rule=rule, trigger=trigger,
                      status=status, action=action, case=case)

    # ==================================================== the audit row
    def _log_row(self, rec, source, company, state, action, event_id=False,
                 employee=None, rule=None, trigger=False, status=False,
                 case=None, error=False, duplicate_of=None):
        try:
            payload = json.dumps(rec.get('_raw'), indent=2, default=str,
                                 ensure_ascii=False)
        except (TypeError, ValueError):
            payload = repr(rec.get('_raw'))
        employee = employee if employee and len(employee) == 1 else None
        return self.env['pb.zoho.inbox'].sudo().create({
            'external_event_id': event_id or False,
            'zoho_record_id': rec.get('zoho_record_id') or False,
            'employee_number': rec.get('employee_number') or False,
            'person_name': rec.get('name') or False,
            'payload_json': payload,
            'source': source,
            'state': state,
            'employee_id': employee.id if employee else False,
            'case_id': case.id if case else False,
            'rule_id': rule.id if rule else False,
            'trigger': trigger or False,
            'status_value': status or False,
            'action_taken': action,
            'error_note': error or False,
            'duplicate_of_id': duplicate_of.id if duplicate_of else False,
            'company_id': company.id,
        })
