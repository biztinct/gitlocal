# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA redesign Cycle 3 — the Settings hub's gates.

The hub is a DESCRIPTOR: eight categories, their gates and their cards live in
one JS array, and everything the surface does follows from it. Two whole classes
of defect are therefore invisible at runtime.

  * a card naming an action xmlid that does not resolve renders normally and
    answers a click with silence — nothing errors, nothing logs, and the tile
    looks exactly like a working one (W79). The hub probes at open time, so the
    bad card would simply never appear, which means the BEHAVIOUR test can never
    catch it either: the way to tell "absent" from "wrong" is to read the source
    and check the name.
  * a gate naming a group xmlid that does not resolve FAILS OPEN, on purpose —
    an unresolvable group means the module is not installed, and treating that
    as "denied" would hide a category for the wrong reason. Which means a
    TYPO in a group name silently ungates its category, and the only place that
    is visible is here.

So these tests read the descriptor back out of the file and check every name in
it against the database. They are the floor, not the proof: the live Chrome run
is what shows the surface mounts (W10).
"""
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_JS = None


def _js():
    """The descriptor file's source, read once."""
    global _JS
    if _JS is None:
        path = get_module_path('pb_settings')
        with open(path + '/static/src/js/settings_hub.js', encoding='utf-8') as fh:
            _JS = fh.read()
    return _JS


def _icons():
    """Every key in the shared Lucide registry."""
    path = get_module_path('pb_import_kit')
    with open(path + '/static/src/js/import_icons.js', encoding='utf-8') as fh:
        src = fh.read()
    return set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'", src, re.M))


_RE_XMLID = re.compile(r"""xmlid:\s*["']([\w.]+)["']""")
_RE_TAG = re.compile(r"""\btag:\s*["']([\w.]+)["']""")
_RE_ICON = re.compile(r"""\bicon:\s*["']([A-Za-z0-9_]+)["']""")
_RE_KEY = re.compile(r"""^\s{8}key:\s*["'](\w+)["']""", re.M)
_RE_CARD_ID = re.compile(r"""\{\s*id:\s*["'](\w+)["']""")
# Every gate group is bound to an UPPER_CASE module-level const whose value ends
# in `.group_…`. Matching the shape rather than a fixed list of names means a
# gate added in a later cycle is checked automatically instead of quietly
# skipped — and a gate that fails to resolve is invisible at runtime, because
# group resolution deliberately fails OPEN.
_RE_GROUP_CONST = re.compile(
    r"""^const\s+[A-Z][A-Z0-9_]*\s*=\s*["']([\w.]+\.group_\w+)["']""", re.M)
# Python-style implicit string concatenation is a JS SyntaxError, and Odoo's
# asset pipeline concatenates without ever parsing — so one of these blanks the
# whole backend with a clean server log (W74).
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")

# A source gate written the obvious way fails on the paragraph that explains it
# (W101, and W114's fifth and sixth bites) — the comment above `setCat` has to
# be able to name `soleCard`. Every gate below reads the CODE, not the file.
_RE_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.S)
_RE_LINE_COMMENT = re.compile(r'(?<![:"\'])//[^\n]*')


def _code(src):
    """The file with its `/* … */` and `//` comments removed."""
    return _RE_LINE_COMMENT.sub('', _RE_BLOCK_COMMENT.sub('', src))


@tagged('post_install', '-at_install')
class TestSettingsDescriptor(TransactionCase):
    """Every name the descriptor uses must exist on this database."""

    def test_every_action_xmlid_in_the_descriptor_resolves(self):
        # Scoped to the CATEGORIES array. The file names one other xmlid — the
        # hub's own `ir.actions.client`, which the return chip navigates to —
        # and that one is checked by TestSettingsAction instead.
        body = _js().split('export const CATEGORIES = [', 1)[1].split('\n];', 1)[0]
        xmlids = _RE_XMLID.findall(body)
        self.assertTrue(xmlids, "the descriptor names no act_window at all")
        for xmlid in xmlids:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(
                rec, "Settings card points at %s, which does not resolve — the "
                     "card would render and open nothing (W79)" % xmlid)
            self.assertEqual(
                rec._name, 'ir.actions.act_window',
                "%s is a %s; the hub opens xmlid cards as native act_windows "
                "and would hand doAction something it cannot show"
                % (xmlid, rec._name))

    def test_every_gate_group_in_the_descriptor_resolves(self):
        groups = _RE_GROUP_CONST.findall(_js())
        self.assertGreaterEqual(
            len(groups), 8,
            "expected the gate constants to be found; got %s" % groups)
        for xmlid in groups:
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(
                rec, "gate %s does not resolve. Group resolution FAILS OPEN, so "
                     "a typo here ungates its whole category silently" % xmlid)
            self.assertEqual(rec._name, 'res.groups')

    def test_the_descriptor_is_eight_categories_with_unique_keys(self):
        keys = _RE_KEY.findall(_js())
        self.assertEqual(
            keys,
            ['formula', 'structures', 'statutory', 'integrations',
             'payroll', 'roles', 'org', 'nav'],
            "the category order is the mockup's and is fixed; the localStorage "
            "key pbst.cat.v1 also remembers one of these by name")
        self.assertEqual(len(set(keys)), len(keys))

    def test_the_cockpit_tags_are_the_five_this_cycle_agreed_on(self):
        # Client-action cards are probed against the JS registry at open time, so
        # a renamed or mistyped tag makes its card vanish rather than break —
        # which is the right runtime behaviour and a terrible way to find out.
        # Pinning the set here is the only place a rename becomes loud.
        self.assertEqual(
            sorted(set(_RE_TAG.findall(_js()))),
            ['pb_formula_studio', 'pb_integrations', 'pb_statutory',
             'pb_structures', 'pb_tenants'],
            "the tags are the four payroll cockpits plus Tenants. The hub's own "
            "return door is an XMLID, not a tag — a bare tag reaches the action "
            "service with no NAME, and the breadcrumb reads 'Unnamed'")

    def test_no_two_cards_share_an_id(self):
        # The ids are the t-key of the card loop. Two identical keys make OWL
        # reuse one node for two cards, and the second one silently does not
        # render.
        ids = _RE_CARD_ID.findall(_js())
        self.assertTrue(ids)
        dupes = {i for i in ids if ids.count(i) > 1}
        self.assertFalse(dupes, "duplicate card ids: %s" % sorted(dupes))

    def test_every_icon_name_is_in_the_shared_registry(self):
        # `ic()` falls back to a checkmark for an unknown name, so a typo is a
        # wrong icon rather than an error (W2 — never a per-module icon file).
        known = _icons()
        self.assertIn('calculator', known, "the icon registry did not parse")
        for name in set(_RE_ICON.findall(_js())):
            self.assertIn(
                name, known,
                "icon '%s' is not in pb_import_kit's IC registry — ic() would "
                "silently render its fallback" % name)

    def test_a_single_card_category_opens_its_one_door_directly(self):
        """Integrations Cycle 1 — the rule, and the fact that it fires.

        Two halves, because each fails in the opposite direction and both are
        invisible at runtime. The RULE lives in `setCat`, which is a click
        handler — reading it out of the source is the only way to tell "the
        category has one card and the hub still renders a page for it" from
        "the category has two cards". And the FACT that Integrations has
        exactly one card is what makes the rule fire today; the moment Cycle 2
        adds a Mapping Studio card, the section page returns on its own and
        this half of the assertion is what will say so.

        The source is read with its comments stripped (W101/W114): the
        paragraph above `setCat` has to be able to say `soleCard` out loud.
        """
        src = _code(_js())
        self.assertIn(
            'soleCard(', src,
            "the single-card rule is gone from settings_hub.js — a category "
            "with one door would render a page whose only content is that door")
        setcat = src.split('setCat(key)', 1)[1].split('\n    }', 1)[0]
        self.assertIn('this.openCard(sole)', setcat,
                      "setCat must navigate for a single-card category")
        self.assertNotIn(
            'localStorage.setItem', setcat.split('this.openCard(sole)', 1)[0],
            "a category that is skipped must not become the remembered one")

        body = _js().split('export const CATEGORIES = [', 1)[1].split('\n];', 1)[0]
        block = body.split('key: "integrations"', 1)[1].split('cards: [', 1)[1]
        block = block.split('\n    },', 1)[0]
        self.assertEqual(
            len(_RE_CARD_ID.findall(block)), 1,
            "Integrations is the category the single-card rule was written for")

    def test_a_card_may_carry_its_own_arrival_context(self):
        # `openHub` merges an arbitrary context (hub_nav.js:63); forwarding it
        # is what lets a later card deep-link a cockpit onto a lens without
        # every such card editing openCard.
        opencard = _code(_js()).split('openCard(card) {', 1)[1].split('\n    }', 1)[0]
        self.assertIn('card.context', opencard)

    def test_no_python_style_implicit_string_concatenation(self):
        for fname in ('settings_hub.js', 'settings_palette.js'):
            path = get_module_path('pb_settings') + '/static/src/js/' + fname
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                "%s has two adjacent string literals across a newline. That is "
                "Python; in JavaScript it is a SyntaxError, and one unparseable "
                "file blanks web.assets_backend for every user with a clean "
                "server log (W74)" % fname)


@tagged('post_install', '-at_install')
class TestSettingsProbe(TransactionCase):
    """`pb.settings.resolve_actions` — the existence probe."""

    def test_it_answers_true_for_a_real_action_and_false_for_an_invented_one(self):
        res = self.env['pb.settings'].resolve_actions([
            'base.action_res_users', 'pb_settings.no_such_action_at_all',
        ])
        self.assertEqual(res, {
            'base.action_res_users': True,
            'pb_settings.no_such_action_at_all': False,
        })

    def test_it_ignores_junk_rather_than_raising(self):
        # The caller is a template descriptor; one malformed entry must not take
        # the whole Settings hub down with it.
        res = self.env['pb.settings'].resolve_actions(
            [None, 42, '', 'nodot', 'base.action_res_users'])
        self.assertEqual(res, {'base.action_res_users': True})

    def test_it_is_bounded(self):
        res = self.env['pb.settings'].resolve_actions(
            ['base.action_res_users'] * 10 + ['a.b%s' % i for i in range(200)])
        self.assertLessEqual(
            len(res), 50,
            "a forged call must not turn one RPC into an unbounded "
            "ir.model.data walk")

    def test_the_probe_writes_nothing(self):
        # A settings surface has every reason to be read-only and no reason not
        # to be, so say it out loud rather than relying on the next contributor
        # reading the method (W25's shape).
        path = get_module_path('pb_settings') + '/models/pb_settings.py'
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        for forbidden in ('.create(', '.write(', '.unlink(', 'sudo('):
            self.assertNotIn(
                forbidden, src,
                "pb.settings is a read-only probe; found %s" % forbidden)


@tagged('post_install', '-at_install')
class TestSettingsAction(TransactionCase):
    """The client action itself."""

    def test_it_exists_and_carries_a_name(self):
        act = self.env.ref('pb_settings.action_pb_settings_hub')
        self.assertEqual(act.tag, 'pb_settings_hub')
        # The chip and the cog navigate to this XMLID, not to the tag. Both
        # spellings reach the same component; only this one carries the name.
        self.assertIn('pb_settings.action_pb_settings_hub', _js())
        # The NAME is load-bearing, not decoration: it is what puts "Settings"
        # in the breadcrumb, and the breadcrumb is the return path from the four
        # native admin actions the hub opens (a back chip cannot be rendered
        # inside Odoo's own views).
        self.assertEqual(act.name, 'Settings')

    def test_it_has_no_menu_and_exactly_one_rail_item(self):
        """CYCLE 5 REVERSED THE RAIL HALF OF THIS TEST.

        Cycle 3 asserted there must be "no rail record for this hub at all
        yet" — the cog and the palette were the only doors, and a rail item
        would have BEEN the cutover two cycles early. The cutover has happened:
        Settings is the whole SYSTEM section, and the four SETUP items and six
        ADMIN items it replaced are retired. The reversal is written at the site
        rather than silently deleted, because a gate whose history is invisible
        is one the next reader will "fix" back (W76.3).

        The MENU half is unchanged and still matters: the rail, the cog and the
        palette are three doors to one place, and an `ir.ui.menu` would be a
        fourth that nothing else in the product uses.
        """
        act = self.env.ref('pb_settings.action_pb_settings_hub')
        menus = self.env['ir.ui.menu'].sudo().with_context(
            active_test=False).search([('action', '!=', False)])
        hits = [m.complete_name for m in menus
                if m.action._name == 'ir.actions.client' and m.action.id == act.id]
        self.assertFalse(hits, "the Settings hub must not be on a menu: %s" % hits)
        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].sudo().with_context(
                active_test=False).search([('action_tag', '=', 'pb_settings_hub')])
            self.assertEqual(len(items), 1, "exactly one rail item opens Settings")
            self.assertTrue(items.active)
            self.assertEqual(items.section_id.technical_key, 'system')
            self.assertEqual(items.sequence, 10)
            self.assertFalse(items.groups_id,
                             "the Settings rail item is UNGATED on purpose — "
                             "the hub hides the categories a persona cannot "
                             "open, which is the narrower answer (W95)")

    def test_the_payroll_defaults_card_opens_the_unreachable_settings_form(self):
        # The whole point of that card: `res.config.settings` had no rail item
        # and its native menu is hidden behind base.group_system, so the payroll
        # defaults screen existed and could not be opened in-product.
        act = self.env.ref('om_hr_payroll.action_hr_payroll_configuration')
        self.assertEqual(act.res_model, 'res.config.settings')
        self.assertIn('om_hr_payroll', act.context or '')


@tagged('post_install', '-at_install')
class TestSettingsGatesMatchTheAcls(TransactionCase):
    """A gate must not offer a card the target's own ACL would refuse.

    This is the gate that would have caught the live finding: the hub's first
    version gated Formula Engine on the payroll manager tiers, `hr.formula.
    config` grants read to the FORMULA groups, and neither implies the other —
    so a payroll manager saw the card and got an access dialog (W29). Group
    resolution fails open by design, so nothing about that is visible at
    runtime; only comparing the gate against `ir.model.access` can see it.
    """

    # category key -> (the model its card reads, the gate constants in the file)
    CARD_MODELS = {
        'formula': 'hr.formula.config',
        'structures': 'hr.payroll.structure',
        'statutory': 'vietnam.insurance.policy',
        'integrations': 'hr.integration.connector',
    }

    def _gate_of(self, key):
        """The group xmlids the descriptor gates a category on."""
        src = _js()
        block = src.split('key: "%s"' % key, 1)[1].split('cards:', 1)[0]
        const = re.search(r'groups:\s*(\w+)', block).group(1)
        listed = re.search(r'^const\s+%s\s*=\s*\[([^\]]*)\]' % const, src, re.M).group(1)
        names = [n.strip() for n in listed.split(',') if n.strip()]
        out = []
        for n in names:
            m = re.search(r'^const\s+%s\s*=\s*["\']([\w.]+)["\']' % n, src, re.M)
            self.assertTrue(m, "gate constant %s is not defined" % n)
            out.append(m.group(1))
        return out

    def test_every_gate_group_can_actually_read_its_card_model(self):
        Access = self.env['ir.model.access'].sudo()
        for key, model in self.CARD_MODELS.items():
            if model not in self.env:
                continue
            allowed = set()
            for a in Access.search([('model_id.model', '=', model),
                                    ('perm_read', '=', True)]):
                if a.group_id:
                    xid = a.group_id.get_external_id().get(a.group_id.id)
                    if xid:
                        allowed.add(xid)
            if not allowed:
                continue        # granted to everyone; nothing to prove
            for gate in self._gate_of(key):
                self.assertIn(
                    gate, allowed,
                    "the %s category is offered to %s, which cannot READ %s — "
                    "that card can only produce an access dialog (W29). "
                    "Groups that can: %s"
                    % (key, gate, model, sorted(allowed)))
