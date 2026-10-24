"""Reusable questions over the native survey editor; assessment copies are snapshots."""
from odoo import api, fields, models, Command, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression


class QuestionTopic(models.Model):
    _name = 'pb.training.question.topic'
    _description = 'Question topic'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char(required=True)
    parent_id = fields.Many2one('pb.training.question.topic', ondelete='restrict', index=True)
    parent_path = fields.Char(index=True)
    complete_name = fields.Char(compute='_compute_name', store=True, recursive=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_name(self):
        for rec in self:
            rec.complete_name = ' / '.join(filter(None, [rec.parent_id.complete_name, rec.name]))

    @api.constrains('parent_id')
    def _check_parent(self):
        if self._has_cycle():
            raise ValidationError(_('A topic cannot contain itself.'))


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    pb_bank = fields.Boolean('Library question', copy=False, index=True)
    pb_bank_company_id = fields.Many2one('res.company', string='Library company', copy=False, index=True, default=lambda self: self.env.company if self.env.context.get('default_pb_bank') else False)
    pb_bank_state = fields.Selection([('draft', 'Needs review'), ('approved', 'Approved'),
                                      ('archived', 'Archived')], string='Status', default='draft', copy=False, index=True)
    pb_bank_revision = fields.Integer('Library version', default=1, copy=False)
    pb_bank_source_id = fields.Many2one('survey.question', string='Library source', copy=False, ondelete='restrict', index=True)
    pb_bank_source_revision = fields.Integer('Copied version', copy=False)
    pb_bank_origin_id = fields.Many2one('survey.survey', string='Source test', copy=False, ondelete='set null', index=True)
    pb_bank_origin_slide_id = fields.Many2one('slide.slide', string='Source lesson', copy=False, ondelete='set null')
    pb_bank_restrict_ids = fields.Many2many('res.users', 'pb_bank_question_user_rel', string='Restricted to', copy=False)
    pb_bank_topic_id = fields.Many2one('pb.training.question.topic', string='Topic', index=True)
    pb_bank_skill_ids = fields.Many2many('hr.skill', 'pb_bank_question_skill_rel', string='Skills / objectives')
    pb_bank_tag_ids = fields.Many2many('slide.tag', 'pb_bank_question_tag_rel', string='Tags')
    pb_bank_difficulty = fields.Selection([('basic', 'Basic'), ('intermediate', 'Intermediate'),
                                           ('advanced', 'Advanced')], string='Difficulty', index=True)
    pb_bank_language_id = fields.Many2one('res.lang', string='Language',
        default=lambda self: self.env['res.lang'].search([('code', '=', self.env.lang)], limit=1), index=True)
    pb_bank_owner_id = fields.Many2one('res.users', string='Question owner', default=lambda self: self.env.user, index=True)
    pb_bank_explanation = fields.Text('Answer explanation', translate=True)
    pb_bank_dependency_note = fields.Char('Dependency review', copy=False,
        help='Imported conditional questions need rewriting as standalone questions. Clear this note only after that review.')
    pb_bank_code = fields.Char('Reference', compute='_compute_bank_code')
    pb_bank_usage = fields.Integer('Used in', compute='_compute_bank_usage')
    scoring_type = fields.Selection(related=False, compute='_compute_pb_scoring_type',
        selection=[('no_scoring', 'No scoring'), ('scoring_with_answers', 'Scoring with answers'),
                   ('scoring_without_answers', 'Scoring without answers')])

    @api.depends('pb_bank', 'survey_id.scoring_type')
    def _compute_pb_scoring_type(self):
        for q in self:
            q.scoring_type = 'scoring_with_answers' if q.pb_bank else q.survey_id.scoring_type

    def _compute_bank_code(self):
        for q in self:
            q.pb_bank_code = 'QB-%06d' % q.id if isinstance(q.id, int) else _('New question')

    def _compute_bank_usage(self):
        for q in self:
            q.pb_bank_usage = self.search_count([('pb_bank_source_id', '=', q.id)]) + self.env['slide.question'].search_count([('pb_bank_source_id', '=', q.id)])

    @api.constrains('pb_bank', 'survey_id', 'is_page', 'pb_bank_company_id')
    def _check_bank_independence(self):
        for q in self.filtered('pb_bank'):
            if q.survey_id or q.is_page or not q.pb_bank_company_id:
                raise ValidationError(_('Library questions must belong to a company and be independent of test sections.'))

    def _bank_problem(self, lesson=False, scored=False):
        self.ensure_one()
        if not self.title or not self.question_type or self.is_page:
            return _('Give this question a title and a type.')
        if self.pb_bank_dependency_note or self.triggering_answer_ids:
            return _('Review this conditional question as a standalone question first.')
        choices = self.suggested_answer_ids
        if self.question_type in ('simple_choice', 'multiple_choice', 'matrix') and len(choices) < 2:
            return _('Add at least two answer choices.')
        if self.question_type == 'matrix' and not self.matrix_row_ids:
            return _('Add matrix rows.')
        if self.question_type == 'simple_choice' and len(choices.filtered('is_correct')) > 1:
            return _('A single-choice question can have only one correct answer.')
        if lesson:
            if self.question_type not in ('simple_choice', 'multiple_choice'):
                return _('Lesson knowledge checks support choice questions only.')
            if any(not a.value or a.value_image for a in choices):
                return _('This lesson format requires text answers without answer images.')
            if not choices.filtered('is_correct') or not choices.filtered(lambda a: not a.is_correct):
                return _('Lesson questions need a correct and an incorrect answer.')
        if scored:
            if self.question_type in ('simple_choice', 'multiple_choice'):
                if not choices.filtered(lambda a: a.is_correct and a.answer_score > 0):
                    return _('Set a correct answer with positive points.')
                if any(a.is_correct != (a.answer_score > 0) for a in choices):
                    return _('Correct answers must have positive points; incorrect answers must have zero or negative points.')
            elif self.question_type not in ('numerical_box', 'date', 'datetime') or not self.is_scored_question or self.answer_score <= 0:
                return _('This question is not configured for automatic scoring.')
        return ''

    def action_bank_approve(self):
        self.env['pb.training']._require_write()
        for q in self:
            if not q.pb_bank:
                raise UserError(_('Only library questions can be approved.'))
            problem = q._bank_problem(scored=q.is_scored_question)
            if problem:
                raise UserError('%s: %s' % (q.title, problem))
        self.write({'pb_bank_state': 'approved'})

    @api.constrains('pb_bank_state')
    def _check_bank_approval(self):
        for q in self.filtered(lambda r: r.pb_bank and r.pb_bank_state == 'approved'):
            problem = q._bank_problem(scored=q.is_scored_question)
            if problem:
                raise ValidationError(problem)

    def action_bank_archive(self):
        self.filtered('pb_bank').write({'pb_bank_state': 'archived'})

    def action_bank_draft(self):
        self.filtered('pb_bank').write({'pb_bank_state': 'draft'})

    def write(self, vals):
        # Metadata changes don't alter assessment snapshots. Content edits reset approval.
        content = set(vals) - {n for n in self._fields if n.startswith('pb_bank_') and n != 'pb_bank_explanation'} - {'sequence'}
        bank = self.filtered('pb_bank') if content else self.browse()
        result = super().write(vals)
        for q in bank:
            super(SurveyQuestion, q).write({'pb_bank_revision': q.pb_bank_revision + 1, 'pb_bank_state': 'draft'})
        return result

    def action_save_to_bank(self):
        self.ensure_one()
        self.env['pb.training']._require_write()
        if self.pb_bank or self.is_page:
            raise UserError(_('Choose an assessment question to save to the library.'))
        if self.pb_bank_source_id:
            bank = self.pb_bank_source_id
        else:
            vals = dict(pb_bank=True, survey_id=False, is_page=False, triggering_answer_ids=[Command.clear()],
                pb_bank_company_id=self.env.company.id, pb_bank_origin_id=self.survey_id.id,
                pb_bank_owner_id=self.create_uid.id,
                pb_bank_restrict_ids=[Command.set(self.survey_id.restrict_user_ids.ids)],
                pb_bank_dependency_note=_('Rewrite the source question without its conditional dependencies.') if self.triggering_answer_ids else False)
            bank = self.copy(vals)
            # Native copy deliberately restores dependencies; library drafts carry a review note instead.
            bank.triggering_answer_ids = [Command.clear()]
            self.write({'pb_bank_source_id': bank.id, 'pb_bank_source_revision': bank.pb_bank_revision})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': bank.id,
                'views': [(self.env.ref('pb_training.question_bank_form').id, 'form')], 'target': 'current'}

    @api.model
    def _migrate_question_bank(self):
        # Idempotent metadata-only changes on source questions; no answers/results moved.
        for q in self.search([('pb_bank', '=', False), ('is_page', '=', False), ('survey_id', '!=', False), ('pb_bank_source_id', '=', False)]):
            q.with_company(q.survey_id.user_id.company_id or self.env.company).action_save_to_bank()
        for q in self.env['slide.question'].search([('pb_bank_source_id', '=', False)]):
            q.with_company(q.slide_id.channel_id.user_id.company_id or self.env.company).action_save_to_bank()


class SlideQuestion(models.Model):
    _inherit = 'slide.question'
    pb_bank_source_id = fields.Many2one('survey.question', string='Library source', copy=False, ondelete='restrict', index=True)
    pb_bank_source_revision = fields.Integer('Copied version', copy=False)

    def action_save_to_bank(self):
        self.ensure_one()
        self.env['pb.training']._require_write()
        bank = self.pb_bank_source_id
        if not bank:
            bank = self.env['survey.question'].create({
                'pb_bank': True, 'pb_bank_company_id': self.env.company.id,
                'pb_bank_origin_slide_id': self.slide_id.id, 'title': self.question,
                'question_type': 'multiple_choice' if len(self.answer_ids.filtered('is_correct')) > 1 else 'simple_choice',
                'pb_bank_explanation': '\n'.join(filter(None, self.answer_ids.mapped('comment'))),
                'suggested_answer_ids': [Command.create({'value': a.text_value, 'sequence': a.sequence,
                    'is_correct': a.is_correct, 'answer_score': 1 if a.is_correct else 0}) for a in self.answer_ids]})
            self.write({'pb_bank_source_id': bank.id, 'pb_bank_source_revision': bank.pb_bank_revision})
        return {'type': 'ir.actions.act_window', 'res_model': 'survey.question', 'res_id': bank.id,
                'views': [(self.env.ref('pb_training.question_bank_form').id, 'form')], 'target': 'current'}


class BankAnswerRevision(models.Model):
    _inherit = 'survey.question.answer'

    def _touch_library(self):
        for q in (self.question_id | self.matrix_question_id).filtered('pb_bank'):
            q.write({'pb_bank_state': 'draft', 'pb_bank_revision': q.pb_bank_revision + 1})

    def write(self, vals):
        result = super().write(vals)
        self._touch_library()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        answers = super().create(vals_list)
        answers._touch_library()
        return answers

    def unlink(self):
        self._touch_library()
        return super().unlink()


class QuestionBank(models.AbstractModel):
    _name = 'pb.training.question.bank'
    _description = 'Question library search and controlled reuse'

    def _gate(self):
        self.env['pb.training']._require_write()

    def _target(self, model, res_id, writing=False):
        if model not in ('survey.survey', 'slide.slide'):
            raise UserError(_('Choose a test or a lesson.'))
        rec = self.env[model].browse(int(res_id)).exists()
        if not rec:
            raise UserError(_('Save the test or lesson first.'))
        rec.check_access('write' if writing else 'read')
        return rec

    def _editable(self, target):
        if target._name == 'survey.survey':
            if self.env['survey.user_input'].sudo().search_count([('survey_id', '=', target.id), ('test_entry', '=', False)]) or target.slide_ids.filtered('is_published'):
                raise UserError(_('This assessment is already in use. Duplicate it before changing its question set.'))
        elif target.is_published or self.env['slide.slide.partner'].sudo().search_count([('slide_id', '=', target.id), ('quiz_attempts_count', '>', 0)]):
            raise UserError(_('This lesson is published or has quiz attempts. Create a new lesson version before changing questions.'))

    @api.model
    def browse_bank(self, filters=None, offset=0, model=False, res_id=False):
        self._gate()
        filters = filters or {}
        domain = [('pb_bank', '=', True), ('is_page', '=', False)]
        state = filters.get('state', 'approved')
        if state:
            domain.append(('pb_bank_state', '=', state))
        query = str(filters.get('query') or '').strip()[:200]
        if query:
            search = [('title', 'ilike', query)]
            if query.upper().startswith('QB-') and query[3:].isdigit():
                search = expression.OR([search, [('id', '=', int(query[3:]))]])
            domain = expression.AND([domain, search])
        for key, field in [('difficulty', 'pb_bank_difficulty'), ('type', 'question_type'),
                           ('topic', 'pb_bank_topic_id'), ('language', 'pb_bank_language_id'),
                           ('owner', 'pb_bank_owner_id'), ('source', 'pb_bank_origin_id'),
                           ('tag', 'pb_bank_tag_ids'), ('skill', 'pb_bank_skill_ids')]:
            if filters.get(key):
                value = filters[key] if key in ('difficulty', 'type') else int(filters[key])
                domain.append((field, 'child_of' if key == 'topic' else '=', value))
        used = []
        target = self._target(model, res_id) if model and res_id else False
        if target:
            used = (target.question_ids if model == 'slide.slide' else target.question_and_page_ids).pb_bank_source_id.ids
        if filters.get('unused', True) and used:
            domain.append(('id', 'not in', used))
        if model == 'slide.slide':
            domain += [('question_type', 'in', ['simple_choice', 'multiple_choice']), ('is_scored_question', '=', True), ('suggested_answer_ids.value_image', '=', False)]
        if filters.get('scored'):
            domain.append(('is_scored_question', '=', True))
        questions = self.env['survey.question']
        offset = max(0, int(offset))
        sort = {'recent': 'write_date desc, id desc', 'title': 'title, id', 'oldest': 'write_date, id'}.get(filters.get('sort'), 'write_date desc, id desc')
        records = questions.search(domain, limit=20, offset=offset, order=sort)
        return {'total': questions.search_count(domain), 'rows': [self._summary(q, q.id in used, model == 'slide.slide') for q in records],
                'sections': [{'id': p.id, 'name': p.title} for p in target.page_ids] if target and model == 'survey.survey' else []}

    def _summary(self, q, used=False, lesson=False):
        return {'id': q.id, 'code': q.pb_bank_code, 'title': q.title, 'type': q.question_type,
                'difficulty': q.pb_bank_difficulty or 'Unspecified', 'topic': q.pb_bank_topic_id.display_name or 'Uncategorised',
                'state': q.pb_bank_state, 'version': q.pb_bank_revision, 'used': used,
                'problem': q._bank_problem(lesson=lesson), 'scored': q.is_scored_question}

    @api.model
    def facets(self):
        self._gate()
        q = self.env['survey.question']
        domain = [('pb_bank', '=', True)]
        result = {}
        for key, field in [('topics', 'pb_bank_topic_id'), ('languages', 'pb_bank_language_id'), ('owners', 'pb_bank_owner_id'),
                           ('sources', 'pb_bank_origin_id'), ('tags', 'pb_bank_tag_ids'), ('skills', 'pb_bank_skill_ids')]:
            result[key] = [{'id': rec.id, 'name': rec.display_name} for rec, in q._read_group(domain, [field], [], limit=200) if rec]
        result['types'] = [{'id': k, 'name': v} for k, v in q._fields['question_type']._description_selection(self.env)]
        return result

    @api.model
    def preview(self, question_id):
        self._gate()
        q = self.env['survey.question'].browse(int(question_id)).exists()
        q.check_access('read')
        if not q or not q.pb_bank:
            raise UserError(_('That library question is unavailable.'))
        data = self._summary(q)
        data.update(description=q.description or '', explanation=q.pb_bank_explanation or '',
            answers=[{'id': a.id, 'text': a.value or '', 'image': bool(a.value_image), 'correct': a.is_correct, 'points': a.answer_score} for a in q.suggested_answer_ids],
            matrix_rows=q.matrix_row_ids.mapped('value'), score=q.answer_score,
            correct_answer=str(q['answer_'+q.question_type]) if q.question_type in ('numerical_box', 'date', 'datetime') and q.is_scored_question else '',
            scale='%s–%s' % (q.scale_min, q.scale_max) if q.question_type == 'scale' else '',
            usage=q.pb_bank_usage, source=q.pb_bank_origin_id.display_name or q.pb_bank_origin_slide_id.display_name or _('Created in library'))
        return data

    @api.model
    def add_questions(self, model, res_id, ids, section_id=False, pool=None):
        self._gate()
        target = self._target(model, res_id, writing=True)
        # Serialize concurrent additions to one destination before checking duplicates.
        self.env.cr.execute('SELECT id FROM %s WHERE id=%%s FOR UPDATE' % target._table, [target.id])
        target.invalidate_recordset()
        self._editable(target)
        ids = list(dict.fromkeys(int(i) for i in ids))
        if not ids or len(ids) > 200:
            raise UserError(_('Select between 1 and 200 questions at a time.'))
        bank = self.env['survey.question'].browse(ids).exists()
        bank.check_access('read')
        if len(bank) != len(ids) or any(not q.pb_bank or q.pb_bank_state != 'approved' for q in bank):
            raise UserError(_('Only approved, available library questions can be added.'))
        rows = target.question_ids if model == 'slide.slide' else target.question_and_page_ids
        if set(rows.pb_bank_source_id.ids) & set(ids):
            raise UserError(_('Some selected questions are already included. Refresh the picker to see the current set.'))
        for q in bank:
            problem = q._bank_problem(lesson=model == 'slide.slide', scored=bool(pool))
            if problem:
                raise UserError('%s: %s' % (q.title, problem))
        if model == 'slide.slide':
            if pool:
                raise UserError(_('Random pools are available for assessments only.'))
            seq = max(rows.mapped('sequence') or [0])
            for q in bank:
                seq += 10
                self.env['slide.question'].create({'slide_id': target.id, 'question': q.title, 'sequence': seq,
                    'pb_bank_source_id': q.id, 'pb_bank_source_revision': q.pb_bank_revision,
                    'answer_ids': [Command.create({'text_value': a.value, 'sequence': a.sequence, 'is_correct': a.is_correct,
                                                  'comment': q.pb_bank_explanation}) for a in q.suggested_answer_ids]})
        else:
            sections = target.page_ids
            page = self.env['survey.question'].browse(int(section_id)).exists() if section_id else self.env['survey.question']
            if page and page not in sections:
                raise UserError(_('Choose a section from this test.'))
            ordered = list(rows.sorted(lambda r: (r.sequence, r.id)))
            if pool:
                groups = []
                if pool.get('balanced'):
                    for difficulty in ('basic', 'intermediate', 'advanced'):
                        count = int(pool.get(difficulty) or 0)
                        subset = bank.filtered(lambda q: q.pb_bank_difficulty == difficulty)
                        if count < 0 or count > len(subset):
                            raise UserError(_('The requested difficulty mix exceeds the selected pool.'))
                        if count:
                            groups.append((difficulty.title(), count, subset))
                else:
                    count = int(pool.get('draw') or 0)
                    if count <= 0 or count > len(bank):
                        raise UserError(_('The draw count must be between 1 and the selected pool size.'))
                    groups = [(str(pool.get('name') or _('Question pool'))[:100], count, bank)]
                if sum(len(group[2]) for group in groups) != len(bank):
                    raise UserError(_('Every selected question must belong to a difficulty with a positive draw count.'))
                if not groups:
                    raise UserError(_('Choose at least one question per attempt.'))
                if target.questions_selection != 'random':
                    for p in sections:
                        p.random_questions_count = len(p.question_ids)
                # Loose questions remain mandatory; native random selection handles sections.
                target.questions_selection = 'random'
                for name, count, subset in groups:
                    p = self.env['survey.question'].create({'survey_id': target.id, 'title': name, 'is_page': True,
                        'sequence': (len(ordered) + 1) * 10, 'random_questions_count': count})
                    ordered.append(p)
                    ordered.extend(self._copy_to_test(q, target) for q in subset)
            else:
                insert = len(ordered)
                if page:
                    insert = ordered.index(page) + 1
                    while insert < len(ordered) and not ordered[insert].is_page:
                        insert += 1
                elif sections:
                    # Unsectioned questions precede sections; never accidentally join the last pool.
                    insert = next(i for i, r in enumerate(ordered) if r.is_page)
                ordered[insert:insert] = [self._copy_to_test(q, target) for q in bank]
            for i, q in enumerate(ordered, 1):
                q.sequence = i * 10
        return {'added': len(bank)}

    def _copy_to_test(self, q, target):
        vals = dict(survey_id=target.id, pb_bank=False, pb_bank_company_id=False,
                    pb_bank_source_id=q.id, pb_bank_source_revision=q.pb_bank_revision,
                    triggering_answer_ids=[Command.clear()])
        return q.copy(vals)

    @api.model
    def refresh_copy(self, model, question_id):
        self._gate()
        if model not in ('survey.question', 'slide.question'):
            raise UserError(_('Choose a copied question.'))
        q = self.env[model].browse(int(question_id)).exists()
        q.check_access('write')
        target = q.survey_id if model == 'survey.question' else q.slide_id
        self._editable(target)
        source = q.pb_bank_source_id
        source.check_access('read')
        if not source or source.pb_bank_state != 'approved':
            raise UserError(_('Approve the library version before updating this draft.'))
        problem = source._bank_problem(lesson=model == 'slide.question')
        if problem:
            raise UserError(problem)
        if model == 'survey.question':
            if q.triggering_answer_ids or self.env['survey.question'].search_count([('triggering_answer_ids', 'in', q.suggested_answer_ids.ids)]):
                raise UserError(_('This question participates in conditional logic. Review that logic before replacing its answers.'))
            vals = source.copy_data()[0]
            for key in list(vals):
                if key.startswith('pb_bank_') or key in ('pb_bank', 'survey_id', 'sequence', 'is_page'):
                    vals.pop(key)
            vals['suggested_answer_ids'] = [Command.clear()] + vals.get('suggested_answer_ids', [])
            vals['matrix_row_ids'] = [Command.clear()] + vals.get('matrix_row_ids', [])
        else:
            vals = {'question': source.title, 'answer_ids': [Command.clear()] + [Command.create({'text_value': a.value,
                'sequence': a.sequence, 'is_correct': a.is_correct, 'comment': source.pb_bank_explanation}) for a in source.suggested_answer_ids]}
        vals['pb_bank_source_revision'] = source.pb_bank_revision
        q.write(vals)
        if model == 'survey.question':
            source.copy_translations(q)
        return True


class TrainingBankDoor(models.AbstractModel):
    _inherit = 'pb.training'

    @api.model
    def open_questions(self):
        self._require_read()
        return self.env['ir.actions.actions']._for_xml_id('pb_training.action_question_bank')
