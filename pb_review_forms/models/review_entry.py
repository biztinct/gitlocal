# -*- coding: utf-8 -*-
"""One filled-in review form: the answers of both sides on one review row.

WHY A SEPARATE MODEL AND NOT FIELDS ON `pb.goal.review` (FACTS §1.4, ledger
PRC-W1). The employee's own login may READ (and write) their review row
(`pb_goals` rule `rule_review_portal`, and `rule_review_mine` for internal
logins). Anything stored there is in their hands the moment it is written —
including a manager's ratings that HR wants kept back until a date. So the
answers, the overall comment and every state of the form live HERE, on a
model no employee login holds any right on. Every employee read and write goes
through `pb.review.forms` (and the portal controller), which proves the review
is theirs and then works under sudo.

The review row itself is still THE review (FACTS §1.3: no second review
object): it is written up through its own `action_review_done`, so its state,
its frozen goals score and its chatter line are exactly what they always were.
Until the manager's part may be shown, the row's `manager_note` holds a neutral
sentence; the real overall comment is copied onto it when the review is shared
(`_release`).
"""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .rf_common import (
    ACK_STATES, MANAGER_STATES, RATING_KEYS, RATING_LABEL, SELF_STATES, tidy,
)

_logger = logging.getLogger(__name__)


class PbReviewEntry(models.Model):
    _name = 'pb.review.entry'
    _description = 'Filled-in review form'
    _order = 'id desc'

    _one_per_review = models.Constraint(
        'unique(review_id)',
        'That review already has a filled-in form.')

    review_id = fields.Many2one('pb.goal.review', string='Review',
                                required=True, index=True, ondelete='cascade')
    form_id = fields.Many2one('pb.review.form', string='Form', required=True,
                              index=True, ondelete='restrict')
    set_id = fields.Many2one('pb.goal.set', related='review_id.set_id',
                             store=True, index=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Whose',
                                  related='review_id.employee_id', store=True,
                                  index=True, readonly=True)
    cycle_id = fields.Many2one('pb.goal.cycle', related='review_id.cycle_id',
                               store=True, index=True, readonly=True)
    company_id = fields.Many2one('res.company', related='review_id.company_id',
                                 store=True, index=True, readonly=True)

    self_state = fields.Selection(SELF_STATES, string='Their own view',
                                  default='todo', required=True)
    self_sent_at = fields.Datetime(string='Own view sent on', readonly=True)
    mgr_state = fields.Selection(MANAGER_STATES, string="Manager's part",
                                 default='todo', required=True)
    mgr_done_at = fields.Datetime(string='Manager finished on', readonly=True)
    mgr_done_by_id = fields.Many2one('res.users', string='Finished by',
                                     readonly=True)
    mgr_without_self = fields.Boolean(
        string='Finished without their own view', readonly=True)
    overall_comment = fields.Text(string='Overall comment')
    released_at = fields.Datetime(string='Shown to them on', readonly=True)
    ack_state = fields.Selection(ACK_STATES, string='Read by them',
                                 default='none', required=True)
    ack_at = fields.Datetime(string='Read on', readonly=True)
    document_id = fields.Many2one('pb.employee.document',
                                  string='Filed in their documents',
                                  readonly=True, ondelete='set null')
    attachment_id = fields.Many2one('ir.attachment', string='PDF',
                                    readonly=True, ondelete='set null')
    answer_ids = fields.One2many('pb.review.answer', 'entry_id',
                                 string='Answers')

    # ============================================================ answers
    def _answers(self, author):
        """{line_id: answer} for one side."""
        self.ensure_one()
        return {a.line_id.id: a for a in self.sudo().answer_ids
                if a.author == author and a.line_id}

    def _store(self, author, answers):
        """Write one side's answers. `answers` = {line_id: value}.

        A value is a rating key '1'..'5', a text, or one of the line's
        choices. Lines of another form, lines this side does not answer and
        values that are not allowed are refused with a sentence.
        """
        self.ensure_one()
        record = self.sudo()
        lines = {line.id: line for line in record.form_id.line_ids}
        mine = record._answers(author)
        Answer = self.env['pb.review.answer'].sudo()
        for raw_id, raw in (answers or {}).items():
            try:
                line_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            line = lines.get(line_id)
            if not line or not line._asks(author):
                continue
            value = ('' if raw is None or raw is False else str(raw)).strip()
            vals = {'rating': False, 'text': False}
            kind = line._kind()
            if value:
                if kind == 'rating':
                    if value not in RATING_KEYS:
                        raise UserError(_(
                            "A rating is one of the five words from Well "
                            "below to Well above."))
                    vals['rating'] = value
                elif kind == 'choice':
                    if value not in line._choice_list():
                        raise UserError(_(
                            "\"%(a)s\" is not one of the answers to pick "
                            "from.", a=value[:80]))
                    vals['text'] = value
                else:
                    vals['text'] = value[:4000]
            existing = mine.get(line_id)
            if existing:
                existing.write(vals)
            elif value:
                Answer.create(dict(vals, entry_id=record.id, line_id=line_id,
                                   author=author))
        return True

    def _missing(self, author):
        """Lines this side must still answer, as their words."""
        self.ensure_one()
        record = self.sudo()
        mine = record._answers(author)
        out = []
        for line in record.form_id._skills() | record.form_id._questions():
            if not line._asks(author):
                continue
            if line.section == 'question' and not line.required:
                continue
            answer = mine.get(line.id)
            if not answer or not answer._value():
                out.append(line.name or '')
        return out

    # ============================================================== maths
    def _parts(self):
        """The three parts of the overall result, from the MANAGER's side.

        Each part is ``{key, label, share, value}`` with ``value`` on 0–5, or
        None while it cannot be worked out. The employee's own ratings are
        shown beside the manager's but never counted.
        """
        self.ensure_one()
        record = self.sudo()
        form = record.form_id
        sheet = record.set_id
        mine = record._answers('manager')
        parts = []
        if form.share_goals:
            parts.append({
                'key': 'goals', 'label': _('Goals score'),
                'share': form.share_goals,
                'value': (round(sheet.score or 0.0, 2)
                          if sheet and sheet.scored else None),
            })
        if form.share_skills:
            parts.append({
                'key': 'skills', 'label': _('Skills and values'),
                'share': form.share_skills,
                'value': self._average(form._skills(), mine),
            })
        if form.share_questions:
            parts.append({
                'key': 'questions', 'label': _('Rated questions'),
                'share': form.share_questions,
                'value': self._average(form._manager_rated_questions(), mine),
            })
        return parts

    @staticmethod
    def _average(lines, answers):
        values = []
        for line in lines:
            answer = answers.get(line.id)
            if not answer or not answer.rating:
                return None
            values.append(int(answer.rating))
        if not values:
            return None
        return round(sum(values) / float(len(values)), 2)

    def _overall(self):
        """The overall result on 0–5, or None while a part is missing."""
        self.ensure_one()
        parts = self._parts()
        share = sum(part['share'] for part in parts)
        if not parts or share <= 0 or any(p['value'] is None for p in parts):
            return None
        total = sum(part['share'] * part['value'] for part in parts)
        return round(total / float(share), 2)

    # ============================================================ sharing
    def _may_show(self, today=None):
        """Whether the manager's part may be shown to the employee now."""
        self.ensure_one()
        record = self.sudo()
        if record.released_at:
            return True
        if record.mgr_state != 'done':
            return False
        form = record.form_id
        if form.reveal == 'manager_done':
            return True
        if record.set_id.state == 'closed':
            return True
        today = today or fields.Date.context_today(self)
        return bool(form.reveal_date and form.reveal_date <= today)

    def _shown_from_words(self, reader='employee'):
        """When the employee will be able to read it, as a whole sentence
        for the employee ("You can…") or for the manager ("They can…")."""
        self.ensure_one()
        form = self.sudo().form_id
        dated = form.reveal == 'date' and form.reveal_date
        if reader == 'manager':
            if dated:
                return _("They can read it from %(day)s.",
                         day=self._day(form.reveal_date))
            return _("They can read it as soon as you finish.")
        if dated:
            return _("You can read it from %(day)s.",
                     day=self._day(form.reveal_date))
        return _("You can read it once your manager has finished.")

    def _day(self, value):
        if not value:
            return ''
        from odoo.tools.misc import format_date
        return format_date(self.env, value)

    def _release(self):
        """Share the finished review with the employee. Idempotent.

        Copies the real overall comment onto the review row, makes the PDF
        and files it in their documents. Each piece of paperwork in its own
        savepoint: a PDF that cannot be made never un-shares a review.
        """
        done = self.browse()
        for entry in self.sudo():
            if entry.released_at or entry.mgr_state != 'done':
                continue
            entry.write({'released_at': fields.Datetime.now()})
            review = entry.review_id
            comment = (entry.overall_comment or '').strip()
            if comment and review.manager_note != comment:
                review.write({'manager_note': comment})
            try:
                with self.env.cr.savepoint():
                    entry._file_pdf()
            except Exception:           # noqa: BLE001 — paperwork never fails
                _logger.warning('pb_review_forms: could not file the PDF for '
                                'review entry %s', entry.id, exc_info=True)
            done |= entry
        return done

    @api.model
    def _cron_release_due(self):
        """Daily: share finished reviews whose "shown from" day has come.

        Quiet by design: it writes the release stamp, the review row's note
        and the PDF in the person's documents. It sends no email. Safe on an
        empty database (nothing matches).
        """
        today = fields.Date.context_today(self)
        due = self.sudo().search([
            ('released_at', '=', False), ('mgr_state', '=', 'done'),
            ('form_id.reveal', '=', 'date'),
            ('form_id.reveal_date', '<=', today),
        ], limit=500)
        count = 0
        for entry in due:
            try:
                with self.env.cr.savepoint():
                    if entry._release():
                        count += 1
            except Exception:           # noqa: BLE001
                _logger.warning('pb_review_forms: could not share review '
                                'entry %s', entry.id, exc_info=True)
        if count:
            _logger.info('pb_review_forms: shared %s finished review(s)',
                         count)
        return count

    # ======================================================= the PDF file
    def _pdf_payload(self):
        """Everything the PDF prints, read once."""
        self.ensure_one()
        record = self.sudo()
        form = record.form_id
        emp = record.employee_id
        theirs = record._answers('employee')
        mine = record._answers('manager')
        lines = []
        for line in form._skills() | form._questions():
            lines.append({
                'section': line.section,
                'name': line.name or '',
                'description': line.description or '',
                'theirs': (theirs.get(line.id)._words()
                           if line._asks('employee') and theirs.get(line.id)
                           else ''),
                'mine': (mine.get(line.id)._words()
                         if line._asks('manager') and mine.get(line.id)
                         else ''),
                'asks_theirs': line._asks('employee'),
                'asks_mine': line._asks('manager'),
            })
        parts = [dict(p, value=tidy(p['value'])) for p in record._parts()]
        return {
            'title': form.name or '',
            'year': record.cycle_id.name or '',
            'employee': emp.name or '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else ''),
            'manager': record.review_id.manager_employee_id.name or '',
            'company': record.company_id.name or '',
            'lines': lines,
            'parts': parts,
            'overall': tidy(record._overall()),
            'comment': record.overall_comment or '',
            'self_sent': record._day(record.self_sent_at
                                     and record.self_sent_at.date()),
            'done_on': record._day(record.mgr_done_at
                                   and record.mgr_done_at.date()),
            'without_self': bool(record.mgr_without_self),
        }

    def _file_pdf(self):
        """Render ONE review (wkhtmltopdf on the server is unpatched: one
        document per call, LEARNING LN33) and file it in the vault.

        Same shape as `pb.hr.letter._make_pdf` / `_file_in_vault`, but no
        `pb.hr.letter` row is made (that model is readable by every lifecycle
        user). Sudo, because filing is the company's act.
        """
        self.ensure_one()
        record = self.sudo()
        if record.document_id:
            return record.document_id
        report = self.env.ref('pb_review_forms.action_report_review_form',
                              raise_if_not_found=False)
        if not report:
            return False
        content, _kind = report.sudo()._render_qweb_pdf(
            'pb_review_forms.report_review_form_document', res_ids=record.ids)
        filename = '%s - %s - %s.pdf' % (
            record.form_id.name or _('Review'),
            record.cycle_id.name or '', record.employee_id.name or '')
        filename = filename.replace('/', '-')
        Attachment = self.env['ir.attachment'].sudo()
        attachment = Attachment.create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(content),
            'res_model': 'pb.review.entry',
            'res_id': record.id,
            'mimetype': 'application/pdf',
        })
        record.write({'attachment_id': attachment.id})
        category = self.env.ref('pb_review_forms.cat_performance_review',
                                raise_if_not_found=False) \
            or self.env.ref('pb_employee_vault.cat_other',
                            raise_if_not_found=False)
        if not category:
            return False
        copy = attachment.copy({'res_model': 'pb.employee.document',
                                'res_id': 0})
        doc = self.env['pb.employee.document'].sudo().create({
            'employee_id': record.employee_id.id,
            'category_id': category.id,
            'name': '%s · %s' % (record.form_id.name or _('Review'),
                                 record.cycle_id.name or ''),
            'attachment_id': copy.id,
            'issue_date': fields.Date.context_today(self),
            'company_id': record.company_id.id or self.env.company.id,
        })
        copy.write({'res_id': doc.id})
        record.write({'document_id': doc.id})
        return doc


class PbReviewAnswer(models.Model):
    _name = 'pb.review.answer'
    _description = 'Review form answer'
    _order = 'entry_id, id'

    _one_per_side = models.Constraint(
        'unique(entry_id, line_id, author)',
        'That line already has an answer from that side.')

    entry_id = fields.Many2one('pb.review.entry', required=True, index=True,
                               ondelete='cascade')
    line_id = fields.Many2one('pb.review.form.line', required=True,
                              index=True, ondelete='cascade')
    author = fields.Selection([('employee', 'The employee'),
                               ('manager', 'The manager')],
                              required=True)
    rating = fields.Selection(
        [(key, label) for key, label in RATING_LABEL.items()],
        string='Rating')
    text = fields.Text(string='Answer')
    employee_id = fields.Many2one('hr.employee',
                                  related='entry_id.employee_id', store=True,
                                  index=True, readonly=True)
    company_id = fields.Many2one('res.company',
                                 related='entry_id.company_id', store=True,
                                 index=True, readonly=True)

    def _value(self):
        self.ensure_one()
        return self.rating or (self.text or '').strip()

    def _words(self):
        """The answer as somebody reads it: "Above", or what was written."""
        self.ensure_one()
        if self.rating:
            labels = dict(self._fields['rating']._description_selection(
                self.env))
            return labels.get(self.rating, self.rating)
        return self.text or ''
