# -*- coding: utf-8 -*-
"""IA redesign Cycle 5 — THE RAIL CUTOVER, asserted in the DATABASE.

Five sections, eight items, thirty-four retirements. Almost every assertion here
reads the RECORD or `get_sidebar_data()` rather than the XML, and that is not
ceremony: W13.1 has bitten this codebase three times, and each time the repo was
correct, the log was clean, `-u` exited 0, and the rail on screen was still
wrong. A repo-only cutover is indistinguishable from a real one unless something
reads the database back.

The three tests that DO read files are the ones that can only be answered there:
that the hand-applied migration agrees with the data files it stands in for
(W27's warning, made a gate), that every icon the rail asks for exists in the
closed set inlined in `pb_sidebar.js`, and that every retired item still points
at an action that resolves (W76 — a retirement is only reversible while the
thing it points at is still there).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# ---------------------------------------------------------------------------
# THE TARGET RAIL. This table IS the specification, and every other assertion in
# the file is derived from it — so a future change to the rail is one edit here
# plus the data, and a data change that forgets this table fails loudly.
#
# (section technical_key, section sequence, show_label,
#  [(item xmlid, sequence, icon, label)])
TARGET_RAIL = [
    ('overview', 10, False, [
        ('pb_home_hub.item_home', 10, 'home', 'Home'),
    ]),
    ('operate', 20, True, [
        ('pb_payhub.item_pay_run', 10, 'zap', 'Pay Run'),
        ('pb_people_hub.item_people', 20, 'users', 'People'),
        # RIZE P0. A journey is about a PERSON and it is work you do rather
        # than something you look up, so it sits beside People — and at 25,
        # which lands it there without renumbering either neighbour (W18: a
        # sequence is a claim, and moving one is a migration).
        ('pb_lifecycle.item_lifecycle', 25, 'refresh-cw', 'Lifecycle'),
        ('pb_mission.item_workforce', 30, 'compass', 'Workforce'),
    ]),
    ('understand', 30, True, [
        ('pb_insights_hub.item_insights', 10, 'trending-up', 'Insights'),
        ('pb_compliance_hub.item_compliance', 20, 'shield', 'Compliance'),
    ]),
    ('learn', 40, True, [
        ('pb_learn.item_learn_journey', 10, 'book-open', 'Learn'),
    ]),
    ('system', 50, False, [
        ('pb_settings.item_settings', 10, 'settings', 'Settings'),
    ]),
]

# Every item the cutover retired, with the 900-band sequence it moved to.
# Grouped by the module that declares the record, because that is what decides
# whether the data file or the post-migrate had to move it.
RETIRED_ITEMS = {
    # ---- pb_sidebar's own, moved by the data file (noupdate="0") ----
    'pb_sidebar.item_dashboard': 900,
    'pb_sidebar.item_approvals': 901,
    'pb_sidebar.item_run_payroll': 910,
    'pb_sidebar.item_pay_runs': 911,
    'pb_sidebar.item_payslips': 912,
    'pb_sidebar.item_import': 913,
    'pb_sidebar.item_wf_payroll_report': 914,
    'pb_sidebar.item_full_final': 915,
    'pb_sidebar.item_proration': 916,
    'pb_sidebar.item_retro': 917,
    'pb_sidebar.item_formula': 920,
    'pb_sidebar.item_structures': 921,
    'pb_sidebar.item_statutory': 922,
    'pb_sidebar.item_integrations': 923,
    'pb_sidebar.item_emp_mapping': 924,
    'pb_sidebar.item_employees': 930,
    'pb_sidebar.item_contracts': 931,
    'pb_sidebar.item_analytics': 940,
    'pb_sidebar.item_explorer': 941,
    'pb_sidebar.item_workforce_insights': 942,
    'pb_sidebar.item_reports': 943,
    'pb_sidebar.item_govt_reports': 950,
    'pb_sidebar.item_wfp_dashboard': 960,
    'pb_sidebar.item_wfp_scenarios': 961,
    'pb_sidebar.item_wfp_forecasts': 962,
    'pb_sidebar.item_wfp_grades': 963,
    'pb_sidebar.item_wfp_merit': 964,
    'pb_sidebar.item_wfp_cycles': 965,
    'pb_sidebar.item_wfp_tags': 966,
    'pb_sidebar.item_roles': 970,
    'pb_sidebar.item_companies': 971,
    'pb_sidebar.item_menu_cfg': 972,
    'pb_sidebar.item_section_cfg': 973,
    # ---- other modules, moved by the post-migrate ----
    'pb_payrun_results.item_payrun_results': 918,
    'pb_pay_delivery.item_pay_deliver': 919,
    'pb_bank_ocr.item_bank_verification': 951,
    'pb_young_worker.item_young_workers': 952,
    'pb_audit.item_audit_console': 974,
    'pb_tenants.item_tenants': 975,
}

# Sections emptied by the cutover.
RETIRED_SECTIONS = {
    'pb_sidebar.sec_setup': 925,
    'pb_sidebar.sec_people': 930,
    'pb_sidebar.sec_workforce': 935,
    'pb_sidebar.sec_compliance': 945,
    'pb_sidebar.sec_planning': 955,
}

# THE MATCH MATRIX, as shipped. Each dimension belongs to exactly ONE live item
# (W71: the rail's active-item index is FLAT and last-writer-wins, so a value
# claimed twice does not produce a tie or a warning — it produces whichever item
# was indexed last, and the user simply learns the rail is unreliable).
MATCH_TAGS = {
    'pb_home_hub.item_home': [
        'pb_home_hub', 'pb_dashboard', 'pb_approval'],
    'pb_payhub.item_pay_run': [
        'pb_pay_hub', 'pb_payrun_wizard', 'pb_payslip_review',
        'pb_payrun_results', 'pb_import', 'pb_import_wizard', 'pb_pay_delivery',
        'pb_fullfinal', 'pb_proration', 'pb_retro'],
    'pb_people_hub.item_people': [
        'pb_people_hub', 'pb_people', 'pb_contracts', 'pb_employee_detail',
        'pb_contract_detail', 'wfp_dashboard'],
    'pb_lifecycle.item_lifecycle': ['pb_lifecycle_hub', 'pb_journeys'],
    'pb_mission.item_workforce': [
        'pb_workforce', 'pb_today', 'pb_schedule', 'pb_time_hub', 'pb_timeoff',
        'pb_ot_desk', 'pb_trips', 'pb_team', 'pb_attendance_weekgrid',
        'pb_attendance_flow', 'pb_driver_map'],
    'pb_insights_hub.item_insights': [
        'pb_insights_hub', 'pb_insights', 'pb_explorer_cockpit',
        'pb_workforce_insights', 'payroll_report_dashboard'],
    'pb_compliance_hub.item_compliance': [
        'pb_compliance_hub', 'pb_govt_reports', 'pb_filing_flow', 'pb_bank_ocr',
        'pb_young_worker', 'pb_audit'],
    'pb_settings.item_settings': [
        'pb_settings_hub', 'pb_formula_studio', 'pb_structures', 'pb_statutory',
        'pb_integrations', 'pb_import_connector_cockpit',
        'pb_integration_onboarding', 'pb_tenants'],
    'pb_learn.item_learn_journey': ['learn_journey'],
}

MATCH_MODELS = {
    'pb_payhub.item_pay_run': [
        'hr.payslip.run', 'hr.payslip', 'hr.payroll.import.batch'],
    'pb_people_hub.item_people': ['hr.employee', 'hr.contract'],
    'pb_lifecycle.item_lifecycle': [
        'pb.journey.case', 'pb.journey.task', 'pb.journey.template',
        'pb.letter.template', 'pb.hr.letter', 'pb.employee.checkin',
        'pb.feedback.request'],
    'pb_settings.item_settings': [
        'hr.integration.connector', 'hr.formula.config', 'hr.payroll.structure',
        'hr.salary.rule', 'vietnam.insurance.policy', 'vietnam.tax.table',
        'vietnam.tax.slab'],
}

MATCH_XMLIDS = {
    'pb_payhub.item_pay_run': ['pb_payruns.action_pb_payruns_kanban'],
    'pb_people_hub.item_people': [
        'pb_hr_workforce_planning.action_wfp_scenario',
        'pb_hr_workforce_planning.action_wfp_forecast',
        'pb_hr_workforce_planning.action_wfp_grade',
        'pb_hr_workforce_planning.action_wfp_merit_matrix',
        'pb_hr_workforce_planning.action_wfp_cycle',
        'pb_hr_workforce_planning.action_wfp_tagging_wizard'],
    'pb_settings.item_settings': [
        'base.action_res_users', 'base.action_res_company_form',
        'pb_sidebar.action_pb_sidebar_item', 'pb_sidebar.action_pb_sidebar_section',
        'om_hr_payroll.action_hr_payroll_configuration'],
}


def _split(val):
    return [v.strip() for v in (val or '').split(',') if v.strip()]


@tagged('post_install', '-at_install')
class TestIaCycle5Rail(TransactionCase):
    """The rail as shipped — read back out of the database."""

    def _rec(self, xmlid):
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.with_context(active_test=False) if rec else rec

    def _installed(self, xmlid):
        return xmlid.split('.')[0] in self.installed

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    # ==================================================== the shape of the rail
    def test_the_rail_is_exactly_the_target_table(self):
        """Fresh eyes: five sections, eight items, in this order.

        Read through `get_sidebar_data()` — the payload the rail actually
        renders — rather than through the records, because that is what filters
        on `active` and on the caller's groups. Run as the superuser environment
        the test suite gives us, which bypasses every gate, so what comes back is
        the WHOLE rail rather than one persona's slice.
        """
        data = self.env['pb.sidebar.item'].get_sidebar_data()
        got = [(s['key'], [i['name'] for i in s['items']]) for s in data]
        expected = []
        for key, _seq, _label, items in TARGET_RAIL:
            names = [label for xmlid, _s, _i, label in items
                     if self._installed(xmlid)]
            if names:
                expected.append((key, names))
        self.assertEqual(
            got, expected,
            'the rail is not the Cycle 5 target rail.\n  got: %s\n  want: %s'
            % (got, expected))

    def test_no_item_has_children_on_the_new_rail(self):
        """Eight items and eight destinations. A sub-item is a second level of
        navigation, and Option A's whole claim is that there is one."""
        data = self.env['pb.sidebar.item'].get_sidebar_data()
        for section in data:
            for item in section['items']:
                self.assertFalse(
                    item['children'],
                    '%s has children on the live rail' % item['name'])

    def test_every_live_section_is_where_the_table_says(self):
        Section = self.env['pb.sidebar.section'].with_context(active_test=False)
        for key, seq, show_label, items in TARGET_RAIL:
            if not any(self._installed(x) for x, _s, _i, _l in items):
                continue
            sec = Section.search([('technical_key', '=', key)])
            self.assertEqual(len(sec), 1,
                             'expected exactly one %r section, got %s'
                             % (key, len(sec)))
            self.assertTrue(sec.active, '%s must be live' % key)
            self.assertEqual(sec.sequence, seq, '%s sequence' % key)
            self.assertEqual(sec.show_label, show_label, '%s show_label' % key)

    def test_every_live_item_is_where_the_table_says(self):
        for key, _seq, _label, items in TARGET_RAIL:
            for xmlid, seq, icon, label in items:
                if not self._installed(xmlid):
                    continue
                item = self._rec(xmlid)
                self.assertTrue(item, '%s is missing' % xmlid)
                self.assertTrue(item.active, '%s is not active' % xmlid)
                self.assertEqual(item.sequence, seq, '%s sequence' % xmlid)
                self.assertEqual(item.icon, icon, '%s icon' % xmlid)
                self.assertEqual(item.name, label, '%s label' % xmlid)
                self.assertEqual(item.section_id.technical_key, key,
                                 '%s section' % xmlid)

    def test_the_retired_sections_are_inactive_and_in_the_900_band(self):
        for xmlid, seq in RETIRED_SECTIONS.items():
            sec = self._rec(xmlid)
            self.assertTrue(sec, '%s is missing — retire, never delete' % xmlid)
            self.assertFalse(sec.active, '%s is still on the rail' % xmlid)
            self.assertEqual(sec.sequence, seq, '%s sequence' % xmlid)

    def test_every_retired_item_is_inactive_and_in_the_900_band(self):
        """W18: `active = False` takes an item off the rail but not out of its
        section, and after this cutover almost every retired item's old number
        belongs to something else. So a retirement MOVES; it does not merely
        deactivate."""
        wrong = []
        for xmlid, seq in RETIRED_ITEMS.items():
            if not self._installed(xmlid):
                continue
            item = self._rec(xmlid)
            if not item:
                wrong.append('%s: missing (retire, never delete)' % xmlid)
                continue
            if item.active:
                wrong.append('%s: still active' % xmlid)
            if item.sequence != seq:
                wrong.append('%s: sequence %s, expected %s'
                             % (xmlid, item.sequence, seq))
        self.assertFalse(wrong, 'retirements that did not land:\n  %s'
                                % '\n  '.join(wrong))

    def test_get_sidebar_data_serves_none_of_the_retired_items(self):
        """The end-to-end proof, through the payload the rail renders. Runs as a
        superuser environment, which bypasses every group gate — so anything
        that shows up here is genuinely still on the rail."""
        live = set()
        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            for item in section['items']:
                live.add(item['id'])
                live.update(c['id'] for c in item['children'])
        offenders = []
        for xmlid in RETIRED_ITEMS:
            item = self._rec(xmlid)
            if item and item.id in live:
                offenders.append(xmlid)
        self.assertFalse(offenders, 'still served by the rail: %s' % offenders)

    def test_the_whole_table_still_has_no_sequence_collision(self):
        """W8/W18 over the WHOLE table, retired items included, bucketed by
        (section, parent) because a sub-item's sequence orders it among its
        siblings rather than among the section's top level."""
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search([])
        buckets = {}
        for item in items:
            buckets.setdefault((item.section_id.id, item.parent_id.id), []).append(item)
        clashes = []
        for group in buckets.values():
            seen = {}
            for item in group:
                seen.setdefault(item.sequence, []).append(item)
            for seq, dupes in seen.items():
                if len(dupes) > 1:
                    clashes.append('%s seq %s: %s' % (
                        dupes[0].section_id.technical_key, seq,
                        ', '.join('%s(%s)' % (i.name, i.active) for i in dupes)))
        self.assertFalse(clashes, 'sidebar sequence collisions:\n%s'
                                  % '\n'.join(clashes))

    def test_no_two_sections_share_a_sequence(self):
        """W70 one level up: the ORM orders sections by `sequence, id`, so two
        sections on one number order themselves by whichever module happened to
        install first — a rail that differs between two databases with the same
        code. GROW lives in `pb_learn` and System in `pb_sidebar`, which is
        exactly the cross-module blind spot the rule is about."""
        sections = self.env['pb.sidebar.section'].with_context(
            active_test=False).search([])
        seen = {}
        for sec in sections:
            seen.setdefault(sec.sequence, []).append(sec)
        clashes = {seq: [s.technical_key for s in v]
                   for seq, v in seen.items() if len(v) > 1}
        self.assertFalse(clashes, 'section sequence collisions: %s' % clashes)

    def test_no_two_live_items_share_a_label(self):
        """W28: a rail label is unique across the WHOLE table, not just its
        section — a user reads labels, not sequences, and the twin usually lives
        in another module. Retired items are excluded on purpose: they are not
        on the rail, and several of them legitimately keep a name the cutover
        reused (`Insights` was `item_analytics` before it was the hub)."""
        items = self.env['pb.sidebar.item'].search([])
        seen = {}
        for item in items:
            seen.setdefault(item.name, []).append(item)
        clashes = {n: len(v) for n, v in seen.items() if len(v) > 1}
        self.assertFalse(clashes, 'duplicate live rail labels: %s' % clashes)

    def test_every_retired_item_still_points_at_something_that_resolves(self):
        """W76: "retire, never delete" is only worth anything while re-enabling
        the item would still WORK. This cycle removed no cockpit and no client
        action, so every retirement here is one `active` flag away from coming
        back — and this is what says so."""
        broken = []
        for xmlid in RETIRED_ITEMS:
            item = self._rec(xmlid)
            if not item or not item.action_xmlid:
                continue
            if not self.env.ref(item.action_xmlid, raise_if_not_found=False):
                broken.append('%s -> %s' % (xmlid, item.action_xmlid))
        self.assertFalse(broken, 'retired items pointing at nothing: %s' % broken)

    def test_every_rail_icon_exists_in_the_fixed_set(self):
        """The rail's icon set is a CLOSED dict inlined in `pb_sidebar.js`; an
        unknown name renders a plain circle and logs nothing. `book-open` was
        added in this cycle for the Learn leaf, which used to draw the same
        compass as Mission Control four rows above it."""
        path = os.path.join(get_module_path('pb_sidebar'), 'static', 'src', 'js',
                            'pb_sidebar.js')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        block = re.search(r'const ICONS = \{(.*?)\n\};', body, re.S)
        self.assertTrue(block, 'could not find the ICONS set in pb_sidebar.js')
        known = set(re.findall(r'^\s{4}"?([A-Za-z0-9_-]+)"?\s*:', block.group(1), re.M))
        self.assertIn('book-open', known)
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search([])
        missing = sorted({i.icon for i in items if i.icon and i.icon not in known})
        self.assertFalse(missing, 'rail icons with no path (silent circles): %s'
                                  % missing)


@tagged('post_install', '-at_install')
class TestIaCycle5MatchMatrix(TransactionCase):
    """Active-item highlighting — where Cycle 1's two pinned double-claims die."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    def _rec(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _installed(self, xmlid):
        return xmlid.split('.')[0] in self.installed

    def test_every_live_item_claims_exactly_the_matrix_it_was_given(self):
        for xmlid, tags in MATCH_TAGS.items():
            if not self._installed(xmlid):
                continue
            item = self._rec(xmlid)
            self.assertTrue(item, '%s is missing' % xmlid)
            got = _split(item.match_action_tags)
            self.assertEqual(got, tags, '%s match_action_tags' % xmlid)
        for xmlid, models in MATCH_MODELS.items():
            if not self._installed(xmlid):
                continue
            self.assertEqual(_split(self._rec(xmlid).match_models), models,
                             '%s match_models' % xmlid)
        for xmlid, ids in MATCH_XMLIDS.items():
            if not self._installed(xmlid):
                continue
            self.assertEqual(_split(self._rec(xmlid).match_action_xmlids), ids,
                             '%s match_action_xmlids' % xmlid)

    def test_no_model_is_claimed_by_two_live_items(self):
        """Cycle 1 found `hr.integration.connector` claimed twice (A3), fixed
        that one, and PINNED two more it could not fix without changing the rail:
        `hr.payslip.run` (Approvals vs Pay Runs) and `hr.contract` (Employees vs
        Contracts). Both were benign only because `_buildIndex` walks sections
        and items in sequence order, so the LAST writer won and happened to be
        the item a user would expect. Cycle 5 is the rail change, and the set is
        now empty: `hr.payslip.run` belongs to Pay Run, `hr.contract` to People,
        `hr.integration.connector` to Settings."""
        claims = {}
        for item in self.env['pb.sidebar.item'].search([]):
            for model in _split(item.match_models):
                claims.setdefault(model, []).append(item)
        dupes = {m: sorted(i.name for i in v)
                 for m, v in claims.items() if len(v) > 1}
        self.assertEqual(
            dupes, {},
            'a res_model claimed by more than one live rail item silently picks '
            'a winner (_buildIndex is flat):\n%s'
            % '\n'.join('%s -> %s' % (m, ', '.join(v))
                        for m, v in sorted(dupes.items())))

    def test_no_action_tag_is_claimed_by_two_live_items(self):
        claims = {}
        for item in self.env['pb.sidebar.item'].search([]):
            tags = _split(item.match_action_tags)
            if item.action_tag:
                tags.append(item.action_tag)
            for tag in set(tags):
                claims.setdefault(tag, []).append(item)
        dupes = {t: sorted(i.name for i in v)
                 for t, v in claims.items() if len(v) > 1}
        self.assertFalse(dupes, 'an action tag claimed by more than one live '
                                'rail item:\n%s' % dupes)

    def test_no_action_xmlid_is_claimed_by_two_live_items(self):
        claims = {}
        for item in self.env['pb.sidebar.item'].search([]):
            ids = _split(item.match_action_xmlids)
            if item.action_xmlid:
                ids.append(item.action_xmlid)
            for xmlid in set(ids):
                claims.setdefault(xmlid, []).append(item)
        dupes = {x: sorted(i.name for i in v)
                 for x, v in claims.items() if len(v) > 1}
        self.assertFalse(dupes, 'an action xmlid claimed by more than one live '
                                'rail item:\n%s' % dupes)

    def test_every_claimed_xmlid_resolves_on_this_database(self):
        """A match dimension is a claim on a real surface (W71). One that can
        never match is not harmless: it is a reader being told there is a screen
        somewhere that there is not."""
        broken = []
        for item in self.env['pb.sidebar.item'].search([]):
            for xmlid in _split(item.match_action_xmlids) + (
                    [item.action_xmlid] if item.action_xmlid else []):
                if not self.env.ref(xmlid, raise_if_not_found=False):
                    broken.append('%s -> %s' % (item.name, xmlid))
        self.assertFalse(broken, 'live rail items naming an action that does '
                                 'not resolve: %s' % broken)

    def test_the_representative_highlight_matrix(self):
        """Test 5 of the handover, as an assertion.

        `pb_sidebar.js::_resolveActive` reads three flat indexes in
        xmlid -> tag -> res_model order. This reproduces that resolution in
        Python over the payload `get_sidebar_data()` really returns, for the
        ~20 surfaces a user is most likely to arrive on from a bookmark, and
        asserts each lights exactly ONE rail item — the right one.
        """
        # Build the same three indexes _buildIndex builds, in the same order.
        xmlid_idx, tag_idx, model_idx, names = {}, {}, {}, {}
        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            for item in section['items']:
                names[item['id']] = item['name']
                if item['action_xmlid']:
                    xmlid_idx[item['action_xmlid']] = item['id']
                if item['action_tag']:
                    tag_idx[item['action_tag']] = item['id']
                for x in item['match_action_xmlids']:
                    xmlid_idx[x] = item['id']
                for t in item['match_action_tags']:
                    tag_idx[t] = item['id']
                for m in item['match_models']:
                    model_idx[m] = item['id']

        def resolve(xmlid=None, tag=None, model=None):
            if xmlid and xmlid in xmlid_idx:
                return names[xmlid_idx[xmlid]]
            if tag and tag in tag_idx:
                return names[tag_idx[tag]]
            if model and model in model_idx:
                return names[model_idx[model]]
            return None

        # (what a user opened, how the action identifies itself, which item lights)
        cases = [
            ('the payslips list', dict(model='hr.payslip'), 'Pay Run'),
            ('a pay run', dict(model='hr.payslip.run'), 'Pay Run'),
            ('the payslip review cockpit', dict(tag='pb_payslip_review'), 'Pay Run'),
            ('the pay runs kanban',
             dict(xmlid='pb_payruns.action_pb_payruns_kanban'), 'Pay Run'),
            ('the standalone proration ledger', dict(tag='pb_proration'), 'Pay Run'),
            ('the import cockpit', dict(tag='pb_import'), 'Pay Run'),
            ('the import wizard', dict(tag='pb_import_wizard'), 'Pay Run'),
            ('an employee', dict(model='hr.employee'), 'People'),
            ('a contract', dict(model='hr.contract'), 'People'),
            ('the employee detail cockpit',
             dict(tag='pb_employee_detail'), 'People'),
            ('a planning scenario',
             dict(xmlid='pb_hr_workforce_planning.action_wfp_scenario'), 'People'),
            ('the planning dashboard', dict(tag='wfp_dashboard'), 'People'),
            ('the dashboard', dict(tag='pb_dashboard'), 'Home'),
            ('the approvals cockpit', dict(tag='pb_approval'), 'Home'),
            ('Mission Control', dict(tag='pb_workforce'), 'Workforce'),
            ('the schedule cockpit', dict(tag='pb_schedule'), 'Workforce'),
            ('the analytics explorer', dict(tag='pb_explorer_cockpit'), 'Insights'),
            ('the payroll report', dict(tag='payroll_report_dashboard'), 'Insights'),
            ('government reports', dict(tag='pb_govt_reports'), 'Compliance'),
            ('the audit console', dict(tag='pb_audit'), 'Compliance'),
            ('the connector cockpit',
             dict(tag='pb_import_connector_cockpit'), 'Settings'),
            ('a connector', dict(model='hr.integration.connector'), 'Settings'),
            ('the structures cockpit', dict(tag='pb_structures'), 'Settings'),
            ('the users list', dict(xmlid='base.action_res_users'), 'Settings'),
            ('the formula studio', dict(tag='pb_formula_studio'), 'Settings'),
            ('the learn journey', dict(tag='learn_journey'), 'Learn'),
            ('the Lifecycle hub', dict(tag='pb_lifecycle_hub'), 'Lifecycle'),
            ('the journeys cockpit', dict(tag='pb_journeys'), 'Lifecycle'),
            ('a journey', dict(model='pb.journey.case'), 'Lifecycle'),
        ]
        wrong = []
        for what, how, expected in cases:
            # Skip a case whose target module is not installed here rather than
            # asserting a fact about somebody else's database.
            got = resolve(**how)
            if got is None and expected not in names.values():
                continue
            if got != expected:
                wrong.append('%s (%s) lit %r, expected %r'
                             % (what, how, got, expected))
        self.assertFalse(wrong, 'highlight matrix:\n  %s' % '\n  '.join(wrong))


@tagged('post_install', '-at_install')
class TestIaCycle5Migration(TransactionCase):
    """The migration, and the one thing only a source read can check."""

    MIG = os.path.join(get_module_path('pb_sidebar'), 'migrations', '19.0.3.0.0')

    def _mig(self, half):
        with open(os.path.join(self.MIG, '%s-migrate.py' % half),
                  encoding='utf-8') as fh:
            return fh.read()

    def test_the_module_version_is_the_one_the_migration_lives_under(self):
        """Odoo only runs migration scripts on a version CHANGE, so a migration
        directory whose name is not the manifest's version is a script that
        never runs — and nothing says so."""
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'pb_sidebar')], limit=1)
        self.assertTrue(module)
        self.assertEqual(module.latest_version, '19.0.3.0.0')
        self.assertTrue(os.path.isdir(self.MIG))

    def test_the_migration_agrees_with_every_data_file(self):
        """W27's warning, made a gate.

        Six items and three records are HAND-APPLIED by the post-migrate,
        because five of them live in frozen data files and four belong to
        modules that may not be in the `-u`. A hand-applied value is one that can
        drift from the XML it stands in for, silently, and only on databases
        that took a particular upgrade path. So each table is read back out of
        the file that declares the record.
        """
        post = self._mig('post')
        root = os.path.dirname(get_module_path('pb_sidebar'))

        def data_file(module, xmlid_name):
            """The data file in `module` that declares `xmlid_name`."""
            base = os.path.join(root, module)
            for sub, _dirs, files in os.walk(base):
                if '__pycache__' in sub:
                    continue
                for f in files:
                    if not f.endswith('.xml'):
                        continue
                    path = os.path.join(sub, f)
                    with open(path, encoding='utf-8') as fh:
                        body = fh.read()
                    if 'id="%s"' % xmlid_name in body:
                        return body
            return None

        mismatches = []
        for module, name, seq in re.findall(
                r"\('([\w.]+)', '(\w+)', (\d+)\),", post):
            body = data_file(module, name)
            if body is None:
                mismatches.append('%s.%s: no data file declares it' % (module, name))
                continue
            block = re.search(r'<record id="%s".*?</record>' % name, body, re.S)
            self.assertTrue(block, '%s.%s: record block not found' % (module, name))
            block = block.group(0)
            if '<field name="sequence">%s</field>' % seq not in block:
                mismatches.append('%s.%s: migration says seq %s, the data file '
                                  'does not' % (module, name, seq))
            if '<field name="active" eval="False"/>' not in block:
                mismatches.append('%s.%s: migration retires it, the data file '
                                  'does not' % (module, name))
        self.assertFalse(mismatches, 'the post-migrate and the data files '
                                     'disagree:\n  %s' % '\n  '.join(mismatches))

    def test_the_migration_is_guarded_so_a_second_run_writes_nothing(self):
        """Idempotency, asserted at the source as well as proven by running it
        twice on a clone: a retirement writes only while the record is still on
        a pre-cutover sequence, and a move only while it is not already where it
        belongs. That guard is also what stops a later migration overruling an
        administrator who deliberately re-enabled something."""
        post = self._mig('post')
        self.assertIn('if rec.sequence >= 900:', post)
        self.assertIn('if rec.sequence == sequence:', post)
        self.assertIn('rec.section_id == section and rec.sequence == sequence',
                      post)

    def test_the_pre_migrate_unfreezes_only_records_from_unfrozen_files(self):
        """The pre half clears `ir_model_data.noupdate` so the data files can
        apply in the same upgrade (W27). It must not clear it for the five
        records whose files are `noupdate="1"` ON PURPOSE — those are moved by
        hand instead, and unfreezing them would quietly change what a future
        `-u` of their module does to them."""
        pre = self._mig('pre')
        for frozen in ('item_pay_deliver', 'item_audit_console', 'item_tenants',
                       'item_bank_verification', 'item_young_workers'):
            self.assertNotIn(frozen, pre,
                             '%s comes from a deliberately frozen file' % frozen)

    def test_none_of_the_cutover_records_is_left_frozen(self):
        """W13.1, read back from the column that decides it: a stored
        `ir_model_data.noupdate` makes `-u` a silent no-op, EXIT 0 and all."""
        frozen = []
        for xmlid in list(RETIRED_ITEMS) + list(RETIRED_SECTIONS):
            module, name = xmlid.split('.', 1)
            if module in ('pb_pay_delivery', 'pb_audit', 'pb_tenants',
                          'pb_bank_ocr', 'pb_young_worker'):
                continue                # frozen on purpose, moved by hand
            imd = self.env['ir.model.data'].sudo().search([
                ('module', '=', module), ('name', '=', name),
            ], limit=1)
            if imd and imd.noupdate:
                frozen.append(xmlid)
        self.assertFalse(frozen, 'frozen records — the data file cannot reach '
                                 'them and nothing says so: %s' % frozen)


@tagged('post_install', '-at_install')
class TestIaCycle5RailVisibility(TransactionCase):
    """The rail shows itself on any surface it claims."""

    def test_visibility_asks_the_match_indexes_and_not_only_the_name(self):
        """Found on the Cycle-5 live run, by the highlight matrix.

        `_resolveVisibility` decided whether to render the rail from the current
        app plus a NAME test — a tag or xmlid that starts with `pb_`, or a model
        that looks like a payslip. There is exactly one client action in the
        product that test gets wrong: the Payroll Report's tag is
        `payroll_report_dashboard`. Opening it by bookmark therefore hid the
        whole sidebar, and the cutover's highlight matrix could not light the
        Insights item — not because the claim was missing, but because there was
        no rail on screen to light.

        Asking the MATCH INDEXES is the same question without the guesswork, and
        it ties the two halves together: a surface a rail item claims is a
        surface the rail belongs on, so visibility and highlighting can no
        longer disagree.
        """
        path = os.path.join(get_module_path('pb_sidebar'), 'static', 'src', 'js',
                            'pb_sidebar.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('_isClaimed(action)', src)
        self.assertIn('this._isClaimed(a)', src)
        # It reads the SAME three indexes the highlight resolves from — a second
        # opinion about what the rail owns is the defect, not the fix.
        body = re.search(r'_isClaimed\(action\) \{(.*?)\n    \}', src, re.S)
        self.assertTrue(body)
        for idx in ('_xmlidIndex', '_tagIndex', '_modelIndex'):
            self.assertIn(idx, body.group(1))

    def test_the_payroll_report_tag_really_is_the_one_the_name_test_misses(self):
        """The reason the general fix was worth making rather than special-casing
        one string: assert that this tag is claimed by a rail item AND that it
        fails the name heuristic, so the two facts are pinned together."""
        claimants = [i for i in self.env['pb.sidebar.item'].search([])
                     if 'payroll_report_dashboard' in _split(i.match_action_tags)]
        self.assertEqual(len(claimants), 1)
        self.assertFalse('payroll_report_dashboard'.startswith('pb_'))


@tagged('post_install', '-at_install')
class TestIaCycle5HomeButton(TransactionCase):
    """navigateHome: the rail's own logo button."""

    def test_the_home_action_is_the_first_indexed_action_xmlid(self):
        """`pb_sidebar.js::_buildIndex` sets `_homeAction` from the FIRST indexed
        item that carries an `action_xmlid`, walking sections in order and items
        in order; `navigateHome()` falls back to a raw `/odoo` redirect without
        one. The Home item is the first item of the first section AND it carries
        an xmlid, so the rail's home button lands on the Home hub — which is the
        whole reason `pb_home_hub` declares an `ir.actions.client` record rather
        than relying on its tag.
        """
        first = None
        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            for item in section['items']:
                if item['action_xmlid']:
                    first = item
                    break
                for child in item['children']:
                    if child['action_xmlid']:
                        first = child
                        break
                if first:
                    break
            if first:
                break
        self.assertTrue(first, 'no rail item carries an action_xmlid at all — '
                               'navigateHome would fall back to /odoo')
        home = self.env.ref('pb_home_hub.item_home', raise_if_not_found=False)
        if not home:
            self.skipTest('pb_home_hub is not installed here')
        self.assertEqual(first['id'], home.id,
                         'the first indexed action_xmlid belongs to %r, so the '
                         'home button lands there instead of on Home'
                         % first['name'])
        self.assertEqual(first['action_xmlid'],
                         'pb_home_hub.action_pb_home_hub')
        self.assertTrue(self.env.ref(first['action_xmlid'],
                                     raise_if_not_found=False))
