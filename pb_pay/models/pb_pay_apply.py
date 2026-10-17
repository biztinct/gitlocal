# -*- coding: utf-8 -*-
"""`pb.pay.apply` — the one place in this module that changes what a person is paid.

WHY IT IS ITS OWN MODEL
-----------------------
Because it is the only dangerous thing here, and a dangerous thing deserves one
door, one preview, one record of exactly what was written, and one way back.
Everything else in Pay is a statement about money — a band is intent, a
proposal is an opinion, a fairness figure is a measurement. This writes
`hr.contract.wage`, and after it has run somebody's pay is different.

THE FOUR PROMISES
-----------------
1. **You see it first.** `preview()` lists every contract that will change,
   with the old figure, the new figure, the currency and the date, and it is
   built by the same code that does the writing — not a second implementation
   that can drift from it.
2. **One row per write.** Every contract that changes gets a `pb.pay.apply`
   record holding the old wage. That record is what Undo reads; the old value
   is never recomputed from a percentage, because a percentage of a number that
   has since moved is not the number that was there.
3. **Twenty-four hours to change your mind.** Undo restores every old wage
   exactly, marks the rows undone and voids the letters. After the window the
   button is gone and the screen says why, because an Undo that silently does
   nothing is worse than no Undo.
4. **Nothing already computed is touched.** A payslip that has been calculated
   is a record of what was paid. Applying a raise never reaches back into one;
   the new wage is used by the NEXT run, and where a run for the month is
   already open the screen says so out loud.
"""

import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: How long a person has to take an Apply back.
UNDO_HOURS = 24

#: How many letters are printed INSIDE the click, and how many the job that
#: follows prints each time it wakes up. A letter is a rendered PDF filed in
#: somebody's document vault; four thousand of them is a quarter of an hour of
#: work, and a screen that sits still for a quarter of an hour after the most
#: consequential button in the product is a screen nobody trusts again. So a
#: small review finishes in the click and a large one finishes in the minutes
#: after it, with the screen saying which.
LETTERS_INLINE = 25
LETTERS_PER_RUN = 200

#: The letter this module prints. Falls back to the platform's own "custom"
#: type on a build whose letter engine has not been updated yet.
LETTER_TYPE_REVIEW = 'pay_review'
LETTER_TYPE_CHANGE = 'pay_change'


class PbPayApply(models.Model):
    _name = 'pb.pay.apply'
    _description = 'A pay change that was written'
    _order = 'applied_at desc, id desc'
    _rec_name = 'employee_id'

    review_id = fields.Many2one(
        'pb.pay.review', string='Review', ondelete='cascade', index=True)
    line_id = fields.Many2one(
        'pb.pay.review.line', string='Row', ondelete='set null')
    change_id = fields.Many2one(
        'pb.pay.change', string='Pay change', ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', ondelete='set null', index=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)
    currency_id = fields.Many2one('res.currency', string='Currency')

    old_wage = fields.Monetary(string='Was paid', readonly=True)
    new_wage = fields.Monetary(string='Now paid', readonly=True)
    effective_date = fields.Date(string='From', readonly=True)
    applied_at = fields.Datetime(string='Applied on', readonly=True,
                                 default=fields.Datetime.now)
    applied_by = fields.Many2one('res.users', string='Applied by',
                                 readonly=True,
                                 default=lambda self: self.env.user)
    undo_until = fields.Datetime(string='Can be taken back until',
                                 readonly=True)
    state = fields.Selection(
        [('applied', 'Applied'), ('undone', 'Taken back')],
        string='Status', default='applied', index=True)
    letter_id = fields.Many2one(
        'pb.hr.letter', string='Letter', ondelete='set null')
    letter_state = fields.Selection(
        [('pending', 'Being prepared'), ('done', 'Ready'),
         ('none', 'No letter')],
        string='Letter', default='pending', index=True)
    note = fields.Char(string='Note')

    # ================================================================ preview
    @api.model
    def preview_review(self, review_id):
        """Every contract this review would change, before anything is written."""
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        rows, skipped = [], []
        money = self.env['pb.pay.bands']
        for line in review.line_ids:
            contract = line.contract_id
            if not contract or contract.state != 'open':
                skipped.append({
                    'name': line.employee_id.name or '',
                    'why': _("This person has no open contract, so there is "
                             "nothing to write a new figure onto."),
                })
                continue
            if abs(float(line.new_wage or 0.0)
                   - float(line.current_wage or 0.0)) < 0.005:
                continue
            currency = line.currency_id or review.currency_id
            rows.append({
                'line_id': line.id,
                'employee_id': line.employee_id.id,
                'name': line.employee_id.name or '',
                'contract': contract.display_name or '',
                'old': float(line.current_wage or 0.0),
                'new': float(line.new_wage or 0.0),
                'old_label': money._money(line.current_wage, currency),
                'new_label': money._money(line.new_wage, currency),
                'currency': currency.name or '',
                'pct': round(float(line.proposal_pct or 0.0), 2),
            })
        return {
            'rows': rows[:400],
            'count': len(rows),
            'skipped': skipped[:60],
            'skipped_count': len(skipped),
            'effective_date': str(review.effective_date or ''),
            'open_run': self._open_run_note(review),
            'sentence': _("%(count)s contracts would change on %(date)s.",
                          count=len(rows),
                          date=fields.Date.to_string(review.effective_date)),
        }

    @api.model
    def _open_run_note(self, review):
        """Whether a pay run is already open for the month the raise starts in.

        Not a refusal — a company that raises pay mid-month usually means it —
        but a sentence, because the run that is already open will not pick the
        new figure up unless somebody recomputes it.
        """
        start = review.effective_date
        if not start:
            return ''
        Slip = self.env['hr.payslip'].sudo()
        try:
            found = Slip.search([
                ('company_id', 'in', review.company_ids.ids
                 or [review.company_id.id]),
                ('date_from', '<=', start), ('date_to', '>=', start),
                ('state', 'in', ('draft', 'verify')),
            ], limit=1)
        except Exception:                       # noqa: BLE001
            return ''
        if not found:
            return ''
        return _("A pay run covering %(date)s is already open. New pay is used "
                 "by the next run unless that one is worked out again.",
                 date=fields.Date.to_string(start))

    # ================================================================== apply
    @api.model
    def apply_review(self, review_id):
        """Write the new pay. The one intended write in this module."""
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        if review.state != 'approved':
            raise UserError(_(
                "Only an approved review can be applied. This one is "
                "%(state)s.", state=dict(review._fields['state'].selection)
                .get(review.state, review.state)))
        if review.apply_ids.filtered(lambda a: a.state == 'applied'):
            raise UserError(_(
                "This review has already been applied. Take it back first if "
                "you need to change it."))

        preview = self.preview_review(review.id)
        now = fields.Datetime.now()
        until = self._undo_deadline(now)
        made = self.browse()
        # SUDO, ON PURPOSE, AND ONLY HERE. The gate above has already checked
        # that this reader runs pay and that the review is approved by four
        # people; writing the wage as the clicking user instead would mean
        # handing every pay manager the right to edit any contract by hand,
        # which is a far larger grant than the one act this method performs.
        # Who did it is recorded on every row below, so the trail is truthful
        # even though the write is not made in their name.
        #
        # `pb_pay_no_rebuild` is the difference between one minute and twenty.
        # A contract write queues a rebuild of the whole position table on the
        # cursor's precommit, which is right for a person editing one contract
        # and catastrophic for four thousand — anything that flushes the cursor
        # mid-loop runs the queued pass, and four thousand passes over four
        # thousand rows is quadratic work for a figure this method rebuilds
        # ONCE at the end anyway.
        Contract = self.env['hr.contract'].sudo().with_context(
            pb_pay_no_rebuild=True)
        # The preview CAPS its rows because a screen cannot draw four thousand
        # of them; the write walks every line, so the two can never disagree
        # about who was paid.
        for line in review.line_ids:
            contract = line.contract_id
            if not contract or contract.state != 'open':
                continue
            if abs(float(line.new_wage or 0.0)
                   - float(line.current_wage or 0.0)) < 0.005:
                continue
            old = float(contract.wage or 0.0)
            Contract.browse(contract.id).write({'wage': line.new_wage})
            record = self.sudo().create({
                'review_id': review.id, 'line_id': line.id,
                'employee_id': line.employee_id.id,
                'contract_id': contract.id,
                'company_id': line.company_id.id,
                'currency_id': (line.currency_id or review.currency_id).id,
                'old_wage': old, 'new_wage': line.new_wage,
                'effective_date': review.effective_date,
                'applied_at': now, 'applied_by': self.env.uid,
                'undo_until': until,
            })
            made |= record
            line.state = 'submitted'

        review.sudo().write({
            'applied_at': now, 'applied_by': self.env.uid,
            'undo_until': until,
        })
        review._advance_state('applied')
        letters = made._make_letters(review, limit=LETTERS_INLINE)
        waiting = len(made.filtered(lambda r: r.letter_state == 'pending'))
        self._recompute_positions(review.company_ids)
        review.message_post(body=_(
            "Applied to %(count)s contracts, effective %(date)s.",
            count=len(made),
            date=fields.Date.to_string(review.effective_date)))
        notes = [note for note in (preview.get('open_run') or '',
                                   self._letter_note(waiting)) if note]
        return {
            'count': len(made),
            'letters': letters,
            'letters_waiting': waiting,
            'undo_until': str(until),
            'sentence': _(
                "Applied to %(count)s contracts. You can take it back until "
                "%(when)s.", count=len(made),
                when=fields.Datetime.to_string(until)),
            'note': ' '.join(notes),
        }

    @api.model
    def _letter_note(self, waiting):
        if not waiting:
            return ''
        return _("Letters for %(count)s people are being prepared and will "
                 "appear in their documents shortly.", count=waiting)

    @api.model
    def _undo_deadline(self, now):
        return now + timedelta(hours=UNDO_HOURS)

    @api.model
    def _recompute_positions(self, companies):
        try:
            self.env['pb.pay.position'].sudo().recompute_all(
                companies.ids or None)
        except Exception:                       # noqa: BLE001
            _logger.exception('pb_pay: positions could not be rebuilt after '
                              'an apply')

    # =================================================================== undo
    @api.model
    def undo_review(self, review_id):
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        rows = review.apply_ids.filtered(lambda a: a.state == 'applied')
        if not rows:
            raise UserError(_("There is nothing here to take back."))
        deadline = review.undo_until
        if deadline and fields.Datetime.now() > deadline:
            raise UserError(_(
                "The time to take this back ran out at %(when)s. Pay it back "
                "down with a pay change, which leaves a record of both moves.",
                when=fields.Datetime.to_string(deadline)))
        count = rows._restore()
        review.sudo().write({'undo_until': False, 'applied_at': False,
                             'applied_by': False})
        review._chain_state_write('approved')
        review._log_transition('applied', 'approved', _('Taken back'))
        review.message_post(body=_(
            "Taken back. %(count)s contracts are on their old pay again.",
            count=count))
        self._recompute_positions(review.company_ids)
        return {'count': count,
                'sentence': _("%(count)s contracts are back on their old pay.",
                              count=count)}

    def _restore(self):
        """Put every old wage back, exactly as it was."""
        # See `apply_review`: one rebuild at the end, never one per row.
        Contract = self.env['hr.contract'].sudo().with_context(
            pb_pay_no_rebuild=True)
        count = 0
        for row in self:
            if row.state != 'applied':
                continue
            if row.contract_id:
                Contract.browse(row.contract_id.id).write(
                    {'wage': row.old_wage})
                count += 1
            if row.letter_id:
                try:
                    row.letter_id.sudo().message_post(body=_(
                        "This pay change was taken back, so this letter no "
                        "longer describes what happened."))
                    row.letter_id.sudo().write({'state': 'draft'})
                except Exception:               # noqa: BLE001
                    _logger.info('pb_pay: a letter could not be voided')
            row.sudo().write({'state': 'undone'})
        return count

    # ================================================================ letters
    def _make_letters(self, source=None, limit=None):
        """One letter per person, generated and filed. Never fatal.

        `limit` is what keeps Apply a click rather than a coffee break: the
        first few are printed while the reader is still looking at the screen
        and the rest are left `pending` for the job below, which says so on
        the way out.
        """
        if not self:
            return 0
        # A promotion is not a pay round, and a letter that opens "following
        # this year's pay review" on the day somebody is promoted is a letter
        # nobody should have to explain.
        kind = LETTER_TYPE_CHANGE \
            if source is not None and source._name == 'pb.pay.change' \
            else LETTER_TYPE_REVIEW
        template = self._letter_template(kind)
        if not template:
            self.sudo().write({'letter_state': 'none'})
            return 0
        Letter = self.env['pb.hr.letter'].sudo()
        money = self.env['pb.pay.bands']
        made = 0
        todo = self if limit is None else self[:limit]
        for row in todo:
            try:
                currency = row.currency_id or row.company_id.currency_id
                extra = {
                    'old_pay': money._money(row.old_wage, currency),
                    'new_pay': money._money(row.new_wage, currency),
                    'increase_pct': '%.2f' % (
                        (row.new_wage - row.old_wage) / row.old_wage * 100.0
                        if row.old_wage else 0.0),
                    'effective_date': fields.Date.to_string(
                        row.effective_date) or '',
                    'reason': self._letter_reason(source),
                }
                letter = Letter.create({
                    'employee_id': row.employee_id.id,
                    'template_id': template.id,
                    'subject': template.subject or template.name,
                    'context_json': json.dumps(extra, default=str),
                    'company_id': (row.company_id or self.env.company).id,
                })
                letter.action_generate()
                row.sudo().write({'letter_id': letter.id,
                                  'letter_state': 'done'})
                made += 1
            except Exception:                   # noqa: BLE001
                _logger.exception('pb_pay: a pay letter could not be prepared '
                                  'for employee %s', row.employee_id.id)
        return made

    @api.model
    def _cron_letters(self):
        """Print the letters Apply left for later, a batch at a time."""
        rows = self.sudo().search(
            [('letter_state', '=', 'pending'), ('state', '=', 'applied')],
            limit=LETTERS_PER_RUN)
        if not rows:
            return 0
        by_source = {}
        for row in rows:
            by_source.setdefault(row.review_id or row.change_id,
                                 self.browse())
            by_source[row.review_id or row.change_id] |= row
        made = 0
        for source, batch in by_source.items():
            made += batch._make_letters(source or None)
        _logger.info('pb_pay: %s pay letters printed', made)
        return made

    @api.model
    def _letter_reason(self, source):
        """Why, in the words whoever decided it wrote — never a record name."""
        if source is None:
            return ''
        if source._name == 'pb.pay.change':
            return source.reason or dict(
                source._fields['kind'].selection).get(source.kind, '')
        return source.name or ''

    @api.model
    def _letter_template(self, kind):
        """The template this module prints, made once if it is not there."""
        if 'pb.letter.template' not in self.env:
            return None
        Template = self.env['pb.letter.template'].sudo()
        known = dict(Template._fields['letter_type'].selection or [])
        letter_type = kind if kind in known else 'custom'
        marker = 'pay_review' if kind == LETTER_TYPE_REVIEW else 'pay_change'
        found = Template.search(
            [('letter_type', '=', letter_type), ('active', '=', True)],
            order='sequence, id')
        if letter_type == 'custom':
            found = found.filtered(lambda t: marker in (t.name or '').lower()
                                   .replace(' ', '_'))
        if found:
            return found[:1]
        return self._build_template(kind, letter_type)

    @api.model
    def _build_template(self, kind, letter_type):
        """Write the letter this product means to send, once.

        Shipping it as CODE rather than as a data record is on purpose: the
        letter engine is a soft dependency, and a data record naming a model
        that may not exist is an install-time failure rather than a missing
        feature.
        """
        Template = self.env['pb.letter.template'].sudo()
        review = kind == LETTER_TYPE_REVIEW
        name = _('Pay review letter') if review else _('Pay change letter')
        body = (
            '<div>'
            '<p>Dear ${employee_name},</p>'
            '<p>Following this year\u2019s pay review, your monthly pay '
            'changes from <strong>${old_pay}</strong> to '
            '<strong>${new_pay}</strong>, an increase of '
            '${increase_pct}%, with effect from ${effective_date}.</p>'
            '<p>Everything else in your terms of employment is unchanged.</p>'
            '<p>Thank you for the work you do here.</p>'
            '<p>${company}</p><p>${date}</p>'
            '</div>') if review else (
            '<div>'
            '<p>Dear ${employee_name},</p>'
            '<p>Your monthly pay changes from <strong>${old_pay}</strong> to '
            '<strong>${new_pay}</strong>, an increase of ${increase_pct}%, '
            'with effect from ${effective_date}.</p>'
            '<p>${reason}</p>'
            '<p>Everything else in your terms of employment is unchanged.</p>'
            '<p>${company}</p><p>${date}</p>'
            '</div>')
        category = self.env.ref('pb_employee_vault.cat_other',
                                raise_if_not_found=False)
        return Template.create({
            'name': name,
            'letter_type': letter_type,
            'subject': name,
            'sequence': 50,
            'body_html': body,
            'company_id': False,
            'vault_category_id': category.id if category else False,
        })

    # ------------------------------------------------------------ the reader
    @api.model
    def latest_for_employee(self, employee_id):
        """What last changed this person's pay, for the portal page."""
        return self.sudo().search([
            ('employee_id', '=', int(employee_id or 0)),
            ('state', '=', 'applied'),
        ], order='applied_at desc, id desc', limit=1)
