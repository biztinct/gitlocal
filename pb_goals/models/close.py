# -*- coding: utf-8 -*-
"""Closing a goal year: the one irreversible-looking press in this module.

WHAT CLOSING ACTUALLY DOES, in order, and why each piece is there.

  1. **It says how many and what is missing, BEFORE it does anything** (R54).
     A press that scores four thousand people and emails them all has to be a
     press somebody makes twice, and the first press is a sentence: how many
     sheets, how many have no score, and which people they belong to.
  2. **It refuses while anything is unscored** — unless somebody deliberately
     ticks "close it anyway", which is then written into the year's own record
     with the number in it. A year closed with holes in it is a legitimate
     thing a company sometimes has to do; a year closed with holes in it that
     nobody wrote down is how a figure gets quoted in March that nobody can
     account for.
  3. **It freezes.** Every sheet's score, band, weights and key-result
     figures are copied into `frozen_json` at that moment. Everything above
     it is a live compute and a live compute over a finished year re-answers
     the day somebody corrects a neighbouring row.
  4. **It archives the goals** so the live lists stop being full of last
     year's work — and changes nothing about the numbers, because every
     compute on the sheet reads its goals with `active_test=False`.
  5. **It tells people**, once, with the band in the sentence.

NOTHING IS DELETED, EVER. "Closed" is a status on the sheet and `active =
False` on the goals; the employee still reads the whole year under "Other
years" on their own page. A close that destroyed anything would be a close
nobody could be persuaded to press.

IT CAN BE UNDONE, and saying so out loud is most of why people will press it.
`action_reopen_cycle` puts the year back to open and the sheets back to agreed;
the frozen copy is kept, because what the year looked like when somebody closed
it by mistake is still a fact.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .goals_common import (
    P_BULK_CAP, P_YEAREND_MAIL, counted, flag, leg, number,
)

_logger = logging.getLogger(__name__)


class PbGoalCycleClose(models.Model):
    _inherit = 'pb.goal.cycle'

    closed_at = fields.Datetime(string='Closed on', readonly=True, copy=False)
    closed_by_id = fields.Many2one('res.users', string='Closed by',
                                   readonly=True, copy=False)
    closed_with_gaps = fields.Integer(
        string='Closed with this many unscored', readonly=True, copy=False,
        help='How many goal sheets had no score when the year was put away. '
             'Nought is the ordinary case; anything else was a deliberate '
             'decision and is written here so nobody has to reconstruct it.')

    # ==================================================================
    @api.model
    def preview_close(self, cycle_id):
        """What closing would do, WITHOUT doing any of it."""
        cycle = self.sudo().browse(int(cycle_id or 0)).exists()
        if not cycle:
            return {'ok': False, 'sentence': _("That goal year is gone.")}
        if cycle.state == 'closed':
            return {'ok': False, 'sentence': _(
                "%s is already closed.", cycle.name or '')}
        sheets = self.env['pb.goal.set'].sudo().search(
            [('cycle_id', '=', cycle.id)])
        live = sheets.filtered(lambda s: s.state == 'locked')
        unscored = live.filtered(lambda s: s.applies_year_end and not s.scored)
        carried = live.filtered(lambda s: not s.applies_year_end)
        never = sheets.filtered(lambda s: s.state != 'locked')
        names = ', '.join(sheet.employee_id.name or ''
                          for sheet in unscored[:5])
        if not live:
            sentence = _(
                "Nobody's goals on %s were ever agreed, so there is nothing "
                "to score. Closing it simply puts the year away.",
                cycle.name or '')
        elif unscored:
            sentence = _(
                "%(total)s %(word)s agreed on %(cycle)s and %(n)s of them "
                "%(has)s no score yet — %(who)s%(more)s. Score them, or tick "
                "the box below to close the year without them.",
                total=len(live), word=counted(len(live), _('goal sheet'),
                                              _('goal sheets')),
                cycle=cycle.name or '', n=len(unscored),
                has=counted(len(unscored), _('has'), _('have')), who=names,
                more=(_(" and %s more", len(unscored) - 5)
                      if len(unscored) > 5 else ''))
        elif len(live) == 1:
            # THE WHOLE SENTENCE, AND NEVER A FRAME WITH A NUMBER IN IT
            # (R117). "Every one of the 1 agreed goal sheet" is grammatical
            # nonsense for exactly one of its values, and one is the ordinary
            # case on a small team. Both are written out.
            sentence = _(
                "The one agreed goal sheet on %(cycle)s has a score. Closing "
                "the year freezes it and tells them what they came out at.",
                cycle=cycle.name or '')
        else:
            sentence = _(
                "All %(total)s agreed goal sheets on %(cycle)s have a score. "
                "Closing the year freezes them and tells everybody what they "
                "came out at.", total=len(live), cycle=cycle.name or '')
        extra = []
        if carried:
            extra.append(_(
                "%(n)s %(word)s carried into next year because they joined "
                "too late to be scored on this one; they are left alone.",
                n=len(carried),
                word=counted(len(carried), _('person is'), _('people are'))))
        if never:
            extra.append(_(
                "%(n)s %(word)s never agreed and will be closed unscored.",
                n=len(never),
                word=counted(len(never), _('sheet was'), _('sheets were'))))
        return {
            'ok': True,
            'cycle': cycle.name or '',
            'sheets': len(sheets),
            'live': len(live),
            'unscored': len(unscored),
            'carried': len(carried),
            'never': len(never),
            'names': [sheet.employee_id.name or '' for sheet in unscored[:12]],
            'sentence': ' '.join([sentence] + extra),
            'can_close': not unscored,
        }

    @api.model
    def close_cycle(self, cycle_id, with_gaps=False):
        """Put the year away. The HR team's press and nobody else's."""
        cycle = self.sudo().browse(int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That goal year is gone."))
        if not self.env.user.has_group('pb_goals.group_goals_manager'):
            raise UserError(_(
                "Closing a goal year is for the HR team. Ask your HR "
                "administrator."))
        if cycle.state == 'closed':
            raise UserError(_("%s is already closed.", cycle.name or ''))
        preview = self.preview_close(cycle.id)
        if preview.get('unscored') and not with_gaps:
            raise UserError(_(
                "%(n)s %(word)s no score yet. Score them, or close the year "
                "again with \"close it anyway\" ticked — which is written on "
                "the year's own record.",
                n=preview['unscored'],
                word=counted(preview['unscored'], _('goal sheet has'),
                             _('goal sheets have'))))
        return cycle._do_close(int(preview.get('unscored') or 0))

    def _do_close(self, gaps=0):
        self.ensure_one()
        sheets = self.env['pb.goal.set'].sudo().search(
            [('cycle_id', '=', self.id)])
        cap = number(self.env, P_BULK_CAP, 2000)
        mailed = 0
        done = 0
        for sheet in sheets:
            if done >= cap:
                break
            # ONE SAVEPOINT PER SHEET (R131). One person with a broken email
            # address must not cost the other four thousand their year being
            # put away — and a bare try/except would, because the transaction
            # is already dead by the time Python sees the error.
            if leg(self.env, 'closing goal sheet %s' % sheet.id,
                   lambda s=sheet: s._close_for_year()):
                done += 1
                if flag(self.env, P_YEAREND_MAIL) and sheet.applies_year_end \
                        and sheet.scored:
                    if leg(self.env, 'the year-end email for %s' % sheet.id,
                           lambda s=sheet: s._notify_year_end()):
                        mailed += 1
        self.write({
            'state': 'closed',
            'closed_at': fields.Datetime.now(),
            'closed_by_id': self.env.uid,
            'closed_with_gaps': gaps,
        })
        self.message_post(body=_(
            "Closed by %(who)s. %(n)s %(word)s put away%(gaps)s. %(mail)s",
            who=self.env.user.name or '', n=done,
            word=counted(done, _('goal sheet'), _('goal sheets')),
            gaps=(_(", %s of them with no score") % gaps if gaps else ''),
            mail=(_("%(n)s %(word)s told what they came out at.", n=mailed,
                    word=counted(mailed, _('person was'), _('people were')))
                  if mailed else _("Nobody was emailed."))))
        _logger.info('pb_goals: cycle %s closed — %s sheet(s), %s unscored, '
                     '%s mailed', self.id, done, gaps, mailed)
        return {'ok': True, 'closed': done, 'unscored': gaps,
                'mailed': mailed,
                'sentence': _(
                    "%(n)s %(word)s put away.%(gaps)s %(mail)s", n=done,
                    word=counted(done, _('goal sheet'), _('goal sheets')),
                    gaps=(_(" %s of them had no score.") % gaps
                          if gaps else ''),
                    mail=(_("%(n)s %(word)s told what they came out at.",
                            n=mailed,
                            word=counted(mailed, _('person was'),
                                         _('people were')))
                          if mailed else ''))}

    def action_close_cycle(self):
        """The button on the year's own form."""
        self.ensure_one()
        return self.close_cycle(self.id, with_gaps=False)

    def action_reopen_cycle(self):
        """It was closed by mistake, or a score has to be corrected.

        NOTHING IS LOST EITHER WAY. The frozen copy stays exactly where it is
        — what the year looked like when somebody closed it is still a fact —
        and the sheets go back to agreed with their goals un-archived.
        """
        self.ensure_one()
        if not self.env.user.has_group('pb_goals.group_goals_manager'):
            raise UserError(_(
                "Reopening a goal year is for the HR team."))
        if self.state != 'closed':
            raise UserError(_("%s is not closed.", self.name or ''))
        sheets = self.env['pb.goal.set'].sudo().search(
            [('cycle_id', '=', self.id), ('state', '=', 'closed')])
        for sheet in sheets:
            leg(self.env, 'reopening goal sheet %s' % sheet.id,
                lambda s=sheet: s._reopen_for_year())
        self.sudo().write({'state': 'open', 'closed_at': False,
                           'closed_by_id': False})
        self.message_post(body=_(
            "Reopened by %(who)s. %(n)s %(word)s can be scored again; what "
            "they said when the year was closed is kept.",
            who=self.env.user.name or '', n=len(sheets),
            word=counted(len(sheets), _('goal sheet'), _('goal sheets'))))
        return True


class PbGoalSetClose(models.Model):
    _inherit = 'pb.goal.set'

    def _close_for_year(self):
        """Freeze this sheet and put its goals away."""
        self.ensure_one()
        record = self.sudo()
        if record.state == 'closed':
            return True
        frozen = record._freeze()
        record.write({
            'state': 'closed',
            'closed_at': fields.Datetime.now(),
            'frozen_json': frozen,
        })
        record._all_goals().write({'active': False})
        record.message_post(body=record._close_sentence())
        return True

    def _close_sentence(self):
        """What the chatter says, whole (R117), for each of the three cases."""
        self.ensure_one()
        record = self.sudo()
        if record.scored:
            return _(
                "The year is finished. %(who)s came out at %(words)s.",
                who=record.employee_id.name or _('This person'),
                words=record._score_words())
        if not record.applies_year_end:
            return _(
                "The year is finished. These goals were not scored, because "
                "%(who)s joined too late in the year for a score to say "
                "anything useful — they carry into next year instead.",
                who=record.employee_id.name or _('this person'))
        return _(
            "The year is finished. These goals were never scored and the "
            "year was closed without them.")

    def _reopen_for_year(self):
        self.ensure_one()
        record = self.sudo()
        if record.state != 'closed':
            return True
        record.write({'state': 'locked', 'closed_at': False})
        record.with_context(active_test=False).goal_ids.write({'active': True})
        return True

    def _notify_year_end(self):
        """One email that says what the year came out at (R6: explicit `to`)."""
        self.ensure_one()
        return self._send('pb_goals.mail_goals_year_end')
