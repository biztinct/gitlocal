# -*- coding: utf-8 -*-
"""LEARNING L0 — the Learning rail, the board's props, Overview and Remind.

Handover tests T4–T8. The first four classes read the source (registration,
command bar, board props) because those are contracts a screen depends on and
nothing at runtime would report a broken one: a lens registered into the
wrong registry simply is not there. The last two run the facades against the
database as real users.

Fixtures are named "DEMO" (ledger rule 9) and roll back with the transaction.
"""

import ast
import json
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from .test_assignments import AssignmentCase
from .test_training import _src

#: (key, sequence, label, icon, Component) — handover §3.2, in rail order.
RAIL = [
    ('overview', 10, 'Overview', 'layoutGrid', 'PbLearningOverview'),
    ('mine', 20, 'My learning', 'user', 'PbMyLearningLens'),
    ('courses', 30, 'Courses', 'bookOpen', 'PbTrainingBoard'),
    # LEARNING L3
    ('paths', 35, 'Paths', 'route', 'PbPathsLens'),
    ('assigned', 40, 'Assigned', 'userCheck', 'PbTrainingBoard'),
    # LEARNING L2: its own screen (Matrix · Rules · Day one · Comes round again)
    ('required', 50, 'Required', 'listChecks', 'PbRequiredLens'),
    ('tests', 60, 'Tests', 'fileCheck', 'PbTrainingTestsLens'),
    # LEARNING L1
    ('certificates', 65, 'Certificates', 'award', 'PbCertificatesLens'),
    ('claims', 70, 'Claims', 'receipt', 'PbTrainingBoard'),
    ('numbers', 80, 'Numbers', 'barChart', 'PbTrainingNumbers'),
]


def _lens_blocks(src):
    """{key: (body, sequence)} for every `lenses.add("key", {...}, {seq})`."""
    out = {}
    for m in re.finditer(r'lenses\.add\("(\w+)", \{(.*?)\n\}, \{ sequence: (\d+) \}\);',
                         src, re.S):
        out[m.group(1)] = (m.group(2), int(m.group(3)))
    return out


# =========================================================================
#  T4 — the eight lenses, and nothing left on Talent
# =========================================================================
@tagged('post_install', '-at_install')
class TestT4TheRail(TransactionCase):

    def test_t4_exactly_the_eight_lenses_in_order(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        blocks = _lens_blocks(src)
        self.assertEqual(list(blocks), [k for k, *_ in RAIL],
                         'the Learning rail is not the handover table')
        for key, seq, label, icon, comp in RAIL:
            body, got_seq = blocks[key]
            self.assertEqual(got_seq, seq, key)
            self.assertIn('key: "%s"' % key, body)
            self.assertIn('label: _t("%s")' % label, body)
            self.assertIn('icon: "%s"' % icon, body)
            self.assertIn('Component: %s' % comp, body)
        self.assertIn('const lenses = registry.category(LEARNING_LENSES);', src)

    def test_t4_the_gates_are_the_handover_gates(self):
        blocks = _lens_blocks(_src('static', 'src', 'js', 'training_palette.js'))
        self.assertIn('groups: ["base.group_user"]', blocks['mine'][0])
        for key in ('overview', 'courses', 'paths', 'assigned', 'required',
                    'tests', 'certificates', 'claims'):
            self.assertIn('groups: TRAINING_GATE,', blocks[key][0], key)
        self.assertIn('groups: TRAINING_GATE.concat(["base.group_system"])',
                      blocks['numbers'][0])

    def test_t4_the_board_lenses_carry_their_tabs(self):
        blocks = _lens_blocks(_src('static', 'src', 'js', 'training_palette.js'))
        # LEARNING L4: Courses owns Courses + Sessions and reads its arrival.
        self.assertIn('propsFromContext(ctx)', blocks['courses'][0])
        self.assertIn('const COURSE_TABS = ["courses", "sessions"];',
                      _src('static', 'src', 'js', 'training_palette.js'))
        # LEARNING L2: Required reads its arrival (tab, cell state, pack).
        self.assertIn('propsFromContext(ctx)', blocks['required'][0])
        self.assertIn('const REQUIRED_TABS = ["matrix", "rules", "day_one", "recurring"];',
                      _src('static', 'src', 'js', 'training_palette.js'))
        self.assertIn('props: { startTab: "claims", tabs: ["claims"] }',
                      blocks['claims'][0])
        # Assigned reads the arrival so Overview can open the requests.
        self.assertIn('propsFromContext(ctx)', blocks['assigned'][0])
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertIn('const ASSIGNED_TABS = ["assignments", "requests"];', src)

    def test_t4_nothing_registers_into_talent(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertNotIn('TALENT_LENSES', src)
        self.assertNotIn('@pb_talent_hub', src)

    def test_t4_the_manifest_depends_on_learning_not_talent(self):
        depends = ast.literal_eval(_src('__manifest__.py'))['depends']
        self.assertIn('pb_learning_hub', depends)
        self.assertNotIn('pb_talent_hub', depends)
        self.assertNotIn('pb_learn', depends)

    def test_t4_the_insights_lens_is_unchanged(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        m = re.search(r'registry\.category\(INSIGHTS_LENSES\)\.add\("training", '
                      r'\{(.*?)\}, \{ sequence: (\d+) \}\);', src, re.S)
        self.assertTrue(m)
        self.assertEqual(int(m.group(2)), 40)
        self.assertIn('label: _t("Training")', m.group(1))
        self.assertIn('Component: PbTrainingNumbers', m.group(1))
        self.assertIn('icon: "graduationCap"', m.group(1))

    def test_t4_every_new_asset_is_in_the_bundle(self):
        bundle = ast.literal_eval(_src('__manifest__.py'))['assets'][
            'web.assets_backend']
        for f in ('js/learning_overview.js', 'js/my_learning_lens.js',
                  'js/training_tests_lens.js', 'xml/learning_overview.xml',
                  'xml/my_learning_lens.xml', 'xml/training_tests_lens.xml',
                  'scss/learning_overview.scss', 'scss/my_learning_lens.scss',
                  'scss/training_tests_lens.scss'):
            self.assertIn('pb_training/static/src/' + f, bundle)

    def test_t4_the_new_templates_parse_and_keep_the_house_rules(self):
        from xml.etree import ElementTree
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        for f in ('learning_overview.xml', 'my_learning_lens.xml',
                  'training_tests_lens.xml', 'certificates_lens.xml'):
            body = _src('static', 'src', 'xml', f)
            ElementTree.fromstring(body)
            for comment in re.findall(r'<!--(.*?)-->', body, flags=re.S):
                self.assertNotIn('--', comment, f)
            for name in re.findall(r't-as="(\w+)"', body):
                self.assertNotIn(name, reserved, f)
        for f in ('learning_overview.js', 'my_learning_lens.js',
                  'training_tests_lens.js', 'certificates_lens.js'):
            self.assertFalse(re.search(r"""["']\s*\n\s*["']""",
                                       _src('static', 'src', 'js', f)), f)

    def test_t4_no_vendor_name_or_emoji_in_what_a_reader_sees(self):
        emoji = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
        for f in ('learning_overview.js', 'my_learning_lens.js',
                  'training_tests_lens.js', 'training_palette.js',
                  'certificates_lens.js'):
            for s in re.findall(r'_t\("([^"]*)"', _src('static', 'src', 'js', f)):
                self.assertNotIn('odoo', s.lower(), f)
                self.assertFalse(emoji.search(s), f)
        for f in ('learning_overview.xml', 'my_learning_lens.xml',
                  'training_tests_lens.xml', 'certificates_lens.xml'):
            body = re.sub(r'<!--.*?-->', '', _src('static', 'src', 'xml', f),
                          flags=re.S)
            self.assertNotIn('Odoo', body, f)
            self.assertFalse(emoji.search(body), f)

    def test_t4_every_new_word_has_its_vietnamese(self):
        po = _src('i18n', 'vi_VN.po')
        for word, vi in (('Overview', 'Tổng quan'), ('My learning', 'Của tôi'),
                         ('Assigned', 'Đã giao'), ('Required', 'Bắt buộc'),
                         ('Tests', 'Kiểm tra'), ('Claims', 'Hoàn tiền'),
                         ('Numbers', 'Số liệu'), ('Courses', 'Khóa học'),
                         ('Remind', 'Nhắc'), ('Next up', 'Việc tiếp theo'),
                         ('A reminder already went today.',
                          'Hôm nay đã gửi lời nhắc rồi.')):
            self.assertIn('msgid "%s"\nmsgstr "%s"' % (word, vi), po)


# =========================================================================
#  T5 — the command bar points at Learning
# =========================================================================
@tagged('post_install', '-at_install')
class TestT5CommandBar(TransactionCase):

    def _row(self, src, row_id):
        m = re.search(r'palette\.add\("%s", \{(.*?)\n\}, \{ sequence: (\d+) \}\);'
                      % row_id, src, re.S)
        self.assertTrue(m, 'no command-bar row %s' % row_id)
        return m.group(1), int(m.group(2))

    def test_t5_rows_3900_to_3960_open_the_learning_hub(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertIn('const HUB_XMLID = LEARNING_HUB_XMLID;', src)
        for row_id, seq, lens in (
                ('training_board', 3900, 'overview'),
                ('training_courses', 3910, 'courses'),
                ('training_tests', 3920, 'tests'),
                ('training_my', 3930, 'mine'),
                ('training_assignments', 3940, 'assigned'),
                ('training_schedules', 3950, 'required'),
                ('training_claims', 3960, 'claims')):
            body, got = self._row(src, row_id)
            self.assertEqual(got, seq, row_id)
            self.assertIn('action: { xmlid: HUB_XMLID, lens: "%s" }' % lens,
                          body, row_id)
            self.assertIn('sublabel: _t("Learning")', body, row_id)
            self.assertIn('"talent"', body, row_id)

    def test_t5_my_learning_row(self):
        body, _seq = self._row(_src('static', 'src', 'js',
                                    'training_palette.js'), 'training_my')
        self.assertIn('label: _t("My learning")', body)
        self.assertIn('"training"', body)
        self.assertNotIn('groups:', body, 'the row is everybody\'s')

    def test_t5_the_numbers_row_is_unchanged(self):
        body, seq = self._row(_src('static', 'src', 'js',
                                   'training_palette.js'), 'training_numbers')
        self.assertEqual(seq, 3970)
        self.assertIn('xmlid: "pb_training.action_pb_training_numbers"', body)
        self.assertIn('requires: "pb_training_numbers"', body)

    def test_t5_the_hub_xmlid_resolves(self):
        self.assertTrue(self.env.ref('pb_learning_hub.action_pb_learning_hub',
                                     raise_if_not_found=False))


# =========================================================================
#  T6 — the board's startTab / tabs props
# =========================================================================
@tagged('post_install', '-at_install')
class TestT6BoardProps(TransactionCase):

    def test_t6_the_props_are_declared(self):
        src = _src('static', 'src', 'js', 'training_board.js')
        self.assertIn('startTab: { type: String, optional: true },', src)
        self.assertIn('tabs: { type: Array, optional: true },', src)
        self.assertIn('embedded: { type: Boolean, optional: true },', src)
        self.assertIn('"*": true,', src)
        self.assertNotIn('static props = ["*"];', src)

    def test_t6_on_will_start_opens_the_start_tab_after_the_load(self):
        src = _src('static', 'src', 'js', 'training_board.js')
        block = src.split('onWillStart(async () => {', 1)[1].split('});', 1)[0]
        self.assertLess(block.index('await this.load();'),
                        block.index('await this.setTab(this.props.startTab);'))

    def test_t6_the_template_draws_only_the_owned_tabs(self):
        xml = _src('static', 'src', 'xml', 'training_board.xml')
        self.assertIn('t-if="!props.tabs or props.tabs.length > 1"', xml)
        for key in ('courses', 'assignments', 'requests', 'schedules', 'rules',
                    'claims'):
            self.assertIn('<button t-if="showTab(\'%s\')" class="pbtn-tab"' % key,
                          xml, key)
        src = _src('static', 'src', 'js', 'training_board.js')
        self.assertIn('return !this.props.tabs || this.props.tabs.includes(key);',
                      src)

    def test_t6_the_assigned_rows_offer_remind(self):
        xml = _src('static', 'src', 'xml', 'training_board.xml')
        self.assertIn('t-on-click="() => this.remindAssignment(asg.id)"', xml)
        src = _src('static', 'src', 'js', 'training_board.js')
        self.assertIn('await this.actA("remind", { assignment_id: id });', src)


# =========================================================================
#  T7 — the Overview facade
# =========================================================================
@tagged('post_install', '-at_install')
class TestT7Overview(AssignmentCase):
    """Run in a company of its own, so whatever the database already holds
    cannot change the sentence: every read is `company_id in env.companies`
    and the trainer belongs to this company only."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The sentences are asserted in English; this database's default
        # language may be Vietnamese (the translations are checked in T4).
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))
        cls.co = cls.env['res.company'].create({'name': 'DEMO L0 Learning Co'})
        cls.trainer = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Trainer L0',
                'login': 'demo.trainer.l0@example.com',
                'email': 'demo.trainer.l0@example.com',
                'company_id': cls.co.id,
                'company_ids': [(6, 0, [cls.co.id])],
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref('pb_training.group_training_manager').id])],
            })

    def _assign(self, channel, emp, days):
        return self.Assignment.create({
            'channel_id': channel.id, 'employee_id': emp.id,
            'company_id': self.co.id,
            'due_date': fields.Date.today() + timedelta(days=days)})

    def test_t7_a_plain_user_is_refused_in_data_not_an_error(self):
        data = self.env['pb.training'].with_user(self.u_one).overview()
        self.assertEqual(data, {'allowed': False})

    def test_t7_zero_state_is_one_calm_sentence(self):
        data = self.env['pb.training'].with_user(self.trainer).overview()
        self.assertTrue(data['allowed'])
        self.assertEqual(data['headline'], 'Nobody is on a course yet.')
        self.assertTrue(data['calm'])
        self.assertEqual([q['count'] for q in data['queue']], [0, 0, 0, 0])

    def test_t7_the_headline_counts_people_and_courses(self):
        for emp in (self.e_one, self.e_two):
            self._assign(self.course, emp, 10)
        self._assign(self.simple, self.e_three, -4)
        data = self.env['pb.training'].with_user(self.trainer).overview()
        self.assertEqual(data['people'], 3)
        self.assertEqual(data['courses'], 2)
        self.assertIn('3 people are on 2 courses.', data['headline'])
        self.assertIn('1 is past their date.', data['headline'])
        self.assertFalse(data['calm'])

    def test_t7_the_queue_is_the_boards_own_numbers(self):
        self._assign(self.course, self.e_one, -2)
        board = self.env['pb.training'].with_user(self.trainer)
        data = board.overview()
        kpis = board.get_assignments()['kpis']
        claims = board.get_claims()['kpis']
        queue = {q['key']: q for q in data['queue']}
        self.assertEqual(queue['late']['count'], kpis['overdue'])
        self.assertEqual(queue['requests']['count'], kpis['waiting'])
        self.assertEqual(queue['claims']['count'], claims['waiting'])
        self.assertEqual(queue['late']['count'], 1)
        self.assertEqual((queue['claims']['lens'], queue['requests']['lens'],
                          queue['requests']['tab'], queue['late']['lens']),
                         ('claims', 'assigned', 'requests', 'assigned'))
        self.assertEqual(data['month']['past'], 1)

    def test_t7_departments_are_capped_and_named(self):
        self._assign(self.course, self.e_one, 5)
        data = self.env['pb.training'].with_user(self.trainer).overview()
        self.assertLessEqual(len(data['departments']), 6)
        for dep in data['departments']:
            self.assertTrue(dep['name'])
            self.assertGreaterEqual(dep['people'], 1)


# =========================================================================
#  T8 — the one-tap Remind
# =========================================================================
@tagged('post_install', '-at_install')
class TestT8Remind(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The sentences are asserted in English; this database's default
        # language may be Vietnamese (the translations are checked in T4).
        cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.stranger = Users.create({
            'name': 'DEMO Stranger',
            'login': 'demo.stranger.l0@example.com',
            'email': 'demo.stranger.l0@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.trainer = Users.create({
            'name': 'DEMO HR Trainer L0',
            'login': 'demo.hrtrainer.l0@example.com',
            'email': 'demo.hrtrainer.l0@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_training.group_training_user').id])],
        })

    def _row(self, days=5, emp=None):
        return self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': (emp or self.e_one).id,
            'due_date': fields.Date.today() + timedelta(days=days),
        })

    def _manual_keys(self, row):
        return [k for k in json.loads(row.reminder_log or '{}')
                if k.startswith('manual:')]

    def test_t8_a_manager_reminds_a_direct_report(self):
        row = self._row()
        before = self._mails()
        res = self.env['pb.my.training'].with_user(self.boss_user).remind(row.id)
        self.assertIn('has been sent a reminder', res['message'])
        self.assertEqual(self._mails() - before, 1, 'exactly one email queued')
        self.assertEqual(len(self._manual_keys(row)), 1)

    def test_t8_a_late_course_sends_the_overdue_email(self):
        row = self._row(days=-3)
        self.env['pb.my.training'].with_user(self.boss_user).remind(row.id)
        mail = self.env['mail.mail'].sudo().search([], order='id desc', limit=1)
        overdue = self.env.ref('pb_training.mail_template_assignment_overdue')
        self.assertEqual(
            mail.subject, overdue._render_field('subject', row.ids)[row.id])
        self.assertEqual(mail.email_to, 'demo.tr.one@example.com')

    def test_t8_a_second_press_within_a_day_is_refused_in_words(self):
        row = self._row()
        me = self.env['pb.my.training'].with_user(self.boss_user)
        me.remind(row.id)
        with self.assertRaises(UserError) as caught:
            me.remind(row.id)
        self.assertIn('A reminder already went today.', str(caught.exception))
        self.assertEqual(len(self._manual_keys(row)), 1)

    def test_t8_yesterdays_stamp_does_not_block(self):
        row = self._row()
        old = fields.Datetime.now() - timedelta(hours=25)
        row._mark_sent('manual:' + fields.Datetime.to_string(old))
        self.env['pb.my.training'].with_user(self.boss_user).remind(row.id)
        self.assertEqual(len(self._manual_keys(row)), 2)

    def test_t8_a_stranger_is_refused(self):
        row = self._row()
        with self.assertRaises(AccessError) as caught:
            self.env['pb.my.training'].with_user(self.stranger).remind(row.id)
        self.assertIn('You can only remind people who report to you.',
                      str(caught.exception))
        self.assertEqual(self._manual_keys(row), [])

    def test_t8_the_hr_trainer_can_remind_anybody(self):
        row = self._row(emp=self.e_two)
        res = self.env['pb.training'].with_user(self.trainer).act(
            'remind', {'assignment_id': row.id})
        self.assertIn('has been sent a reminder', res['message'])
        self.assertEqual(len(self._manual_keys(row)), 1)

    def test_t8_the_morning_job_ledger_is_untouched(self):
        """The manual stamp never stands in for one of the job's own keys."""
        row = self._row(days=3)
        self.env['pb.my.training'].with_user(self.boss_user).remind(row.id)
        counts = {'employee': 0, 'manager': 0, 'hr': 0}
        self.Auto._chase_one(row, fields.Date.today(), 2, 5, counts)
        self.assertEqual(counts['employee'], 1, 'the d3 nudge still goes')

    def test_t8_a_finished_course_is_not_chased(self):
        row = self._row()
        row.sudo().write({'state': 'done'})
        with self.assertRaises(UserError):
            self.env['pb.my.training'].with_user(self.boss_user).remind(row.id)

    def test_t8_remind_is_on_the_allow_list(self):
        self.assertIn('remind', self.env['pb.training']._VERBS)
