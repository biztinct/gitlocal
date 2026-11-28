# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA redesign Cycle 3 — the one-door law, and the ledgers that made it possible.

A closed door is not a feature you can see. Every one of the seven doors this
cycle shut looked exactly like a working button the day before, and re-opening
one is a two-line change nobody would call a regression — a tile added back to a
launch list, an `openLink` restored because "the raw list has a group-by". So the
enumeration is a TEST, not a paragraph in a report: `test_the_door_enumeration_
is_exactly_the_agreed_list` walks every `pb_*` module's client-side source and
fails on any new reference to the raw satellite actions.

Two things it deliberately does NOT assert:

  * that the legacy actions are gone. They are not, and must not be — hidden
    menus and other callers keep working, and this cycle replaced the DOORS, not
    the models (W76's rule about retirement records is about surfaces that were
    DELETED; nothing here was);
  * that the source never says those names at all. A word-shaped gate fails on
    the documentation that explains the rule (W48's corollary), and this
    module's Python has to name each legacy action to record what its ledger
    replaced. So the gate reads the CLIENT-SIDE files, where a door lives.
"""
import os
import re

from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# The three act_windows the raw-list tiles used to open, and the connector list
# Import used to launch.
RAW_SATELLITE_ACTIONS = (
    'pb_hr_payroll_formula.action_field_mapping',
    'pb_hr_payroll_formula.action_api_data_store',
    'pb_hr_payroll_formula.action_api_transformation_rule',
)
RAW_CONNECTOR_LIST = 'pb_hr_payroll_formula.action_integration_connector'
ONBOARDING_MODAL = 'pb_hr_payroll_formula.action_hr_integration_onboarding'

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")

# An OWL template expression is compiled against the COMPONENT's context and
# nothing else: a bare `String(x)` becomes `ctx.String(x)` and the surface dies
# at mount with "ctx.String is not a function". There is no lint for it and the
# module's own Python tests cannot see it — an OWL template error surfaces only
# at runtime (C18.71/W10), which is how this one reached the live pass.
# Matched inside `t-*` ATTRIBUTE VALUES only, so the prose above and any
# docstring may say the word (W48's corollary about word-shaped gates).
_RE_T_ATTR = re.compile(r'\st-[a-z-]+="([^"]*)"')
_TEMPLATE_GLOBALS = ('String(', 'Number(', 'Boolean(', 'parseInt(', 'parseFloat(',
                     'Object.', 'JSON.', 'Math.', 'Array.', 'Date(')


def _client_sources(module):
    """Every JS and XML file under a module's `static/src` — where doors live."""
    path = get_module_path(module, display_warning=False)
    if not path:
        return []
    root = os.path.join(path, 'static', 'src')
    out = []
    for base, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(('.js', '.xml')):
                out.append(os.path.join(base, f))
    return out


def _pb_modules():
    """Every `pb_*` module directory beside this one."""
    here = get_module_path('pb_integrations')
    parent = os.path.dirname(here)
    return sorted(d for d in os.listdir(parent)
                  if d.startswith('pb_')
                  and os.path.isdir(os.path.join(parent, d, 'static')))


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestOneDoor(TransactionCase):
    """Where a connector and its satellites can be reached FROM."""

    def test_import_no_longer_launches_the_raw_connector_list(self):
        src = _read(get_module_path('pb_import') + '/models/pb_import.py')
        launch = src.split('LAUNCH_CANDIDATES = [')[1].split(']')[0]
        self.assertNotIn(
            RAW_CONNECTOR_LIST, launch,
            "the Import cockpit's launch tiles must not include the raw "
            "connector list again — connectors have one home")

    def test_import_no_longer_renders_a_connectors_panel(self):
        tpl = _read(get_module_path('pb_import') + '/static/src/xml/import.xml')
        js = _read(get_module_path('pb_import') + '/static/src/js/import.js')
        for needle in ('pbm-conn ', 'pbm-conns', 'openConnector'):
            self.assertNotIn(needle, tpl + js,
                             "Import's connector panel is closed; found %r" % needle)
        # …and the door that replaced it is really there. A gate that only
        # forbids would pass perfectly on a cockpit that offers nothing at all.
        self.assertIn('manageConnectors', js)
        self.assertIn('pb_integrations', js)

    def test_the_connector_cockpit_links_land_in_the_ledgers(self):
        tpl = _read(get_module_path('pb_import_advanced')
                    + '/static/src/xml/connector_cockpit.xml')
        for needle in ('action_view_mappings', 'action_view_data_store'):
            self.assertNotIn(
                needle, tpl,
                "the connector cockpit must not open the raw %s list" % needle)
        # Each of the three satellite tables is still reachable IN the cockpit.
        # Asserted by KIND rather than by a count: Integrations Cycle 1 added a
        # fourth door (per-feed "View data", which deep-links the store ledger
        # scoped to one data type), and a `count == 3` would have failed on a
        # cycle that added a door rather than removed one.
        for kind in ('mapping', 'store', 'rule'):
            self.assertIn(
                "this.openLedger('%s')" % kind, tpl,
                "the %s ledger is no longer reachable from the connector "
                "cockpit" % kind)

    def test_the_native_form_escape_moved_into_the_admin_overflow(self):
        """Integrations Cycle 1 REVERSED the assertion that used to live above.

        This test asserted the literal `'Open record'` — a toolbar button, the
        second thing on the page, offered to every operator. It was Cycle 3's
        way of recording "the native-form escape is relabelled, not hidden",
        and that was right while the cockpit had nothing else to show for the
        connector. It is now wrong for the same reason: dropping into Odoo's
        raw form is an ADMINISTRATOR's tool, and a cockpit that offers it beside
        "Test connection" teaches every operator that it is a normal step.

        Reversed AT THE SITE with the reasoning rather than quietly deleted
        (W76.3), and it still asserts the door EXISTS — a gate that only forbade
        would be satisfied by removing the escape altogether, which would leave
        an admin with no way to reach a field the cockpit does not render (W5).
        """
        tpl = _read(get_module_path('pb_import_advanced')
                    + '/static/src/xml/connector_cockpit.xml')
        js = _read(get_module_path('pb_import_advanced')
                   + '/static/src/js/connector_cockpit.js')
        self.assertNotIn(
            'Open record', tpl,
            "the native form is no longer a toolbar button")
        self.assertIn('pbcc-kebab', tpl, "the overflow menu is gone")
        self.assertIn('Open native record', tpl,
                      "the escape must still exist, one click deeper")
        # …and it is gated on the SAME system-group flag that gates the
        # credentials panel, so "may edit this connector's secrets" and "may
        # open its raw record" cannot drift apart into two answers.
        self.assertIn('t-if="canAdmin" class="pbcc-kebab"', tpl)
        self.assertIn('openAdvancedForm', js)
        self.assertIn(
            'credentials.editable', js,
            "canAdmin must be derived from the payload's editable flag")

    def test_the_mapping_studio_door_is_open_and_arrives_configured(self):
        """Integrations Cycle 2 adds a door — deliberately, and here.

        Cycle 1 shipped the feeds strip with NO map button and said so in the
        template, because the studio did not exist and "a door that opens onto
        nothing is worse than no door" (W29). The studio exists now, so the
        button ships — and the thing worth gating is not that it EXISTS but
        that it arrives CONFIGURED. A deep link that lands the studio on its
        own defaults would send the user to a screen that looks right and is
        mapping the wrong connector, which is this codebase's worst bug class
        (W76.3/W117) and is invisible in a screenshot.
        """
        tpl = _read(get_module_path('pb_import_advanced')
                    + '/static/src/xml/connector_cockpit.xml')
        js = _read(get_module_path('pb_import_advanced')
                   + '/static/src/js/connector_cockpit.js')
        self.assertIn('this.openMapping(ep)', tpl,
                      "a feed must be mappable from the strip it lives in")
        self.assertIn('this.openMapping(null)', tpl,
                      "…and the connector as a whole, for a reader who has not "
                      "picked a feed yet")
        self.assertIn('hasMapping', tpl,
                      "the button is probed against the actions registry, so a "
                      "database without pb_formula_studio renders no dead door")
        for key in ('pb_connector', 'pb_endpoint', 'pb_mode'):
            self.assertIn(key, js,
                          "the door must carry %s or the studio opens on its "
                          "own defaults" % key)
        # …and it comes back. A one-way door is not a door (W5).
        openmap = js.split('openMapping(ep) {', 1)[1].split('\n    }', 1)[0]
        self.assertIn('back:', openmap)
        self.assertIn('SELF_TAG', openmap)

    def test_the_board_count_is_a_door_into_the_studio(self):
        js = _read(get_module_path('pb_integrations')
                   + '/static/src/js/integrations.js')
        tpl = _read(get_module_path('pb_integrations')
                    + '/static/src/xml/integrations.xml')
        self.assertIn('openMappingStudio', js)
        self.assertIn('pb_mapping_studio', js)
        self.assertIn('itg-maplink', tpl,
                      "the mappings count on a connector card opens the studio")
        # The card itself opens the connector cockpit, so the inner button has
        # to stop the click or one click does two navigations.
        self.assertIn('t-on-click.stop="() => this.openMappingStudio(c)"', tpl)

    def test_the_studio_action_record_carries_a_name(self):
        act = self.env.ref('pb_formula_studio.action_pb_mapping_studio',
                           raise_if_not_found=False)
        self.assertTrue(act, "the Mapping Studio needs an action RECORD, not "
                             "just a registry tag — a bare tag reaches the "
                             "action service with no name and every breadcrumb "
                             "through it reads 'Unnamed'")
        self.assertEqual(act.tag, 'pb_mapping_studio')
        self.assertTrue(act.name)

    def test_the_integrations_board_has_no_raw_list_tiles_left(self):
        for path in _client_sources('pb_integrations'):
            src = _read(path)
            for action in RAW_SATELLITE_ACTIONS:
                self.assertNotIn(
                    action, src,
                    "%s still names %s — the satellites are IN this cockpit now"
                    % (os.path.basename(path), action))

    def test_nothing_in_payobook_opens_the_onboarding_modal(self):
        offenders = []
        for module in _pb_modules():
            for path in _client_sources(module):
                if ONBOARDING_MODAL in _read(path):
                    offenders.append('%s/%s' % (module, os.path.basename(path)))
        self.assertFalse(
            offenders,
            "the stock onboarding modal stays registered and nothing in "
            "Payobook opens it; these still do: %s" % offenders)

    def test_the_door_enumeration_is_exactly_the_agreed_list(self):
        """No `pb_*` surface may open a raw satellite list.

        This is IA Cycle 3 in one assertion. Import's tile, the board's three
        link tiles and the connector cockpit's two links were the five
        client-side doors; the two that remain are server-side (`get_link` for
        the payroll-import form) and the hidden legacy menus, neither of which
        is a `pb_*` client source.

        Integrations Cycle 2 added THREE doors and none of them belongs here:
        the Settings card, the cockpit's "Map fields" and the board's mappings
        count all open `pb_mapping_studio`, a cockpit — which is the shape this
        gate exists to encourage. The list this test enumerates is the RAW-LIST
        one, and it is unchanged. The new doors are gated positively, one test
        each, above.
        """
        offenders = []
        for module in _pb_modules():
            for path in _client_sources(module):
                src = _read(path)
                for action in RAW_SATELLITE_ACTIONS + (RAW_CONNECTOR_LIST,):
                    if action in src:
                        offenders.append('%s/%s -> %s'
                                         % (module, os.path.basename(path), action))
        self.assertFalse(offenders, "raw-list doors are back: %s" % offenders)

    def test_the_legacy_actions_are_still_registered(self):
        # The complement, and it matters: a gate that only forbids would be
        # satisfied by DELETING the actions, which would break the hidden menus
        # and every other caller. The models keep their doors; Payobook stopped
        # using them.
        for xmlid in RAW_SATELLITE_ACTIONS + (RAW_CONNECTOR_LIST, ONBOARDING_MODAL):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                "%s must remain registered — this cycle replaced doors, not "
                "models" % xmlid)

    def test_both_client_actions_exist(self):
        self.assertEqual(
            self.env.ref('pb_integrations.action_pb_integrations').tag,
            'pb_integrations')
        self.assertEqual(
            self.env.ref('pb_integrations.action_pb_integration_onboarding').tag,
            'pb_integration_onboarding')

    def test_no_template_expression_calls_a_javascript_global(self):
        offenders = []
        for path in _client_sources('pb_integrations'):
            if not path.endswith('.xml'):
                continue
            for expr in _RE_T_ATTR.findall(_read(path)):
                for g in _TEMPLATE_GLOBALS:
                    if g in expr:
                        offenders.append('%s: %s' % (os.path.basename(path), expr))
        self.assertFalse(
            offenders,
            "an OWL template resolves every identifier against the component, "
            "so a global becomes ctx.<name> and the surface dies at mount. Put "
            "it in a method: %s" % offenders)

    def test_no_python_style_implicit_string_concatenation(self):
        # One unparseable JS file blanks web.assets_backend for every user, with
        # a clean server log and a 200 on the bundle (W74).
        for path in _client_sources('pb_integrations'):
            if not path.endswith('.js'):
                continue
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(_read(path)),
                "%s has two adjacent string literals across a newline — that is "
                "Python, and in JavaScript it is a SyntaxError"
                % os.path.basename(path))


@tagged('post_install', '-at_install')
class TestLedgers(TransactionCase):
    """The three satellite tables, as in-cockpit grids."""

    def test_every_kind_returns_a_grid(self):
        for kind in ('mapping', 'store', 'rule'):
            d = self.env['pb.integrations'].get_ledger(kind)
            self.assertTrue(d['columns'], "%s has no columns" % kind)
            self.assertIn('total', d)
            self.assertIn('shown', d)
            self.assertTrue(d['title'], "%s has no title" % kind)
            self.assertTrue(d['empty'], "%s has no empty state" % kind)
            for r in d['rows']:
                self.assertEqual(
                    len(r['cells']), len(d['columns']),
                    "%s: a row's cells must line up with the columns, or the "
                    "table silently shifts a column left" % kind)
                self.assertIn('label', r['badge'])
                self.assertIn('tone', r['badge'])

    def test_an_unknown_kind_is_an_empty_grid_and_never_a_table_lookup(self):
        # `kind` comes from the browser. It is looked up in a whitelist rather
        # than used to index `self.env`, so a forged value cannot point this at
        # another model.
        d = self.env['pb.integrations'].get_ledger('res_users')
        self.assertEqual(d['rows'], [])
        self.assertEqual(d['columns'], [])
        self.assertEqual(self.env['pb.integrations'].get_ledger_detail('res_users', 1), {})

    def test_no_row_names_a_connector_the_caller_cannot_read(self):
        """The bug the first live run found, gated.

        All three satellites reach their connector by many2one and none carries
        a company of its own, while `hr.integration.connector` has a
        multi-company record rule. An unscoped ledger therefore rendered
        `connector_id.name` for a row the caller may not read, raised, and the
        client showed "This table could not be loaded" — one unreadable row took
        the whole table with it.
        """
        readable = set(self.env['pb.integrations']._readable_connectors())
        for kind, spec in (('mapping', 'hr.integration.field.mapping'),
                           ('store', 'hr.api.data.store'),
                           ('rule', 'hr.api.transformation.rule')):
            d = self.env['pb.integrations'].get_ledger(kind)
            ids = [r['id'] for r in d['rows']]
            if not ids:
                continue
            recs = self.env[spec].with_context(active_test=False).browse(ids)
            for r in recs:
                self.assertIn(
                    r.connector_id.id, readable,
                    "%s row %s belongs to a connector this caller cannot read"
                    % (kind, r.id))

    def test_a_deep_link_cannot_widen_the_scope(self):
        # The connector id comes from the browser. Pointing it at a connector
        # the record rules hide must return nothing, not that connector's rows.
        every = self.env['hr.integration.connector'].with_context(
            active_test=False).sudo().search([]).ids
        readable = set(self.env['pb.integrations']._readable_connectors())
        hidden = [i for i in every if i not in readable]
        if not hidden:
            self.skipTest("this persona can read every connector")
        d = self.env['pb.integrations'].get_ledger('mapping', hidden[0])
        self.assertEqual(d['rows'], [])
        self.assertEqual(d['total'], 0)

    def test_the_connector_scope_really_filters(self):
        conn = self.env['hr.integration.connector'].search([], limit=1)
        if not conn:
            self.skipTest("no connector on this database")
        M = self.env['hr.integration.field.mapping']
        if not M.search_count([('connector_id', '=', conn.id)]):
            self.skipTest("that connector has no mappings")
        scoped = self.env['pb.integrations'].get_ledger('mapping', conn.id)
        every = self.env['pb.integrations'].get_ledger('mapping')
        self.assertLessEqual(scoped['total'], every['total'])
        self.assertEqual(
            scoped['total'], M.search_count([('connector_id', '=', conn.id)]))

    def test_a_row_opens_a_drawer_with_sections(self):
        M = self.env['hr.integration.field.mapping'].search([], limit=1)
        if not M:
            self.skipTest("no field mappings on this database")
        d = self.env['pb.integrations'].get_ledger_detail('mapping', M.id)
        self.assertEqual(d['res_model'], 'hr.integration.field.mapping')
        self.assertTrue(d['title'])
        self.assertTrue(d['sections'], "a drawer with no sections is a dead row")
        for sec in d['sections']:
            self.assertTrue(sec['fields'],
                            "an empty section is noise in a 320px panel")

    def test_a_deleted_row_is_an_empty_panel_not_a_traceback(self):
        self.assertEqual(
            self.env['pb.integrations'].get_ledger_detail('mapping', 2 ** 31 - 1), {})

    def test_a_boolean_renders_as_yes_and_no_not_as_one_and_zero(self):
        # `isinstance(True, int)` is True, so any ordering that tests numbers
        # first turns Yes into a 1 — and any ordering that lumps the two bools
        # together renders True as "No".
        sec = self.env['pb.integrations']._section('X', [
            {'label': 'on', 'value': True},
            {'label': 'off', 'value': False, 'keep_false': True},
            {'label': 'dropped', 'value': False},
            {'label': 'zero', 'value': 0},
        ])
        self.assertEqual([(f['label'], f['value']) for f in sec['fields']],
                         [('on', 'Yes'), ('off', 'No')])

    def test_the_ledgers_never_sudo(self):
        # Read with the caller's own rights: if the user could open the list,
        # they can open the ledger; if not, the ledger is exactly as empty as
        # the list would have been (W12).
        src = _read(get_module_path('pb_integrations') + '/models/pb_integrations.py')
        self.assertNotIn('sudo(', src)
        self.assertIn('check_access', src,
                      "the per-click detail must ask the ORM, not assume")

    def test_a_payload_preview_is_bounded(self):
        from odoo.addons.pb_integrations.models.pb_integrations import _payload_preview
        pairs, more = _payload_preview({str(i): 'x' * 400 for i in range(50)})
        self.assertEqual(len(pairs), 12)
        self.assertEqual(more, 38)
        self.assertTrue(all(len(v) <= 120 for _k, v in pairs),
                        "a 320px drawer may not be handed an unbounded blob")
        self.assertEqual(_payload_preview(None), ([], 0))
        self.assertEqual(_payload_preview([1, 2, 3]), ([], 0))


@tagged('post_install', '-at_install')
class TestOnboardingFlow(TransactionCase):
    """The stepped flow over the existing transient."""

    def test_start_creates_a_transient_and_no_connector(self):
        before = self.env['hr.integration.connector'].search_count([])
        d = self.env['pb.integration.onboarding'].start()
        self.assertTrue(d['wizard_id'])
        self.assertEqual(d['step'], 'vendor')
        self.assertEqual(d['step_index'], 0)
        self.assertTrue(d['vendors'], "the vendor list drives step 1")
        self.assertEqual(
            self.env['hr.integration.connector'].search_count([]), before,
            "the flow's MOUNT must not create a connector — mount hooks read, "
            "event handlers write (W21)")

    def test_it_never_hands_back_a_credential(self):
        d = self.env['pb.integration.onboarding'].start()
        w = self.env['hr.integration.onboarding.wizard'].browse(d['wizard_id'])
        w.write({'connector_type': 'demo', 'api_key': 'super-secret-value',
                 'client_secret': 'another-secret'})
        state = self.env['pb.integration.onboarding'].get_state(w.id)
        blob = str(state)
        self.assertNotIn('super-secret-value', blob)
        self.assertNotIn('another-secret', blob)
        self.assertTrue(state['has_api_key'])
        self.assertTrue(state['has_client_secret'])

    def test_a_forged_field_cannot_write_a_result(self):
        # `applied_count` / `summary_html` are the wizard's OUTPUTS. A call that
        # could set them would let a caller manufacture a plausible outcome for
        # a step it never ran.
        d = self.env['pb.integration.onboarding'].start()
        self.env['pb.integration.onboarding'].save_auth(
            d['wizard_id'], {'applied_count': 99, 'name': 'IA-C3 probe'})
        w = self.env['hr.integration.onboarding.wizard'].browse(d['wizard_id'])
        self.assertEqual(w.applied_count, 0)
        self.assertEqual(w.name, 'IA-C3 probe')

    def test_an_empty_vendor_is_refused_in_words(self):
        # The wizard's own guard raises through `models.ValidationError`, which
        # Odoo 19 does not export — so reaching it answers with an AttributeError
        # traceback. The facade asks first, in a sentence.
        d = self.env['pb.integration.onboarding'].start()
        with self.assertRaises(UserError):
            self.env['pb.integration.onboarding'].choose_vendor(d['wizard_id'], {})

    def test_an_expired_flow_says_so(self):
        with self.assertRaises(UserError):
            self.env['pb.integration.onboarding'].get_state(2 ** 31 - 1)

    def test_the_flow_walks_the_same_step_order_as_the_transient(self):
        from odoo.addons.pb_integrations.models.pb_onboarding import STEPS
        wiz = self.env['hr.integration.onboarding.wizard']
        self.assertEqual(
            STEPS, [k for k, _v in wiz._fields['step'].selection],
            "two copies of a sequence is how a Back button ends up one step "
            "out of phase")
