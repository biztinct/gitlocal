# -*- coding: utf-8 -*-
"""pb_people_hub — the gates, and the promises that are absences.

The load-bearing test in this file used to prove a NEGATIVE: that the Plan
lens changed nothing in the old workforce planning module. That module has
been retired, so the ruling it enforced is spent and the test is gone with it.
What replaces it is the OTHER negative: that no file in this module still
names the retired module or any of its models, because a single leftover
reference is a screen that opens nothing.

Every source gate reads `_code(src)` — the file with its comments removed —
because a word-shaped gate fails on the documentation that explains the rule
(W48's corollary, promoted to a required helper by W101).
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


def _hub(*parts):
    return _read(HERE, *parts)


def _code(src):
    """The file with its COMMENTS removed — both `//` and `/* … */`."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src[i] in '"\'`':
            q = src[i]
            out.append(q)
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(q)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


def _js_list(src, name):
    m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
    assert m, "no such exported list: %s" % name
    return re.findall(r'"([^"]+)"', m.group(1))


@tagged('post_install', '-at_install')
class TestPeopleHubGates(TransactionCase):
    """W95: every gate is derived from the ACL of the model behind the door."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRC = _hub('static', 'src', 'js', 'people_hub.js')
        cls.Access = cls.env['ir.model.access']

    def _read_groups(self, model):
        """The group xmlids `ir.model.access` grants READ on `model`."""
        rows = self.Access.sudo().search([
            ('model_id.model', '=', model), ('perm_read', '=', True),
        ])
        out = set()
        for row in rows:
            if not row.group_id:
                continue
            data = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'res.groups'), ('res_id', '=', row.group_id.id),
            ], limit=1)
            if data:
                out.add('%s.%s' % (data.module, data.name))
        return out

    def test_the_two_cockpit_lenses_match_their_models_acls_exactly(self):
        for name, model in (('EMPLOYEE_GATE', 'hr.employee'),
                            ('CONTRACT_GATE', 'hr.contract')):
            declared = set(_js_list(self.SRC, name))
            acl = self._read_groups(model)
            self.assertTrue(acl, '%s has no ACL rows to derive from' % model)
            self.assertEqual(
                declared, acl,
                '%s and %s\'s read ACL disagree; lens-only=%s acl-only=%s'
                % (name, model, declared - acl, acl - declared))

    def test_the_lens_gates_are_not_the_retired_rail_items_gates(self):
        """The rail gated Employees and Contracts at the pb_hr_payroll_base
        officer/manager/super tiers — a DIFFERENT group family from the one the
        ACL grants. A persona holding the payroll tier and not the HR one saw
        the item, clicked it and got an access dialog: W29's door that can only
        produce an error, which the rail has been shipping. This asserts the new
        gate did not simply inherit it."""
        for name in ('EMPLOYEE_GATE', 'CONTRACT_GATE'):
            for xmlid in _js_list(self.SRC, name):
                self.assertFalse(
                    xmlid.startswith('pb_hr_payroll_base.'),
                    '%s copied the rail item\'s gate instead of the ACL' % name)

    def test_every_gate_group_exists_on_this_database(self):
        names = set(_js_list(self.SRC, 'EMPLOYEE_GATE'))
        names |= set(_js_list(self.SRC, 'CONTRACT_GATE'))
        plan = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        names |= set(re.findall(r'"(pb_decision_room\.\w+)"', plan))
        for xmlid in sorted(names):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'a gate names a group that does not exist here: %s' % xmlid)


@tagged('post_install', '-at_install')
class TestPlanLensIsAMountPoint(TransactionCase):
    """The Plan lens holds a planning PRODUCT, and nothing of its own."""

    def test_nothing_in_this_module_names_the_retired_planning_module(self):
        """The negative that matters now the old module is gone.

        A leftover action id opens a blank screen, a leftover group xmlid
        gates a lens on a permission nobody can hold, and neither of them
        errors anywhere a person would see. Only a grep can tell "we removed
        it" from "we meant to".
        """
        offenders = []
        for base, _dirs, files in os.walk(HERE):
            if '__pycache__' in base:
                continue
            if os.sep + 'tests' in base + os.sep:
                continue
            for name in files:
                if not name.endswith(('.py', '.js', '.xml', '.csv')):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding='utf-8') as handle:
                    body = handle.read()
                if name.endswith('.js'):
                    body = _code(body)
                for word in ('pb_hr_workforce_planning', 'wfp.', 'wfp_'):
                    if word in body:
                        offenders.append('%s: %s' % (name, word))
        self.assertFalse(
            offenders,
            'the People hub still names the retired planning module: %s'
            % offenders)

    def test_the_manifest_no_longer_depends_on_the_planning_module(self):
        manifest = ast.literal_eval(_hub('__manifest__.py'))
        self.assertNotIn('pb_hr_workforce_planning', manifest['depends'])

    def test_the_plan_gate_is_the_planning_rooms_own_roles(self):
        """A lens whose gate names groups that no longer exist is a lens
        nobody is ever offered — the silent kind of dead end."""
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        gate = _js_list(code, 'PLAN_GATE')
        self.assertTrue(gate, 'the Plan lens has no gate at all')
        for xmlid in gate:
            self.assertTrue(xmlid.startswith('pb_decision_room.'),
                            'the Plan gate should name the planning room: %s'
                            % xmlid)
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'the Plan gate names a group that does not exist here: %s'
                % xmlid)

    def test_the_launcher_owns_no_cards_and_no_facade(self):
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertNotIn('PLAN_CARDS', code,
                         'the legacy card grid is retired')
        self.assertNotIn('embedded: true', code)
        self.assertFalse(os.path.isdir(os.path.join(HERE, 'models')),
                         'the hub owns no server code at all')

    def test_the_hero_registry_is_still_the_seam(self):
        """`pb_decision_room` registers itself here; this module may never
        import it back, because the dependency runs the other way."""
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertIn('pb_people_hub_plan_hero', code)
        self.assertNotIn('@pb_decision_room/', code)


@tagged('post_install', '-at_install')
class TestPeopleHubStatic(TransactionCase):
    """The shell contract, and the promises that are absences."""

    def test_the_lens_order_matches_the_mockup(self):
        keys = re.findall(r'key: "(\w+)", icon: "(\w+)", label:',
                          _hub('static', 'src', 'js', 'people_hub.js'))
        self.assertEqual(
            keys,
            [('employees', 'users'), ('contracts', 'file'),
             ('plan', 'trendingUp')])

    def test_the_lens_persistence_key_is_namespaced_per_hub(self):
        self.assertIn('key: "people"', _hub('static', 'src', 'js', 'people_hub.js'))

    def test_the_hub_action_exists_and_is_named(self):
        act = self.env.ref('pb_people_hub.action_pb_people_hub')
        self.assertEqual(act.tag, 'pb_people_hub')
        self.assertEqual(act.name, 'People')

    def test_the_hub_ships_no_menu(self):
        act = self.env.ref('pb_people_hub.action_pb_people_hub')
        self.assertFalse(
            self.env['ir.ui.menu'].search(
                [('action', '=', 'ir.actions.client,%s' % act.id)]))

    def test_the_hub_mounts_the_real_cockpits_and_forks_neither(self):
        src = _hub('static', 'src', 'js', 'people_hub.js')
        for spec in ('@pb_people/js/people', '@pb_contracts/js/contracts'):
            self.assertIn('from "%s"' % spec, src)

    def test_both_cockpits_are_exported_and_still_register(self):
        for module, fname, cls, tag in (
                ('pb_people', 'people.js', 'PbPeople', 'pb_people'),
                ('pb_contracts', 'contracts.js', 'PbContracts', 'pb_contracts')):
            src = _read(ROOT, module, 'static', 'src', 'js', fname)
            self.assertIn('export class %s' % cls, src)
            self.assertIn('registry.category("actions").add("%s"' % tag, src)

    def test_the_hub_declares_no_local_palette(self):
        for f in ('people_hub.js', 'people_hub_palette.js', 'plan_launcher.js'):
            src = _hub('static', 'src', 'js', f)
            self.assertNotIn('pb_hub_palette_yield', src)
            self.assertNotIn('useHotkey', src)

    def test_every_palette_entry_names_a_lens_that_exists_and_the_reverse(self):
        hub = _hub('static', 'src', 'js', 'people_hub.js')
        lenses = set(re.findall(r'key: "(\w+)", icon:', hub))
        pal = _hub('static', 'src', 'js', 'people_hub_palette.js')
        for lens in re.findall(r'lens: "(\w+)"', pal):
            self.assertIn(lens, lenses, 'palette opens unknown lens %r' % lens)
        for lens in lenses:
            self.assertIn('lens: "%s"' % lens, pal,
                          'lens %r has no palette entry' % lens)

    def test_the_palette_imports_its_gates_instead_of_restating_them(self):
        pal = _hub('static', 'src', 'js', 'people_hub_palette.js')
        self.assertIn('from "@pb_people_hub/js/people_hub"', pal)
        self.assertIn('from "@pb_people_hub/js/plan_launcher"', pal)
        self.assertNotIn('group_', pal,
                         'the palette must not restate a gate group literal')

    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        manifest = ast.literal_eval(_hub('__manifest__.py'))
        declared = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                p = os.path.join(root, f)
                on_disk.add('pb_people_hub/'
                            + os.path.relpath(p, HERE).replace(os.sep, '/'))
        self.assertEqual(declared, on_disk)

    def test_no_python_style_implicit_string_concatenation(self):
        """W74: two adjacent string literals are a SyntaxError in JS, and the
        asset pipeline concatenates without parsing."""
        bad = []
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if not f.endswith('.js'):
                    continue
                with open(os.path.join(root, f), encoding='utf-8') as fh:
                    lines = fh.readlines()
                for n, line in enumerate(lines[:-1], 1):
                    nxt = lines[n].strip()
                    if line.strip().startswith(('//', '*', '/*')):
                        continue
                    if nxt.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                        bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, 'adjacent JS string literals: %s' % bad)

    def test_no_template_expression_calls_a_javascript_global(self):
        """W96: an OWL template expression is compiled against the COMPONENT, so
        `String(x)` becomes `ctx.String(x)` and the surface dies at mount with
        nothing in the server log. Reads `t-*` ATTRIBUTE VALUES only, so the
        prose explaining the rule may still say the word."""
        bad = []
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if not f.endswith('.xml'):
                    continue
                src = _read(os.path.join(root, f))
                for m in re.finditer(r't-[\w-]+="([^"]*)"', src):
                    for g in ('String(', 'Number(', 'JSON.', 'Object.',
                              'Array.', 'parseInt(', 'parseFloat('):
                        if g in m.group(1):
                            bad.append('%s: %s' % (f, m.group(1)))
        self.assertFalse(bad, 'JS globals in a template expression: %s' % bad)

    def test_every_template_file_parses(self):
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if f.endswith('.xml'):
                    ElementTree.parse(os.path.join(root, f))
        ElementTree.parse(os.path.join(HERE, 'views', 'pb_people_hub_action.xml'))


@tagged('post_install', '-at_install')
class TestEmbeddedLenses(TransactionCase):
    """W17: one suppression per template, on ONE element."""

    GUARDS = {('pb_people', 'people.xml'): 1, ('pb_contracts', 'contracts.xml'): 1}

    def test_every_embedded_guard_is_a_guard_and_not_a_rewrite(self):
        for (module, fname), n in self.GUARDS.items():
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            self.assertEqual(src.count('!props.embedded'), n,
                             '%s: expected %s embedded guard(s)' % (fname, n))

    def test_the_suppressed_element_is_the_identity_block(self):
        for module, fname in self.GUARDS:
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            for line in src.splitlines():
                if '!props.embedded' not in line:
                    continue
                self.assertIn('ppl-head-id', line,
                              '%s: unexpected suppression -> %s'
                              % (fname, line.strip()))

    def test_the_embedded_root_gets_a_real_scrollport(self):
        """W20/W99: `.pbim-page` is `min-height: 100%` with `overflow: auto`,
        which only scrolls while something above it bounds the height. Inside
        `.pbhub-lens` — a definite-height flex box — it GROWS instead, and the
        roster runs off the bottom of the workspace with nothing to scroll it.
        """
        scss = _hub('static', 'src', 'scss', 'people_hub.scss')
        block = re.search(
            r'\.pbim\.pbim-page\.ppl-people--embedded \{(.*?)\n\}', scss, re.S)
        self.assertTrue(block, 'the embedded block is gone')
        for decl in ('height: 100%', 'min-height: 0'):
            self.assertIn(decl, block.group(1))

    def test_the_scss_carries_a_real_literal_behind_every_pbim_token(self):
        """W14/W19: a `var()` fallback is a real colour and a real value, and a
        token that does not exist renders permanently from its fallback while
        claiming to be themed."""
        scss = _hub('static', 'src', 'scss', 'people_hub.scss')
        bare = re.findall(r'var\((--pbim-[\w-]+)\s*\)', scss)
        self.assertFalse(bare, 'pbim var() with no fallback: %s' % bare)
        for token, literal in (('--pbim-primary', '#5A4BB0'),
                               ('--pbim-ink', '#1B1733'),
                               ('--pbim-line', '#E2E8F0'),
                               ('--pbim-soft', '#EDEAF8')):
            self.assertIn('var(%s, %s)' % (token, literal), scss)
