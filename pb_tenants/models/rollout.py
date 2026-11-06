# -*- coding: utf-8 -*-
"""A rollout: one release, reaching the fleet in waves.

WHY THIS IS A RECORD AND NOT A SCRIPT. Bringing one customer in step is a
button and a minute. Bringing the fleet in step is hours — a practice run, the
template, one customer, a day of watching, then the rest, each inside their own
night — and nobody is going to sit at the screen for it. So the intention is
written down once, when a person presses Start, and a background worker spends
the next two days doing exactly what was written down and nothing else.

That is also the whole of rail R1 in this phase. The worker never decides to
update anybody. It reads the list a person made, and it stops at the first
thing that goes wrong.
"""
import json

from odoo import api, fields, models

from .rollout_rules import (
    CUSTOMER_RINGS, DEFAULT_HOURS, DEFAULT_START_HOUR, RING_LABEL,
    RING_MEANING, RING_ORDER,
)

RING_SELECTION = [(r, RING_LABEL[r]) for r in CUSTOMER_RINGS]


class PbTenantRollout(models.Model):
    """Which wave a customer is in, and when their night is."""
    _inherit = 'pb.tenant'

    #: Which wave this customer is updated in. Everybody starts in the last
    #: one: a customer becomes a canary because somebody decided they should
    #: be, never because they happened to be created first.
    ring = fields.Selection(
        RING_SELECTION, default='everyone', required=True, index=True,
        help="Which wave of a rollout this customer is updated in.")
    #: The hour their night starts, in THEIR time zone, and how long it lasts.
    maintenance_start = fields.Integer(
        default=DEFAULT_START_HOUR,
        help="The hour their quiet window opens, on their own clock (0–23).")
    maintenance_hours = fields.Integer(
        default=DEFAULT_HOURS,
        help="How many hours the quiet window stays open.")
    #: Read off their own company record the first time it is needed, then
    #: kept here so the worker never has to open their registry to answer
    #: "what time is it where they are".
    tz = fields.Char(
        help="The customer's time zone, read from their own company record.")
    rollout_task_ids = fields.One2many('pb.rollout.task', 'tenant_id')

    def ring_meaning(self):
        self.ensure_one()
        return RING_MEANING.get(self.ring, '')


class PbRollout(models.Model):
    _name = 'pb.rollout'
    _description = 'Payobook release rollout'
    _order = 'create_date desc, id desc'

    release_id = fields.Many2one('pb.release', required=True, ondelete='restrict',
                                 index=True)
    name = fields.Char(compute='_compute_name')
    state = fields.Selection([
        ('draft', 'Not started'),
        ('running', 'Running'),
        ('waiting', 'Waiting'),
        ('paused', 'Stopped'),
        ('done', 'Finished'),
        ('aborted', 'Called off'),
    ], default='draft', required=True, index=True)
    current_ring = fields.Selection([(r, RING_LABEL[r]) for r in RING_ORDER],
                                    default='rehearsal')
    watch_hours_canary = fields.Integer(default=24)
    watch_hours_early = fields.Integer(default=48)
    #: Set when somebody presses "Continue now" — the watch period for the
    #: CURRENT wave is over early. Cleared the moment the next wave starts, so
    #: it can never quietly shorten a wave nobody meant to shorten.
    watch_skipped = fields.Boolean()
    ring_started_at = fields.Datetime()
    ring_done_at = fields.Datetime()
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    #: Why it stopped, in words the owner can act on. Never a traceback.
    reason = fields.Text()
    started_by = fields.Many2one('res.users', ondelete='set null')
    #: Everything the worker did, newest last: one line per step, the same
    #: trail a provisioning run leaves.
    log = fields.Text(default='[]')
    task_ids = fields.One2many('pb.rollout.task', 'rollout_id')

    task_count = fields.Integer(compute='_compute_counts')
    done_count = fields.Integer(compute='_compute_counts')
    failed_count = fields.Integer(compute='_compute_counts')
    queued_count = fields.Integer(compute='_compute_counts')
    customer_total = fields.Integer(compute='_compute_counts')
    customer_done = fields.Integer(compute='_compute_counts')

    @api.depends('release_id.name', 'create_date')
    def _compute_name(self):
        for r in self:
            r.name = r.release_id.name or 'Rollout'

    @api.depends('task_ids.state', 'task_ids.ring')
    def _compute_counts(self):
        for r in self:
            tasks = r.task_ids
            r.task_count = len(tasks)
            r.done_count = len(tasks.filtered(lambda t: t.state == 'done'))
            r.failed_count = len(tasks.filtered(lambda t: t.state == 'failed'))
            r.queued_count = len(tasks.filtered(lambda t: t.state == 'queued'))
            cust = tasks.filtered(lambda t: t.ring in CUSTOMER_RINGS)
            r.customer_total = len(cust)
            r.customer_done = len(cust.filtered(lambda t: t.state == 'done'))

    def log_line(self, line, level='info'):
        """One line in the rollout's own trail. Never raises."""
        self.ensure_one()
        try:
            rows = json.loads(self.log or '[]')
        except ValueError:
            rows = []
        rows.append({'line': line, 'level': level,
                     'ts': fields.Datetime.now().isoformat(timespec='seconds')})
        self.sudo().write({'log': json.dumps(rows[-400:])})
        return line

    def log_rows(self):
        self.ensure_one()
        try:
            rows = json.loads(self.log or '[]')
        except ValueError:
            return []
        return rows if isinstance(rows, list) else []


class PbRolloutTask(models.Model):
    """One database, one release, one attempt at a time."""
    _name = 'pb.rollout.task'
    _description = 'Payobook rollout task'
    _order = 'sequence, id'

    rollout_id = fields.Many2one('pb.rollout', required=True, ondelete='cascade',
                                 index=True)
    sequence = fields.Integer(default=10, index=True)
    ring = fields.Selection([(r, RING_LABEL[r]) for r in RING_ORDER],
                            required=True, index=True)
    #: Empty for the practice run and the template — neither is a customer.
    tenant_id = fields.Many2one('pb.tenant', ondelete='cascade', index=True)
    #: Whose backup the practice copy is restored from. Only the rehearsal has
    #: one, and it is deliberately NOT `tenant_id`: a practice run on a copy of
    #: somebody's data is not an update that customer received, and it must
    #: never appear on their own timeline as though it were.
    source_tenant_id = fields.Many2one('pb.tenant', ondelete='set null')
    label = fields.Char(required=True)
    #: The database actually acted on: `abm-staging`, `payobook_template`, `abm`.
    target_db = fields.Char(required=True)
    state = fields.Selection([
        ('queued', 'Waiting'),
        ('running', 'Updating'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ], default='queued', required=True, index=True)
    #: Somebody pressed "Run now": ignore the window for this one task.
    run_now = fields.Boolean()
    run_now_by = fields.Many2one('res.users', ondelete='set null')
    notified_at = fields.Datetime(
        help="When this customer's users were told it was coming.")
    scheduled_for = fields.Datetime(
        help="When their window next opens. Recomputed as the rollout runs.")
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    duration_s = fields.Integer()
    attempts = fields.Integer()
    result = fields.Text(help="What the update did, as it was reported.")
    error = fields.Text()
    health = fields.Text(help="What the checks found afterwards.")

    def _json(self, field):
        self.ensure_one()
        try:
            return json.loads(getattr(self, field) or '{}')
        except ValueError:
            return {}

    def result_dict(self):
        return self._json('result')

    def health_dict(self):
        return self._json('health')
