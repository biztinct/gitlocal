# -*- coding: utf-8 -*-
"""`pb.my.goals` — everything the employee's own goals page knows.

THE CONTROLLER HOLDS NO RULES. It proves who is asking and it renders; every
fact and every refusal on `/my/goals` comes from here, so the journey a person
walks in a browser is the journey the test suite walks in Python. A controller
that knew the rules would have half of them unreachable from a test and the
other half duplicated in it.

THE EMPLOYEE IS RE-RESOLVED FROM THE SESSION on every call and no method takes
an employee id, so a crafted request can never open somebody else's goals. The
only ids these methods take are a goal, a key result and a template, and every
one of them is checked against the caller's own sheet before anything is read
or written.

READS ARE `sudo()` AND THE BOUNDARY IS THE OWNERSHIP CHECK. An employee holds
no goals group — they are not in HR — so reading their own sheet as themselves
would depend on a record rule doing exactly the right thing for a portal user
on six models. The rule is there (and is tested), and this belt goes with those
braces: prove the row is theirs, then read it as the system. R56 is the other
half — one field of an `hr.employee` prefetches forty, of which forty sit
behind payroll groups.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .goals_common import (
    MAX_GOALS, MAX_KRS, RATINGS, RATING_LABEL, SET_EDITABLE, SET_STATE_LABEL,
    WEIGHT_TOTAL, as_id, counted, due_words,
)

_logger = logging.getLogger(__name__)


def _pct(value):
    """"0", "40", "13.3" — never "0.0".

    A Python float renders through QWeb exactly as Python writes it, so a
    page that has not started reads "0.0% of the way", which is a machine
    talking. Whole numbers print whole.
    """
    number = round(float(value or 0.0), 1)
    return int(number) if number == int(number) else number


def _figure(value):
    """"3,200,000,000" — and "40" rather than "40.0"."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return ''
    if not number:
        return ''
    if number == int(number):
        return '{:,}'.format(int(number))
    return '{:,.2f}'.format(number)


class PbMyGoals(models.AbstractModel):
    _name = 'pb.my.goals'
    _description = 'My goals'

    # ------------------------------------------------------------- plumbing
    @api.model
    def _me(self):
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def _my_sets(self):
        me = self._me()
        if not me:
            return self.env['pb.goal.set'].sudo().browse()
        return self.env['pb.goal.set'].sudo().search(
            [('employee_id', '=', me.id)], order='id desc')

    @api.model
    def _current(self):
        """The sheet the page is about.

        The one in the OPEN goal year if there is one, otherwise the newest.
        Never "the first one the search found": a person with three years of
        goals opening their page wants this year's, and last year's is one
        press away underneath.
        """
        sets = self._my_sets()
        live = sets.filtered(lambda s: s.cycle_id.state == 'open')
        return (live.sorted(lambda s: s.cycle_id.date_start or fields.Date
                            .today(), reverse=True)[:1]
                or sets[:1])

    @api.model
    def _own(self, model, record_id):
        """Prove a row belongs to the caller before touching it."""
        record = self.env[model].sudo().browse(as_id(record_id)).exists()
        if not record:
            raise UserError(_("That is not there any more."))
        me = self._me()
        owner = record.employee_id if 'employee_id' in record._fields \
            else record.set_id.employee_id
        if not me or owner.id != me.id:
            raise UserError(_(
                "That one is not yours. If you think it should be, tell your "
                "HR team."))
        return record

    @api.model
    def home_count(self):
        """The eager counter behind the card on `/my`.

        A CARD GATED ON A COUNTER IS NEVER DRAWN (R62): `portal.portal_my_home`
        fetches counters lazily, after the page has rendered, so a `t-if` on
        one is simply false at render time. The controller sets its own eager
        key; this is the number that goes in the badge.
        """
        sheet = self._current()
        if not sheet:
            return 0
        return 1 if sheet.state in SET_EDITABLE else 0

    # ==================================================================
    #  The page
    # ==================================================================
    @api.model
    def home(self):
        me = self._me()
        today = fields.Date.today()
        if not me:
            return {'ok': False, 'no_employee': True,
                    'why': _("You do not have an employee record yet, so "
                             "there is nowhere to write your goals. Tell your "
                             "HR team.")}
        sheet = self._current()
        if not sheet:
            return {'ok': True, 'empty': True, 'name': me.name or '',
                    'why': _("Nobody has opened a goal sheet for you yet. "
                             "When the goal year opens you will get an email "
                             "and this page will fill in."),
                    'others': self._others(None)}
        editable = sheet.state in SET_EDITABLE
        goals = []
        for goal in sheet.goal_ids.sorted(lambda g: (g.sequence, g.id)):
            goals.append({
                'id': goal.id,
                'title': goal.title or '',
                'description': goal.description or '',
                'weight': _pct(goal.weight),
                'from': str(goal.date_start or ''),
                'to': str(goal.date_end or ''),
                'rating': goal.self_rating or '',
                'rating_word': RATING_LABEL.get(goal.self_rating or '', ''),
                'progress': _pct(goal.progress),
                'locked': bool(goal.locked),
                'krs': [{
                    'id': kr.id,
                    'title': kr.title or '',
                    'measure': kr.measure or '',
                    'target': kr.target or 0.0,
                    'current': kr.current or 0.0,
                    # THE FIGURE A PERSON READS, with the thousands in it. A
                    # Vietnamese revenue target is ten digits long and ten
                    # digits with no separators is a number nobody reads —
                    # they count the noughts. The raw value stays beside it
                    # because the form INPUT has to carry the number itself.
                    'target_words': _figure(kr.target),
                    # AS STRINGS, because `t-att-value` DROPS THE ATTRIBUTE
                    # ENTIRELY for a falsy value — so a key result sitting at
                    # zero rendered as two empty boxes and a person could not
                    # tell "nobody has said" from "it is at nought". A string
                    # is always truthy, and "16" beats "16.0" in a box
                    # somebody is about to type over.
                    'current_num': str(_pct(kr.current)),
                    'progress_num': str(_pct(kr.progress)),
                    'progress': _pct(kr.progress),
                    'due': str(kr.due_date or ''),
                } for kr in goal.kr_ids.sorted(lambda k: (k.sequence, k.id))],
            })
        return {
            'ok': True,
            'empty': False,
            'set_id': sheet.id,
            'name': me.name or '',
            'cycle': sheet.cycle_id.name or '',
            'cycle_from': str(sheet.cycle_id.date_start or ''),
            'cycle_to': str(sheet.cycle_id.date_end or ''),
            'state': sheet.state,
            'state_word': SET_STATE_LABEL.get(sheet.state, sheet.state),
            'deadline': str(sheet.deadline or ''),
            'due_words': ('' if sheet.state in ('locked', 'refused')
                          else due_words(sheet.deadline, today)),
            'overdue': bool(sheet.deadline and sheet.deadline < today
                            and editable),
            'editable': editable,
            'locked': sheet.state == 'locked',
            'locked_on': str(sheet.locked_at or '')[:10],
            'manager': sheet.manager_employee_id.name or '',
            'return_note': sheet.return_note or '',
            'weight_total': _pct(sheet.weight_total),
            'weight_target': WEIGHT_TOTAL,
            'progress': _pct(sheet.progress),
            'goals': goals,
            'max_goals': MAX_GOALS,
            'max_krs': MAX_KRS,
            'ratings': [{'key': key, 'label': label} for key, label in RATINGS],
            'templates': self._templates(me),
            'headline': self._headline(sheet, goals, today),
            'ready': self._ready(sheet),
            'others': self._others(sheet),
        }

    @api.model
    def _others(self, current):
        """Last year's, and the year before. One press away, never in the way."""
        sets = self._my_sets()
        return [{
            'id': other.id,
            'cycle': other.cycle_id.name or '',
            'state_word': SET_STATE_LABEL.get(other.state, other.state),
            'progress': _pct(other.progress),
        } for other in sets if not current or other.id != current.id][:4]

    @api.model
    def _templates(self, me):
        rows = self.env['pb.goal.template'].for_employee(me.id)
        return [{
            'id': row.id,
            'name': row.name or '',
            'title': row.title or '',
            'description': row.description or '',
            'krs': row.kr_lines(),
        } for row in rows]

    @api.model
    def _headline(self, sheet, goals, today):
        """One sentence that says where this person actually is."""
        if sheet.state == 'locked':
            return _("Your goals for %(cycle)s were agreed on %(when)s. Keep "
                     "the numbers on your key results up to date as the year "
                     "goes on.", cycle=sheet.cycle_id.name or '',
                     when=str(sheet.locked_at or '')[:10])
        if sheet.state == 'submitted':
            return _("Your goals are with %s. You will get an email either "
                     "way.", sheet.manager_employee_id.name or _('your manager'))
        if sheet.state == 'manager_ok':
            return _("Your manager has agreed them. The HR team looks at them "
                     "next and then they are locked for the year.")
        if sheet.state == 'refused':
            return _("These were turned down. Talk to your manager about what "
                     "happens next.")
        if sheet.state == 'returned':
            return _("These came back with a note. Have a look at what was "
                     "asked for, change what you need to, and send them in "
                     "again.")
        if not goals:
            return _("Write two to four goals for %(cycle)s and send them to "
                     "%(who)s. %(due)s", cycle=sheet.cycle_id.name or '',
                     who=sheet.manager_employee_id.name or _('your manager'),
                     due=(_("They are due by %s.", sheet.deadline)
                          if sheet.deadline else ''))
        return _("%(n)s %(word)s written. %(due)s Send them in when you are "
                 "happy with them.", n=len(goals),
                 word=counted(len(goals), _('goal'), _('goals')),
                 due=(_("They are due by %s.", sheet.deadline)
                      if sheet.deadline else ''))

    @api.model
    def _ready(self, sheet):
        """Whether Send can be pressed, and what is missing if it cannot.

        THE SCREEN SAYS WHAT IS MISSING BEFORE SOMEBODY PRESSES. A button that
        is enabled and then refuses is a button that teaches nothing; a button
        that is disabled with the reason beside it teaches on the first read.
        """
        if sheet.state not in SET_EDITABLE:
            return {'can': False, 'why': ''}
        try:
            sheet._check_ready_to_submit()
        except UserError as err:
            return {'can': False, 'why': err.args[0] if err.args else ''}
        return {'can': True, 'why': ''}

    # ==================================================================
    #  Writing
    # ==================================================================
    @api.model
    def _editable_set(self):
        sheet = self._current()
        if not sheet:
            raise UserError(_("You have no goal sheet open."))
        if sheet.state not in SET_EDITABLE:
            raise UserError(_(
                "Your goals are %s, so they cannot be changed now. Ask your "
                "manager to send them back if something has to move.",
                SET_STATE_LABEL.get(sheet.state, sheet.state).lower()))
        return sheet

    @api.model
    def add_goal(self, values):
        sheet = self._editable_set()
        if len(sheet.goal_ids) >= MAX_GOALS:
            raise UserError(_(
                "%s goals is as many as this sheet holds. Fold two together "
                "if you need another one.", MAX_GOALS))
        vals = self._clean_goal(values, sheet)
        goal = self.env['pb.goal'].sudo().create(dict(
            vals, set_id=sheet.id,
            sequence=(max(sheet.goal_ids.mapped('sequence') or [0]) + 10)))
        return {'ok': True, 'goal_id': goal.id}

    @api.model
    def edit_goal(self, goal_id, values):
        self._editable_set()
        goal = self._own('pb.goal', goal_id)
        goal.sudo().write(self._clean_goal(values, goal.set_id, partial=True))
        return {'ok': True}

    @api.model
    def delete_goal(self, goal_id):
        self._editable_set()
        goal = self._own('pb.goal', goal_id)
        title = goal.title or ''
        goal.sudo().unlink()
        return {'ok': True,
                'sentence': _("\"%s\" is gone.", title)}

    @api.model
    def _clean_goal(self, values, sheet, partial=False):
        """Everything a goal needs, said once, with the words on the screen."""
        values = dict(values or {})
        out = {}
        if 'title' in values or not partial:
            title = (values.get('title') or '').strip()
            if not title:
                raise UserError(_("Give the goal a name — one line saying "
                                  "what you are going to do."))
            out['title'] = title[:200]
        if 'description' in values or not partial:
            description = (values.get('description') or '').strip()
            if not description:
                raise UserError(_(
                    "Say why it matters and what good looks like. A sentence "
                    "or two is plenty, and it is what makes this a goal rather "
                    "than a task."))
            out['description'] = description
        if 'date_start' in values:
            out['date_start'] = values.get('date_start') or False
        if 'date_end' in values or not partial:
            when = values.get('date_end') or False
            if not when:
                raise UserError(_("Say when it should be done by."))
            out['date_end'] = when
        if 'self_rating' in values:
            rating = str(values.get('self_rating') or '')
            out['self_rating'] = rating if rating in dict(RATINGS) else False
        return out

    @api.model
    def use_template(self, template_id):
        """Copy a template in. A COPY and never a link (see `template.py`)."""
        sheet = self._editable_set()
        if len(sheet.goal_ids) >= MAX_GOALS:
            raise UserError(_(
                "%s goals is as many as this sheet holds.", MAX_GOALS))
        template = self.env['pb.goal.template'].sudo().browse(
            as_id(template_id)).exists()
        if not template:
            raise UserError(_("That template is gone."))
        cycle = sheet.cycle_id
        goal = self.env['pb.goal'].sudo().create({
            'set_id': sheet.id,
            'title': template.title or template.name or '',
            'description': template.description or '',
            'date_start': cycle.date_start,
            'date_end': cycle.date_end,
            'template_id': template.id,
            'sequence': (max(sheet.goal_ids.mapped('sequence') or [0]) + 10),
            'kr_ids': [(0, 0, {'title': line, 'sequence': (index + 1) * 10})
                       for index, line in enumerate(
                           template.kr_lines()[:MAX_KRS])],
        })
        return {'ok': True, 'goal_id': goal.id,
                'sentence': _("\"%s\" has been added. Change any of it — it "
                              "is yours now.", goal.title or '')}

    # ------------------------------------------------------- key results
    @api.model
    def add_kr(self, goal_id, values):
        self._editable_set()
        goal = self._own('pb.goal', goal_id)
        if len(goal.kr_ids) >= MAX_KRS:
            raise UserError(_(
                "%s key results on one goal is as many as it holds.", MAX_KRS))
        vals = self._clean_kr(values)
        kr = self.env['pb.goal.kr'].sudo().create(dict(
            vals, goal_id=goal.id,
            sequence=(max(goal.kr_ids.mapped('sequence') or [0]) + 10)))
        return {'ok': True, 'kr_id': kr.id}

    @api.model
    def edit_kr(self, kr_id, values):
        self._editable_set()
        kr = self._own('pb.goal.kr', kr_id)
        kr.sudo().write(self._clean_kr(values, partial=True))
        return {'ok': True}

    @api.model
    def delete_kr(self, kr_id):
        self._editable_set()
        kr = self._own('pb.goal.kr', kr_id)
        kr.sudo().unlink()
        return {'ok': True}

    @api.model
    def _clean_kr(self, values, partial=False):
        values = dict(values or {})
        out = {}
        if 'title' in values or not partial:
            title = (values.get('title') or '').strip()
            if not title:
                raise UserError(_(
                    "Say what is being measured — \"new customers\", \"days "
                    "to answer a ticket\"."))
            out['title'] = title[:200]
        for key in ('measure',):
            if key in values:
                out[key] = (values.get(key) or '').strip()[:60]
        for key in ('target', 'current'):
            if key in values:
                try:
                    out[key] = float(values.get(key) or 0)
                except (TypeError, ValueError):
                    raise UserError(_("A target has to be a number."))
        if 'due_date' in values:
            out['due_date'] = values.get('due_date') or False
        return out

    @api.model
    def move_kr(self, kr_id, progress, current=None, note=''):
        """Move a key result along. ALLOWED AFTER THE LOCK, on purpose.

        Progress is not a change of plan: it is the work happening, and a page
        that goes read-only the day the goals are agreed is a page nobody opens
        again until December.
        """
        kr = self._own('pb.goal.kr', kr_id)
        return self.env['pb.goal.kr'].move(kr.id, progress, current, note)

    # -------------------------------------------------------------- sending
    @api.model
    def set_rating(self, goal_id, rating):
        self._editable_set()
        goal = self._own('pb.goal', goal_id)
        value = str(rating or '')
        if value not in dict(RATINGS):
            raise UserError(_("Pick one of the five."))
        goal.sudo().write({'self_rating': value})
        return {'ok': True, 'word': RATING_LABEL.get(value, '')}

    @api.model
    def submit(self):
        """Send the sheet to the manager."""
        sheet = self._editable_set()
        sheet.sudo()._check_ready_to_submit()
        # SUBMITTED BY THE PERSON WHOSE GOALS THEY ARE, and not under sudo:
        # the engine records who sent it in, and "the system" is not a name
        # anybody can ask a question of.
        sheet.action_goals_submit()
        return {'ok': True, 'state': sheet.state,
                'sentence': _("Sent to %s. You will get an email either way.",
                              sheet.manager_employee_id.sudo().name
                              or _('your manager'))}
