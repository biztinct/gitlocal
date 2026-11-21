# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The catalogue: one row per business object that can need a sign-off."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

AREAS = [
    ('pay', 'Pay'),
    ('money', 'Money out'),
    ('data', 'Pay data'),
    ('people', 'People'),
    ('time', 'Time'),
    ('setup', 'Setup & rules'),
    ('platform', 'Platform'),
    ('other', 'Other'),
]

#: WDGAP QF1 — the kinds of request a manager may approve several at once
#: when the product is first given the choice. Everything else (pay, money
#: out, pay data, set-up, platform, every `money` process, leavers, verdicts,
#: hires, contracts, pay and bank changes, hiring, "Other request", workflow
#: studio) is decided one at a time. Applied ONCE: a row created later gets
#: it at creation (`create`), the rows already there get it from the
#: 19.0.1.8.0 post-migration (`_seed_bulk_defaults`), and nothing re-asserts
#: it afterwards, so a customer's own choice survives every upgrade.
BULK_DEFAULT_KEYS = frozenset({
    'leave', 'overtime', 'timesheet', 'correction', 'trip',
    'training_request', 'goal_set', 'goal_change', 'recognition',
    'hr_comm_post', 'letters',
})

#: The marker that says the existing rows have had their one-time default.
BULK_SEEDED_PARAM = 'biz_approval_workflow.bulk_ok_seeded'


class BizApprovalProcess(models.Model):
    _name = 'biz.approval.process'
    _description = 'Approval Process'
    _order = 'sequence, name'

    key = fields.Char(required=True, index=True, copy=False,
                      help='Stable identifier an adapter declares.')
    name = fields.Char(required=True, translate=True)
    area = fields.Selection(AREAS, default='other', required=True)
    model_name = fields.Char(
        string='Business object',
        help='The model whose records this process approves.')
    description = fields.Text(translate=True)
    allow_fast = fields.Boolean(
        string='"No approval needed" allowed', default=True,
        help='The business decides. Kept so a later release can advise '
             'against it for a process; it never blocks a publish.')
    money = fields.Boolean(
        string='Money leaves the company',
        help='Publishing a one-person route for this process raises a '
             'warning the publisher confirms.')
    bulk_ok = fields.Boolean(
        string='Can be approved several at once',
        help='A manager may tick several of these in the Approvals inbox and '
             'approve them together. Never allowed where money leaves the '
             'company.')
    connected = fields.Boolean(compute='_compute_connected',
                               string='Wired up')
    #: ANOTHER ROW ALREADY ANSWERS THIS ONE.
    #:
    #: Some acts turn out, once the adapters exist, to be the same decision
    #: as another row rather than one of their own: a retro line is created
    #: inside a pay-data load and travels that route; taking an approved run
    #: back is the pay-run request's own send-back, decided by the same
    #: people on the same request. A row like that must not sit on the
    #: Matrix reading "Not connected yet", which says "nobody is checking
    #: this" about something somebody IS checking. It names the row that
    #: covers it instead, and the screen says so in words.
    #:
    #: Set by the covering adapter's own seed, never in the catalogue's data
    #: file, which is `noupdate` (ledger AM45).
    covered_by_key = fields.Char(string='Covered by')
    covered_by_name = fields.Char(compute='_compute_covered_by',
                                  string='Covered by (name)')

    @api.depends('covered_by_key')
    def _compute_covered_by(self):
        for rec in self:
            other = self._by_key(rec.covered_by_key) \
                if rec.covered_by_key else None
            rec.covered_by_name = other.name if other else ''
    sequence = fields.Integer(default=10)
    workflow_ids = fields.One2many('biz.approval.workflow', 'process_id')
    workflow_count = fields.Integer(compute='_compute_workflow_count')

    _key_uniq = models.Constraint(
        'unique(key)',
        'Another process already uses that identifier.')

    @api.constrains('bulk_ok', 'money')
    def _check_bulk_not_money(self):
        for rec in self:
            if rec.bulk_ok and rec.money:
                raise ValidationError(_(
                    "\"%s\" moves money out of the company, so each one is "
                    "approved on its own. It cannot be approved several at "
                    "once.", rec.name))

    @api.model_create_multi
    def create(self, vals_list):
        # A row born after the one-time default still gets it: the catalogue
        # rows live in other modules' data files, installed in any order.
        for vals in vals_list:
            if 'bulk_ok' not in vals and vals.get('key') in BULK_DEFAULT_KEYS \
                    and not vals.get('money'):
                vals['bulk_ok'] = True
        return super().create(vals_list)

    @api.model
    def _seed_bulk_defaults(self):
        """Give the rows that already exist their one-time default.

        Runs once per database (the marker parameter), so a customer who later
        turns a kind on or off keeps that choice through every upgrade. Only a
        row still at the field's default (False) is touched, and never a money
        process. Returns the keys it switched on."""
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(BULK_SEEDED_PARAM):
            return []
        rows = self.sudo().search([('key', 'in', sorted(BULK_DEFAULT_KEYS)),
                                   ('bulk_ok', '=', False),
                                   ('money', '=', False)])
        rows.write({'bulk_ok': True})
        params.set_param(BULK_SEEDED_PARAM, '1')
        return sorted(rows.mapped('key'))

    @api.depends('model_name', 'key')
    def _compute_connected(self):
        """Wired up means: the model this row names really does answer for THIS
        row's key. A model can serve more than one (`_approval_process_keys`),
        which is how "this run only" and "past pay data" are two rows over one
        pay-data file and still both honest."""
        for rec in self:
            model = rec.model_name
            adapter = self.env[model] if model and model in self.env else None
            declared = getattr(adapter, '_approval_process_key', None) \
                if adapter is not None else None
            served = set(getattr(adapter, '_approval_process_keys', ()) or ()) \
                if adapter is not None else set()
            if declared:
                served.add(declared)
            rec.connected = bool(declared) and rec.key in served

    @api.depends('workflow_ids')
    def _compute_workflow_count(self):
        for rec in self:
            rec.workflow_count = len(rec.workflow_ids)

    @api.model
    def _by_key(self, key):
        return self.sudo().search([('key', '=', key)], limit=1)
