from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestQuestionBank(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env['pb.training.question.bank']
        cls.questions = cls.env['survey.question']
        cls.test = cls.env['survey.survey'].create({'title': 'DEMO bank destination', 'survey_type': 'assessment',
            'scoring_type': 'scoring_with_answers', 'certification': True})
        cls.bank = cls.questions.create({'pb_bank': True, 'pb_bank_company_id': cls.env.company.id,
            'title': 'DEMO reusable safety question', 'question_type': 'simple_choice',
            'pb_bank_difficulty': 'basic', 'pb_bank_explanation': 'First check the area.',
            'suggested_answer_ids': [Command.create({'value': 'Inspect the area', 'is_correct': True, 'answer_score': 1}),
                                     Command.create({'value': 'Start immediately', 'is_correct': False, 'answer_score': 0})]})
        cls.bank.action_bank_approve()
        cls.course = cls.env['slide.channel'].create({'name': 'DEMO bank course', 'channel_type': 'training',
            'visibility': 'members', 'enroll': 'invite'})
        cls.lesson = cls.env['slide.slide'].create({'name': 'DEMO bank lesson', 'channel_id': cls.course.id, 'slide_category': 'quiz', 'is_published': False})

    def add(self, bank=None, **kw):
        return self.api.add_questions('survey.survey', self.test.id, (bank or self.bank).ids, **kw)

    def test_snapshot_is_independent_and_duplicate_blocked(self):
        self.add()
        copy = self.test.question_ids
        self.assertEqual(copy.pb_bank_source_id, self.bank)
        self.assertFalse(copy.pb_bank)
        self.assertNotEqual(copy.suggested_answer_ids, self.bank.suggested_answer_ids)
        before = copy.title
        self.bank.write({'title': 'DEMO Revised library wording'})
        self.assertEqual(copy.title, before)
        self.assertEqual(self.bank.pb_bank_state, 'draft')
        self.bank.action_bank_approve()
        with self.assertRaises(UserError):
            self.add()

    def test_draft_and_archived_are_not_reusable(self):
        for state in ('draft', 'archived'):
            self.bank.pb_bank_state = state
            with self.assertRaises(UserError):
                self.add()

    def test_target_access_and_model_allowlist(self):
        with self.assertRaises(UserError):
            self.api.add_questions('res.users', self.env.user.id, self.bank.ids)
        user = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'DEMO bank no access', 'login': 'bank-no-access@example.invalid', 'group_ids': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.api.with_user(user).preview(self.bank.id)

    def test_approving_incomplete_question_is_blocked(self):
        q = self.bank.copy({'pb_bank': True, 'pb_bank_company_id': self.env.company.id,
                            'suggested_answer_ids': [Command.clear()]})
        with self.assertRaises(UserError):
            q.action_bank_approve()

    def test_bad_scoring_is_blocked(self):
        self.bank.write({'suggested_answer_ids': [Command.update(self.bank.suggested_answer_ids[0].id, {'answer_score': 0})]})
        with self.assertRaises(UserError):
            self.bank.action_bank_approve()

    def test_direct_answer_edit_requires_review(self):
        revision = self.bank.pb_bank_revision
        self.bank.suggested_answer_ids[0].value = 'Review the area first'
        self.assertEqual(self.bank.pb_bank_state, 'draft')
        self.assertGreater(self.bank.pb_bank_revision, revision)

    def test_translations_are_preserved(self):
        language = self.env['res.lang'].with_context(active_test=False).search([('code', '=', 'vi_VN')], limit=1)
        language.active = True
        self.bank.with_context(lang='vi_VN').title = 'Kiểm tra khu vực trước'
        self.bank.action_bank_approve()
        self.add()
        self.assertEqual(self.test.question_ids.with_context(lang='vi_VN').title, 'Kiểm tra khu vực trước')

    def test_conditional_source_is_not_silently_flattened(self):
        self.bank.pb_bank_dependency_note = 'Review the original condition.'
        with self.assertRaises(UserError):
            self.add()

    def test_lesson_conversion_preserves_answers_and_feedback(self):
        self.api.add_questions('slide.slide', self.lesson.id, self.bank.ids)
        q = self.lesson.question_ids
        self.assertEqual(q.pb_bank_source_id, self.bank)
        self.assertEqual(q.answer_ids.mapped('is_correct'), [True, False])
        self.assertEqual(q.answer_ids[0].comment, self.bank.pb_bank_explanation)
        with self.assertRaises(UserError):
            self.api.add_questions('slide.slide', self.lesson.id, self.bank.ids)

    def test_lesson_rejects_unsupported_types(self):
        self.bank.write({'question_type': 'char_box'})
        self.bank.action_bank_approve()
        with self.assertRaises(UserError):
            self.api.add_questions('slide.slide', self.lesson.id, self.bank.ids)

    def test_lesson_keeps_context_and_rejects_rich_context(self):
        self.bank.description = '<p>Consider the weather before answering.</p>'
        self.bank.action_bank_approve()
        self.api.add_questions('slide.slide', self.lesson.id, self.bank.ids)
        self.assertIn('Consider the weather before answering.', self.lesson.question_ids.question)
        rich = self.bank.copy({'pb_bank': True, 'pb_bank_company_id': self.env.company.id,
                              'description': '<table><tr><td>Required data</td></tr></table>'})
        rich.action_bank_approve()
        with self.assertRaises(UserError):
            self.api.add_questions('slide.slide', self.lesson.id, rich.ids)

    def test_published_lesson_is_protected(self):
        self.lesson.is_published = True
        with self.assertRaises(UserError):
            self.api.add_questions('slide.slide', self.lesson.id, self.bank.ids)

    def test_attempted_test_is_protected(self):
        self.env['survey.user_input'].create({'survey_id': self.test.id, 'test_entry': False})
        with self.assertRaises(UserError):
            self.add()

    def test_explicit_refresh_only_on_unused_draft(self):
        self.add()
        q = self.test.question_ids
        self.bank.title = 'DEMO approved new wording'
        self.bank.action_bank_approve()
        self.api.refresh_copy('survey.question', q.id)
        self.assertEqual(q.title, self.bank.title)
        self.assertEqual(q.pb_bank_source_revision, self.bank.pb_bank_revision)
        self.env['survey.user_input'].create({'survey_id': self.test.id, 'test_entry': False})
        with self.assertRaises(UserError):
            self.api.refresh_copy('survey.question', q.id)

    def test_pool_preserves_existing_section_draw(self):
        page = self.questions.create({'survey_id': self.test.id, 'title': 'Existing', 'is_page': True, 'sequence': 1})
        for i in range(3):
            self.questions.create({'survey_id': self.test.id, 'title': 'Existing %s' % i, 'sequence': 2 + i, 'question_type': 'char_box'})
        self.add(pool={'draw': 1, 'name': 'Safety pool'})
        self.assertEqual(self.test.questions_selection, 'random')
        self.assertEqual(page.random_questions_count, 3)
        new_page = self.test.page_ids - page
        self.assertEqual(len(new_page.question_ids), 1)
        self.assertEqual(new_page.random_questions_count, 1)

    def test_balanced_pool_validates_available_counts(self):
        with self.assertRaises(UserError):
            self.add(pool={'balanced': True, 'basic': 2})
        self.add(pool={'balanced': True, 'basic': 1})
        self.assertEqual(self.test.page_ids.title, 'Basic')
        self.assertEqual(self.test.page_ids.random_questions_count, 1)

    def test_section_destination_and_unsectioned_order(self):
        page = self.questions.create({'survey_id': self.test.id, 'is_page': True, 'title': 'Topic', 'sequence': 10})
        self.add(section_id=page.id)
        self.assertEqual(self.test.question_ids.page_id, page)
        q2 = self.bank.copy({'pb_bank': True, 'pb_bank_company_id': self.env.company.id})
        q2.action_bank_approve()
        self.add(q2)
        self.assertFalse(self.test.question_ids.filtered(lambda q: q.pb_bank_source_id == q2).page_id)

    def test_first_use_shows_unapproved_library_without_allowing_unreviewed_reuse(self):
        self.bank.action_bank_draft()
        query = {'query': self.bank.pb_bank_code}
        result = self.api.browse_bank(query, 0, 'survey.survey', self.test.id)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['state'], 'draft')
        self.assertEqual(result['review_counts'], {'draft': 1})
        self.assertEqual(self.api.browse_bank(dict(query, state='approved'))['total'], 0)
        with self.assertRaises(UserError):
            self.add()
        preview = self.api.preview(self.bank.id)
        self.assertTrue(preview['can_edit'])
        self.assertFalse(preview['approval_problem'])
        self.bank.action_bank_approve()
        self.add()
        self.assertEqual(self.test.question_ids.pb_bank_source_id, self.bank)
        self.bank.action_bank_archive()
        self.assertEqual(self.api.browse_bank(query)['total'], 0)
        self.assertEqual(self.api.browse_bank(dict(query, state='archived'))['total'], 1)

    def test_preview_explains_why_imported_question_needs_changes(self):
        self.bank.suggested_answer_ids.filtered('is_correct').answer_score = 0
        self.assertTrue(self.api.preview(self.bank.id)['approval_problem'])
        with self.assertRaises(UserError):
            self.bank.action_bank_approve()
        self.assertEqual(self.bank.pb_bank_state, 'draft')

    def test_search_pagination_and_filters(self):
        self.bank.pb_bank_topic_id = self.env['pb.training.question.topic'].create({'name': 'DEMO Safety'})
        result = self.api.browse_bank({'query': self.bank.pb_bank_code, 'difficulty': 'basic'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['id'], self.bank.id)
        self.assertEqual(self.api.browse_bank({'query': self.bank.pb_bank_code}, 20)['rows'], [])
        self.add()
        self.assertEqual(self.api.browse_bank({'query': self.bank.pb_bank_code}, 0, 'survey.survey', self.test.id)['total'], 0)
        self.assertEqual(self.api.preview(self.bank.id)['answers'][0]['points'], 1)

    def test_company_and_source_restrictions(self):
        company = self.env['res.company'].create({'name': 'DEMO bank separate company'})
        trainer = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'DEMO bank trainer', 'login': 'bank-trainer@example.invalid', 'company_id': self.env.company.id, 'company_ids': [Command.set(self.env.company.ids)], 'group_ids': [Command.set([self.env.ref('pb_training.group_training_user').id])]})
        self.bank.pb_bank_company_id = company
        with self.assertRaises(AccessError):
            self.api.with_user(trainer).preview(self.bank.id)
        self.assertEqual(self.api.with_user(trainer).browse_bank({'query': self.bank.pb_bank_code})['review_counts'], {})
        self.bank.pb_bank_company_id = self.env.company
        self.bank.pb_bank_restrict_ids = self.env.user
        with self.assertRaises(AccessError):
            self.api.with_user(trainer).preview(self.bank.id)
        self.assertEqual(self.api.with_user(trainer).browse_bank({'query': self.bank.pb_bank_code})['review_counts'], {})
        with self.assertRaises(AccessError):
            self.bank.suggested_answer_ids.with_user(trainer).read(['value'])

    def test_trainer_can_create_bank_and_native_answers(self):
        trainer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO bank author', 'login': 'bank-author@example.invalid',
            'company_id': self.env.company.id, 'company_ids': [Command.set(self.env.company.ids)],
            'group_ids': [Command.set([self.env.ref('pb_training.group_training_user').id])]})
        bank = self.questions.with_user(trainer).create({'title': 'DEMO authored by trainer',
            'pb_bank': True, 'pb_bank_company_id': self.env.company.id, 'question_type': 'simple_choice',
            'suggested_answer_ids': [Command.create({'value': 'Yes', 'is_correct': True, 'answer_score': 1}),
                                     Command.create({'value': 'No', 'is_correct': False, 'answer_score': 0})]})
        bank.action_bank_approve()
        self.assertEqual(len(bank.suggested_answer_ids.read(['value'])), 2)
        self.api.with_user(trainer).add_questions('survey.survey', self.test.id, bank.ids)
        self.assertEqual(len(self.test.with_user(trainer).question_ids.suggested_answer_ids.read(['value'])), 2)

    def test_save_to_bank_does_not_move_original(self):
        q = self.questions.create({'title': 'DEMO Existing source', 'survey_id': self.test.id, 'question_type': 'char_box'})
        q.action_save_to_bank()
        bank = q.pb_bank_source_id
        self.assertTrue(bank.pb_bank)
        self.assertFalse(bank.survey_id)
        self.assertEqual(q.survey_id, self.test)
        self.assertEqual(bank.pb_bank_state, 'draft')
        q.action_save_to_bank()
        self.assertEqual(q.pb_bank_source_id, bank)

    def test_all_native_question_types_copy(self):
        for kind in ('char_box', 'text_box', 'numerical_box', 'date', 'datetime', 'scale', 'matrix', 'multiple_choice'):
            q = self.bank.copy({'pb_bank': True, 'pb_bank_company_id': self.env.company.id, 'question_type': kind,
                'answer_date': '2026-10-25', 'answer_datetime': '2026-10-25 10:00:00', 'answer_numerical_box': 5,
                'answer_score': 2, 'is_scored_question': kind in ('numerical_box', 'date', 'datetime', 'multiple_choice'), 'matrix_row_ids': [Command.create({'value': 'Row'})] if kind == 'matrix' else []})
            q.action_bank_approve()
            self.add(q)
            copied = self.test.question_ids.filtered(lambda r: r.pb_bank_source_id == q)
            self.assertEqual(copied.question_type, kind)
            self.assertEqual(copied.matrix_row_ids.mapped('value'), q.matrix_row_ids.mapped('value'))
