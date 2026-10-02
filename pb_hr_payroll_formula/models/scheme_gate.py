# -*- coding: utf-8 -*-
"""The doors into a live pay scheme, and the one key that opens them.

FIVE DOORS. Activate, merge a branch, seal a release, roll one back, retire the
scheme. Each of them changes what people are paid, and each of them used to be
a button gated on nothing but "may this person edit schemes?".

ONE KEY. `_require_proposal(config, kind)` lets a door through only when the
context carries the apply sentinel — which only `pb.scheme.proposal._approval_apply`
can put there. Everything else is refused with a sentence naming the way in.

TWO WAYS PAST IT, BOTH OF THEM THE BUSINESS'S OWN CHOICE:

  * no published "Scheme change" route at all, or
  * a route that is the fast lane ("no approval needed"),

in which case the door does what it always did, and writes a proposal row
marked `applied` so the trail exists either way. This is the flexibility ruling
in the ledger: the business decides, the system records.

THE ISOLATION RULE. A rule on an ACTIVE scheme cannot have its arithmetic
changed in place while scheme-change approval is in force — the change belongs
on a branch, which is then proposed. Only the fields that decide what a
component PAYS are held: renaming a component, moving it on the payslip or
changing where its value comes from is not a change to the money and has never
needed a route. (Deliberate narrowing of the handover's "rule-bearing fields";
see the ledger.)
"""

import hashlib
import json
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from .scheme_proposal import KIND_NAME, SCHEME_PROCESS_KEY, is_applying

_logger = logging.getLogger(__name__)

#: The rule fields that decide what a component PAYS. Anything outside this set
#: is presentation or plumbing and stays editable on a live scheme.
MONEY_FIELDS = {'excel_formula', 'python_formula', 'constant_value',
                'column_type'}

#: What the route decided, in three words the doors can read.
ROUTE_OPEN = 'open'        # nothing is set up — the old behaviour
ROUTE_FAST = 'fast'        # published choice: no approval needed
ROUTE_STEPS = 'steps'      # somebody has to say yes


class HrFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    # ==================================================================
    # the content stamp
    # ==================================================================
    def _content_hash(self):
        """A key for "these are the rules that decide the money".

        Everything that can change a number and nothing that cannot: each
        component's code, what kind of column it is, its formula normalised the
        way the engine normalises it, and its fixed value; then every tax band
        table with its brackets. A name, a sequence or a payslip position moves
        no money, so none of them belongs in here — a key that changed when
        somebody renamed a component would cry stale for nothing.

        Moved here from `pb_blueprint`, which computed exactly this under the
        name `_evidence_hash` and now calls this. Two copies of a hash are two
        different answers to the same question, one of which will be wrong.
        """
        self.ensure_one()
        Rule = self.env['hr.formula.rule']
        parts = []
        for rule in self.rule_ids:
            code = (rule.code or '').upper()
            if not code:
                continue
            formula = Rule._normalize_excel_formula(rule.excel_formula or '') \
                or ''
            constant = round(float(rule.constant_value or 0.0), 6)
            parts.append((code, rule.column_type or '', formula, constant))
        tables = []
        for table in self.rate_table_ids:
            brackets = sorted((round(float(line.lower or 0.0), 6),
                               round(float(line.rate or 0.0), 6))
                              for line in table.line_ids)
            tables.append(((table.code or '').upper(), brackets))
        blob = json.dumps({'components': sorted(parts),
                           'tables': sorted(tables)},
                          sort_keys=True, default=str)
        return hashlib.sha256(blob.encode('utf-8')).hexdigest()

    def _touches_tax_rules(self, codes):
        """Does any of these component codes sit in a statutory category?"""
        self.ensure_one()
        if not codes:
            return False
        wanted = {(code or '').upper() for code in codes}
        for rule in self.sudo().rule_ids:
            if (rule.code or '').upper() not in wanted:
                continue
            category = (rule.category_id.code or '').upper()
            if category in ('TAX', 'SI', 'HI', 'UI', 'STAT', 'DED'):
                return True
        return False

    # ==================================================================
    # the route
    # ==================================================================
    def _scheme_route(self):
        """What the business published for changing THIS scheme.

        Read under `sudo()` because it is a GUARD: the person activating a
        scheme is not necessarily allowed to read the approval set-up, and
        refusing them because they cannot look would be the wrong answer to the
        wrong question (the audit-console pattern, ledger AM35).
        """
        self.ensure_one()
        if 'biz.approval.engine' not in self.env:
            return ROUTE_OPEN, None
        process = self.env['biz.approval.process']._by_key(SCHEME_PROCESS_KEY)
        if not process or not process.connected:
            return ROUTE_OPEN, None
        company = self.company_id or self.env.company
        engine = self.env['biz.approval.engine'].sudo()
        answer = engine.resolve_binding(
            company.id, SCHEME_PROCESS_KEY, ['scheme:%s' % self.id, ''],
            'any')
        if answer.get('error'):
            # No route, a tie, a pause: "no route" is an open door (nothing was
            # ever asked for), and anything else is a set-up fault that must not
            # silently become one.
            if answer['error'].get('code') == 'no_route':
                return ROUTE_OPEN, None
            raise UserError(_(
                "Changes to this pay scheme cannot be made right now: %s",
                answer['error'].get('message') or ''))
        version = self.env['biz.approval.workflow.version'].sudo().browse(
            answer['version_id'])
        from odoo.addons.biz_approval_workflow.models import definition as D
        steps = [step for step in D.decision_steps(version.definition)]
        if not steps or any(step.get('kind') == 'fast' for step in steps):
            return ROUTE_FAST, version
        return ROUTE_STEPS, version

    def _require_proposal(self, kind):
        """The gate every door calls. Returns the proposal row it recorded."""
        self.ensure_one()
        if is_applying(self.env):
            return self.env['pb.scheme.proposal']
        mode, version = self._scheme_route()
        if mode == ROUTE_STEPS:
            raise UserError(_(
                "“%(what)s” on “%(scheme)s” is approved before it happens. Use "
                "“Propose for approval” on the scheme — the change goes to "
                "whoever your business has chosen for scheme changes, and is "
                "carried out once they agree.",
                what=_(KIND_NAME.get(kind, kind)),
                scheme=self.name or ''))
        # The business chose not to check this. Record it anyway.
        return self._record_unchecked(kind, mode)

    def _record_unchecked(self, kind, mode):
        """A proposal row for a change nobody was asked about."""
        self.ensure_one()
        Proposal = self.env['pb.scheme.proposal'].sudo()
        note = (_("No approval needed for scheme changes here — recorded.")
                if mode == ROUTE_FAST
                else _("No approval route is set up for scheme changes here — "
                       "recorded."))
        try:
            proposal = Proposal.create({
                'company_id': (self.company_id or self.env.company).id,
                'config_id': self.id,
                'kind': kind,
                'sealed_hash': self._content_hash(),
                'note': note,
                'state': 'applied',
                'apply_note': note,
            })
            proposal.write({'applied_at': fields.Datetime.now()})
            return proposal
        except Exception:       # noqa: BLE001 — the trail must not stop the act
            _logger.exception('pb_hr_payroll_formula: a scheme change on %s '
                              'could not be recorded', self.id)
            return Proposal.browse()

    # ==================================================================
    # the doors this model owns
    # ==================================================================
    def action_activate(self):
        for config in self:
            config._require_proposal('activate')
        return super().action_activate()

    def action_archive(self):
        for config in self:
            # A branch is scratch work: discarding one is not a change to
            # anything anybody is paid by, and routing it through an approval
            # would be an approval for tidying up.
            if config.parent_branch_id:
                continue
            config._require_proposal('archive')
        return super().action_archive()

    def write(self, vals):
        """Adding or removing components on a live scheme is a money change."""
        if vals and 'rule_ids' in vals and not is_applying(self.env):
            for config in self:
                if config.state == 'active':
                    config._require_proposal('activate')
        return super().write(vals)


class HrFormulaRule(models.Model):
    _inherit = 'hr.formula.rule'

    def _scheme_isolation_check(self, vals=None, what='edit'):
        """Refuse a money change made straight onto a live scheme."""
        if is_applying(self.env):
            return
        if vals is not None and not MONEY_FIELDS.intersection(vals):
            return
        configs = self.mapped('config_id').filtered(
            lambda c: c.state == 'active' and not c.parent_branch_id)
        for config in configs:
            mode, _version = config._scheme_route()
            if mode != ROUTE_STEPS:
                continue
            raise UserError(_(
                "“%(scheme)s” is live, so what it pays cannot be changed here. "
                "Create a branch, make the change there, then propose it — the "
                "change goes live once it is approved.",
                scheme=config.name or ''))

    def write(self, vals):
        self._scheme_isolation_check(vals)
        return super().write(vals)

    def unlink(self):
        self._scheme_isolation_check(None, what='remove')
        return super().unlink()
