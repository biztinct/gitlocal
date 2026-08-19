# -*- coding: utf-8 -*-
"""pb_people_hub — the gates, the launcher, and the ruling it has to keep.

The load-bearing test in this file is the one that proves a NEGATIVE: that the
Plan lens changed nothing in `pb_hr_workforce_planning`. The owner's ruling for
this programme is that Workforce Planning gets a minimal menu change and no
product change, and "we did not touch it" is exactly the kind of claim that
quietly stops being true. So it is checked against git, not against memory.

Every source gate reads `_code(src)` — the file with its comments removed —
because a word-shaped gate fails on the documentation that explains the rule
(W48's corollary, promoted to a required helper by W101).
"""
import ast
import os
import re
import subprocess
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
PLANNING = os.path.join(ROOT, 'pb_hr_workforce_planning')


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


def _plan_cards():
    """The descriptor, parsed back out of `plan_launcher.js`."""
    src = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
    block = re.search(r'export const PLAN_CARDS = \[(.*?)\n\];', src, re.S)
    assert block, 'PLAN_CARDS is gone'
    cards = []
    for chunk in re.findall(r'\{(.*?)\n    \}', block.group(1), re.S):
        card = {}
        for key in ('id', 'icon', 'xmlid', 'tag', 'model'):
            m = re.search(r'\b%s: "([^"]+)"' % key, chunk)
            if m:
                card[key] = m.group(1)
        gate = re.search(r'gate: \[([^\]]*)\]', chunk)
        card['gate'] = [g.strip() for g in gate.group(1).split(',') if g.strip()] \
            if gate else []
        cards.append(card)
    return cards


# The JS constant names the descriptor uses for each planning group.
_GROUP_CONST = {
    'WFP_USER': 'pb_hr_workforce_planning.group_wfp_user',
    'WFP_MANAGER': 'pb_hr_workforce_planning.group_wfp_manager',
    'WFP_ADMIN': 'pb_hr_workforce_planning.group_wfp_admin',
}


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
        names |= set(re.findall(r'"(pb_hr_workforce_planning\.\w+)"', plan))
        for xmlid in sorted(names):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'a gate names a group that does not exist here: %s' % xmlid)


@tagged('post_install', '-at_install')
class TestPlanLauncherIsALauncher(TransactionCase):
    """The owner ruling: a minimal menu change and no product change."""

    def test_this_cycle_changed_nothing_in_pb_hr_workforce_planning(self):
        """Asserted against git rather than against memory.

        The ruling is the whole reason the Plan lens is a card grid instead of
        an embedded cockpit, and "we did not touch it" is exactly the sort of
        claim that quietly stops being true.

        IT SKIPS ON A DEPLOYED SERVER, AND THE SKIP HAS TO BE ARGUED FOR RATHER
        THAN ASSUMED, because the naive version of this test FAILS there for a
        reason that has nothing to do with the ruling. `/odoo/odoo-server` is
        itself a git checkout — of odoo/odoo — and the custom modules are
        UNTRACKED inside it, so `git status --porcelain` answers
        `?? pb_hr_workforce_planning/` and a bare emptiness check reads that as
        "the module was modified". The question is therefore asked in two parts:
        does git track this path here at all (`ls-files`), and only then, is it
        dirty. A tree that does not track the module cannot answer the question
        and says so, instead of answering it wrongly. (W78's shape: a guard
        around the only assertion is a smell — so the guard here is a SKIP, which
        is loud, rather than a silent pass.)
        """
        try:
            tracked = subprocess.run(
                ['git', '-C', ROOT, 'ls-files', '--', 'pb_hr_workforce_planning'],
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            self.skipTest('git is not available here: %s' % e)
        if tracked.returncode != 0:
            self.skipTest('not a git checkout: %s' % tracked.stderr.strip())
        if not tracked.stdout.strip():
            self.skipTest('this tree does not track pb_hr_workforce_planning — '
                          'a deployed addons directory cannot answer this')
        out = subprocess.run(
            ['git', '-C', ROOT, 'status', '--porcelain', '--',
             'pb_hr_workforce_planning'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(
            out.stdout.strip(), '',
            'the Plan lens is a LAUNCHER by owner ruling — Workforce Planning '
            'must be byte-identical this cycle, and git says otherwise:\n%s'
            % out.stdout)

    def test_the_launcher_embeds_no_planning_component_and_owns_no_facade(self):
        """A grep is the only thing that can tell "did not embed" from
        "embedded and it happens to look like a grid" (W79)."""
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertNotIn('@pb_hr_workforce_planning/', code,
                         'the launcher must import nothing from Planning')
        self.assertNotIn('embedded: true', code)
        self.assertNotIn('wfp.', code.replace('wfp.planning.scenario', '')
                                     .replace('wfp.employee.forecast', '')
                                     .replace('wfp.pay.grade', '')
                                     .replace('wfp.merit.matrix', '')
                                     .replace('wfp.compensation.cycle', '')
                                     .replace('wfp.tagging.wizard', ''),
                         'the only planning model names allowed here are the '
                         'seven the gates are derived from')
        self.assertFalse(os.path.isdir(os.path.join(HERE, 'models')),
                         'the hub owns no server code at all')

    def test_all_seven_planning_actions_are_offered_and_all_of_them_resolve(self):
        cards = _plan_cards()
        self.assertEqual(len(cards), 7, 'seven screens, seven cards')
        for card in cards:
            self.assertTrue(
                self.env.ref(card['xmlid'], raise_if_not_found=False),
                'card %s names an action that does not exist: %s'
                % (card['id'], card['xmlid']))

    def test_the_card_order_is_the_retired_planning_sections_order(self):
        self.assertEqual(
            [c['id'] for c in _plan_cards()],
            ['dashboard', 'scenarios', 'forecasts', 'grades', 'merit',
             'cycles', 'tagging'])

    def test_each_card_is_gated_on_its_own_models_acl(self):
        """The seven planning models do NOT all grant read to the same tier —
        pay grades and the merit matrix are admin+user while the rest are
        manager+user, and the tagging wizard is manager only. One gate for the
        lens would therefore have been the wrong gate for three of its cards."""
        Access = self.env['ir.model.access'].sudo()
        Data = self.env['ir.model.data'].sudo()
        for card in _plan_cards():
            rows = Access.search([('model_id.model', '=', card['model']),
                                  ('perm_read', '=', True)])
            acl = set()
            for row in rows:
                if not row.group_id:
                    continue
                d = Data.search([('model', '=', 'res.groups'),
                                 ('res_id', '=', row.group_id.id)], limit=1)
                if d:
                    acl.add('%s.%s' % (d.module, d.name))
            declared = {_GROUP_CONST[g] for g in card['gate']}
            self.assertTrue(acl, '%s has no ACL rows' % card['model'])
            self.assertEqual(
                declared, acl,
                'card %s is gated %s but %s grants read to %s'
                % (card['id'], sorted(declared), card['model'], sorted(acl)))

    def test_the_launcher_opens_by_xmlid_and_keeps_the_breadcrumb(self):
        """`clearBreadcrumbs: false` is the way back for the six native lists —
        they render Odoo's own control panel, and a back chip is not something
        an Odoo view can host (W98's corollary). The Planning Dashboard renders
        no control panel and its way back is the rail, exactly as it is today
        from the rail's own Planning Dashboard item."""
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertIn('clearBreadcrumbs: false', code)
        self.assertNotIn('clearBreadcrumbs: true', code)

    def test_a_card_that_opens_nothing_is_not_rendered(self):
        """W79: a resolver with a swallowing fallback makes a DEAD entry
        indistinguishable from an ABSENT one, so presence is probed rather than
        assumed — server-side for the act_windows, against the registry for the
        one client action."""
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertIn('"pb.settings", "resolve_actions"', code)
        self.assertIn('registry.category("actions").contains', code)

    def test_the_probe_facade_answers_for_every_card(self):
        """Behaviour, against the real method the launcher calls."""
        cards = _plan_cards()
        xmlids = [c['xmlid'] for c in cards]
        out = self.env['pb.settings'].resolve_actions(xmlids)
        self.assertEqual(set(out), set(xmlids))
        self.assertTrue(all(out.values()),
                        'resolve_actions says a planning action is missing: %s'
                        % {k: v for k, v in out.items() if not v})

    def test_the_double_click_guard_is_there(self):
        code = _code(_hub('static', 'src', 'js', 'plan_launcher.js'))
        self.assertIn('this._opening', code)


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
