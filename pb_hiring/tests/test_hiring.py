# -*- coding: utf-8 -*-
"""RIZE W2 A1 — the rails that must not quietly stop working.

The live Chrome run is what proves the board mounts; these are the floor.
Every one of them is written against a failure this module could have and
that nothing at runtime would report:

  * a budget answer that GUESSES rather than admitting it does not know
    would send a request past Finance on a number built out of nothing —
    and the screen would look perfectly normal while doing it;
  * a request anybody with a login could create is a hiring pipeline with
    no author;
  * a referral whose state is stored rather than read is wrong within a
    week, and nobody would ever notice because the person it is wrong for
    is not an employee;
  * a palette row pointing at an xmlid that does not resolve renders and
    opens nothing;
  * two adjacent string literals in a JS file blank the entire backend
    asset bundle for every user, with a clean server log.
"""

import re
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


def _src(*parts):
    path = get_module_path('pb_hiring')
    with open(path + '/' + '/'.join(parts), encoding='utf-8') as fh:
        return fh.read()


class HiringCase(TransactionCase):
    """One department, one head, one manager above them."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        Employee = self.env['hr.employee']
        self.boss = Employee.create({
            'name': 'RIZE W2 Test Boss',
            'company_id': self.company.id,
        })
        self.head = Employee.create({
            'name': 'RIZE W2 Test Head',
            'company_id': self.company.id,
            'parent_id': self.boss.id,
        })
        self.dept = self.env['hr.department'].create({
            'name': 'RIZE W2 Test Function',
            'company_id': self.company.id,
            'manager_id': self.head.id,
        })

    def _requisition(self, **extra):
        vals = {
            'title': 'RIZE W2 Test Role',
            'department_id': self.dept.id,
            'company_id': self.company.id,
            'requested_by_id': self.head.id,
            'headcount': 2,
            'budget_cost': 100.0,
            'requirements': 'Able to do the job.',
        }
        vals.update(extra)
        return self.env['pb.hiring.requisition'].sudo().create(vals)

    def _budget(self, forecast, actual=0.0, months=1):
        rows = self.env['pb.budget.line'].sudo()
        first = date(fields.Date.context_today(self.env.user).year, 1, 1)
        for i in range(months):
            rows |= rows.create({
                'company_id': self.company.id,
                'department_id': self.dept.id,
                'period_month': first.replace(month=i + 1),
                'forecast_cost': forecast,
                'actual_cost': actual,
                'pb_currency_id': self.company.currency_id.id,
            })
        return rows


# =========================================================================
#  The budget answer
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheBudgetAnswer(HiringCase):

    def test_no_budget_rows_means_nobody_has_said(self):
        """Not within, not over: unknown. A department with nothing budgeted
        is not a department that has overspent (R23/R88 — a number built on a
        missing row is a lie rather than an estimate)."""
        req = self._requisition(budget_cost=1000.0)
        req._refresh_budget()
        self.assertEqual(req.budget_status, 'unknown')
        self.assertIn(self.dept.name, req.budget_note)

    def test_within_budget_is_the_sum_of_the_rows(self):
        self._budget(forecast=500.0, actual=100.0, months=2)
        req = self._requisition(budget_cost=300.0)
        req._refresh_budget()
        self.assertEqual(req.budget_status, 'within')
        self.assertAlmostEqual(req.budget_remaining, 800.0, places=2)

    def test_over_budget_says_by_how_much(self):
        self._budget(forecast=500.0, actual=450.0)
        req = self._requisition(budget_cost=300.0)
        req._refresh_budget()
        self.assertEqual(req.budget_status, 'over')
        self.assertAlmostEqual(req.budget_over_by, 250.0, places=2)

    def test_a_different_currency_is_never_converted(self):
        """A rate that is missing reads as 1.0 and turns twenty-six thousand
        dong into a dollar without a word (R23). The honest answer is that
        nobody can say."""
        other = self.env['res.currency'].search(
            [('id', '!=', self.company.currency_id.id)], limit=1)
        if not other:
            self.skipTest('this database has only one currency')
        self._budget(forecast=500.0)
        req = self._requisition(budget_cost=10.0, currency_id=other.id)
        req._refresh_budget()
        self.assertEqual(req.budget_status, 'unknown')
        self.assertIn(other.name, req.budget_note)

    def test_the_budget_is_read_again_when_the_cost_changes(self):
        self._budget(forecast=500.0)
        req = self._requisition(budget_cost=100.0)
        self.assertEqual(req.budget_status, 'within')
        req.write({'budget_cost': 900.0})
        self.assertEqual(req.budget_status, 'over')


# =========================================================================
#  Who may ask for a person
# =========================================================================
@tagged('post_install', '-at_install')
class TestWhoMayAsk(HiringCase):

    def _plain_user(self):
        return self.env['res.users'].create({
            'name': 'RIZE W2 Test Plain',
            'login': 'rize.w2.plain.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)],
            'company_id': self.company.id,
        })

    def test_a_plain_user_cannot_raise_one(self):
        """The ACCESS LIST cannot ask this question — every internal user
        needs create rights because a department head holds no hiring group
        by definition — so `create` is the boundary."""
        user = self._plain_user()
        self.assertFalse(
            self.env['pb.hiring.requisition'].with_user(user)._can_raise())
        with self.assertRaises(AccessError):
            self.env['pb.hiring.requisition'].with_user(user).create({
                'title': 'RIZE W2 Test Sneaky',
                'department_id': self.dept.id,
                'requested_by_id': self.head.id,
            })

    def test_a_department_head_can(self):
        user = self._plain_user()
        self.head.write({'user_id': user.id})
        self.assertTrue(
            self.env['pb.hiring.requisition'].with_user(user)._can_raise())

    def test_a_hiring_manager_can_even_without_a_department(self):
        user = self._plain_user()
        user.write({'group_ids': [
            (4, self.env.ref('pb_hiring.group_hiring_manager').id)]})
        self.assertTrue(
            self.env['pb.hiring.requisition'].with_user(user)._can_raise())


# =========================================================================
#  What happens when everybody has said yes
# =========================================================================
@tagged('post_install', '-at_install')
class TestOpening(HiringCase):

    def test_opening_makes_the_job_once(self):
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        self.assertTrue(req.job_id)
        job_id = req.job_id.id
        req._on_opened()
        self.assertEqual(req.job_id.id, job_id)

    def test_a_quiet_replacement_is_never_open_to_referrals(self):
        req = self._requisition(role_type='sensitive_replacement')
        req._chain_state_write('open')
        req._on_opened()
        self.assertFalse(req.referral_open)

    def test_an_ordinary_role_is(self):
        req = self._requisition(role_type='new_role')
        req._chain_state_write('open')
        req._on_opened()
        self.assertTrue(req.referral_open)

    def test_the_country_rule_names_the_recruiter(self):
        user = self.env['res.users'].create({
            'name': 'RIZE W2 Test Recruiter',
            'login': 'rize.w2.rec.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)],
            'company_id': self.company.id,
        })
        self.env['pb.hiring.country.rule'].sudo().create({
            'company_id': self.company.id,
            'recruiter_id': user.id,
        })
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        self.assertEqual(req.recruiter_id.id, user.id)

    def test_no_rule_still_opens_the_role(self):
        """Absence is an answer, and it is never an error (R120)."""
        self.env['pb.hiring.country.rule'].sudo().search(
            [('company_id', '=', self.company.id)]).unlink()
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        self.assertFalse(req.recruiter_id)
        self.assertEqual(req.state, 'open')

    def test_only_one_fallback_rule_per_company(self):
        """Postgres keeps NULLs distinct, so the unique constraint does not
        stop a second "everywhere else" row on its own."""
        Rule = self.env['pb.hiring.country.rule'].sudo()
        Rule.search([('company_id', '=', self.company.id)]).unlink()
        user = self.env.user
        Rule.create({'company_id': self.company.id, 'recruiter_id': user.id})
        with self.assertRaises(ValidationError):
            Rule.create({'company_id': self.company.id,
                         'recruiter_id': user.id})


# =========================================================================
#  The advert
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheAdvert(HiringCase):

    def test_versions_number_themselves(self):
        req = self._requisition()
        Jd = self.env['pb.hiring.jd'].sudo()
        first = Jd.create({'requisition_id': req.id, 'body': '<p>One</p>'})
        second = Jd.create({'requisition_id': req.id, 'body': '<p>Two</p>'})
        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)

    def test_agreeing_one_makes_it_the_current_one(self):
        req = self._requisition()
        Jd = self.env['pb.hiring.jd'].sudo()
        first = Jd.create({'requisition_id': req.id, 'body': '<p>One</p>'})
        first._chain_state_write('approved')
        first._become_current()
        self.assertEqual(req.jd_current_id.id, first.id)
        second = Jd.create({'requisition_id': req.id, 'body': '<p>Two</p>'})
        second._chain_state_write('approved')
        second._become_current()
        self.assertEqual(req.jd_current_id.id, second.id)
        # The older one stays readable — that is the whole point of a version
        self.assertTrue(first.exists())
        self.assertEqual(first.body, '<p>One</p>')

    def test_only_one_version_can_be_out_for_agreement(self):
        req = self._requisition()
        Jd = self.env['pb.hiring.jd'].sudo()
        first = Jd.create({'requisition_id': req.id, 'body': '<p>One</p>'})
        first._chain_state_write('submitted')
        second = Jd.create({'requisition_id': req.id, 'body': '<p>Two</p>'})
        with self.assertRaises(ValidationError):
            second._chain_state_write('submitted')

    def test_an_empty_advert_cannot_be_sent(self):
        req = self._requisition()
        jd = self.env['pb.hiring.jd'].sudo().create(
            {'requisition_id': req.id, 'body': ''})
        with self.assertRaises(UserError):
            jd.action_submit()

    def test_the_words_are_in_the_stamp(self):
        """A consumer whose OWN values are what somebody is signing for
        stamps them (ledger AM32's carve-out). Editing the advert after it
        has gone out has to send it round again."""
        req = self._requisition()
        jd = self.env['pb.hiring.jd'].sudo().create(
            {'requisition_id': req.id, 'body': '<p>One</p>'})
        stamp = jd._chain_revision_values()
        self.assertIn('body', stamp)
        self.assertNotIn('write_date', stamp)


# =========================================================================
#  Referrals
# =========================================================================
@tagged('post_install', '-at_install')
class TestReferrals(HiringCase):

    def _open_role(self):
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        return req

    def test_a_referral_becomes_a_real_candidate_tagged_referral(self):
        req = self._open_role()
        referral = self.env['pb.hiring.referral'].refer(
            req.id, self.boss.id,
            {'name': 'RIZE W2 Test Candidate',
             'email': 'rize.w2.candidate@example.com',
             'phone': '', 'note': 'Worked with them.'})
        applicant = referral.applicant_id
        self.assertTrue(applicant)
        self.assertEqual(applicant.job_id.id, req.job_id.id)
        self.assertEqual((applicant.source_id.name or '').lower(), 'referral')
        self.assertEqual(applicant.pb_requisition_id.id, req.id)

    def test_the_state_is_read_from_the_candidate_never_typed(self):
        req = self._open_role()
        referral = self.env['pb.hiring.referral'].refer(
            req.id, self.boss.id,
            {'name': 'RIZE W2 Test Candidate 2',
             'email': 'rize.w2.candidate2@example.com'})
        self.assertEqual(referral.state, 'received')
        referral.applicant_id.sudo().write({'active': False})
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(referral.state, 'not_this_time')

    def test_a_role_that_is_not_open_refuses(self):
        req = self._requisition()
        with self.assertRaises(ValueError):
            self.env['pb.hiring.referral'].refer(
                req.id, self.boss.id, {'name': 'RIZE W2 Test Nope'})

    def test_a_quiet_replacement_refuses(self):
        req = self._requisition(role_type='sensitive_replacement')
        req._chain_state_write('open')
        req._on_opened()
        with self.assertRaises(ValueError):
            self.env['pb.hiring.referral'].refer(
                req.id, self.boss.id, {'name': 'RIZE W2 Test Nope 2'})


# =========================================================================
#  Publishing
# =========================================================================
@tagged('post_install', '-at_install')
class TestPublishing(HiringCase):

    def test_publishing_needs_an_agreed_advert(self):
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        with self.assertRaises(UserError):
            self.env['pb.hiring.posting'].publish_for(req.id)

    def test_publishing_twice_makes_one_row_per_job_board(self):
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        jd = self.env['pb.hiring.jd'].sudo().create(
            {'requisition_id': req.id, 'body': '<p>Advert</p>'})
        jd._chain_state_write('approved')
        jd._become_current()
        platforms = self.env['hr.job.platform'].sudo().search_count([])
        self.env['pb.hiring.posting'].publish_for(req.id)
        self.env['pb.hiring.posting'].publish_for(req.id)
        self.assertEqual(len(req.posting_ids), platforms)
        self.assertTrue(req.job_id.is_published)

    def test_sending_is_refused_while_the_switch_is_off(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.platform_mail', '0')
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        jd = self.env['pb.hiring.jd'].sudo().create(
            {'requisition_id': req.id, 'body': '<p>Advert</p>'})
        jd._chain_state_write('approved')
        jd._become_current()
        self.env['pb.hiring.posting'].publish_for(req.id)
        if not req.posting_ids:
            self.skipTest('this database has no job boards set up')
        with self.assertRaises(UserError):
            req.posting_ids[0].action_send()


# =========================================================================
#  Screening
# =========================================================================
@tagged('post_install', '-at_install')
class TestScreening(HiringCase):

    def _applicant(self):
        req = self._requisition()
        req._chain_state_write('open')
        req._on_opened()
        return req, self.env['hr.applicant'].sudo().create({
            'partner_name': 'RIZE W2 Test Applicant',
            'email_from': 'rize.w2.applicant@example.com',
            'job_id': req.job_id.id,
            'company_id': self.company.id,
            'pb_requisition_id': req.id,
        })

    def test_not_this_time_archives_with_a_reason(self):
        _req, applicant = self._applicant()
        applicant.action_pb_screen('rejected')
        self.assertFalse(applicant.active)
        self.assertTrue(applicant.refuse_reason_id)

    def test_worth_keeping_puts_them_in_a_pool(self):
        _req, applicant = self._applicant()
        applicant.action_pb_screen('future_fit')
        self.assertTrue(applicant.talent_pool_ids)

    def test_another_role_moves_them_to_its_first_stage(self):
        req, applicant = self._applicant()
        other = self.env['hr.job'].sudo().create({
            'name': 'RIZE W2 Test Other Role',
            'company_id': self.company.id,
        })
        applicant.action_pb_screen('other_role', job_id=other.id)
        self.assertEqual(applicant.job_id.id, other.id)
        first = self.env['hr.recruitment.stage'].sudo().search(
            [], order='sequence, id', limit=1)
        self.assertEqual(applicant.stage_id.id, first.id)

    def test_an_unknown_answer_is_refused(self):
        _req, applicant = self._applicant()
        with self.assertRaises(UserError):
            applicant.action_pb_screen('promoted')


# =========================================================================
#  The daily job
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheDailyJob(HiringCase):

    def test_it_is_idempotent(self):
        req = self._requisition()
        jd = self.env['pb.hiring.jd'].sudo().create(
            {'requisition_id': req.id, 'body': '<p>Advert</p>'})
        jd._chain_state_write('submitted')
        self.head.write({'user_id': self.env.uid})
        # FLUSH BEFORE THE RAW SQL, AND INVALIDATE AFTER IT. Odoo leaves the
        # state write in the `towrite` buffer, and the very next `search()`
        # flushes it — which stamps `write_date` back to now and undoes the
        # ageing this test is built on. The job then finds nothing and reads
        # as broken when it is fine (R22's shape, reached from the test side).
        self.env.flush_all()
        old = fields.Datetime.now() - timedelta(days=30)
        self.env.cr.execute(
            'UPDATE pb_hiring_jd SET write_date = %s WHERE id = %s',
            (old, jd.id))
        self.env.invalidate_all()
        first = self.env['pb.hiring.automation']._nudge_adverts()
        second = self.env['pb.hiring.automation']._nudge_adverts()
        self.assertGreaterEqual(first, 1)
        self.assertEqual(second, 0)

    def test_it_never_raises(self):
        counts = self.env['pb.hiring.automation'].run_now()
        self.assertIn('jd', counts)
        self.assertIn('recruiter', counts)

    def test_the_sentence_has_the_numbers_in_it(self):
        Auto = self.env['pb.hiring.automation']
        self.assertIn('Nothing', Auto.describe({'jd': 0, 'recruiter': 0}))
        self.assertIn('1', Auto.describe({'jd': 1, 'recruiter': 0}))
        self.assertIn('2', Auto.describe({'jd': 0, 'recruiter': 2}))
        both = Auto.describe({'jd': 3, 'recruiter': 4})
        self.assertIn('3', both)
        self.assertIn('4', both)


# =========================================================================
#  The board
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheBoard(HiringCase):

    def test_the_board_answers_and_is_ordered_problem_first(self):
        board = self.env['pb.hiring'].get_board()
        self.assertTrue(board['allowed'])
        ranks = [r['rank'] for r in board['rows']]
        self.assertEqual(ranks, sorted(ranks))

    def test_an_unknown_verb_is_refused_by_name(self):
        with self.assertRaises(UserError):
            self.env['pb.hiring'].act('drop_the_database', {})

    def test_a_private_helper_is_not_reachable_as_a_verb(self):
        """`act` dispatches on `_act_<verb>`, so a verb of "_row" would
        resolve to `_act__row` and not to `_row` — proven rather than
        assumed, because the alternative is a facade that can be asked for
        anything."""
        with self.assertRaises(UserError):
            self.env['pb.hiring'].act('_row', {})
        with self.assertRaises(UserError):
            self.env['pb.hiring'].act('safe', {})


# =========================================================================
#  The gates — two whole classes of defect that are invisible at runtime
# =========================================================================
@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JS SyntaxError, and the asset pipeline
        concatenates without ever parsing — so one of these blanks
        `web.assets_backend` for every user with a clean server log (R2)."""
        for fname in ('hiring_board.js', 'hiring_palette.js'):
            src = _src('static', 'src', 'js', fname)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline' % fname)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into the generated function
        as a bare `<` and the whole template dies, pointing at the template
        and never at the loop (R1)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        src = _src('static', 'src', 'xml', 'hiring_board.xml')
        for name in re.findall(r't-as="(\w+)"', src):
            self.assertNotIn(name, reserved,
                             'hiring_board.xml uses the reserved name %s'
                             % name)

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` falls back for an unknown name, so a typo is a wrong icon
        rather than an error — never a per-module icon file."""
        path = get_module_path('pb_import_kit')
        with open(path + '/static/src/js/import_icons.js',
                  encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('briefcase', known, 'the icon registry did not parse')
        used = set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                              _src('static', 'src', 'xml',
                                   'hiring_board.xml')))
        for fname in ('hiring_board.js', 'hiring_palette.js'):
            src = _src('static', 'src', 'js', fname)
            used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"', src))
            used |= set(re.findall(r':\s*"([A-Za-z0-9_]+)",\s*//\s*icon', src))
        for name in used:
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry"
                          % name)

    def test_the_word_odoo_appears_in_no_user_visible_string(self):
        """The white-label rule, and only where it actually binds.

        It covers user-visible STRINGS. Engineering comments MUST be able to
        say the real name — the sentence that stops the next contributor
        reintroducing a bug is worth more than a gate that forbids it (R118)
        — so the comments are stripped and everything that is left is
        checked, which is the half a person can read.
        """
        for parts in (('static', 'src', 'xml', 'hiring_board.xml'),
                      ('views', 'hiring_views.xml'),
                      ('views', 'portal_templates.xml'),
                      ('data', 'mail_template_data.xml'),
                      ('data', 'approval_process.xml'),
                      ('security', 'pb_hiring_security.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn(
                'Odoo', src,
                '%s shows the word Odoo to a user' % parts[-1])
            self.assertNotIn('odoo.com', src.lower())

    def test_no_bracketed_plurals(self):
        """"1 role(s)" is how a screen announces it was written by a
        programme rather than by a person (R46)."""
        for parts in (('models', 'hiring_automation.py'),
                      ('models', 'pb_hiring.py'),
                      ('models', 'posting.py'),
                      ('static', 'src', 'xml', 'hiring_board.xml'),
                      ('views', 'portal_templates.xml')):
            src = _src(*parts)
            self.assertFalse(
                re.search(r'\w\(s\)', src),
                '%s has a bracketed plural' % parts[-1])

    def test_every_hand_built_window_action_carries_views(self):
        """`_preprocessAction` runs `action.views.map(...)` unconditionally,
        and the ORM-computed `views` field exists only on real act_window
        RECORDS — so a dict without it throws in the client and the user
        sees the generic "something went wrong" dialog with nothing useful
        in the console (R125)."""
        import ast
        import os
        path = get_module_path('pb_hiring')
        offenders = []
        for root, _dirs, files in os.walk(path):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                full = os.path.join(root, fname)
                with open(full, encoding='utf-8') as fh:
                    tree = ast.parse(fh.read(), full)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Dict):
                        continue
                    keys = [k.value for k in node.keys
                            if isinstance(k, ast.Constant)]
                    values = [v.value for v in node.values
                              if isinstance(v, ast.Constant)]
                    if 'ir.actions.act_window' not in values:
                        continue
                    if 'views' not in keys:
                        offenders.append('%s:%s' % (fname, node.lineno))
        self.assertFalse(
            offenders,
            'these act_window dicts carry no `views`: %s' % offenders)

    def test_every_nolabel_field_in_a_group_carries_a_colspan(self):
        """An inner group is a two-column grid and a label-less field takes
        the NARROW cell, so a note box renders about 150px wide with a
        thousand pixels of empty row beside it (R128)."""
        from lxml import etree
        offenders = []
        for parts in (('views', 'hiring_views.xml'),):
            tree = etree.fromstring(_src(*parts).encode('utf-8'))
            for field in tree.iter('field'):
                if field.get('nolabel') != '1':
                    continue
                parent = field.getparent()
                if parent is None or parent.tag != 'group':
                    continue
                if not field.get('colspan'):
                    offenders.append('%s line %s'
                                     % (parts[-1], field.sourceline))
        self.assertFalse(offenders, 'nolabel without colspan: %s' % offenders)

    def test_no_search_group_carries_a_string_or_expand(self):
        """Odoo 19 search `<group>` takes neither, and either one fails RNG
        validation and ABORTS THE WHOLE MODULE LOAD (R129)."""
        from lxml import etree
        tree = etree.fromstring(
            _src('views', 'hiring_views.xml').encode('utf-8'))
        for search in tree.iter('search'):
            for group in search.iter('group'):
                self.assertIsNone(group.get('string'))
                self.assertIsNone(group.get('expand'))


@tagged('post_install', '-at_install')
class TestTheDoors(TransactionCase):

    def test_the_client_action_exists_and_carries_a_name(self):
        """A bare tag reaches the action service with no NAME and the
        breadcrumb reads "Unnamed"."""
        act = self.env.ref('pb_hiring.action_pb_hiring_board')
        self.assertEqual(act.tag, 'pb_hiring_board')
        self.assertEqual(act.name, 'Hiring')

    def test_the_palette_and_the_settings_card_name_real_actions(self):
        src = _src('static', 'src', 'js', 'hiring_palette.js')
        for xmlid in set(re.findall(r'xmlid:\s*"([\w.]+)"', src)):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'the palette points at %s, which does not resolve — the row '
                'would render and open nothing' % xmlid)

    def test_the_palette_takes_the_3500_block(self):
        src = _src('static', 'src', 'js', 'hiring_palette.js')
        seqs = sorted(int(n) for n in re.findall(r'sequence:\s*(3\d{3})', src))
        self.assertTrue(seqs)
        self.assertGreaterEqual(seqs[0], 3500)
        self.assertLess(seqs[-1], 3600,
                        'A1 owns the 3500 block; B1 starts at 3600')

    def test_the_lens_sits_at_sequence_ten(self):
        src = _src('static', 'src', 'js', 'hiring_palette.js')
        self.assertIn('sequence: 10', src)
        self.assertIn('LIFECYCLE_LENSES', src)

    def test_this_module_ships_no_menu_and_no_rail_item(self):
        """Its doors are the hub lens, the Settings card and the palette."""
        act = self.env['ir.actions.client'].sudo().search(
            [('tag', '=', 'pb_hiring_board')], limit=1)
        menus = self.env['ir.ui.menu'].sudo().with_context(
            active_test=False).search([('action', '!=', False)])
        hits = [m.complete_name for m in menus
                if m.action._name == 'ir.actions.client'
                and m.action.id == act.id]
        self.assertFalse(hits, 'the board must not be on a menu: %s' % hits)
        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].sudo().with_context(
                active_test=False).search(
                    [('match_action_tags', 'ilike', 'pb_hiring')])
            self.assertFalse(items, 'this module must not add a rail item')


@tagged('post_install', '-at_install')
class TestTheApprovalWiring(TransactionCase):

    def test_both_catalogue_rows_exist_and_are_wired_up(self):
        """`connected` means the model the row names really does answer for
        that row's key. A row that says "not connected yet" on the Matrix is
        a row saying nobody is checking this."""
        for key, model in (('hiring_request', 'pb.hiring.requisition'),
                           ('hiring_jd', 'pb.hiring.jd')):
            process = self.env['biz.approval.process']._by_key(key)
            self.assertTrue(process, 'no catalogue row for %s' % key)
            self.assertEqual(process.model_name, model)
            self.assertTrue(process.connected,
                            '%s is in the catalogue but not wired up' % key)

    def test_this_module_never_depends_on_the_configuration_screen(self):
        """An adapter depends on the ENGINE only (ledger AM52)."""
        src = _src('__manifest__.py')
        self.assertNotIn("'pb_approval_config'", src)
        self.assertIn("'biz_approval_workflow'", src)

    def test_the_route_asks_finance_only_when_it_is_over_budget(self):
        from odoo.addons.pb_hiring.models.requisition_approval import (
            hiring_route)
        steps = hiring_route()['steps']
        self.assertEqual(len(steps), 3)
        self.assertIsNone(steps[0]['condition'])
        self.assertIsNone(steps[1]['condition'])
        self.assertEqual(steps[2]['condition'],
                         {'fact': 'over_budget', 'op': 'eq', 'value': True})

    def test_every_fact_the_route_conditions_on_is_declared(self):
        """A condition on a fact nobody declares is a condition on nothing,
        and it would silently include or exclude the step for ever."""
        from odoo.addons.pb_hiring.models.requisition_approval import (
            hiring_route)
        specs = self.env['pb.hiring.requisition']._chain_fact_specs()
        for step in hiring_route()['steps']:
            if step.get('condition'):
                self.assertIn(step['condition']['fact'], specs)

    def test_the_migration_is_guarded_on_a_version(self):
        """Without the guard it also runs on a fresh install, where the hook
        has already done the work (ledger AM70)."""
        src = _src('migrations', '19.0.1.0.0', 'post-hiring_approval.py')
        self.assertIn('if not version:', src)
