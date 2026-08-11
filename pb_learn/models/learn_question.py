# -*- coding: utf-8 -*-
"""Question mining — the F7 completion, opt-in and deletable.

WHY THIS IS NOT `learn.event`
-----------------------------
Phase A2 ruled that the Coach must NOT log the learner's question text.
health_learn logs `q.slice(0, 40)` into its event table, which on a payroll
help box is "why is <a colleague>'s net only 4.2m" — a named person and their
pay, landing in an APPEND-ONLY table with no retention policy and no way for
that person to know it is there.

That ruling stands, and this model is not a reversal of it. The difference is
in four properties `learn.event` cannot have without stopping being an event
log:

  * it is ORDINARY, not append-only — rows can be deleted, by the person who
    created them and by an author;
  * it is OPT-IN TWICE — a system parameter the tenant sets, AND this user's
    own recorded consent. Either one missing and nothing is stored;
  * the text is SCRUBBED on the way in, through the composer's own scrub, so
    a name or an amount typed into the box does not become a row even after
    consent;
  * it expires — a cron deletes anything older than the retention window.

The default forever is the Phase B behaviour: key only, no question text.
Turning this on is a decision a tenant makes, twice.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# The tenant's half of the opt-in. Absent or falsey means off.
COLLECT_FLAG = 'pb_learn.collect_questions'

# The learner's half is a row in learn.consent.
RETENTION_DAYS = 180


def _flag_on(env, name):
    raw = env['ir.config_parameter'].sudo().get_param(name)
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')


class LearnConsent(models.Model):
    """One row per learner, holding what they were asked and what they said.

    Server-side because it has to be: a preference kept only in localStorage
    is a preference the server cannot honour, and the server is where the
    refusal has to bite. Modelled on learn.progress — own-rows rule, the user
    writes their own — because that is the shape this module already uses for
    learner-owned state.
    """
    _name = 'learn.consent'
    _description = 'Learn learner consent'
    _order = 'write_date desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user,
                              ondelete='cascade')
    questions = fields.Selection(
        selection=lambda self: self._selection_questions(),
        required=True, default='unset')
    decided_at = fields.Datetime()

    _sql_constraints = [
        ('user_uniq', 'unique(user_id)', 'One consent row per learner.'),
    ]

    @api.model
    def _selection_questions(self):
        return [('unset', self.env._('Not asked yet')),
                ('granted', self.env._('Questions may be stored')),
                ('declined', self.env._('Questions must not be stored'))]

    @api.model
    def _my_row(self):
        return self.search([('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def questions_state(self):
        """'unset' | 'granted' | 'declined'. The drawer asks once."""
        row = self._my_row()
        return row.questions if row else 'unset'

    @api.model
    def should_ask_questions(self):
        """True only when there is something to ask ABOUT.

        A consent prompt for a collection that is switched off is a dialog
        that costs the reader attention and buys nothing — and worse, it
        implies the collection is happening.
        """
        return _flag_on(self.env, COLLECT_FLAG) and self.questions_state() == 'unset'

    @api.model
    def set_questions(self, granted):
        """Record this learner's answer. Idempotent; only ever their own row."""
        value = 'granted' if granted else 'declined'
        row = self._my_row()
        vals = {'questions': value, 'decided_at': fields.Datetime.now()}
        if row:
            row.write(vals)
        else:
            self.create(dict(vals, user_id=self.env.uid))
        return value

    @api.model
    def _questions_granted(self):
        return self.questions_state() == 'granted'


class LearnQuestion(models.Model):
    """A question somebody asked the Coach. Ordinary, deletable, expiring."""
    _name = 'learn.question'
    _description = 'Learn coach question'
    _order = 'occurred_at desc, id desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user,
                              ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    screen = fields.Char(index=True, help="learn.screen key the Coach was grounded on.")
    question = fields.Char(size=200, required=True,
                           help="Scrubbed on the way in — see learn.intent._scrub.")
    matched = fields.Boolean(
        default=False, index=True,
        help="Whether the Coach had an answer. The rows where this is FALSE "
             "are the point of the table: a question a real person asked that "
             "the content does not cover is the next thing to write.")
    lang = fields.Char(size=8)
    occurred_at = fields.Datetime(required=True, default=fields.Datetime.now,
                                  index=True)

    @api.model
    def _collect_enabled(self):
        return _flag_on(self.env, COLLECT_FLAG)

    @api.model
    def record(self, question, screen=None, matched=False, lang=None):
        """The frontend's only write into this table.

        BOTH gates are re-asked here. The browser checks them too, so that it
        does not send text it knows will be dropped — but a check in the
        browser is a courtesy, not a control: this method is reachable by RPC
        from anything holding a session, and it is the one that has to say no.
        """
        if not self._collect_enabled():
            return False
        if not self.env['learn.consent']._questions_granted():
            return False
        text = self.env['learn.intent']._scrub(question or '').strip()
        if not text:
            return False
        self.create({
            'screen': (screen or '')[:64] or False,
            'question': text[:200],
            'matched': bool(matched),
            'lang': (lang or '')[:8] or False,
        })
        return True

    @api.model
    def _gc_questions(self, days=RETENTION_DAYS):
        """Retention. Called by the cron; safe to call by hand.

        Deliberately a hard delete rather than an archive: a retention policy
        that leaves the rows on the table is not a retention policy.
        """
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        stale = self.sudo().search([('occurred_at', '<', cutoff)])
        count = len(stale)
        if count:
            stale.unlink()
            _logger.info('pb_learn: deleted %s stored question(s) older than '
                         '%s days.', count, days)
        return count
