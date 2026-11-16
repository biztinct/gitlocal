# -*- coding: utf-8 -*-
"""WDGAP W3-B (owner ruling PRV1) — the yearly Pay Review waits for its start date.

WHAT WAS TRUE BEFORE. Pressing Apply on an approved Pay Review wrote every
person's new wage at once (`pb.pay.apply.apply_review`, pb_pay), whatever "New
pay starts on" said, and wrote no dated record — so neither proration nor the
Past-month re-work could see a review's rise.

WHAT IS TRUE NOW (everything here is by inheritance; no pb_pay file changes):

* Apply still needs the review's existing approval (nothing about WHO approves
  or WHO may press Apply changed).
* A start date TODAY OR EARLIER: the original Apply runs untouched (same
  wages, same 24-hour take-back, same letters) and, for every person written,
  the SAME dated contract amount-change record Change job and "Raise the
  scale" write (`hr.contract.advantage.change`, source "From the pay review",
  effective date = the review's start date) — for the input of the person's
  pay scheme that reads the wage (BASIC / WAGE / BASE), when it has one.
* A start date in the FUTURE: nothing is written on any contract or payslip.
  Each person gets a `pb.pay.apply` row in the new state "Waiting for its day"
  holding the wage seen at Apply and the new one; the review reads "Applies on
  <date>" with "Take it back" until that day. The existing quiet hourly job of
  this module ("write approved rises on their day", `pb.pay.scale.raise.
  _cron_apply_due`) writes them on the day — one review per transaction,
  row-locked, idempotent; a person whose pay moved since Apply (or whose
  contract stopped running) is skipped with the reason, never overwritten.
* A start date in a month ALREADY PAID: once written, the review says "This
  change starts in a month already paid" with the button that opens NEW draft
  Past-month re-works (one per pay scheme) through `pb_retro`'s own door and
  gate. C-6: no back-pay input is written here. Without `pb_retro`: a calm note.
* A review with NO start date behaves exactly as before (the field is
  required, so none exist today — the branch is the golden fallback).
* Reviews applied before this change are not touched: the job only reads rows
  in the new state, which only a new Apply writes; their take-back writes no
  reverse dated row because they never had one (`pbs_change_id`).
"""
import json
import logging
from datetime import datetime, time, timedelta

import pytz
from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

REVIEW_SOURCE = 'pay_review'
LOCK_ERRORS = (pg_errors.LockNotAvailable,)
#: Letters printed inside the job's own pass; the pay letters job prints the rest.
LETTERS_INLINE = 25


def _day(env, value):
    return format_date(env, value, date_format='d MMM y') if value else ''


class HrContractAdvantageChangeReview(models.Model):
    """One more word for the pay-line trail: "From the pay review"."""
    _inherit = 'hr.contract.advantage.change'

    change_source = fields.Selection(
        selection_add=[(REVIEW_SOURCE, 'From the pay review')],
        # Uninstalling never deletes trail rows: they read "Manual" instead.
        ondelete={REVIEW_SOURCE: lambda recs: recs.write({'change_source': 'manual'})})


class PbPayApplyDated(models.Model):
    _inherit = 'pb.pay.apply'

    state = fields.Selection(
        selection_add=[('scheduled', 'Waiting for its day'),
                       ('skipped', 'Not written')],
        # Uninstalling: a row that never reached a contract reads "Taken back".
        ondelete={'scheduled': lambda recs: recs.write({'state': 'undone'}),
                  'skipped': lambda recs: recs.write({'state': 'undone'})})
    pbs_change_id = fields.Many2one(
        'hr.contract.advantage.change', string='Dated change',
        ondelete='set null', readonly=True,
        help='The dated amount-change record written with this pay, read by '
             'proration and the Past-month re-work.')

    # ------------------------------------------------------------- helpers
    @api.model
    def _pbs_today(self, company):
        return self.env['pb.pay.scale.raise']._today_for(company)

    @api.model
    def _pbs_zone(self, company):
        """The zone "the day" is read in — the order `_today_for` uses."""
        for tz in ((company.partner_id.tz if company else False), self.env.user.tz):
            if tz and tz in pytz.all_timezones_set:
                return tz
        return 'UTC'

    @api.model
    def _pbs_day_starts(self, day, company):
        """The first moment of `day` in the company's zone, as stored (UTC)."""
        zone = pytz.timezone(self._pbs_zone(company))
        local = zone.localize(datetime.combine(day, time.min))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _pbs_lock(self, review, wait=False):
        """Row-lock the review: Apply, take back and the job never overlap."""
        self.env.flush_all()
        query = ('SELECT id FROM pb_pay_review WHERE id = %s FOR UPDATE '
                 + ('NOWAIT' if wait else 'SKIP LOCKED'))
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(query, [review.id])
                got = self.env.cr.fetchone()
        except LOCK_ERRORS:
            return False
        review.invalidate_recordset()
        review.apply_ids.invalidate_recordset()
        return bool(got)

    @api.model
    def _pbs_busy(self):
        return UserError(_("This review is being applied right now. Look again "
                           "in a minute."))

    @api.model
    def _pbs_wage_code(self, employee):
        return self.env['pb.pay.scale.raise']._wage_code(employee)

    def _pbs_log(self, actor, reverse=False, note=''):
        """The dated record for each row (once), dated the row's start date.
        ``reverse`` writes the way back (new → old) for a take-back."""
        Change = self.env(user=actor.id, su=True)['hr.contract.advantage.change']
        Raise = self.env['pb.pay.scale.raise']
        made = 0
        for row in self:
            contract = row.contract_id
            if not contract:
                continue
            if reverse:
                done = row.sudo().pbs_change_id
                if not done:
                    continue
                Change.log(contract, done.advantage_template_id,
                           float(row.new_wage), float(row.old_wage), REVIEW_SOURCE,
                           notes=note, user=actor, effective_date=row.effective_date)
                made += 1
                continue
            if row.pbs_change_id:
                continue
            code = self._pbs_wage_code(contract.employee_id)
            if not code:
                continue
            change = Change.log(contract, Raise._template_for(code),
                                float(row.old_wage), float(row.new_wage),
                                REVIEW_SOURCE, notes=note, user=actor,
                                effective_date=row.effective_date)
            row.sudo().write({'pbs_change_id': change.id})
            made += 1
        return made

    @api.model
    def _pbs_note(self, review, effective):
        return _("Pay review %(name)s, from %(day)s", name=review.name or '',
                 day=_day(self.env, effective))

    # ================================================================ preview
    @api.model
    def preview_review(self, review_id):
        answer = super().preview_review(review_id)
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if review and review.effective_date \
                and review.effective_date > self._pbs_today(review.company_id):
            day = _day(self.env, review.effective_date)
            answer['pbs_when'] = _(
                "Nothing is written today. The new pay is written on %(day)s; "
                "until then contracts and payslips stay as they are.", day=day)
            answer['pbs_undo_line'] = _(
                "You can take it back until %(day)s, on one button.", day=day)
        return answer

    # ================================================================== apply
    @api.model
    def apply_review(self, review_id):
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review or not review.effective_date:
            # Golden: a review with no start date applies exactly as before.
            return super().apply_review(review_id)
        if not self._pbs_lock(review, wait=True):
            raise self._pbs_busy()
        if review.effective_date > self._pbs_today(review.company_id):
            return self._pbs_schedule(review)
        answer = super().apply_review(review_id)
        rows = review.apply_ids.filtered(
            lambda a: a.state == 'applied' and not a.pbs_change_id)
        rows._pbs_log(self.env.user, note=self._pbs_note(review, review.effective_date))
        review._pbs_remember_paid_months()
        paid = review._pbs_paid_info()
        if paid:
            answer['note'] = ' '.join(n for n in (answer.get('note') or '',
                                                  paid['sentence']) if n)
        return answer

    @api.model
    def _pbs_schedule(self, review):
        """Approved, future start date: record who moves, write nothing."""
        if review.state != 'approved':
            raise UserError(_(
                "Only an approved review can be applied. This one is "
                "%(state)s.", state=dict(review._fields['state'].selection)
                .get(review.state, review.state)))
        if review.apply_ids.filtered(lambda a: a.state in ('applied', 'scheduled')):
            raise UserError(_(
                "This review has already been applied. Take it back first if "
                "you need to change it."))
        now = fields.Datetime.now()
        until = self._pbs_day_starts(review.effective_date, review.company_id)
        made = self.browse()
        for line in review.line_ids:
            contract = line.contract_id
            if not contract or contract.state != 'open':
                continue
            if abs(float(line.new_wage or 0.0)
                   - float(line.current_wage or 0.0)) < 0.005:
                continue
            made |= self.sudo().create({
                'review_id': review.id, 'line_id': line.id,
                'employee_id': line.employee_id.id,
                'contract_id': contract.id,
                'company_id': line.company_id.id,
                'currency_id': (line.currency_id or review.currency_id).id,
                'old_wage': float(contract.wage or 0.0),
                'new_wage': line.new_wage,
                'effective_date': review.effective_date,
                'applied_at': now, 'applied_by': self.env.uid,
                'undo_until': False,
                'state': 'scheduled',
            })
            line.state = 'submitted'
        review.sudo().write({'applied_at': now, 'applied_by': self.env.uid,
                             'undo_until': until,
                             'pbs_paid_months_json': False,
                             'pbs_rework_ids_json': False})
        review._advance_state('applied')
        day = _day(self.env, review.effective_date)
        review.message_post(body=_(
            "Applied for %(count)s contracts. The new pay starts on %(day)s; "
            "nothing changes on any contract or payslip until then.",
            count=len(made), day=day))
        return {
            'count': len(made),
            'letters': 0,
            'letters_waiting': 0,
            'undo_until': str(until),
            'scheduled': True,
            'sentence': _(
                "Recorded for %(count)s contracts. The new pay starts on "
                "%(day)s; nothing changes until then, and you can take it back "
                "until that day.", count=len(made), day=day),
            'note': '',
        }

    # ========================================================= the day comes
    @api.model
    def _pbs_start_review(self, review, by_job=True):
        """Write a review's waiting rows whose day has come. ``(outcome, n)``:
        started / busy / gone."""
        if not self._pbs_lock(review, wait=not by_job):
            return 'busy', 0
        rows = review.apply_ids.filtered(lambda a: a.state == 'scheduled')
        if not rows:
            return 'gone', 0
        effective = min(rows.mapped('effective_date'))
        if effective > self._pbs_today(review.company_id):
            return 'gone', 0
        actor = review.applied_by if review.applied_by and review.applied_by.active \
            else self.env.user
        me = self.env(user=actor.id, su=True)
        C = me['hr.contract'].with_context(pb_pay_no_rebuild=True)
        now = fields.Datetime.now()
        note = self._pbs_note(review, effective)
        money = self.env['pb.pay.bands']
        written = self.browse()
        for row in rows:
            contract = row.contract_id
            skip = ''
            if not contract or contract.state != 'open':
                skip = _("Their contract is no longer running, so nothing was "
                         "written for them.")
            elif abs(float(contract.wage or 0.0) - float(row.old_wage or 0.0)) >= 0.005:
                skip = _("Their pay changed since the review was applied (now "
                         "%s), so nothing was written for them.",
                         money._money(contract.wage, row.currency_id
                                      or contract.currency_id))
            elif contract.date_end and contract.date_end < row.effective_date:
                skip = _("Their contract ends before the new pay starts.")
            if skip:
                row.sudo().write({'state': 'skipped', 'note': skip})
                continue
            try:
                with self.env.cr.savepoint():
                    C.browse(contract.id).write({'wage': float(row.new_wage)})
                    row.sudo().write({'state': 'applied', 'applied_at': now,
                                      'letter_state': 'pending', 'note': False})
                    row._pbs_log(actor, note=note)
                    written |= row
            except Exception as error:      # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('pay review %s: contract %s not written',
                                  review.id, contract.id)
                row.sudo().write({'state': 'skipped', 'note': _(
                    "It could not be written: %s",
                    str(error.args[0] if getattr(error, 'args', None) else error)[:300])})
        # The take-back was "until the day"; the day has come and the pay is
        # written, so it closes now whatever clock the job ran by.
        review.sudo().write({'undo_until': now - timedelta(seconds=1)})
        review._pbs_remember_paid_months()
        if written:
            try:
                written._make_letters(review, limit=LETTERS_INLINE)
            except Exception:       # noqa: BLE001 — the paperwork is not the pay
                _logger.exception('pay review %s: letters not printed', review.id)
            self._recompute_positions(review.company_ids)
        skipped = len(rows) - len(written)
        review.message_post(body=_(
            "New pay written for %(count)s contracts from %(day)s.",
            count=len(written), day=_day(self.env, effective))
            + (' ' + _("%(count)s were not written; the review lists why.",
                       count=skipped) if skipped else ''))
        return 'started', len(written)

    @api.model
    def _pbs_start_due_reviews(self, limit=20):
        """Called by the quiet hourly job. Safe on an empty database (one
        search); one review per transaction."""
        testing = bool(odoo_module.current_test)
        rows = self.sudo().search([('state', '=', 'scheduled'),
                                   ('review_id', '!=', False)],
                                  order='effective_date, id')
        tally = {}
        for review in rows.mapped('review_id')[:int(limit or 20)]:
            try:
                with self.env.cr.savepoint():
                    outcome, _n = self._pbs_start_review(review, by_job=True)
            except LOCK_ERRORS:
                self.env.invalidate_all()
                outcome = 'busy'
            except Exception:   # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('pay review %s: could not start', review.id)
                outcome = 'failed'
            if outcome != 'gone':
                tally[outcome] = tally.get(outcome, 0) + 1
            if not testing:
                self.env.cr.commit()
        if tally:
            _logger.info('pb_pay_scales: pay reviews on their day %s', tally)
        return tally

    # =================================================================== undo
    @api.model
    def undo_review(self, review_id):
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            return super().undo_review(review_id)
        if not self._pbs_lock(review, wait=True):
            raise self._pbs_busy()
        waiting = review.apply_ids.filtered(lambda a: a.state == 'scheduled')
        if not waiting:
            dated = review.apply_ids.filtered(
                lambda a: a.state == 'applied' and a.pbs_change_id)
            answer = super().undo_review(review_id)
            dated.filtered(lambda a: a.state == 'undone')._pbs_log(
                self.env.user, reverse=True,
                note=_("Taken back: pay review %s", review.name or ''))
            review.sudo().write({'pbs_paid_months_json': False})
            return answer
        deadline = review.undo_until
        if deadline and fields.Datetime.now() > deadline:
            raise UserError(_(
                "The new pay starts on %(day)s, so this can no longer be taken "
                "back. To move the pay again, make a pay change.",
                day=_day(self.env, min(waiting.mapped('effective_date')))))
        # Nothing reached any contract: the rows simply stop waiting.
        waiting.sudo().write({'state': 'undone', 'letter_state': 'none'})
        review.sudo().write({'undo_until': False, 'applied_at': False,
                             'applied_by': False})
        review._chain_state_write('approved')
        review._log_transition('applied', 'approved', _('Taken back'))
        review.message_post(body=_(
            "Taken back before it started. Nobody's pay changed."))
        return {'count': 0,
                'sentence': _("Taken back. Nobody's pay changed, and the review "
                              "is approved again.")}


class PbPayReviewDated(models.Model):
    _inherit = 'pb.pay.review'

    #: ``[{month, month_label, config_id, config, people, count}]`` — finished
    #: regular payslips of the people written, ending on or after the start
    #: date. A count only (C-6): nothing is recalculated here.
    pbs_paid_months_json = fields.Text(readonly=True, copy=False)
    pbs_rework_ids_json = fields.Text(readonly=True, copy=False)

    def _pbs_json(self, name, default):
        self.ensure_one()
        try:
            value = json.loads(self[name] or 'null')
        except (TypeError, ValueError):
            return default
        return value if value is not None else default

    def _pbs_written(self):
        self.ensure_one()
        return self.apply_ids.filtered(lambda a: a.state == 'applied')

    def _pbs_remember_paid_months(self):
        """Months already paid for the people this review wrote."""
        self.ensure_one()
        people = self._pbs_written().mapped('employee_id')
        months = []
        if people and self.effective_date:
            probe = self.env['pb.pay.scale.raise'].new(
                {'effective_date': self.effective_date})
            months = probe._paid_months_for(people)
        self.sudo().write({'pbs_paid_months_json': json.dumps(months)
                           if months else False})
        return months

    def _pbs_paid_info(self):
        """The "starts in a month already paid" banner, or {}."""
        self.ensure_one()
        if self.state not in ('applied', 'closed') or not self._pbs_written():
            return {}
        months = self._pbs_json('pbs_paid_months_json', [])
        if not months:
            return {}
        labels = []
        people = set()
        for row in months:
            if row.get('month_label') and row['month_label'] not in labels:
                labels.append(row['month_label'])
            people.update(row.get('people') or [])
        retro = self.env['pb.pay.scale.raise']._retro_installed()
        made = self._pbs_json('pbs_rework_ids_json', [])
        return {
            'sentence': _("This change starts in a month already paid."),
            'months': ', '.join(labels),
            'people': len(people),
            'detail': _("One person was paid for %(months)s before their new "
                        "pay was written.", months=', '.join(labels))
            if len(people) == 1 else
            _("%(people)s people were paid for %(months)s before their new "
              "pay was written.", people=len(people), months=', '.join(labels)),
            'can_rework': bool(retro),
            'rework_made': bool(made),
            'note': '' if retro else _(
                "Tell the pay team: they can work out any difference by hand "
                "on the next pay run."),
        }

    def _pbs_status(self):
        """What the review screen shows about the start date."""
        self.ensure_one()
        out = {}
        waiting = self.apply_ids.filtered(lambda a: a.state == 'scheduled')
        if waiting and self.state == 'applied':
            day = _day(self.env, min(waiting.mapped('effective_date')))
            out['pbs_waits'] = {
                'day': day,
                'label': _("Applies on %s", day),
                'count': len(waiting),
                'note': _("New pay for %(count)s contracts is written on "
                          "%(day)s. Until then nothing changes on any contract "
                          "or payslip, and you can take it back.",
                          count=len(waiting), day=day),
            }
        skipped = self.apply_ids.filtered(lambda a: a.state == 'skipped')
        if skipped and self.state in ('applied', 'closed'):
            out['pbs_skipped'] = {
                'count': len(skipped),
                'sentence': _("One person was not written on the day:")
                if len(skipped) == 1 else
                _("%(count)s people were not written on the day:",
                  count=len(skipped)),
                'rows': [{'id': r.id, 'name': r.employee_id.name or '',
                          'why': r.note or ''} for r in skipped[:30]],
            }
        paid = self._pbs_paid_info()
        if paid:
            out['pbs_paid'] = paid
        return out

    def _before_approval_transition(self, to_state):
        super()._before_approval_transition(to_state)
        if to_state == 'closed' and self.apply_ids.filtered(
                lambda a: a.state == 'scheduled'):
            raise UserError(_(
                "This review's new pay has not started yet. Close it after it "
                "starts, or take it back."))

    def pbs_open_rework(self):
        """Open NEW draft Past-month re-works for the people written and the
        paid months, one per pay scheme, through the re-work's own door and
        gate (it is called in the reader's rights). Writes nothing else.
        Returns ``{'review_id', 'review_ids'}``."""
        self.ensure_one()
        Raise = self.env['pb.pay.scale.raise']
        if not Raise._retro_installed():
            raise UserError(_("Past-month re-work is not part of this database. "
                              "Tell the pay team: they can work out any difference "
                              "by hand on the next pay run."))
        if not self._pbs_paid_info():
            raise UserError(_("No month already paid is affected."))
        known = [int(i) for i in self._pbs_json('pbs_rework_ids_json', [])]
        alive = self.env['pb.retro.review'].sudo().browse(known).exists()
        if alive:
            return {'review_id': alive[:1].id, 'review_ids': alive.ids}
        written = set(self._pbs_written().mapped('employee_id').ids)
        by_scheme = {}
        for row in self._pbs_json('pbs_paid_months_json', []):
            if not row.get('config_id'):
                continue
            entry = by_scheme.setdefault(row['config_id'],
                                         {'months': set(), 'people': set()})
            entry['months'].add(row['month'])
            entry['people'].update(p for p in row.get('people') or []
                                   if p in written)
        made = []
        for config_id, entry in sorted(by_scheme.items()):
            if not entry['people']:
                continue
            picked = sorted(entry['months'])
            first = fields.Date.to_date(picked[0])
            last = fields.Date.to_date(picked[-1])
            if (last.year - first.year) * 12 + last.month - first.month >= 12:
                first = (last.replace(day=1) - timedelta(days=330)).replace(day=1)
            answer = self.env['pb.retro.board'].save_review({
                'config_id': config_id,
                'month_from': fields.Date.to_string(first),
                'month_to': fields.Date.to_string(last),
                'people': 'picked',
                'employee_ids': sorted(entry['people'])[:500],
                'reason': _("Pay review %(name)s starts on %(day)s, in a month "
                            "already paid.", name=self.name or '',
                            day=_day(self.env, self.effective_date)),
            })
            if (answer or {}).get('id'):
                made.append(int(answer['id']))
        if not made:
            raise UserError(_("The paid months have no pay scheme on them, so "
                              "they cannot be re-worked here."))
        self.sudo().write({'pbs_rework_ids_json': json.dumps(made)})
        return {'review_id': made[0], 'review_ids': made}


class PbPayReviewsDated(models.AbstractModel):
    """The review screen: "Applies on <date>", the paid-month banner, and the
    re-work door. Read and gated exactly like the rest of the screen."""
    _inherit = 'pb.pay.reviews'

    @api.model
    def _card(self, review):
        card = super()._card(review)
        status = self._safe(lambda: review._pbs_status(), default={}) or {}
        card.update(status)
        waits = status.get('pbs_waits')
        if waits:
            card['state_label'] = waits['label']
            card['next_step'] = waits['label']
        return card

    @api.model
    def _actions(self, review):
        actions = super()._actions(review)
        if review.apply_ids.filtered(lambda a: a.state == 'scheduled'):
            actions['close'] = False
        return actions

    @api.model
    def pbs_open_rework(self, review_id):
        self._require_write()
        review = self._review(review_id)
        return review.pbs_open_rework()
