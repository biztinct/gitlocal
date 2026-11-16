# -*- coding: utf-8 -*-
"""`pb.review.forms` — every screen's one door into review forms.

THREE READERS, THREE SETS OF METHODS, AND EACH SET PROVES WHO IS ASKING FIRST:

  * HR (`studio_*`) — the Review forms screen in Settings. Reading needs
    "Goals administrator"; writing, putting in use and sharing need "HR lead
    for goals" (the same rung that closes a goal year). Forms are read and
    written AS THE CALLER, so the access rules decide too.
  * The manager (`drawer_*`) — the review form inside the Goals drawer. The
    caller must be able to read the goal sheet (the Goals rules: their team,
    or HR), must not be the person reviewed, and writes only when
    `pb.goal.review._may_write_up()` says so.
  * The employee (`my_*`) — My Payobook. The review must be the caller's OWN
    (`employee_id.user_id == uid`); nothing else is accepted. The manager's
    part is not in the answer at all until it may be shown.

Everything after the check runs under sudo, because no employee login and no
line manager holds a right on the answers model.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .rf_common import (
    ACK_STATES, FORM_KIND, GROUP_MANAGER, GROUP_USER, MANAGER_STATES,
    MAX_QUESTIONS, MAX_SKILLS, QUESTION_TYPES, rating_options,
    REVEAL_MODES, SELF_STATES, WHO_ANSWERS, tidy,
)

_logger = logging.getLogger(__name__)

_FORM_FIELDS = ('name', 'intro', 'share_goals', 'share_skills',
                'share_questions', 'reveal', 'reveal_date')
_LINE_FIELDS = ('section', 'sequence', 'name', 'description', 'qtype',
                'choices', 'who', 'required')


def _labels(pairs):
    return [{'key': key, 'label': label} for key, label in pairs]


class PbReviewForms(models.AbstractModel):
    _name = 'pb.review.forms'
    _description = 'Review forms (screens)'

    # ================================================================ gates
    @api.model
    def _hr_reader(self):
        return self.env.user.has_group(GROUP_USER)

    @api.model
    def _hr_lead(self):
        return self.env.user.has_group(GROUP_MANAGER)

    @api.model
    def _require_reader(self):
        if not self._hr_reader():
            raise AccessError(_(
                "Review forms are set up by the HR team. Ask your HR "
                "administrator."))

    @api.model
    def _require_lead(self):
        if not self._hr_lead():
            raise AccessError(_(
                "Only the HR lead for goals can change a review form."))

    @api.model
    def _cycle(self, cycle_id):
        """A goal year the caller can read (access rules apply)."""
        cycle = self.env['pb.goal.cycle'].browse(int(cycle_id or 0)).exists()
        if not cycle:
            raise UserError(_("That goal year is not there any more."))
        cycle.check_access('read')
        return cycle

    @api.model
    def _form_of(self, cycle):
        return self.env['pb.review.form'].search(
            [('cycle_id', '=', cycle.id)], limit=1)

    @api.model
    def can_open(self):
        """The ⌘K / Settings probe: the server answers who may open it."""
        return bool(self._hr_reader())

    # =============================================================== studio
    @api.model
    def studio_load(self, cycle_id=None):
        """The Review forms screen: the goal years, and one year's form."""
        if not self._hr_reader():
            return {'ok': False, 'why': _(
                "Review forms are set up by the HR team.")}
        cycles = self.env['pb.goal.cycle'].search(
            [], order='date_start desc, id desc', limit=40)
        Form = self.env['pb.review.form']
        forms = {form.cycle_id.id: form for form in Form.search(
            [('cycle_id', 'in', cycles.ids)])}
        years = []
        for cycle in cycles:
            form = forms.get(cycle.id)
            years.append({
                'id': cycle.id,
                'name': cycle.name or '',
                'company': cycle.company_id.name or '',
                'dates': '%s – %s' % (self._day(cycle.date_start),
                                      self._day(cycle.date_end)),
                'closed': cycle.state == 'closed',
                'open': cycle.state == 'open',
                'has_form': bool(form),
                'state': form.state if form else '',
                'locked': bool(form and form.locked_at),
                'status': self._year_status(cycle, form),
            })
        chosen = 0
        if cycle_id and any(y['id'] == int(cycle_id) for y in years):
            chosen = int(cycle_id)
        elif years:
            # The year that is running first, then any not closed yet.
            running = [y for y in years if y['open']]
            not_closed = [y for y in years if not y['closed']]
            chosen = (running or not_closed or years)[0]['id']
        payload = {
            'ok': True,
            'may_edit': bool(self._hr_lead()),
            'years': years,
            'cycle_id': chosen,
            'form': None,
            'limits': {'skills': MAX_SKILLS, 'questions': MAX_QUESTIONS},
            'question_types': _labels(QUESTION_TYPES),
            'who_answers': _labels(WHO_ANSWERS),
            'reveal_modes': _labels(REVEAL_MODES),
            'ratings': rating_options(self.env),
            'has_values': 'pb.company.value' in self.env,
        }
        if chosen:
            payload['form'] = self._form_payload(self._cycle(chosen))
        return payload

    @api.model
    def _year_status(self, cycle, form):
        if not form:
            return _("No form")
        if form.state == 'draft':
            return _("Being written")
        if form.locked_at:
            return _("In use · locked")
        return _("In use")

    @api.model
    def _day(self, value):
        if not value:
            return ''
        from odoo.tools.misc import format_date
        return format_date(self.env, value)

    @api.model
    def _form_payload(self, cycle):
        form = self._form_of(cycle)
        base = {
            'cycle_id': cycle.id,
            'cycle': cycle.name or '',
            'cycle_closed': cycle.state == 'closed',
            'exists': bool(form),
        }
        if not form:
            return dict(base, id=0, state='draft', locked=False,
                        name=_('End-of-year review'), intro='',
                        share_goals=70, share_skills=30, share_questions=0,
                        reveal='manager_done', reveal_date='', skills=[],
                        questions=[], problems=[], progress={},
                        preview_url='')
        def line_row(line):
            return {
                'id': line.id,
                'section': line.section,
                'name': line.name or '',
                'description': line.description or '',
                'qtype': line.qtype or 'rating',
                'choices': line.choices or '',
                'who': line.who or 'both',
                'required': bool(line.required),
            }
        return dict(
            base,
            id=form.id,
            state=form.state,
            locked=bool(form.locked_at),
            locked_on=self._day(form.locked_at and form.locked_at.date()),
            locked_words=_(
                "Locked on %(day)s, when the first review was sent in. Only "
                "when the manager's part is shown can still change. For a "
                "new version, copy it to another year.",
                day=self._day(form.locked_at and form.locked_at.date()))
            if form.locked_at else '',
            published_on=self._day(form.published_at
                                   and form.published_at.date()),
            name=form.name or '',
            intro=form.intro or '',
            share_goals=form.share_goals,
            share_skills=form.share_skills,
            share_questions=form.share_questions,
            reveal=form.reveal,
            reveal_date=fields.Date.to_string(form.reveal_date) or '',
            skills=[line_row(line) for line in form._skills()],
            questions=[line_row(line) for line in form._questions()],
            problems=form._problems(),
            progress=self._progress(form),
            preview_url='/my/goals/review-form/%s/preview' % form.id,
        )

    @api.model
    def _progress(self, form):
        """How far the year's reviews have got — counts only, no contents."""
        Entry = self.env['pb.review.entry'].sudo()
        entries = Entry.search([('form_id', '=', form.id)])
        reviews = self.env['pb.goal.review'].sudo().search_count([
            ('cycle_id', '=', form.cycle_id.id), ('kind', '=', FORM_KIND)])
        finished = entries.filtered(lambda e: e.mgr_state == 'done')
        return {
            'reviews': reviews,
            'self_sent': len(entries.filtered(
                lambda e: e.self_state == 'sent')),
            'manager_done': len(finished),
            'shared': len(finished.filtered('released_at')),
            'waiting_to_show': len(finished.filtered(
                lambda e: not e.released_at)),
            'read': len(entries.filtered(lambda e: e.ack_state == 'read')),
            'talk': len(entries.filtered(lambda e: e.ack_state == 'talk')),
        }

    @api.model
    def studio_save(self, cycle_id, vals):
        """Save the form of one year: its settings and all its lines.

        Lines are matched by id: a known id is updated, a new row (no id) is
        made, a line no longer sent is removed. A locked form only takes a
        change of WHEN the manager's part is shown.
        """
        self._require_lead()
        cycle = self._cycle(cycle_id)
        vals = dict(vals or {})
        Form = self.env['pb.review.form']
        form = self._form_of(cycle)
        values = {key: vals[key] for key in _FORM_FIELDS if key in vals}
        if 'reveal_date' in values:
            values['reveal_date'] = values['reveal_date'] or False
        for key in ('share_goals', 'share_skills', 'share_questions'):
            if key in values:
                try:
                    values[key] = int(values[key] or 0)
                except (TypeError, ValueError):
                    raise UserError(_("A share is a number from 0 to 100."))
        if form and form.locked_at:
            values = {key: values[key] for key in ('reveal', 'reveal_date')
                      if key in values}
            if values:
                form.write(values)
            return self._form_payload(cycle)
        if cycle.state == 'closed':
            raise UserError(_("%(year)s is closed, so its review form cannot "
                              "change.", year=cycle.name or ''))
        if not form:
            form = Form.create(dict(values, cycle_id=cycle.id))
        elif values:
            form.write(values)
        if 'skills' in vals or 'questions' in vals:
            self._save_lines(form, vals.get('skills'), vals.get('questions'))
        return self._form_payload(cycle)

    @api.model
    def _save_lines(self, form, skills, questions):
        Line = self.env['pb.review.form.line']
        rows = []
        if skills is not None:
            if len(skills) > MAX_SKILLS:
                raise UserError(_("Keep it to %(n)s skills or values at "
                                  "most.", n=MAX_SKILLS))
            rows += [dict(row, section='skill') for row in skills]
        if questions is not None:
            if len(questions) > MAX_QUESTIONS:
                raise UserError(_("Keep it to %(n)s questions at most.",
                                  n=MAX_QUESTIONS))
            rows += [dict(row, section='question') for row in questions]
        sections = set()
        if skills is not None:
            sections.add('skill')
        if questions is not None:
            sections.add('question')
        current = {line.id: line for line in form.line_ids
                   if line.section in sections}
        kept = set()
        for index, row in enumerate(rows):
            data = {key: row[key] for key in _LINE_FIELDS if key in row}
            data['sequence'] = index + 1
            data['name'] = (data.get('name') or '').strip()
            if data.get('section') == 'skill':
                data.update({'qtype': 'rating', 'who': 'both',
                             'required': True})
            line_id = int(row.get('id') or 0)
            if line_id and line_id in current:
                current[line_id].write(data)
                kept.add(line_id)
            else:
                Line.create(dict(data, form_id=form.id))
        gone = [line for key, line in current.items() if key not in kept]
        if gone:
            Line.browse([line.id for line in gone]).unlink()
        return True

    @api.model
    def studio_publish(self, cycle_id):
        self._require_lead()
        cycle = self._cycle(cycle_id)
        form = self._form_of(cycle)
        if not form:
            raise UserError(_("Write the form first."))
        form.action_publish()
        return self._form_payload(cycle)

    @api.model
    def studio_unpublish(self, cycle_id):
        self._require_lead()
        cycle = self._cycle(cycle_id)
        form = self._form_of(cycle)
        if form:
            form.action_unpublish()
        return self._form_payload(cycle)

    @api.model
    def studio_copy(self, cycle_id, to_cycle_id):
        """A new version is next year's form: copy this one to another year."""
        self._require_lead()
        source = self._form_of(self._cycle(cycle_id))
        target = self._cycle(to_cycle_id)
        if not source:
            raise UserError(_("That year has no form to copy."))
        if target.id == source.cycle_id.id:
            raise UserError(_("Choose a different goal year."))
        if target.state == 'closed':
            raise UserError(_("%(year)s is closed.", year=target.name or ''))
        if self._form_of(target):
            raise UserError(_("%(year)s already has a review form.",
                              year=target.name or ''))
        form = self.env['pb.review.form'].create({
            'cycle_id': target.id,
            'name': source.name,
            'intro': source.intro,
            'share_goals': source.share_goals,
            'share_skills': source.share_skills,
            'share_questions': source.share_questions,
            'reveal': source.reveal,
        })
        for line in source.line_ids.sorted(lambda l: (l.section, l.sequence,
                                                      l.id)):
            self.env['pb.review.form.line'].create({
                key: line[key] for key in _LINE_FIELDS} | {'form_id': form.id})
        return {'ok': True, 'cycle_id': target.id,
                'sentence': _("Copied to %(year)s as a form being written.",
                              year=target.name or '')}

    @api.model
    def studio_values(self):
        """Company values from Praise, to add as rated lines (probe)."""
        self._require_reader()
        if 'pb.company.value' not in self.env:
            return []
        values = self.env['pb.company.value'].sudo().search(
            ['|', ('company_id', '=', False),
             ('company_id', 'in', self.env.companies.ids)], limit=MAX_SKILLS)
        return [{'name': value.name or '', 'description': value.motto or ''}
                for value in values]

    @api.model
    def studio_show_now(self, cycle_id):
        """Share every finished review of the year now."""
        self._require_lead()
        cycle = self._cycle(cycle_id)
        form = self._form_of(cycle)
        if not form or form.state != 'published':
            raise UserError(_("This year has no form in use."))
        today = fields.Date.context_today(self)
        if form.reveal == 'date' and (not form.reveal_date
                                      or form.reveal_date > today):
            form.write({'reveal_date': today})
        entries = self.env['pb.review.entry'].sudo().search([
            ('form_id', '=', form.id), ('mgr_state', '=', 'done'),
            ('released_at', '=', False)])
        shared = entries._release()
        payload = self._form_payload(cycle)
        payload['sentence'] = (
            _("1 finished review is shared now.") if len(shared) == 1
            else _("%(n)s finished reviews are shared now.", n=len(shared)))
        return payload

    # =============================================================== drawer
    @api.model
    def _review_for_reader(self, review_id):
        review = self.env['pb.goal.review'].browse(
            int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        try:
            review.sudo().set_id.with_env(self.env).check_access('read')
        except AccessError:
            raise AccessError(_("That review is not one you can see."))
        return review.sudo()

    @api.model
    def drawer_form(self, review_id):
        """The review form inside the Goals drawer, for the manager or HR."""
        review = self._review_for_reader(review_id)
        if review._rf_is_self():
            return {'ok': True, 'is_self': True,
                    'url': '/my/goals/review/%s' % review.id,
                    'sentence': _("This is your own review. You fill in "
                                  "your part on your own page.")}
        if not review._rf_applies():
            return {'ok': False, 'why': _(
                "This review does not use a review form.")}
        entry = review._rf_entry(create=True)
        if not entry:
            return {'ok': False, 'why': _(
                "This review does not use a review form.")}
        may_edit = bool(review.with_env(self.env)._may_write_up()
                        and entry.mgr_state != 'done'
                        and review.set_id.state != 'closed')
        return self._drawer_payload(entry, may_edit)

    @api.model
    def _drawer_payload(self, entry, may_edit):
        form = entry.form_id
        theirs = entry._answers('employee') if entry.self_state == 'sent' \
            else {}
        mine = entry._answers('manager')

        def row(line):
            mine_answer = mine.get(line.id)
            their_answer = theirs.get(line.id)
            return {
                'id': line.id,
                'name': line.name or '',
                'description': line.description or '',
                'kind': line._kind(),
                'choices': line._choice_list(),
                'asks_me': line._asks('manager'),
                'asks_them': line._asks('employee'),
                'required': bool(line.section == 'skill' or line.required),
                'mine': mine_answer._value() if mine_answer else '',
                'theirs': their_answer._words() if their_answer else '',
            }
        parts = [dict(p, value=tidy(p['value'])) for p in entry._parts()]
        sheet = entry.set_id
        return {
            'ok': True,
            'is_self': False,
            'entry_id': entry.id,
            'review_id': entry.review_id.id,
            'title': form.name or '',
            'may_edit': may_edit,
            'self_state': entry.self_state,
            'self_word': dict(SELF_STATES).get(entry.self_state, ''),
            'self_sent_on': self._day(entry.self_sent_at
                                      and entry.self_sent_at.date()),
            'mgr_state': entry.mgr_state,
            'mgr_word': dict(MANAGER_STATES).get(entry.mgr_state, ''),
            'done_on': self._day(entry.mgr_done_at
                                 and entry.mgr_done_at.date()),
            'without_self': bool(entry.mgr_without_self),
            'released': bool(entry.released_at),
            'shown_on': self._day(entry.released_at
                                  and entry.released_at.date()),
            'reveal_words': entry._shown_from_words('manager'),
            'ack_state': entry.ack_state,
            'ack_word': dict(ACK_STATES).get(entry.ack_state, ''),
            'skills': [row(line) for line in form._skills()],
            'questions': [row(line) for line in form._questions()],
            'comment': entry.overall_comment or '',
            'parts': parts,
            'overall': tidy(entry._overall()),
            'goals_scored': bool(sheet.scored),
            'ratings': rating_options(self.env),
        }

    @api.model
    def drawer_save(self, review_id, answers=None, comment=None, finish=False,
                    without_self=False):
        """The manager's answers, saved; with `finish`, the review is done."""
        review = self._review_for_reader(review_id)
        if review._rf_is_self():
            raise AccessError(_("Your own review is filled in on your own "
                                "page."))
        if not review.with_env(self.env)._may_write_up():
            raise AccessError(_(
                "A review is written up by the person's own manager or by "
                "the HR team."))
        entry = review._rf_entry(create=True) if review._rf_applies() \
            else None
        if not entry:
            raise UserError(_("This review does not use a review form."))
        if entry.mgr_state == 'done':
            raise UserError(_("This review is finished already."))
        if review.set_id.state == 'closed':
            raise UserError(_("This year has been closed, so the review "
                              "cannot change."))
        entry._store('manager', answers or {})
        values = {}
        if comment is not None:
            values['overall_comment'] = (comment or '').strip() or False
        if entry.mgr_state == 'todo':
            values['mgr_state'] = 'draft'
        if values:
            entry.write(values)
        if not finish:
            return dict(self._drawer_payload(entry, True),
                        sentence=_("Saved. Nothing is shown to them until "
                                   "you finish."))
        return self._finish(entry, review, bool(without_self))

    @api.model
    def _finish(self, entry, review, without_self):
        if entry.self_state != 'sent' and not without_self:
            raise UserError(_(
                "They have not sent their own view yet. Wait for it, or "
                "finish without it."))
        missing = entry._missing('manager')
        if missing:
            raise UserError(_("Still to answer: %(what)s.",
                              what=', '.join(missing[:4])))
        comment = (entry.overall_comment or '').strip()
        if not comment:
            raise UserError(_(
                "Write the overall comment. It is the part of the review "
                "people read first."))
        if entry.form_id.share_goals and not review.set_id.scored:
            raise UserError(_(
                "Score every key result first: the goals score is part of "
                "the overall result."))
        if entry._overall() is None:
            raise UserError(_("The overall result cannot be worked out yet. "
                              "Answer every rated line."))
        entry.write({
            'mgr_state': 'done',
            'mgr_done_at': fields.Datetime.now(),
            'mgr_done_by_id': self.env.uid,
            'mgr_without_self': entry.self_state != 'sent',
        })
        entry.form_id._lock_now()
        shown = entry._may_show()
        note = comment if shown else _(
            "The written review is kept on the review form until it is "
            "shared with them.")
        # The review row is written up through ITS OWN press, as the
        # manager, so its state, its frozen goals score and its chatter line
        # are exactly what they always were.
        review.with_env(self.env).action_review_done(note)
        if shown:
            entry._release()
        payload = self._drawer_payload(entry, False)
        payload['sentence'] = (
            _("Finished. They can read it now on their own page.")
            if shown else _("Finished. %(when)s",
                            when=entry._shown_from_words('manager')))
        return payload

    # ============================================================= employee
    @api.model
    def _own_review(self, review_id):
        """The caller's OWN review, or a refusal. The one employee gate."""
        review = self.env['pb.goal.review'].sudo().browse(
            int(review_id or 0)).exists()
        if not review or not review._rf_is_self():
            raise AccessError(_(
                "That one is not yours. If you think it should be, tell your "
                "HR team."))
        return review

    @api.model
    def my_form(self, review_id):
        review = self._own_review(review_id)
        if not review._rf_applies():
            return {'ok': False, 'why': _(
                "This review does not use a review form.")}
        entry = review._rf_entry(create=True)
        if not entry:
            return {'ok': False, 'why': _(
                "This review does not use a review form.")}
        if not entry.released_at and entry._may_show():
            entry._release()
        return self._my_payload(entry)

    @api.model
    def _my_payload(self, entry, preview=False):
        form = entry.form_id
        shown = bool(entry.released_at) and not preview
        mine = entry._answers('employee')
        theirs = entry._answers('manager') if shown else {}
        may_edit = (entry.self_state != 'sent' and entry.mgr_state != 'done'
                    and entry.set_id.state != 'closed') or preview

        def row(line):
            answer = mine.get(line.id)
            out = {
                'id': line.id,
                'name': line.name or '',
                'description': line.description or '',
                'kind': line._kind(),
                'choices': line._choice_list(),
                'asks_me': line._asks('employee'),
                'required': bool(line.section == 'skill' or line.required),
                'mine': answer._value() if answer else '',
                'mine_words': answer._words() if answer else '',
            }
            if shown and line._asks('manager'):
                manager_answer = theirs.get(line.id)
                out['manager_words'] = (manager_answer._words()
                                        if manager_answer else '')
            return out
        review = entry.review_id
        payload = {
            'ok': True,
            'preview': preview,
            'review_id': review.id,
            'title': form.name or '',
            'year': entry.cycle_id.name or '',
            'intro': form.intro or '',
            'manager': review.manager_employee_id.name or '',
            'self_state': entry.self_state,
            'self_sent_on': self._day(entry.self_sent_at
                                      and entry.self_sent_at.date()),
            'may_edit': may_edit,
            'mgr_done': entry.mgr_state == 'done',
            'shown': shown,
            'when_words': entry._shown_from_words(),
            'skills': [row(line) for line in form._skills()],
            'questions': [row(line) for line in form._questions()],
            'ratings': rating_options(self.env),
            'ack_state': entry.ack_state,
            'ack_on': self._day(entry.ack_at and entry.ack_at.date()),
            'has_pdf': bool(shown and entry.attachment_id),
            'ask_hr': 'pb.ask.hr.ticket' in self.env,
        }
        if shown:
            payload['result'] = {
                'comment': entry.overall_comment or '',
                'overall': tidy(entry._overall()),
                'parts': [dict(p, value=tidy(p['value']))
                          for p in entry._parts()],
                'done_on': self._day(entry.mgr_done_at
                                     and entry.mgr_done_at.date()),
                'without_self': bool(entry.mgr_without_self),
            }
        return payload

    @api.model
    def my_save(self, review_id, answers=None, send=False):
        review = self._own_review(review_id)
        entry = review._rf_entry(create=True) if review._rf_applies() \
            else None
        if not entry:
            raise UserError(_("This review does not use a review form."))
        if entry.self_state == 'sent':
            raise UserError(_("You have sent your own view already."))
        if entry.mgr_state == 'done':
            raise UserError(_("Your manager has finished this review "
                              "already."))
        if review.set_id.state == 'closed':
            raise UserError(_("This year has been closed."))
        entry._store('employee', answers or {})
        if entry.self_state == 'todo':
            entry.write({'self_state': 'draft'})
        if not send:
            return {'ok': True, 'sentence': _(
                "Saved. Your manager sees nothing until you send it.")}
        missing = entry._missing('employee')
        if missing:
            raise UserError(_("Still to answer: %(what)s.",
                              what=', '.join(missing[:4])))
        entry.write({'self_state': 'sent',
                     'self_sent_at': fields.Datetime.now()})
        entry.form_id._lock_now()
        return {'ok': True, 'sentence': _(
            "Sent to your manager. They write their part next.")}

    @api.model
    def my_ack(self, review_id, kind='read'):
        """"I have read this" / "I want to talk about it". Once each."""
        review = self._own_review(review_id)
        entry = review._rf_entry()
        if not entry or not entry.released_at:
            raise UserError(_("Your review is not ready to read yet."))
        if kind not in ('read', 'talk'):
            raise UserError(_("That is not something to do with a review."))
        ticket = False
        if entry.ack_state == 'none' or (kind == 'talk'
                                         and entry.ack_state == 'read'):
            entry.write({'ack_state': kind,
                         'ack_at': fields.Datetime.now()})
        if kind == 'talk' and 'pb.ask.hr.ticket' in self.env:
            ticket = self._ask_hr(entry)
        return {'ok': True, 'ticket_id': ticket.id if ticket else 0,
                'sentence': (_("Thank you. It is marked as read.")
                             if kind == 'read' else
                             _("Your HR team has been asked to talk with "
                               "you."))}

    @api.model
    def _ask_hr(self, entry):
        """One Ask HR question in the person's own name. It says only that
        they would like to talk; nothing from the review is copied into it,
        because every HR user can read Ask HR."""
        Ticket = self.env['pb.ask.hr.ticket'].sudo()
        try:
            with self.env.cr.savepoint():
                return Ticket._portal_create(
                    entry.employee_id, 'other',
                    _("I would like to talk about my review"),
                    _("About my %(form)s for %(year)s.",
                      form=entry.form_id.name or _('review'),
                      year=entry.cycle_id.name or ''))
        except Exception:               # noqa: BLE001
            _logger.warning('pb_review_forms: could not open the Ask HR '
                            'question for entry %s', entry.id, exc_info=True)
            return False

    @api.model
    def my_pdf(self, review_id):
        """The attachment of the caller's own shared review, or False."""
        review = self._own_review(review_id)
        entry = review._rf_entry()
        if not entry or not entry.released_at:
            return False
        if not entry.attachment_id:
            try:
                with self.env.cr.savepoint():
                    entry._file_pdf()
            except Exception:           # noqa: BLE001
                _logger.warning('pb_review_forms: could not make the PDF for '
                                'entry %s', entry.id, exc_info=True)
        return entry.attachment_id.sudo() if entry.attachment_id else False

    # =============================================================== preview
    @api.model
    def preview(self, form_id):
        """The employee's page for HR, filled with nothing and saving nothing.

        Built on an UNSAVED entry (`new()`), so no row is written and no
        review is touched.
        """
        self._require_reader()
        form = self.env['pb.review.form'].browse(int(form_id or 0)).exists()
        if not form:
            raise UserError(_("That review form is not there any more."))
        form.check_access('read')
        Entry = self.env['pb.review.entry'].sudo()
        entry = Entry.new({'form_id': form.id})
        payload = self._my_payload(entry, preview=True)
        payload.update({
            'year': form.cycle_id.name or '',
            'manager': _('Their manager'),
            'review_id': 0,
        })
        return payload

    # ======================================================= My Payobook
    @api.model
    def needs_rows(self, emp):
        """The "Needs you" rows for one employee (home hook)."""
        if not emp:
            return []
        reviews = self.env['pb.goal.review'].sudo().search([
            ('employee_id', '=', emp.id), ('kind', '=', FORM_KIND)],
            order='due_date desc', limit=4)
        rows = []
        for review in reviews:
            if not review._rf_applies():
                continue
            entry = review._rf_entry()
            url = '/my/goals/review/%s' % review.id
            year = review.cycle_id.name or ''
            if review.state == 'planned' and (
                    not entry or (entry.self_state != 'sent'
                                  and entry.mgr_state != 'done')):
                rows.append(('review_self', url, _("Give your own view "
                                                   "for your review"), year,
                             'clipboard-list', 'indigo'))
            elif entry and entry.released_at and entry.ack_state == 'none':
                rows.append(('review_read', url,
                             _("Your review is ready to read"), year,
                             'file-text', 'amber'))
        return rows
