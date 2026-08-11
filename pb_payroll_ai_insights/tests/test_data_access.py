# -*- coding: utf-8 -*-
"""PayAI's data boundary — who the query layer runs as, and what it refuses.

WHAT THIS FILE IS PROTECTING
----------------------------
`payroll.data.query` is the only place in Payobook where a chat box turns into
a database read, and until Phase D1 every one of those reads ran with
superuser rights. Two separate promises are asserted here:

1. **The queries run as the ASKER.** Not "mostly" — the escalation call is
   pinned absent from the whole file, because one surviving call is one query
   that answers around the record rules while every other query answers
   inside them, and nothing in the UI would show the difference.
2. **A named person's pay needs a group.** `_query_individual_data` is the
   path that posts employee names, job titles and salaries to an external
   model provider; the ORM gate is necessary and it is not sufficient, so a
   product-level group gate sits on top of it.

Most of what follows is a SOURCE-LEVEL assertion, for the reason the ledger
gives: the thing being promised is the absence of a call and the presence of a
gate, and a behavioural test can only ever sample the queries it thought to
try. Two functional tests then check that the gate actually behaves, on a
database.

LEDGER RULE OBSERVED: a source-level assertion must be scoped to code, or be
written against a string the code has to contain and the prose cannot
plausibly repeat. `payroll_data_query.py` carries a note telling the next
reader not to write the escalation literal in its own comments — this test
greps the whole file, deliberately, because a comment showing the reader how
to re-add it is halfway to somebody re-adding it.
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

# The literal that must not come back. Written by concatenation so that THIS
# file — which does have to name it — is not itself a false positive if the
# same scan is ever pointed at the tests.
ESCALATION = '.' + 'sudo' + '('

MODULE = 'pb_payroll_ai_insights'


def _path(rel):
    base = get_module_path(MODULE)
    return os.path.join(base, rel) if base else None


def _read(rel):
    path = _path(rel)
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _po_map(text):
    """msgid -> msgstr, for single-line entries (which is how ours are written)."""
    out = {}
    pat = re.compile(r'^msgid ("(?:[^"\\]|\\.)*")\nmsgstr ("(?:[^"\\]|\\.)*")$', re.M)
    for raw_id, raw_str in pat.findall(text):
        out[ast.literal_eval(raw_id)] = ast.literal_eval(raw_str)
    return out


@tagged('post_install', '-at_install')
class TestDataQueryAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.query_src = _read('models/payroll_data_query.py')
        cls.engine_src = _read('models/payroll_ai_engine.py')
        cls.report_src = _read('models/payroll_ai_report.py')
        cls.po_src = _read('i18n/vi_VN.po')
        cls.Query = cls.env['payroll.data.query']

    # -- 1. the escalation is gone ---------------------------------------
    def test_01_no_privilege_escalation_survives_in_the_query_layer(self):
        """The whole promise of Phase D1, in one grep.

        Scoped to the whole file on purpose: a commented-out escalation is a
        template, and this module's own history (the `absent` contract checks
        in pb_learn B2 and C2) is that the explanation gets written before the
        code does.
        """
        self.assertTrue(self.query_src, "payroll_data_query.py could not be read")
        self.assertNotIn(
            ESCALATION, self.query_src,
            "payroll.data.query escalates again — PayAI can answer around the "
            "asker's record rules")

    def test_01b_the_module_check_does_not_need_privileges_either(self):
        """The soft-dependency probe used to read ir.module.module elevated.

        The registry answers the same question without any privilege, and
        answers the more useful version of it: whether `self.env[model]` will
        raise for the query that is about to run.
        """
        self.assertIn('_OPTIONAL_MODULE_MODELS', self.query_src)
        self.assertNotIn(
            "self.env['ir.module.module']", self.query_src,
            "the module check reads ir.module.module again")
        for module in ('hr_attendance', 'hr_holidays', 'hr_recruitment', 'hr_timesheet'):
            # Never raises, whatever is installed — that is the contract the
            # routing table depends on.
            self.assertIsInstance(self.Query._is_module_installed(module), bool)
        self.assertFalse(self.Query._is_module_installed('a_module_that_is_not_here'))

    # -- 2. every query path can refuse ----------------------------------
    def test_02_every_query_path_is_guarded(self):
        """An unguarded path is an Odoo traceback in a chat bubble.

        Read off the AST rather than by regex, because a decorator is a
        structural fact and 'the line above starts with @' is not.
        """
        tree = ast.parse(self.query_src)
        unguarded = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith('_query_') or node.name == 'query_for_message':
                continue
            names = [d.func.id for d in node.decorator_list
                     if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)]
            if '_guarded' not in names:
                unguarded.append(node.name)
        self.assertEqual(
            unguarded, ['_query_trend_data'],
            "a query path either lost its guard or gained one it does not need "
            "(_query_trend_data owns no query — it delegates to a guarded one)")

    def test_02b_a_refusal_is_a_normal_answer_with_a_translatable_message(self):
        for topic in ('attendance', 'leave', 'recruitment', 'timesheet', 'salary',
                      'headcount', 'overtime', 'deduction', 'cost', 'periods',
                      'department', 'individual', 'summary', 'forecast',
                      'a_topic_nobody_declared'):
            out = self.Query._access_refused_response(topic)
            self.assertTrue(out.get('access_refused'))
            self.assertEqual(out['query_type'], 'access_refused')
            self.assertEqual(out['data'], [], "a refusal carried data")
            self.assertIsNone(out['suggested_chart'])
            self.assertTrue(out['message'].strip(), "a refusal with nothing to read")
            self.assertNotIn('%(topic)s', out['message'],
                             "the interpolation reached the reader")
            self.assertIn('Payroll Manager', out['message'],
                          "the refusal does not name anybody who CAN see the data")

    def test_02c_a_refused_half_does_not_become_an_empty_department_table(self):
        """`_query_department_data` merges two queries. Two zeroes read as
        'nobody works here', which is a different answer from 'you may not
        see this' — and a much worse one to put in front of a manager."""
        src = self.query_src.split('def _query_department_data')[1].split('def _query_')[0]
        self.assertIn("access_refused", src,
                      "the department merge no longer checks its halves")

    # -- 3. the individual gate ------------------------------------------
    def test_03_the_individual_path_names_both_groups(self):
        self.assertIn('INDIVIDUAL_SALARY_GROUPS', self.query_src)
        from odoo.addons.pb_payroll_ai_insights.models.payroll_data_query import (
            INDIVIDUAL_SALARY_GROUPS,
        )
        self.assertEqual(
            set(INDIVIDUAL_SALARY_GROUPS),
            {'pb_hr_payroll_base.group_payroll_base_manager',
             'pb_hr_payroll_base.group_payroll_final_approver'})
        for xmlid in INDIVIDUAL_SALARY_GROUPS:
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                "the individual gate names a group that does not exist: %s" % xmlid)

    def test_03b_the_gate_is_in_the_individual_path_and_only_there(self):
        body = self.query_src.split('def _query_individual_data')[1].split('def _query_')[0]
        self.assertIn('has_group', body,
                      "_query_individual_data no longer checks a group")
        self.assertIn('INDIVIDUAL_SALARY_GROUPS', body)
        self.assertIn('access_note', body,
                      "the gated answer no longer says what was withheld")

    def test_04_below_the_gate_an_officer_gets_the_aggregate_and_the_note(self):
        officer = self._user('payai_officer', [
            'base.group_user',
            'pb_hr_payroll_base.group_payroll_base_officer',
            'pb_payroll_ai_insights.group_payai_user',
        ])
        out = self.Query.with_user(officer)._query_individual_data('salary by name', {})
        if out.get('access_refused'):
            # A bare officer may not read hr.contract on this database at all.
            # That is a STRICTER outcome than the gate, and still correct.
            self.assertIn('Payroll Manager', out['message'])
            return
        self.assertTrue(out.get('individual_data_withheld'),
                        "an officer was handed the individual salary list")
        self.assertEqual(out.get('query_type'), 'salary_by_department',
                         "the substitute answer is not the aggregate one")
        self.assertTrue(out.get('access_note'), "the substitution was silent")
        for row in out.get('data') or []:
            self.assertNotIn('employee', row,
                             "a named employee survived into the gated answer")
            self.assertNotIn('job_title', row)

    def test_04b_above_the_gate_a_manager_gets_the_individual_shape(self):
        manager = self._user('payai_manager', [
            'base.group_user',
            'pb_hr_payroll_base.group_payroll_base_manager',
            'pb_payroll_ai_insights.group_payai_user',
        ])
        out = self.Query.with_user(manager)._query_individual_data('salary by name', {})
        self.assertFalse(out.get('individual_data_withheld'),
                         "a payroll manager was refused their own wage roster")
        if out.get('access_refused'):
            self.skipTest("hr.contract is not readable by a payroll manager on "
                          "this database — an ACL question, not a gate one")
        self.assertEqual(out.get('query_type'), 'individual_employees')

    def test_04c_a_final_approver_is_above_the_gate_too(self):
        approver = self._user('payai_approver', [
            'base.group_user',
            'pb_hr_payroll_base.group_payroll_final_approver',
            'pb_payroll_ai_insights.group_payai_user',
        ])
        out = self.Query.with_user(approver)._query_individual_data('salary by name', {})
        self.assertFalse(out.get('individual_data_withheld'),
                         "a final approver was gated out of the individual path")

    def _user(self, login, group_xmlids):
        groups = self.env['res.groups']
        for xmlid in group_xmlids:
            grp = self.env.ref(xmlid, raise_if_not_found=False)
            if not grp:
                self.skipTest("group %s is not installed on this database" % xmlid)
            groups |= grp
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, groups.ids)],
        })

    # -- 4. a refusal never reaches the provider -------------------------
    def test_05_the_engine_short_circuits_a_refusal_before_the_prompt(self):
        """The refusal must not be handed to a model to paraphrase.

        Two reasons, and the second is the one that would be missed: the
        sentence is the one thing in this flow that has to be exact, and
        sending it means the fact that somebody was refused goes over the wire
        to an external provider along with the question that earned it.
        """
        body = self.engine_src.split('def _process_data_query')[1].split('\n    def ')[0]
        self.assertIn("payroll_data.get('access_refused')", body,
                      "the engine no longer recognises a refusal")
        refusal_at = body.index("access_refused")
        prompt_at = body.index('json.dumps(payroll_data')
        self.assertLess(refusal_at, prompt_at,
                        "the refusal is checked AFTER the data is put in the prompt")

    def test_05b_the_gate_note_survives_both_return_paths(self):
        """Including the parse-failure fallback. A user whose individual detail
        was withheld has to be told so even when the chart JSON did not
        parse — that branch is reached by a bad response, not by a rare one."""
        body = self.engine_src.split('def _process_data_query')[1].split('\n    def ')[0]
        self.assertEqual(
            body.count('_with_access_note('), 2,
            "one of the two return paths drops the gate note")

    def test_05c_a_refused_report_section_says_so_instead_of_rendering_empty(self):
        self.assertIn('_section_access', self.report_src,
                      "the PDF report no longer surfaces a refusal")
        body = self.report_src.split('def _generate_section_narratives')[1]
        self.assertIn("section.get('access_refused')", body,
                      "a refused section is sent to the provider for a narrative "
                      "about an empty list, overwriting the refusal")

    # -- 5. the refusal is bilingual -------------------------------------
    def test_06_every_sentence_a_refusal_can_print_ships_in_vietnamese(self):
        """A refusal is the one PayAI response a user reads verbatim — no model
        rewrites it — so it is also the one that cannot fall back to English on
        a Vietnamese session."""
        self.assertTrue(self.po_src, "pb_payroll_ai_insights/i18n/vi_VN.po is missing")
        catalogue = _po_map(self.po_src)
        tree = ast.parse(self.query_src)
        literals = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == '_' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                literals.append(node.args[0].value)
        self.assertTrue(literals, "no translatable strings found — the scan is broken")
        missing = [s for s in literals if not catalogue.get(s)]
        self.assertFalse(
            missing, "refusal copy with no Vietnamese: %r" % (missing[:3],))
        english = [s for s in literals if catalogue.get(s) == s]
        self.assertFalse(english, "Vietnamese identical to English: %r" % (english[:3],))
        for src in literals:
            self.assertEqual(
                '%(topic)s' in src, '%(topic)s' in catalogue[src],
                "a translation lost or invented the interpolation: %r" % (src[:40],))

    def test_06b_the_vietnamese_refusal_avoids_the_browser_word(self):
        """`trình duyệt` is Vietnamese for "web browser". The ledger has ruled
        on it three times; a rule broken three times is a missing test."""
        catalogue = _po_map(self.po_src or '')
        offenders = [v for v in catalogue.values()
                     if re.search(r'(?<!phê )trình\s+duyệt(?!\s+web)', v, re.I)]
        self.assertFalse(offenders, "'trình duyệt' used as a noun: %r" % (offenders[:2],))
