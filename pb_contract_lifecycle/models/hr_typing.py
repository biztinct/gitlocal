# -*- coding: utf-8 -*-
"""What kind of employment somebody is on — as a FIELD, not as a guess.

BEFORE THIS MODULE the only way to know an intern from a permanent employee was
to read the NAME of the contract type they happened to be on and look for the
word. `pb_hr_payroll_analytics` does exactly that
(`'contractor' in contract.type_id.name.lower()`), which is why a tenant that
calls its type "Consultant — outsourced" has a contractor count of zero and no
error anywhere.

THE FIELD ALREADY EXISTED AND NOBODY USED IT. Odoo's own
`employee_type` — employee / worker / student / trainee / contractor /
freelance — is on this build and no custom code reads or writes it. So this
module adopts it rather than minting a `pb_employment_kind` beside it, and adds
the ONE value the blueprint needs and Odoo does not ship: `intern`.

WHERE THE FIELD LIVES MATTERS (R14). On this build the employment fields sit on
a VERSION record: `hr.version.employee_type` is the real, stored, required
column and `hr.employee.employee_type` is a non-stored related onto it. So the
selection is extended on `hr.version` and the employee's own field follows it,
and every read and write here goes through the ORM — a raw `SELECT
employee_type FROM hr_employee` fails with *column does not exist* while the
ORM read of the same field works perfectly.

THE BACKFILL NEVER ARGUES WITH A PERSON. It only ever changes a record that
still says `employee` AND that nobody has deliberately typed — because
`employee_type` is required with that default, so "nobody has said" and
"somebody said permanent" are otherwise the same value. A deliberate write
stamps `pb_employment_type_set`, and the nightly guess never looks at a record
that carries it.
"""

import logging

from odoo import api, fields, models, _

from .contract_common import (
    CONTRACT_TYPE_FIXED_TERM, CONTRACT_TYPE_INTERN, EMPLOYEE_TYPE_LABEL,
    NON_PERMANENT_TYPES, TYPE_WORDS, type_from_words,
)

_logger = logging.getLogger(__name__)

#: How many employees one backfill pass looks at. The whole workforce on this
#: tenant is under five thousand and the pass is one search plus a write per
#: matched row, so the cap is a seatbelt rather than a plan.
BACKFILL_CAP = 6000


class HrVersion(models.Model):
    """The employment record. `intern` is added here because this is where the
    stored column is; `hr.employee.employee_type` is a related onto it and
    picks the new value up for free.

    `ondelete` is required for a `selection_add` on a stored field, and
    `set default` is the honest policy: if this module is ever removed, an
    intern becomes an employee rather than an empty required field.
    """
    _inherit = 'hr.version'

    employee_type = fields.Selection(
        selection_add=[('intern', 'Intern')],
        ondelete={'intern': 'set default'})


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_employment_type_set = fields.Boolean(
        string='Employment type was set deliberately', copy=False,
        help='True once a person, a connected system or a contract decision '
             'has said what kind of employment this is. The nightly guess from '
             'contract names never touches a record that carries it.')

    # ------------------------------------------------------------- reading
    def pb_employment_label(self):
        """"Intern", "Contractor", "Permanent" — the word, never the code."""
        self.ensure_one()
        kind = self._pb_employment_type()
        return EMPLOYEE_TYPE_LABEL.get(kind, kind or '')

    def _pb_employment_type(self):
        """This person's employment type, read as the system.

        SUDO ON THE READ AND NOTHING ELSE (R56). `employee_type` carries
        `groups="hr.group_hr_user"`, and reading one field of an `hr.employee`
        prefetches every stored field of the record — about forty of which are
        behind payroll groups on this build. A reader who holds the lifecycle
        tier but not the payroll ones would get an AccessError naming forty
        columns nobody asked for. The security boundary stays the search that
        found the record.
        """
        self.ensure_one()
        try:
            return self.sudo().employee_type or ''
        except Exception:               # noqa: BLE001
            _logger.debug('pb_contract_lifecycle: no employment type on %s',
                          self.id)
            return ''

    def _pb_is_non_permanent(self):
        """Is this somebody whose employment has an end built into it?"""
        self.ensure_one()
        return self._pb_employment_type() in NON_PERMANENT_TYPES

    # ------------------------------------------------------------- writing
    def pb_set_employment_type(self, kind, reason=None):
        """Write the employment type and say why in the chatter. Never raises.

        Through the ORM, always — the column is on the version record and a
        raw write both fails on some columns and lies about others (R14).
        """
        self.ensure_one()
        if kind not in EMPLOYEE_TYPE_LABEL:
            _logger.warning('pb_contract_lifecycle: %s is not an employment '
                            'type this build knows', kind)
            return False
        if self._pb_employment_type() == kind:
            # Already that. Still stamp it as deliberate — somebody said so
            # out loud — and still align the trial state, because the reason
            # this is being pressed at all is usually that something else
            # about the record disagrees with it.
            try:
                if not self.sudo().pb_employment_type_set:
                    self.sudo().pb_employment_type_set = True
            except Exception:           # noqa: BLE001
                _logger.warning('pb_contract_lifecycle: could not stamp the '
                                'employment type on %s', self.id,
                                exc_info=True)
            self._pb_align_trial_state(kind)
            return True
        try:
            self.sudo().write({'employee_type': kind,
                               'pb_employment_type_set': True})
            if reason:
                self.sudo().message_post(body=reason)
            self._pb_align_trial_state(kind)
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not set the '
                              'employment type on employee %s', self.id)
            return False

    def _pb_align_trial_state(self, kind):
        """An intern is not on probation, so the Probation board says so.

        P5's OWN RULE, applied at the moment the type changes.
        `probation_common.NON_STAFF_TYPES` already says a contractor or an
        intern has a trial state of "not applicable" — that is what P5's
        default computes for a new record — but a person whose type is set
        AFTER they arrive keeps whatever state they were given first. The
        arriving intern from the connected system landed as "In probation"
        with a trial end date, and turned up on the Probation lens beside four
        genuine new joiners.

        One direction only. Becoming non-permanent means the trial period does
        not apply; becoming permanent says nothing about whether somebody
        passed one, so that case is left exactly as it is.

        Never raises: this is a tidy-up, not the write the caller asked for.
        """
        self.ensure_one()
        if kind not in NON_PERMANENT_TYPES:
            return False
        try:
            if self.sudo().pb_probation_state == 'na':
                return True
            self._pb_set_probation_state('na', reason=_(
                "Recorded as %s, so a trial period does not apply.",
                EMPLOYEE_TYPE_LABEL.get(kind, kind)))
            return True
        except Exception:               # noqa: BLE001
            _logger.warning('pb_contract_lifecycle: could not align the trial '
                            'state on employee %s', self.id, exc_info=True)
            return False

    # --------------------------------------------------------- the backfill
    @api.model
    def _pb_backfill_employment_type(self, cap=BACKFILL_CAP):
        """Give everybody already on this database an honest employment type.

        READ THE CONTRACT, WRITE THE PERSON. The only evidence a database that
        has never had this field has is the NAME of the contract type somebody
        was put on, and the name of the contract itself. Both are read; the
        more specific word wins (`type_from_words`).

        NEVER A DOWNGRADE, AND NEVER AN ARGUMENT WITH A PERSON. Two guards,
        and the second one was learned the hard way. `employee_type` is
        required with a default of `employee`, so "nobody has said" and
        "somebody said permanent" are the SAME VALUE and cannot be told apart
        — which meant the nightly top-up read the contract of somebody who had
        just been made permanent, saw the word "contractor" in the category
        they used to be on, and typed them back. Every night. So a deliberate
        write — by a person, by a connected system, or by a conversion —
        stamps `pb_employment_type_set`, and this pass never looks at a record
        that carries it. A guess must lose to a statement, and the only way it
        can is if the statement is written down.

        Returns the counts, and logs them, because a backfill that reports
        nothing is a backfill nobody can check.
        """
        counts = {'intern': 0, 'contractor': 0, 'other': 0, 'looked_at': 0}
        Emp = self.sudo().with_context(active_test=False)
        Contract = self.env['hr.contract'].sudo()
        Type = self.env['hr.contract.type'].sudo()

        # START FROM THE EVIDENCE, NOT FROM THE PEOPLE. Walking five thousand
        # employees to read the name of a contract type there are eighteen of
        # is five thousand prefetches of forty columns each (R56) to answer a
        # question eighteen rows already answer. So the contract TYPES are read
        # once, turned into a map, and only the people on a type that means
        # something are touched.
        by_kind = {}
        try:
            for row in Type.search([]):
                kind = type_from_words(row.name)
                if kind and kind != 'employee':
                    by_kind.setdefault(kind, []).append(row.id)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_contract_lifecycle: could not read the '
                              'contract types for the backfill')

        def _apply(kind, domain):
            """Type everybody a domain of contracts points at. Never raises."""
            try:
                contracts = Contract.search(domain, limit=cap)
                ids = [c.employee_id.id for c in contracts if c.employee_id]
                if not ids:
                    return 0
                people = Emp.search([('id', 'in', ids),
                                     ('employee_type', '=', 'employee'),
                                     ('pb_employment_type_set', '=', False)],
                                    limit=cap)
                counts['looked_at'] += len(people)
                if not people:
                    return 0
                people.write({'employee_type': kind})
                return len(people)
            except Exception:           # noqa: BLE001 — one pass, one grave
                _logger.exception('pb_contract_lifecycle: the %s pass of the '
                                  'employment-type backfill', kind)
                return 0

        for kind, type_ids in by_kind.items():
            counts[kind] = counts.get(kind, 0) + _apply(
                kind, [('type_id', 'in', type_ids)])

        # AND THEN THE CONTRACT'S OWN NAME. A tenant whose types are all called
        # "Permanent" but whose contracts are called "Intern — summer 2026"
        # has the answer written down; it is just written somewhere else. A
        # handful of `ilike` searches over one table is cheap, and it is the
        # only place a second signal is worth having.
        for kind, words in TYPE_WORDS:
            if kind == 'employee':
                continue
            domain = ['|'] * (len(words) - 1) + [
                ('name', 'ilike', word) for word in words]
            counts[kind] = counts.get(kind, 0) + _apply(kind, domain)

        # EVERY KIND NAMED, never a bucket called "other". A backfill that
        # reports "2 something else" is a backfill nobody can check — the
        # whole reason it logs at all is so somebody can read the number and
        # decide whether it is the number they expected.
        named = ', '.join(
            '%s %s' % (v, EMPLOYEE_TYPE_LABEL.get(k, k).lower())
            for k, v in sorted(counts.items())
            if k not in ('looked_at', 'other') and v)
        _logger.info(
            'pb_contract_lifecycle backfill: %s employees still on the '
            'default were looked at; %s',
            counts['looked_at'], named or 'nobody was retyped')
        return counts

    # ------------------------------------------------- the two contract types
    @api.model
    def _pb_ensure_contract_types(self):
        """Make sure "Intern" and "Fixed-term contractor" exist, ONCE.

        ENSURED RATHER THAN SEEDED, and the difference is the whole point. The
        standard `hr` module already seeds twelve contract types on this
        database, "Intern" among them — so a `<record>` of our own would put a
        SECOND row called Intern in the picker, and a picker with two identical
        options is a picker nobody can use correctly. Matched by name,
        case-insensitively, and created only when nothing matches.

        Idempotent, so the daily job calls it too: a tenant that renames or
        deletes one gets it back rather than a silent hole (R44's discipline).
        """
        Type = self.env['hr.contract.type'].sudo()
        made = {}
        for label in (CONTRACT_TYPE_INTERN, CONTRACT_TYPE_FIXED_TERM):
            try:
                found = Type.search([('name', '=ilike', label)], limit=1)
                if found:
                    made[label] = found.id
                    continue
                # Company-less (R8): a type created onto whichever company ran
                # the install is a type the standard company rule then hides
                # from everybody else.
                vals = {'name': label, 'sequence': 1100}
                if 'company_id' in Type._fields:
                    vals['company_id'] = False
                made[label] = Type.create(vals).id
                _logger.info('pb_contract_lifecycle: created the "%s" '
                             'contract type', label)
            except Exception:           # noqa: BLE001
                _logger.exception('pb_contract_lifecycle: could not ensure '
                                  'the "%s" contract type', label)
        return made


class HrContract(models.Model):
    """One computed field, and it is a convenience rather than a fact.

    `pb_days_to_end` is what every screen in this module wants and what nobody
    should compute twice. Non-stored on purpose: it changes every night without
    anybody writing anything, and a stored copy of a countdown is a stored copy
    that is wrong by morning.
    """
    _inherit = 'hr.contract'

    pb_review_ids = fields.One2many(
        'pb.contract.review', 'contract_id', string='Contract decisions')
    pb_renewed_from_id = fields.Many2one(
        'hr.contract', string='Follows on from', index=True,
        ondelete='set null', copy=False,
        help='The contract this one replaces. Set when an extension or a '
             'conversion creates a new agreement — the old one is left to end '
             'on its own date and is never rewritten.')
    pb_renewal_ids = fields.One2many(
        'hr.contract', 'pb_renewed_from_id', string='Replaced by')
    pb_days_to_end = fields.Integer(
        compute='_compute_pb_days_to_end', string='Days left')

    def _compute_pb_days_to_end(self):
        today = fields.Date.today()
        for rec in self:
            rec.pb_days_to_end = ((rec.date_end - today).days
                                  if rec.date_end else 0)

    def pb_terms_summary(self):
        """The terms a new contract would copy — for the confirm dialog.

        Money IS shown here, and only here. The board itself carries no wage
        (a screen that lists what everybody earns is a screen nobody can leave
        open), but a person about to create a contract has to see the number
        they are about to agree to.
        """
        self.ensure_one()
        currency = (self.company_id or self.env.company).currency_id
        return {
            'wage': self.wage or 0.0,
            'currency': currency.symbol or '',
            'structure': (self.struct_id.name
                          if getattr(self, 'struct_id', False) else '')
            or (self.structure_type_id.name
                if self.structure_type_id else '') or _('None set'),
            'calendar': (self.resource_calendar_id.name
                         if self.resource_calendar_id else _('None set')),
            'type': self.type_id.name if self.type_id else _('None set'),
            'date_start': str(self.date_start) if self.date_start else '',
            'date_end': str(self.date_end) if self.date_end else '',
        }
