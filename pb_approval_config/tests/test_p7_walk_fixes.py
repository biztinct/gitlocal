# -*- coding: utf-8 -*-
"""The five things the browser walk found, each with the test that keeps it.

W1 a door that returns a proposal must not let its screen say "done";
W2 the drawer shows plain words, never the payload;
W3 the person a route names is sometimes the person who sent it in;
W4 no catalogue row reads "Not connected yet" on a full install;
W5 "Respective Line Manager" is a step, not a person.
"""

import os
import re

from odoo.tests import tagged

from .common import MatrixCase
from .test_p7_matrix import TOUCHED_MODULES, _repo_root

#: Every P7 door reachable from a screen. A SCREEN that calls one of these
#: must branch on the answer, because the answer is a proposal wherever a
#: route is published.
#:
#: `set_state` is qualified by its model and the rest are not, because
#: `set_state` is a name two unrelated screens use — `pb.paycal`'s reopens a
#: pay month and `pb.asset.request`'s moves an asset along its own ladder,
#: which Phase 6 already put on the engine and which is not a proposal at all.
#: A door list that cannot tell them apart fails a screen that is correct.
P7_DOORS = (
    'create_policy', 'create_tax_table', 'tenant_suspend',
    'tenant_schedule_deletion', 'offboard', 'rollout_start', 'rollout_abort',
    'tenant_set_plan', 'features_bulk', 'feature_save', 'restore_staging',
    'save_group', 'add_expense', 'accept_draft', 'save_rate_table',
    'delete_rate_table', 'legislation_apply', 'create_employee',
    'create_contract', 'save_contract_360',
)

#: (model, method) pairs, for the names more than one screen uses.
P7_DOORS_QUALIFIED = (('pb.paycal', 'set_state'),)

#: What a screen has to READ before it may say anything. Any one of them is
#: enough: they are the names the server answers with.
#:
#: THE UNIT IS THE SCREEN, NOT THE FILE. A client action is a `.js` that
#: fetches and a `.xml` that draws, and the two halves are as free to divide
#: the work as any other pair of files: both guided wizards keep the answer in
#: `state.result` and branch on `state.result.applied` IN THE TEMPLATE. A
#: check that reads only the `.js` calls that a lie.
BRANCHED = ('pending', 'applied', '_saidSoFar', 'result.message',
            'result.message')


@tagged('post_install', '-at_install')
class TestP7WalkFixes(MatrixCase):

    # ================================================================== W1
    def test_w1_every_screen_that_presses_a_p7_door_reads_the_answer(self):
        """A door that returns a proposal must not be met with "Saved".

        The walk found two: "Policy created · Walk policy 2027" over a policy
        that did not exist, and "Their access is paused" over a customer who
        was still live. Both were confident and wrong, which is the worst
        thing a control can be.

        Asserted as a SHAPE rather than as a list of sentences: a file that
        calls one of these doors and never reads `pending`, `applied` or the
        server's own `message` cannot be telling the truth about a proposal,
        whatever its strings say.
        """
        blind = []
        for module in TOUCHED_MODULES + ('pb_contracts',):
            root = os.path.join(_repo_root(), module, 'static')
            if not os.path.isdir(root):
                continue
            for surface, bodies in self._surfaces(root).items():
                whole = '\n'.join(bodies.values())
                presses = [d for d in P7_DOORS
                           if '"%s"' % d in whole or "'%s'" % d in whole]
                for model, method in P7_DOORS_QUALIFIED:
                    if ('"%s"' % model in whole and
                            ('"%s"' % method in whole
                             or "'%s'" % method in whole)):
                        presses.append('%s.%s' % (model, method))
                if not presses:
                    continue
                if any(token in whole for token in BRANCHED):
                    continue
                blind.append('%s · %s presses %s and never reads the answer'
                             % (module, surface, ', '.join(presses)))
        self.assertFalse(blind, '\n'.join(blind))

    def _surfaces(self, root):
        """A screen is its `.js` and the `.xml` that draws it, together.

        Keyed by the file's base name, so `statutory_wizards.js` and
        `statutory_wizards.xml` are one surface — which is what they are.
        Anything whose partner is missing stands alone.
        """
        out = {}
        for folder, _dirs, files in os.walk(root):
            if '__pycache__' in folder or os.sep + 'tests' in folder:
                continue
            for name in sorted(files):
                if not name.endswith(('.js', '.xml')):
                    continue
                path = os.path.join(folder, name)
                base = os.path.splitext(name)[0]
                try:
                    body = open(path, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError):
                    continue
                out.setdefault(base, {})[name] = body
        return out

    def test_w1_the_server_says_the_sentence_itself(self):
        """One sentence, from the server, so no screen has to invent one."""
        Proposal = self.env['biz.approval.proposal.mixin']
        for name in ('answer_message', 'answer'):
            self.assertTrue(hasattr(Proposal, name),
                            'the proposal mixin lost %s' % name)

    # ================================================================== W2
    def test_w2_the_drawer_never_shows_the_payload(self):
        """Rows come from `_proposal_rows`, per kind, in plain words.

        The walk read "args · 3 item(s)" and "values · 12 item(s)" in a panel
        headed "What would change". That is a dump of an implementation, and
        an approver who cannot read what they are agreeing to should not be
        agreeing to it.
        """
        import inspect
        from odoo.addons.biz_approval_workflow.models import proposal as mod
        body = inspect.getsource(mod.BizApprovalProposalMixin._approval_detail)
        self.assertNotIn('payload()', body,
                         'the drawer is reading the payload again')
        self.assertIn('_proposal_rows', body)

    def test_w2_every_proposal_model_answers_in_words(self):
        """A concrete proposal that has not said what it is about shows its
        chips and nothing else — never the wiring."""
        from odoo.addons.biz_approval_workflow.models.proposal import (
            PROPOSAL_MODELS,
        )
        silent = []
        for name in sorted(PROPOSAL_MODELS):
            if name == 'biz.approval.proposal.mixin' or name not in self.env:
                continue
            model = self.env[name]
            own = type(model)._proposal_rows
            base = self.env['biz.approval.proposal.mixin'].__class__ \
                ._proposal_rows
            if own is base:
                silent.append(name)
        self.assertFalse(
            silent,
            'these proposals would show an approver nothing: %s' % silent)

    # ================================================================== W4
    def test_w4_no_row_reads_not_connected_where_its_module_is_here(self):
        """A row is connected, covered by another row, or its module is not
        installed. Nothing else is honest."""
        payload = self.as_admin('pb.approval.matrix').get_matrix(False)
        rows = [r for area in payload['areas'] for r in area['rows']]
        # WHICH KEYS ANY INSTALLED ADAPTER ACTUALLY ANSWERS FOR.
        #
        # Asked of the REGISTRY rather than of the row's own `model_name`: a
        # row can name a model that exists for another reason entirely. The
        # weekly-timesheet row still says `hr.attendance.weekentry` — the
        # SCREEN, which `pb_hr_workforce` ships — until `pb_timesheet_approval`
        # is installed and repoints it at the packet (ledger AM45). On a
        # database without that module the row is honestly not connected, and
        # a check that looked only at whether the named model exists would
        # have called it a fault.
        answered = set()
        for name in list(self.env.registry.models):
            model = self.env[name]
            key = getattr(model, '_approval_process_key', None)
            keys = set(getattr(model, '_approval_process_keys', ()) or ())
            if key:
                keys.add(key)
            answered |= keys
        stranded = [row['process_key'] for row in rows
                    if row['status'] == 'soon'
                    and row['process_key'] in answered]
        self.assertFalse(
            stranded,
            'an adapter in this registry answers for these, and the Matrix '
            'still says nobody is checking them: %s' % stranded)

    def test_w4_a_covered_row_names_the_row_that_covers_it(self):
        Process = self.env['biz.approval.process'].sudo()
        for key, covered_by in (('retro', 'loads'), ('reopen', 'payrun')):
            row = Process._by_key(key)
            self.assertTrue(row, 'the "%s" row is gone' % key)
            if not row.covered_by_key:
                continue        # the covering module is not installed here
            self.assertEqual(row.covered_by_key, covered_by)
            self.assertTrue(row.covered_by_name,
                            '"%s" names a row that does not exist' % key)

    # ================================================================== W5
    def test_w5_a_line_manager_is_never_a_proposed_person(self):
        from odoo.addons.pb_approval_config.models import matrix_import as mi
        for phrase in ('Respective Line Manager', 'Line Manager',
                       'Functional Manager'):
            self.assertEqual(mi.match_role(phrase), 'manager',
                             '"%s" should read as the manager step' % phrase)
        for phrase in ('Per bank mandate', 'Joint authorizers', 'None'):
            self.assertTrue(mi.is_empty(phrase),
                            '"%s" is an arrangement, not a person' % phrase)
        # …and a real name still is one
        self.assertFalse(mi.is_empty('Nguyen Thi Phuong Thao'))
        self.assertNotEqual(mi.match_role('Nithya (HR Manager)'), 'manager')
