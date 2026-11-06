# -*- coding: utf-8 -*-
"""`pb.pay.rating` — how well somebody did, as far as a pay review is concerned.

THIS IS NOT A PERFORMANCE PRODUCT
---------------------------------
There is no goal, no cycle, no self-assessment and no calibration of the score
itself. A pay review needs one number per person, and this is where that number
is kept for that review and nowhere else. Companies that run performance
somewhere else paste their scores in; companies that do not, type them.

WHY A ROW PER REVIEW
--------------------
Because a score is a fact about a MOMENT. Keeping the latest score on the
employee means last year's review silently rewrites itself when somebody is
re-scored, and then nobody can explain a raise that was given on a number the
system no longer holds. A rating belongs to the review it was used in.

The exception is the LEGACY snapshot: the old planning module kept one rating
on the employee record, and when that column goes it would go with it. Those
values are copied here with `review_id` empty and `source = 'legacy'`, so a
company that had them can still see what they were.
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SOURCES = [
    ('entered', 'Typed in'),
    ('pasted', 'Pasted from a spreadsheet'),
    ('synced', 'Read from the connected system'),
    ('legacy', 'Carried over'),
]

#: A paste bigger than this is a mistake, not a review.
MAX_PASTE = 20000


class PbPayRating(models.Model):
    _name = 'pb.pay.rating'
    _description = 'How well somebody did, for a pay review'
    _order = 'review_id, employee_id'
    _rec_name = 'employee_id'

    review_id = fields.Many2one(
        'pb.pay.review', string='Review', ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, ondelete='cascade',
        index=True)
    person_id = fields.Integer(string='Person', index=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)
    rating = fields.Integer(string='Score', required=True)
    source = fields.Selection(SOURCES, string='Where it came from',
                              default='entered', required=True)
    note = fields.Text(string='Note')

    _rating_uniq = models.Constraint(
        'unique(review_id, employee_id)',
        'That person already has a score in this review.')

    # ---------------------------------------------------------------- paste
    @api.model
    def paste(self, review_id, text, dry_run=True):
        """Read "name or code, score" rows and say what would happen.

        Never writes on the first pass. A paste is somebody's spreadsheet and
        a spreadsheet always has a header row, a blank row and one person whose
        name is spelt differently — so the answer to a paste is a PREVIEW that
        names every row it could not place, and the write only happens when
        somebody has read it.
        """
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        levels = int(review.rating_scale or '4')
        lines = [line for line in (text or '').splitlines() if line.strip()]
        if len(lines) > MAX_PASTE:
            raise UserError(_(
                "That is %(count)s rows, which is more than one paste can "
                "hold. Paste it in a few goes.", count=len(lines)))

        people = {}
        for line in review.line_ids:
            employee = line.employee_id
            people.setdefault(self._key(employee.name), employee.id)
            for code in (getattr(employee, 'barcode', ''),
                         getattr(employee, 'registration_number', ''),
                         getattr(employee, 'work_email', '')):
                if code:
                    people.setdefault(self._key(code), employee.id)

        good, bad, seen = [], [], set()
        for number, line in enumerate(lines, 1):
            parts = re.split(r'[\t,;]', line)
            parts = [part.strip() for part in parts if part.strip()]
            if len(parts) < 2:
                bad.append({'row': number, 'text': line[:80],
                            'why': _("This row has no score on it.")})
                continue
            who, score = parts[0], parts[-1]
            employee_id = people.get(self._key(who))
            if not employee_id:
                bad.append({'row': number, 'text': line[:80],
                            'why': _("Nobody in this review is called that.")})
                continue
            try:
                value = int(float(score))
            except (TypeError, ValueError):
                bad.append({'row': number, 'text': line[:80],
                            'why': _("“%(score)s” is not a score.",
                                     score=score[:20])})
                continue
            if not 1 <= value <= levels:
                bad.append({'row': number, 'text': line[:80],
                            'why': _("A score runs from 1 to %(top)s.",
                                     top=levels)})
                continue
            if employee_id in seen:
                bad.append({'row': number, 'text': line[:80],
                            'why': _("This person is on the list twice.")})
                continue
            seen.add(employee_id)
            good.append({'employee_id': employee_id, 'rating': value,
                         'name': who})

        answer = {
            'good': len(good), 'bad': len(bad), 'rows': bad[:60],
            'sentence': self._sentence(len(good), len(bad)),
        }
        if dry_run or not good:
            return answer
        self._write_many(review, good, 'pasted')
        review.apply_guidance_to()
        answer['written'] = len(good)
        return answer

    @api.model
    def _sentence(self, good, bad):
        if good and not bad:
            return _("%(count)s scores read, all of them good.", count=good)
        if good and bad:
            return _("%(good)s scores read. %(bad)s rows could not be placed "
                     "and are listed below.", good=good, bad=bad)
        return _("Nothing on that list could be placed. The rows are below.")

    @staticmethod
    def _key(value):
        """A name matched the way a person means it, not the way it is typed."""
        text = (value or '').strip().lower()
        return re.sub(r'\s+', ' ', text)

    @api.model
    def _write_many(self, review, rows, source):
        Rating = self.sudo()
        existing = {rating.employee_id.id: rating
                    for rating in Rating.search(
                        [('review_id', '=', review.id)])}
        made = []
        for row in rows:
            found = existing.get(row['employee_id'])
            if found:
                found.write({'rating': row['rating'], 'source': source})
                continue
            made.append({'review_id': review.id,
                         'employee_id': row['employee_id'],
                         'rating': row['rating'], 'source': source})
        if made:
            Rating.create(made)
        return len(rows)

    @api.model
    def set_one(self, review_id, employee_id, rating):
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        levels = int(review.rating_scale or '4')
        value = int(rating or 0)
        if value and not 1 <= value <= levels:
            raise UserError(_("A score runs from 1 to %(top)s.", top=levels))
        self._write_many(review, [{'employee_id': int(employee_id),
                                   'rating': value}], 'entered')
        line = review.line_ids.filtered(
            lambda l: l.employee_id.id == int(employee_id))
        review.apply_guidance_to(line)
        return True

    # ------------------------------------------------------------- the sync
    @api.model
    def sync_from_connected_system(self, review_id):
        """Read scores from the connected system, where one carries them.

        This is deliberately a PROBE and not a dependency: a company with no
        connected system asks the question and is told plainly that there is
        nothing to read, rather than being offered a button that fails.
        """
        review = self.env['pb.pay.review'].browse(int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        field = None
        employee_fields = self.env['hr.employee']._fields
        for name in ('pb_performance_rating', 'wfp_performance_rating'):
            if name in employee_fields:
                field = name
                break
        if not field:
            return {'read': 0, 'sentence': _(
                "Nothing connected to this system carries a score, so there "
                "is nothing to read in. Type or paste them instead.")}
        rows = []
        for line in review.line_ids:
            raw = line.employee_id.sudo()[field]
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value:
                rows.append({'employee_id': line.employee_id.id,
                             'rating': value})
        if rows:
            self._write_many(review, rows, 'synced')
            review.apply_guidance_to()
        return {'read': len(rows),
                'sentence': _("%(count)s scores read in.", count=len(rows))
                if rows else _("Nobody in this review has a score on record.")}

    # --------------------------------------------------------- the migration
    @api.model
    def migrate_legacy(self):
        """Keep the old per-employee rating before its column disappears.

        Written with no review, because it belonged to no review — it was the
        latest score somebody had typed on the employee record. It is kept so
        the number is not simply lost, and it seeds the new field this module
        puts on the employee so the two screens that used to write the old one
        have somewhere to write.
        """
        report = {'found': 0, 'kept': 0, 'seeded': 0}
        Employee = self.env['hr.employee'].sudo()
        if 'wfp_performance_rating' not in Employee._fields:
            return report
        people = Employee.with_context(active_test=False).search(
            [('wfp_performance_rating', '!=', False)])
        report['found'] = len(people)
        if not people:
            return report
        existing = set(self.sudo().search(
            [('review_id', '=', False), ('source', '=', 'legacy')]).mapped(
                lambda r: r.employee_id.id))
        made = []
        for employee in people:
            try:
                value = int(employee.wfp_performance_rating)
            except (TypeError, ValueError):
                continue
            if 'pb_performance_rating' in Employee._fields \
                    and not employee.pb_performance_rating:
                employee.write({'pb_performance_rating': str(value)})
                report['seeded'] += 1
            if employee.id in existing:
                continue
            made.append({
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'rating': value, 'source': 'legacy',
                'note': 'Carried over from the old planning screens.',
            })
        if made:
            self.sudo().create(made)
            report['kept'] = len(made)
        return report


class HrEmployeePayRating(models.Model):
    """The one score that lives on the person rather than on a review.

    It is the LATEST score anybody recorded, and the only thing it is for is
    to fill a new review in before somebody has scored its people. The score a
    raise was actually given on is always the one on the review's own row.

    It exists because two screens in this product — the improvement plan and
    the probation review — record an outcome against a person, and the column
    they used to write belonged to a module that is being retired.

    THIS FIELD IS SHARED WITH `pb_demo`, ON PURPOSE AND WITH ITS EYES OPEN.
    The demo generator has always written `hr.employee.pb_performance_rating`
    with exactly this meaning and exactly these five values, and 4,502 people
    on the demo company carry one. Declaring a SECOND field for the same fact
    would have left the demo's scores stranded and a pay review opening
    "nobody has been scored" on a database full of scores. So the definition
    below is deliberately IDENTICAL in every attribute that the platform
    merges — the same selection keys, no `groups` restriction, no tracking —
    because two modules defining one field is only safe while neither of them
    narrows it, and load order decides which `string` wins. The labels differ
    in wording alone.
    """
    _inherit = 'hr.employee'

    pb_performance_rating = fields.Selection([
        ('1', '1 - Needs Improvement'),
        ('2', '2 - Developing'),
        ('3', '3 - Meets Expectations'),
        ('4', '4 - Exceeds Expectations'),
        ('5', '5 - Outstanding'),
    ], string='Performance Rating',
        help='The most recent score recorded for this person. A pay review '
             'copies it in as a starting point and then keeps its own.')
