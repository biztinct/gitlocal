# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T05–T10 — which route a request follows, and what happens when none does."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ApprovalCase, build, people_step


@tagged('post_install', '-at_install')
class TestRouting(ApprovalCase):

    def _flow(self, name):
        flow, _version = self.workflow(
            build([people_step('s1', [self.bob.id])]), name=name)
        return flow

    # ------------------------------------------------------------------ T05
    def test_t05_most_specific_scope_wins(self):
        company_flow = self._flow('Company default')
        area_flow = self._flow('Retail only')
        self.bind(company_flow, scope_key='')
        self.bind(area_flow, scope_key='area:retail')

        answer = self.engine.resolve_binding(
            self.company.id, 'generic', ['area:retail', ''], 'any')
        self.assertFalse(answer['error'])
        self.assertEqual(answer['workflow_name'], 'Retail only')
        self.assertTrue(any(t['win'] for t in answer['trace']))

        answer = self.engine.resolve_binding(
            self.company.id, 'generic', ['area:ops', ''], 'any')
        self.assertEqual(answer['workflow_name'], 'Company default')

    # ------------------------------------------------------------------ T06
    def test_t06_exact_kind_beats_any_kind(self):
        any_flow = self._flow('Any kind')
        off_flow = self._flow('Off-cycle only')
        self.bind(any_flow, scope_key='', kind_key='any')
        self.bind(off_flow, scope_key='', kind_key='offcycle')

        answer = self.engine.resolve_binding(
            self.company.id, 'generic', [''], 'offcycle')
        self.assertEqual(answer['workflow_name'], 'Off-cycle only')

        answer = self.engine.resolve_binding(
            self.company.id, 'generic', [''], 'endcycle')
        self.assertEqual(answer['workflow_name'], 'Any kind')

    # ------------------------------------------------------------------ T07
    def test_t07_a_tie_is_refused_and_fails_closed(self):
        first = self._flow('First')
        second = self._flow('Second')
        self.bind(first, scope_key='')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.bind(second, scope_key='')

        # force a tie past the guard the way a bad migration would, and check
        # the runtime does not pick one at random
        twin = self.bind(second, scope_key='', kind_key='temporarily_other')
        self.env.cr.execute(
            "UPDATE biz_approval_binding SET kind_key = 'any' WHERE id = %s",
            (twin.id,))
        self.env.invalidate_all()
        answer = self.engine.resolve_binding(
            self.company.id, 'generic', [''], 'any')
        self.assertEqual((answer['error'] or {}).get('code'),
                         'ambiguous_route')

    # ------------------------------------------------------------------ T08
    def test_t08_never_crosses_a_company(self):
        beta_flow = self.workflow(
            build([people_step('s1', [self.bob.id])]),
            name='Beta route', company=self.other_company)[0]
        self.bind(beta_flow, scope_key='', company=self.other_company)

        answer = self.engine.resolve_binding(
            self.company.id, 'generic', [''], 'any')
        self.assertEqual((answer['error'] or {}).get('code'), 'no_route')

        record = self.ask()
        with self.assertRaises(UserError):
            self.submit(record)

    # ------------------------------------------------------------------ T09
    def test_t09_a_paused_route_is_a_stop(self):
        company_flow = self._flow('Company default')
        paused_flow = self._flow('Paused for retail')
        self.bind(company_flow, scope_key='')
        self.bind(paused_flow, scope_key='area:retail', mode='paused')

        record = self.ask(area='retail')
        before = self.Request.search_count([])
        with self.assertRaises(UserError) as caught:
            self.submit(record)
        self.assertIn('paused', str(caught.exception).lower())
        self.assertEqual(self.Request.search_count([]), before,
                         'a paused route must not fall back to a wider one')

    # ------------------------------------------------------------------ T10
    def test_t10_no_route_refuses_and_writes_nothing(self):
        record = self.ask()
        before = self.Request.search_count([])
        with self.assertRaises(UserError):
            self.submit(record)
        self.assertEqual(self.Request.search_count([]), before)
        self.assertEqual(record.state, 'draft')
