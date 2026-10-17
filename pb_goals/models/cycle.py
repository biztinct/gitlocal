# -*- coding: utf-8 -*-
"""`pb.goal.cycle` — the year everybody's goals belong to.

ONE OPEN CYCLE PER COMPANY AT A TIME, and the refusal names the one that is
already open. Two open cycles is not a configuration, it is a question nobody
can answer: the kick-off on a new joiner's second day has to put their goal
sheet in A cycle, and "whichever one the search found first" is how a
Vietnamese joiner ends up writing goals for last year.

"OPEN IT FOR EVERYONE" IS A BUTTON AND NEVER A NIGHT'S WORK (R54). It makes one
goal sheet per active employee of the company, which on this database is four
and a half thousand rows and four and a half thousand emails, so it is off the
automatic path entirely: a human presses it, and the button SAYS HOW MANY it
would make before it makes any. Pressing it twice makes nothing the second
time — a person already holding a sheet in this cycle is skipped, which is what
makes "run it again after the new starters arrive" a safe thing to do rather
than a thing somebody has to think about.
"""

import logging

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import (
    CYCLE_STATES, P_BULK_CAP, P_SUBMISSION_DAYS, counted, leg, number,
)

_logger = logging.getLogger(__name__)


class PbGoalCycle(models.Model):
    _name = 'pb.goal.cycle'
    _description = 'Goal cycle'
    _inherit = ['mail.thread']
    #: Newest first: the year somebody is working in is the year they opened
    #: last, and a list that opens on 2019 is a list nobody scrolls.
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='What it is called', required=True, tracking=True,
        help='The year as people say it out loud — "FY2026", "2026", '
             '"April 2026 to March 2027".')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    date_start = fields.Date(string='Runs from', required=True, tracking=True)
    date_end = fields.Date(string='Runs to', required=True, tracking=True)
    mid_year_date = fields.Date(
        string='Half-way point',
        help='The day the year is looked at half-way through. Nothing happens '
             'on it yet; it is here so the date is agreed once, at the top, '
             'rather than argued about in October.')
    submission_days = fields.Integer(
        string='Days to write their goals', default=lambda self: number(
            self.env, P_SUBMISSION_DAYS, 14),
        help='How long somebody gets from the day their goal sheet is opened. '
             'Two weeks by default.')
    state = fields.Selection(
        CYCLE_STATES, string='Status', default='draft', required=True,
        index=True, tracking=True, copy=False)
    active = fields.Boolean(default=True)

    set_ids = fields.One2many('pb.goal.set', 'cycle_id',
                              string='Goal sheets')
    set_count = fields.Integer(string='Goal sheets',
                               compute='_compute_counts')
    locked_count = fields.Integer(string='Agreed and locked',
                                  compute='_compute_counts')
    note = fields.Text(string='Anything to say about this year')

    # ------------------------------------------------------------ the shape
    @api.depends('set_ids', 'set_ids.state')
    def _compute_counts(self):
        # ONE QUERY FOR ALL OF THEM. A count per record over a cycle with
        # four thousand sheets on it is four thousand reads to draw a list.
        grouped = {}
        if self.ids:
            rows = self.env['pb.goal.set'].sudo()._read_group(
                [('cycle_id', 'in', self.ids)], ['cycle_id', 'state'],
                ['__count'])
            for cycle, state, count in rows:
                bucket = grouped.setdefault(cycle.id, {})
                bucket[state] = count
        for cycle in self:
            bucket = grouped.get(cycle.id, {})
            cycle.set_count = sum(bucket.values())
            cycle.locked_count = bucket.get('locked', 0)

    @api.constrains('date_start', 'date_end', 'mid_year_date')
    def _check_dates(self):
        for cycle in self:
            if cycle.date_end and cycle.date_start \
                    and cycle.date_end <= cycle.date_start:
                raise ValidationError(_(
                    "A goal year has to end after it starts. %(name)s runs "
                    "from %(start)s to %(end)s.", name=cycle.name or '',
                    start=cycle.date_start, end=cycle.date_end))
            if cycle.mid_year_date and cycle.date_start and cycle.date_end \
                    and not (cycle.date_start <= cycle.mid_year_date
                             <= cycle.date_end):
                raise ValidationError(_(
                    "The half-way point has to fall inside the year. "
                    "%(name)s runs from %(start)s to %(end)s.",
                    name=cycle.name or '', start=cycle.date_start,
                    end=cycle.date_end))

    @api.constrains('submission_days')
    def _check_submission_days(self):
        for cycle in self:
            if cycle.submission_days < 1:
                raise ValidationError(_(
                    "Somebody needs at least a day to write their goals."))

    def _compute_display_name(self):
        # Odoo 19: `_compute_display_name`, never `name_get`.
        for cycle in self:
            cycle.display_name = cycle.name or _('Goal year')

    # ------------------------------------------------------------ the doors
    @api.model
    def open_cycle_for(self, company_id=None):
        """The one open cycle of a company, or an empty recordset.

        Read AS THE SYSTEM and never as the caller: the kick-off runs for a new
        joiner who holds no goals permission at all, and a cycle nobody can
        read is a cycle nobody can be put in. The company clause is written out
        explicitly, which is this product's rule everywhere (R89).
        """
        company_id = int(company_id or self.env.company.id)
        return self.sudo().search(
            [('company_id', '=', company_id), ('state', '=', 'open')],
            order='date_start desc', limit=1)

    def action_open(self):
        """Open it. One at a time, and the refusal names the other one."""
        for cycle in self:
            if cycle.state == 'open':
                continue
            other = cycle.sudo().search([
                ('company_id', '=', cycle.company_id.id),
                ('state', '=', 'open'), ('id', '!=', cycle.id)], limit=1)
            if other:
                raise UserError(_(
                    "%(other)s is already open for %(company)s, and only one "
                    "goal year can be open at a time. Close that one first, "
                    "or open this one afterwards.", other=other.name or '',
                    company=cycle.company_id.name or ''))
            cycle.write({'state': 'open'})
            cycle.message_post(body=_("Open. People can be given their goal "
                                      "sheets now."))
        return True

    def action_close(self):
        for cycle in self:
            if cycle.state == 'closed':
                continue
            cycle.write({'state': 'closed'})
            cycle.message_post(body=_("Closed."))
        return True

    def action_back_to_draft(self):
        self.filtered(lambda c: c.state != 'draft').write({'state': 'draft'})
        return True

    # ------------------------------------------- opening it for everybody
    def _eligible_employees(self):
        """Who would get a goal sheet, as the system.

        READ AS THE SYSTEM (R56/R104): one field of an `hr.employee` prefetches
        forty and about forty of those sit behind payroll groups, so an HR
        administrator who holds the goals groups and not the payroll ones is
        otherwise refused a list of names. The security boundary is the search
        that found them — the company clause below — and not the read.
        """
        self.ensure_one()
        return self.env['hr.employee'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ], order='id')

    @api.model
    def preview_open_for_everyone(self, cycle_id):
        """How many sheets the button would make, WITHOUT making any.

        A SWITCH THAT IS OFF AND DOES NOT SAY SO IS REPORTED AS BROKEN (R54),
        and the same is true of a button that writes to four thousand people:
        it has to say the number first. Answers a plain dict so the board can
        put the sentence in the dialog.
        """
        cycle = self.sudo().browse(int(cycle_id or 0)).exists()
        if not cycle:
            return {'ok': False, 'sentence': _("That goal year is gone.")}
        if cycle.state != 'open':
            return {'ok': False, 'sentence': _(
                "%s is not open yet. Open it first, then hand out the goal "
                "sheets.", cycle.name or '')}
        people = cycle._eligible_employees()
        already = self.env['pb.goal.set'].sudo().search_count(
            [('cycle_id', '=', cycle.id)])
        existing = set(self.env['pb.goal.set'].sudo().search(
            [('cycle_id', '=', cycle.id)]).mapped('employee_id').ids)
        todo = [emp for emp in people if emp.id not in existing]
        cap = number(self.env, P_BULK_CAP, 2000)
        capped = len(todo) > cap
        if not todo:
            sentence = _(
                "Everybody in %(company)s already has a goal sheet for "
                "%(cycle)s — all %(n)s of them. There is nothing to hand out.",
                company=cycle.company_id.name or '', cycle=cycle.name or '',
                n=already)
        else:
            sentence = _(
                "This will open a goal sheet for %(n)s %(word)s in "
                "%(company)s, each due %(days)s days from today. "
                "%(skip)s",
                n=len(todo) if not capped else cap,
                word=counted(len(todo), _('person'), _('people')),
                company=cycle.company_id.name or '',
                days=cycle.submission_days or 14,
                skip=(_("%s already have one and are left alone.", already)
                      if already else _("Nobody has one yet.")))
            if capped:
                sentence += ' ' + _(
                    "There are %(total)s to do and this press will do the "
                    "first %(cap)s — press it again for the rest.",
                    total=len(todo), cap=cap)
        return {'ok': bool(todo), 'todo': len(todo), 'already': already,
                'cap': cap, 'capped': capped, 'sentence': sentence,
                'cycle': cycle.name or ''}

    @api.model
    def open_for_everyone(self, cycle_id):
        """Make the sheets. Idempotent: a second press makes none."""
        cycle = self.sudo().browse(int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That goal year is gone."))
        if not self.env.user.has_group('pb_goals.group_goals_manager'):
            raise UserError(_(
                "Handing out goal sheets to a whole company is for the HR "
                "team. Ask your HR administrator."))
        if cycle.state != 'open':
            raise UserError(_(
                "%s is not open yet. Open it first, then hand out the goal "
                "sheets.", cycle.name or ''))
        return cycle._open_for_everyone()

    def _open_for_everyone(self):
        self.ensure_one()
        Set = self.env['pb.goal.set'].sudo()
        existing = set(Set.search([('cycle_id', '=', self.id)]).mapped(
            'employee_id').ids)
        cap = number(self.env, P_BULK_CAP, 2000)
        today = fields.Date.today()
        deadline = today + timedelta(days=max(self.submission_days or 14, 1))
        made = self.env['pb.goal.set'].sudo()
        skipped = 0
        for employee in self._eligible_employees():
            if employee.id in existing:
                skipped += 1
                continue
            if len(made) >= cap:
                break
            # ONE SAVEPOINT PER PERSON (R131). One employee with a broken
            # manager pointer must not cost the other four thousand their
            # goal sheets — and a bare try/except would, because the
            # transaction is already dead by the time Python sees the error.
            created = leg(self.env, 'goal sheet for %s' % employee.id,
                          lambda emp=employee: Set.create({
                              'employee_id': emp.id,
                              'cycle_id': self.id,
                              'deadline': deadline,
                              'company_id': (emp.company_id
                                             or self.company_id).id,
                          }))
            if created:
                made |= created
        if made:
            made._notify_kickoff()
            self._register_demo(made)
        self.message_post(body=_(
            "%(n)s %(word)s opened, due %(due)s. %(skip)s",
            n=len(made), word=counted(len(made), _('goal sheet'),
                                      _('goal sheets')),
            due=deadline,
            skip=(_("%s already had one.", skipped) if skipped
                  else _("Nobody had one already."))))
        _logger.info('pb_goals: %s goal sheet(s) opened on cycle %s, %s '
                     'skipped', len(made), self.id, skipped)
        return {'made': len(made), 'skipped': skipped,
                'deadline': str(deadline)}

    def _register_demo(self, records):
        """Put anything this makes on the demo register when there is one.

        The guard keeps `pb_demo_seed` optional: a tenant that has not got the
        module gets `None` and nothing happens (ledger rule 9).
        """
        seed = self.env.get('pb.demo.seed')
        if seed is None or not records:
            return False
        try:
            return seed.register(records, 'Goal sheets for %s' % (
                self.name or 'a goal year'))
        except Exception:               # noqa: BLE001 — a register is not the
            _logger.warning('pb_goals: the goal sheets could not be '        # work
                            'registered as demo data', exc_info=True)
            return False

    # ------------------------------------------------------------ the doors
    def action_view_sets(self):
        """Open this year's goal sheets.

        R125 — A HAND-BUILT `ir.actions.act_window` DICT MUST CARRY `views`.
        `_preprocessAction` maps over `action.views` unconditionally, and the
        ORM computes that field only on a real action RECORD, so a dict
        returned from a facade and handed to `doAction` throws a TypeError the
        theme shows as a generic "something went wrong" with nothing in the
        console.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal sheets · %s', self.name or ''),
            'res_model': 'pb.goal.set',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('cycle_id', '=', self.id)],
            'context': {'default_cycle_id': self.id},
        }
