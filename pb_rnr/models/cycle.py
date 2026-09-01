# -*- coding: utf-8 -*-
"""`pb.rnr.cycle` — a quarter, the roll-up, and the people it ended on.

A quarter is a WINDOW and nothing more clever than that. What makes it useful is
the roll-up: everybody who was recognised inside the window, ranked by how many
colleagues said so and under which values, so a choice is made from a table
rather than from whoever somebody remembered on the day.

Picking a winner marks their praise `is_winner` and, when an amount is set,
raises the award through the SAME `_make_award` path a single decision uses.
There is no second money lane in this module and there is not going to be one.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rnr_common import CYCLE_STATES, PUBLIC_OUTCOMES, counted

_logger = logging.getLogger(__name__)

ROLLUP_LIMIT = 60


class PbRnrCycle(models.Model):
    _name = 'pb.rnr.cycle'
    _description = 'Recognition quarter'
    _order = 'date_from desc, id desc'

    name = fields.Char(string='Name', required=True,
                       help='What people call it — "Q3 2026".')
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    state = fields.Selection(CYCLE_STATES, string='Where it is', default='open',
                             required=True)
    top_ids = fields.Many2many(
        'pb.rnr.nomination', 'pb_rnr_cycle_top_rel', 'cycle_id',
        'nomination_id', string='The ones that were chosen')
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 default=lambda self: self.env.company)
    winner_count = fields.Integer(string='Winners',
                                  compute='_compute_winner_count')

    @api.depends('top_ids')
    def _compute_winner_count(self):
        for rec in self:
            rec.winner_count = len(rec.top_ids)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Quarter')

    @api.constrains('date_from', 'date_to')
    def _check_window(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise UserError(_("A quarter cannot end before it starts."))

    # ------------------------------------------------------------- the reads
    def _window_domain(self):
        """The praise this quarter is about.

        AGREED praise only, and by the date it was DECIDED rather than written:
        a story written in June and agreed in July belongs to the quarter that
        agreed it, which is the one that can still do something about it.
        """
        self.ensure_one()
        domain = [
            ('state', '=', 'done'),
            ('outcome', 'in', list(PUBLIC_OUTCOMES)),
            ('decided_at', '>=', fields.Datetime.to_datetime(self.date_from)),
        ]
        if self.date_to:
            end = fields.Datetime.to_datetime(self.date_to).replace(
                hour=23, minute=59, second=59)
            domain.append(('decided_at', '<=', end))
        if self.company_id:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', self.company_id.id)]
        return domain

    def roll_up(self):
        """Rank the quarter. Reads only — nothing is written until somebody
        picks, and then they have already read this table.

        Returns a list of rows, most-named first:
        `{employee, employee_id, initials, avatar, count, values, story,
          nomination_id, is_winner, award}`.
        """
        self.ensure_one()
        Nom = self.env['pb.rnr.nomination'].sudo()
        recs = Nom.search(self._window_domain(), order='decided_at desc, id desc')
        by_emp = {}
        for rec in recs:
            emp = Nom._person(rec.nominee_id)
            if not emp:
                continue
            row = by_emp.setdefault(emp.id, {
                'employee_id': emp.id,
                'employee': emp.name or '',
                'avatar': '/web/image/hr.employee/%s/image_128' % emp.id,
                'count': 0,
                'values': [],
                'value_keys': set(),
                'story': '',
                'nomination_id': 0,
                'is_winner': False,
                'award': 0.0,
                'currency': (rec.currency_id.symbol or ''),
            })
            row['count'] += 1
            val = rec.value_id.sudo()
            if val and val.id not in row['value_keys']:
                row['value_keys'].add(val.id)
                row['values'].append({'id': val.id, 'name': val.name or '',
                                      'color': val.color or 'primary'})
            if not row['nomination_id']:
                # The most recent agreed story is the one shown beside the name
                # — a ranked list of people with no words on it is a list nobody
                # can make a decision from.
                row['nomination_id'] = rec.id
                row['story'] = rec.story or ''
            if rec.is_winner:
                row['is_winner'] = True
                row['award'] = rec.award_amount or 0.0
        rows = sorted(by_emp.values(),
                      key=lambda r: (-r['count'], r['employee']))
        for row in rows:
            row.pop('value_keys', None)
        return rows[:ROLLUP_LIMIT]

    # ----------------------------------------------------------- the picking
    def pick_winners(self, picks):
        """`picks` is `[{'nomination_id': int, 'amount': float}]`.

        THE CONFIRMATION IS THE CALLER'S JOB and it has already happened: this
        method is reached from a dialog that has printed, in words, who is being
        chosen and what it costs. What happens here is the writing.

        Idempotent: choosing the same story twice sets the same flag and reuses
        the award that already exists (`_make_award` returns the existing one).
        """
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_(
                "This quarter is closed. Open it again if the winners need to "
                "change."))
        Nom = self.env['pb.rnr.nomination']
        chosen = Nom.browse([int(p.get('nomination_id') or 0)
                             for p in (picks or [])]).exists()
        if not chosen:
            raise UserError(_("Nobody was picked, so nothing was changed."))
        amounts = {int(p.get('nomination_id') or 0): float(p.get('amount') or 0.0)
                   for p in (picks or [])}
        awarded, money = 0, 0.0
        for rec in chosen:
            amount = amounts.get(rec.id) or 0.0
            vals = {'is_winner': True, 'cycle_id': self.id}
            if amount and not rec.incentive_id:
                vals['award_amount'] = amount
            rec.write(vals)
            if rec.award_amount and not rec.incentive_id:
                try:
                    rec._make_award()
                    awarded += 1
                    money += rec.award_amount
                except Exception:           # noqa: BLE001 — one row, not all
                    _logger.exception(
                        'pb_rnr: winner %s was marked but the award could not '
                        'be raised', rec.id)
        self.top_ids = [(6, 0, chosen.ids)]
        if self.state == 'open':
            self.state = 'selecting'
        return {
            'ok': True,
            'winners': len(chosen),
            'awarded': awarded,
            'total': money,
            'msg': _(
                "%(w)s chosen for %(name)s. %(a)s raised, and none of it is "
                "paid until the pay team approves it and puts it into a run.",
                w=counted(len(chosen), _('winner'), _('winners')),
                name=self.name or '',
                a=counted(awarded, _('award was'), _('awards were'))),
        }

    def action_close(self):
        for rec in self:
            rec.state = 'closed'
        return True

    def action_reopen(self):
        for rec in self:
            rec.state = 'open'
        return True

    # --------------------------------------------------- the fresh winners
    @api.model
    def fresh_winners(self, days=45, company_ids=None):
        """Quarters that closed recently enough to still be news.

        Used by the wall's banner and by the digest. A banner that congratulates
        the same people for a year is wallpaper, so it has a shelf life.
        """
        limit_date = fields.Date.subtract(
            fields.Date.context_today(self), days=int(days or 45))
        domain = [('state', '=', 'closed'), ('date_to', '>=', limit_date)]
        ids = company_ids if company_ids is not None else self.env.companies.ids
        if ids:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', list(ids))]
        return self.sudo().search(domain, order='date_to desc, id desc', limit=1)
