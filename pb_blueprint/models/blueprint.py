# -*- coding: utf-8 -*-
"""The record behind the guided "New configuration" journey.

One row per configuration that was created through the journey. It holds
everything the journey knows that the configuration itself has no field for —
which step you stopped on, which starter you chose, who you said you were
paying — so that closing the browser loses nothing and the configurations
screen can offer "Resume setup".

The configuration is the working copy and it is ALWAYS a draft while this row
is `draft`: the journey never edits a live configuration (BP-R8).
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

#: The six steps, in order. Keys, never numbers — a number changes meaning the
#: day a step is inserted, a key does not (BP-R2).
STEPS = ('start', 'rules', 'connect', 'outputs', 'test', 'finish')

#: The three tasks on the Connect step, and the words behind each pill.
#:
#: `mapping` and `payslip` are things a person does; `approvals` is information
#: only (the owner's ruling of 2026-09-10 — pay runs already follow a fixed
#: chain and a per-configuration approval rule is a later programme), so it has
#: exactly one status for ever and no button.
CONNECT_TASKS = ('mapping', 'payslip', 'approvals')

#: not_started → in_progress → configured, with skipped reachable from any of
#: them and reversible. `needs_review` is NEVER STORED: it is what
#: `bp_readiness` says about a `configured` task whose components have changed
#: since, and storing it would make a status that has to be recomputed anyway
#: into a second, staler answer to the same question.
CONNECT_STATUSES = ('not_started', 'in_progress', 'configured', 'skipped')

DEFAULT_OPTIONAL_STATUS = {
    'mapping': {'status': 'not_started', 'opened_at': '', 'done_at': '',
                'snapshot': []},
    'payslip': {'status': 'not_started', 'opened_at': '', 'done_at': '',
                'snapshot': [], 'snapshot_all': []},
    'approvals': {'status': 'info'},
}


class PbFormulaBlueprint(models.Model):
    _name = 'pb.formula.blueprint'
    _description = 'Guided Payroll Setup'
    _order = 'write_date desc'

    config_id = fields.Many2one(
        'hr.formula.config',
        string='Configuration',
        required=True,
        ondelete='cascade',
        index=True,
        help="The configuration this setup is building.")

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='config_id.company_id',
        store=True,
        index=True)

    # The client mints this once per journey and sends it with every attempt to
    # create the draft. Two presses of Continue, a double click or a retry after
    # a dropped connection therefore all resolve to the SAME configuration.
    token = fields.Char(
        string='Setup Key',
        required=True,
        index=True,
        help="Identifies one run of the setup so a repeated press never "
             "creates a second configuration.")

    state = fields.Selection([
        ('draft', 'Being set up'),
        ('finished', 'Setup complete'),
        ('abandoned', 'Abandoned'),
    ], string='Status', default='draft', required=True, index=True)

    step = fields.Char(
        string='Step',
        default='start',
        required=True,
        help="Which of the six steps the person stopped on.")

    template_key = fields.Char(string='Starting Point')
    template_name = fields.Char(string='Starting Point Name')

    effective_from = fields.Date(string='Effective From')

    situations_json = fields.Text(
        string='Situations (JSON)',
        default='{}',
        help="Who is being paid and which real-life situations were ticked.")

    optional_status_json = fields.Text(
        string='Optional Steps (JSON)',
        default=lambda self: json.dumps(DEFAULT_OPTIONAL_STATUS))

    calendar_json = fields.Text(string='Calendar (JSON)', default='{}')

    # The two tax preferences that are a CHOICE rather than a statutory value:
    # which pay the insurance base is worked out from, and how money is
    # rounded. They live here rather than on the configuration because they are
    # decisions taken during setup, and the configuration has no field for them.
    tax_json = fields.Text(string='Tax Preferences (JSON)', default='{}')

    # Where the screen was left: which tab of Pay rules was open, which group
    # was showing. Deliberately its OWN field rather than a corner of
    # `optional_status_json`: that one is read by the Connect step to decide
    # what is done and what is skipped, and a display preference has no
    # business changing the answer to that question.
    ui_json = fields.Text(string='Screen State (JSON)', default='{}')
    review_items_json = fields.Text(string='Review Items (JSON)', default='[]')

    pack_id = fields.Many2one(
        'hr.formula.legislation.pack',
        string='Rule Pack',
        ondelete='set null',
        help="The statutory rule pack the tax values were pinned to.")
    pack_version = fields.Char(string='Rule Pack Version')

    evidence_hash = fields.Char(string='Evidence Key')
    tests_hash = fields.Char(string='Checks Key')

    revision = fields.Integer(
        string='Revision', default=1, required=True,
        help="Bumped on every save so two people cannot overwrite each other "
             "without being told.")

    # Odoo 19: `_sql_constraints` is silently ignored (GROUP ledger C9) — a
    # uniqueness promise that never reaches the database is worse than none.
    _config_uniq = models.Constraint(
        'unique(config_id)',
        'A configuration can only have one guided setup.')
    _token_uniq = models.Constraint(
        'unique(token, company_id)',
        'That setup key is already in use.')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_company(self):
        """Refuse a blueprint the current user's companies do not cover.

        The record rule on `hr.formula.config` already scopes reads; this is the
        second lock, so a hand-crafted RPC cannot reach another company's draft.
        """
        # `env.company` is not always a member of `env.companies` (a user's
        # `company_id` can sit outside their `company_ids`), so the company the
        # user is standing in is added explicitly — or the guard locks them out
        # of their own screen.
        reachable = set(self.env.companies.ids) | {self.env.company.id}
        for bp in self:
            company = bp.config_id.company_id
            if company and company.id not in reachable:
                raise AccessError(_(
                    "This setup belongs to another company. Ask someone with "
                    "access to %s to open it.", company.name))
        return True

    @property
    def _step_no(self):
        self.ensure_one()
        try:
            return STEPS.index(self.step or 'start') + 1
        except ValueError:
            return 1

    def step_number(self):
        """1..6 for the saved step — the number the picker card shows."""
        self.ensure_one()
        return self._step_no

    @api.model
    def _clean_step(self, step):
        """A step key we are willing to store. Anything else is `start`."""
        step = (step or 'start').strip()
        return step if step in STEPS else 'start'

    def write(self, vals):
        if 'step' in vals:
            vals = dict(vals, step=self._clean_step(vals.get('step')))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'step' in vals:
                vals['step'] = self._clean_step(vals.get('step'))
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # JSON accessors — every reader gets a dict, never a parse error
    # ------------------------------------------------------------------
    def _json(self, field, fallback):
        self.ensure_one()
        raw = self[field]
        if not raw:
            return fallback
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            _logger.warning("pb.formula.blueprint %s: %s is not readable JSON",
                            self.id, field)
            return fallback
        return value if isinstance(value, type(fallback)) else fallback

    def situations(self):
        return self._json('situations_json', {})

    def optional_status(self):
        """The three Connect tasks, always in the same shape.

        B1 stored one WORD per task (`{"mapping": "not_started"}`) because that
        was all the step needed; B4 has to remember when a task was opened, when
        it was marked done, and what the configuration looked like at that
        moment. A draft created before this phase therefore holds the old shape,
        and a reader that assumed the new one would raise on the first live
        draft — so the coercion happens HERE, once, and nothing downstream ever
        sees a bare string.
        """
        status = {}
        for task, blank in DEFAULT_OPTIONAL_STATUS.items():
            status[task] = dict(blank)
        stored = self._json('optional_status_json', {})
        for task, value in (stored or {}).items():
            if task not in status:
                continue
            if isinstance(value, str):
                value = {'status': value}
            if not isinstance(value, dict):
                continue
            entry = status[task]
            entry.update({k: v for k, v in value.items() if k in entry})
            if entry.get('status') not in CONNECT_STATUSES and task != 'approvals':
                entry['status'] = 'not_started'
        status['approvals']['status'] = 'info'
        return status

    def set_optional_status(self, status):
        """Store the three tasks. Never bumps the revision on its own — the
        caller decides, because opening a door is not a change anybody else can
        conflict with while marking one done is."""
        self.ensure_one()
        self.optional_status_json = json.dumps(status or {})
        return status

    def calendar(self):
        return self._json('calendar_json', {})

    def tax_prefs(self):
        return self._json('tax_json', {})

    def ui(self):
        return self._json('ui_json', {})

    def set_ui(self, key, value):
        """Remember one thing about the screen. Never bumps the revision —
        which tab somebody had open is not a change anyone else can conflict
        with."""
        self.ensure_one()
        state = self.ui()
        state[key] = value
        self.ui_json = json.dumps(state)
        return state
