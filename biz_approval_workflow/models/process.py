# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The catalogue: one row per business object that can need a sign-off."""

from odoo import api, fields, models

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
