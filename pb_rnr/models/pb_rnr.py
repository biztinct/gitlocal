# -*- coding: utf-8 -*-
"""`pb.rnr` — the Praise lens's only server surface.

THE QUESTION THIS BOARD ANSWERS: who has been noticed lately, who is waiting on
somebody, and what did we do about it. So the four numbers across the top are
the four places a piece of praise can be — written this month, waiting on a
manager, waiting on HR, and paid for this quarter — and a row is one story with
its state on it.

The roll-up is the hero. Picking a quarter's winners out of a ranked table of
who colleagues actually named, with the money consequence spelled out in a
sentence before anything is written, is the thing this module exists for.

Every employee attribute is read AS THE SYSTEM (R56): reading one field of an
`hr.employee` prefetches forty and about forty of those sit behind payroll
groups a recognition reader has no reason to hold. The security boundary is the
search that found the record, and `_can_read()` above it.
"""

import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .rnr_common import (
    CYCLE_STATE_LABEL, GROUP_MANAGER, GROUP_USER, NOMINATION_STATE_LABEL,
    OUTCOME_LABEL, P_ANNIV_MAIL, P_DIGEST_MAIL, P_DIGEST_TEST, P_MANAGER_MAIL,
    P_THANKS_MAIL, excerpt, flag, fold, initials, param,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300
HISTORY_LIMIT = 12


def _refusal():
    return {
        'allowed': False, 'can_write': False, 'can_review': False,
        'rows': [], 'kpis': {}, 'values': [], 'cycles': [], 'states': [],
        'outcomes': [], 'celebrations': [], 'total': 0, 'capped': False,
        'currency': '', 'switches': {},
        'why': _("Recognition is looked after by the people who run it. This "
                 "screen is not part of the general HR permissions — somebody "
                 "has to add you to it by name."),
    }


class PbRnr(models.AbstractModel):
    _name = 'pb.rnr'
    _description = 'Payobook recognition cockpit data'

    # ------------------------------------------------------------- the gates
    @api.model
    def _safe(self, fn, default=0):
        """Every independent probe gets its OWN try/except — never a shared
        one, or the first failure takes four numbers down with it."""
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('recognition metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return bool(self.env.su or user._is_admin()
                    or user.has_group(GROUP_USER)
                    or user.has_group(GROUP_MANAGER))

    @api.model
    def _can_review(self):
        return bool(self.env.su or self.env.user._is_admin()
                    or self.env.user.has_group(GROUP_MANAGER))

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_refusal()['why'])
        return True

    @api.model
    def _require_review(self):
        if not self._can_review():
            raise AccessError(_(
                "Deciding a piece of praise — and any money with it — is done "
                "by the people who run recognition."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return _refusal()
        Nom = self.env['pb.rnr.nomination']
        recs = Nom.search([
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='id desc', limit=BOARD_LIMIT + 1)
        capped = len(recs) > BOARD_LIMIT
        recs = recs[:BOARD_LIMIT]
        rows = [self._row(rec) for rec in recs]
        today = date.today()
        this_month = today.replace(day=1).isoformat()[:7]
        quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        return {
            'allowed': True,
            'can_write': True,
            'can_review': self._can_review(),
            'rows': rows,
            'total': len(rows),
            'capped': capped,
            'currency': self.env.company.currency_id.symbol or '',
            'values': self.values_list(),
            'cycles': self._cycles(),
            'states': [{'key': k, 'label': v}
                       for k, v in NOMINATION_STATE_LABEL.items()],
            'outcomes': [{'key': k, 'label': v}
                         for k, v in OUTCOME_LABEL.items()],
            'celebrations': self._safe(
                lambda: self.env['pb.rnr.celebration'].upcoming_celebrations(
                    days=14), []),
            'switches': self._switches(),
            'kpis': {
                'this_month': len([r for r in rows
                                   if (r['written'] or '')[:7] == this_month]),
                'with_manager': len([r for r in rows
                                     if r['state'] == 'submitted']),
                'with_hr': len([r for r in rows if r['state'] == 'manager']),
                'awarded_qtd': len([
                    r for r in rows
                    if r['outcome'] == 'awarded'
                    and r['decided'] and r['decided'][:10] >= quarter_start.isoformat()]),
                'awarded_amount': sum(
                    r['amount'] for r in rows
                    if r['outcome'] == 'awarded'
                    and r['decided'] and r['decided'][:10] >= quarter_start.isoformat()),
            },
            'why': '',
        }

    @api.model
    def _switches(self):
        """Which way every send is set, said on the screen.

        A switch that is off and does not SAY so is reported as broken (R54), so
        the lens prints all five rather than making somebody guess why their
        test email never arrived.
        """
        return {
            'digest': flag(self.env, P_DIGEST_MAIL),
            'digest_test': (param(self.env, P_DIGEST_TEST) or '').strip(),
            'celebrations': flag(self.env, P_ANNIV_MAIL),
            'manager_week': flag(self.env, P_MANAGER_MAIL),
            'thanks': flag(self.env, P_THANKS_MAIL),
        }

    @api.model
    def _row(self, rec):
        Nom = self.env['pb.rnr.nomination']
        nominee = Nom._person(rec.nominee_id)
        nominator = Nom._person(rec.nominator_id)
        val = rec.value_id.sudo()
        return {
            'id': rec.id,
            'nominee': nominee.name or '',
            'nominee_id': nominee.id,
            'initials': initials(nominee.name or ''),
            'avatar': ('/web/image/hr.employee/%s/image_128' % nominee.id
                       if nominee else ''),
            'department': (nominee.department_id.name
                           if nominee and nominee.department_id else ''),
            'nominator': nominator.name or '',
            'value': val.name or '',
            'value_id': val.id,
            'color': val.color or 'primary',
            'icon': val.icon or 'award',
            'story': rec.story or '',
            'excerpt': excerpt(rec.story, 220),
            'state': rec.state or 'draft',
            'state_label': NOMINATION_STATE_LABEL.get(rec.state, ''),
            'outcome': rec.outcome or '',
            'outcome_label': OUTCOME_LABEL.get(rec.outcome, ''),
            'amount': rec.award_amount or 0.0,
            'currency': rec.currency_id.symbol or '',
            'public': bool(rec.public),
            'winner': bool(rec.is_winner),
            'cycle': rec.cycle_id.name if rec.cycle_id else '',
            'incentive_id': rec.incentive_id.id if rec.incentive_id else 0,
            'written': (fields.Datetime.to_string(rec.submitted_at)
                        or fields.Datetime.to_string(rec.create_date) or ''),
            'decided': fields.Datetime.to_string(rec.decided_at) or '',
            'note': rec.decision_note or '',
        }

    @api.model
    def values_list(self):
        """The values somebody may pick from. Read for everybody who reaches a
        nominate form, including the portal — a value is a poster, not a
        secret."""
        recs = self.env['pb.company.value'].sudo().search([
            ('active', '=', True),
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='sequence, id')
        return [{'id': v.id, 'name': v.name or '', 'motto': v.motto or '',
                 'description': v.description or '',
                 'icon': v.icon or 'award', 'color': v.color or 'primary'}
                for v in recs]

    @api.model
    def _cycles(self):
        recs = self.env['pb.rnr.cycle'].sudo().search([
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='date_from desc, id desc', limit=12)
        return [{'id': c.id, 'name': c.name or '',
                 'state': c.state, 'state_label': CYCLE_STATE_LABEL.get(c.state, ''),
                 'from': fields.Date.to_string(c.date_from) or '',
                 'to': fields.Date.to_string(c.date_to) or '',
                 'winners': len(c.top_ids)} for c in recs]

    # ------------------------------------------------------------ the writes
    @api.model
    def nominate(self, vals):
        """Write a piece of praise. The same call the portal makes.

        DELIBERATELY UNGATED beyond being signed in. Recognition that only the
        recognition team may start does not happen, because they were not in the
        room; the whole design is that a colleague writes it and two other
        people agree it. What the tiers guard is READING the board and DECIDING
        — not saying thank you.
        """
        return self._create_nomination(vals, self._me())

    @api.model
    def _me(self):
        """The acting person's own employee record, from the SESSION."""
        Emp = self.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', self.env.user.id),
                          ('company_id', '=', self.env.company.id)], limit=1)
        return emp or Emp.search([('user_id', '=', self.env.user.id)], limit=1)

    @api.model
    def _create_nomination(self, vals, nominator, submit=True):
        """The one place a nomination is born. Shared with the portal.

        The friendly refusals happen HERE, before the database's own constraint
        gets a chance to speak, because a Postgres message is not an answer.
        """
        vals = vals or {}
        nominee_id = int(vals.get('nominee_id') or 0)
        value_id = int(vals.get('value_id') or 0)
        story = (vals.get('story') or '').strip()
        if not nominee_id:
            raise UserError(_("Pick the colleague you want to thank."))
        if not value_id:
            raise UserError(_(
                "Pick the value this is an example of — it is what turns a "
                "thank-you into something the whole company can learn from."))
        if not story:
            raise UserError(_(
                "Write what actually happened. One real example is worth three "
                "adjectives, and it is the part everybody else will read."))
        if not nominator:
            raise UserError(_(
                "We could not work out which employee record is yours, so "
                "there is nobody to put on the praise. Ask HR to link your "
                "login to your employee record."))
        if nominee_id == nominator.id:
            raise UserError(_(
                "Praise goes to somebody else. Pick the colleague you want to "
                "say thank you to."))
        nominee = self.env['hr.employee'].sudo().browse(nominee_id).exists()
        if not nominee:
            raise UserError(_("That colleague could not be found."))
        if nominee.company_id and nominator.company_id \
                and nominee.company_id != nominator.company_id:
            raise UserError(_(
                "You can only thank a colleague in your own company."))
        rec = self.env['pb.rnr.nomination'].sudo().create({
            'nominee_id': nominee.id,
            'nominator_id': nominator.id,
            'value_id': value_id,
            'story': story,
            'public': bool(vals.get('public', True)),
            'company_id': (nominee.company_id or self.env.company).id,
        })
        if submit:
            rec.action_submit()
        return rec.id

    @api.model
    def employee_options(self, term=''):
        """Colleagues to pick from — ACTIVE, in the caller's own company, and
        never themselves.

        R27's lesson in a different shape: the list a picker offers has one job
        and it is not the same job as the list a report groups by. Read as the
        system (R56); the domain is the gate.
        """
        Emp = self.env['hr.employee'].sudo()
        me = self._me()
        company = (me.company_id or self.env.company)
        domain = [('active', '=', True), ('company_id', '=', company.id)]
        if me:
            domain.append(('id', '!=', me.id))
        rows = Emp.search(domain, order='name', limit=400)
        needle = fold(term or '')
        out = []
        for emp in rows:
            if needle and needle not in fold(emp.name or '') \
                    and needle not in fold(emp.barcode or ''):
                continue
            out.append({
                'id': emp.id, 'name': emp.name or '',
                'code': emp.barcode or '',
                'department': (emp.department_id.name
                               if emp.department_id else ''),
                'avatar': '/web/image/hr.employee/%s/image_128' % emp.id,
            })
            if len(out) >= 25:
                break
        return out

    # ------------------------------------------------------------- the moves
    @api.model
    def manager_agree(self, nomination_id, note=False):
        self._require_read()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_manager_agree(note=note or False)

    @api.model
    def recognise(self, nomination_id, amount=0.0, note=False):
        self._require_review()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_recognise(amount=amount or 0.0, note=note or False)

    @api.model
    def decline(self, nomination_id, note=False):
        self._require_read()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        return rec.action_decline(note=note or False)

    @api.model
    def set_public(self, nomination_id, public):
        """HR can take a story off the wall. It can never put one on that the
        writer asked to keep private — that switch belongs to them."""
        self._require_review()
        rec = self.env['pb.rnr.nomination'].browse(int(nomination_id))
        if public and not rec.public:
            raise UserError(_(
                "The colleague who wrote this asked for it to stay private. "
                "Ask them if they would like it on the wall."))
        rec.public = bool(public)
        return True

    @api.model
    def nominee_history(self, employee_id):
        """What else this person has been praised for. The review dialog shows
        it, because a decision made without it is a decision made blind."""
        self._require_read()
        Nom = self.env['pb.rnr.nomination']
        recs = Nom.sudo().search([
            ('nominee_id', '=', int(employee_id or 0)),
            ('state', '=', 'done'),
            ('outcome', 'in', ('recognised', 'awarded')),
        ], order='decided_at desc, id desc', limit=HISTORY_LIMIT)
        return [{
            'id': rec.id,
            'value': rec.value_id.sudo().name or '',
            'color': rec.value_id.sudo().color or 'primary',
            'excerpt': excerpt(rec.story, 140),
            'when': fields.Datetime.to_string(rec.decided_at) or '',
            'outcome': rec.outcome or '',
            'amount': rec.award_amount or 0.0,
        } for rec in recs]

    # ------------------------------------------------------------ the quarter
    @api.model
    def ensure_current_cycle(self):
        """The quarter we are in — found, or made.

        A screen whose main action is "roll up the quarter" must never open on
        "there are no quarters". The window is the calendar quarter, which is
        what everybody means by Q3 anyway.
        """
        self._require_read()
        today = fields.Date.context_today(self)
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        end = (date(today.year + 1, 1, 1) if end_month == 12
               else date(today.year, end_month + 1, 1))
        end = fields.Date.subtract(end, days=1)
        Cycle = self.env['pb.rnr.cycle']
        found = Cycle.sudo().search([('date_from', '=', start),
                                     ('date_to', '=', end)], limit=1)
        if not found:
            found = Cycle.sudo().create({
                'name': 'Q%s %s' % (q + 1, today.year),
                'date_from': start, 'date_to': end, 'state': 'open',
                'company_id': self.env.company.id,
            })
        return found.id

    @api.model
    def cycle_rollup(self, cycle_id=None):
        """The ranked table behind "who won this quarter"."""
        self._require_read()
        cid = int(cycle_id or 0) or self.ensure_current_cycle()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(cid).exists()
        if not cycle:
            return {'ok': False, 'rows': [],
                    'problem': _("That quarter no longer exists.")}
        rows = cycle.roll_up()
        return {
            'ok': True,
            'problem': '' if rows else _(
                "Nobody has been recognised in this quarter yet. Once praise "
                "starts being agreed it is ranked here, and the winners are "
                "picked from the table rather than from memory."),
            'cycle': {'id': cycle.id, 'name': cycle.name or '',
                      'state': cycle.state,
                      'state_label': CYCLE_STATE_LABEL.get(cycle.state, ''),
                      'from': fields.Date.to_string(cycle.date_from) or '',
                      'to': fields.Date.to_string(cycle.date_to) or ''},
            'rows': rows,
            'currency': self.env.company.currency_id.symbol or '',
        }

    @api.model
    def pick_winners(self, cycle_id, picks):
        self._require_review()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(
            int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That quarter no longer exists."))
        return cycle.pick_winners(picks or [])

    @api.model
    def close_cycle(self, cycle_id):
        self._require_review()
        cycle = self.env['pb.rnr.cycle'].sudo().browse(
            int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That quarter no longer exists."))
        cycle.action_close()
        return True

    # -------------------------------------------------------- the mood board
    @api.model
    def digest_preview(self, month=None):
        """The email, on screen, before anybody presses anything.

        The HTML is built server-side with every interpolated value escaped by
        QWeb itself, and the lens wraps it once with `markup()` — the narrow
        hatch R51 describes and the only place this module opens it.
        """
        self._require_read()
        Digest = self.env['pb.rnr.digest']
        payload = Digest.build(month=month or None)
        return {
            'html': Digest.render(payload=payload),
            'month': payload['month_label'],
            'stories': len(payload['stories']),
            'joiners': len(payload['joiners']),
            'celebrations': len(payload['celebrations']),
            'switches': self._switches(),
        }

    @api.model
    def digest_send(self, month=None, force=False):
        """Send it. What actually happens depends on the two switches, and the
        answer says which one decided."""
        self._require_review()
        return self.env['pb.rnr.digest'].send_digest(
            month=month or None, force=bool(force))

    @api.model
    def run_celebrations(self):
        """"Run it now" — exactly what the night does, no more and no less
        (R53)."""
        self._require_review()
        today = self.env['pb.rnr.celebration'].run_celebrations_today()
        week = self.env['pb.rnr.celebration'].run_manager_week()
        return {'today': today, 'week': week}
