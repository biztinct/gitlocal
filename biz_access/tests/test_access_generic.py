# -*- coding: utf-8 -*-
"""What has to be true of the Access home when NOBODY has told it anything.

This module is the generic half of a split (ACCESS P6): the models, the home
and the rails belong here, and every word on the board belongs to whichever
application is installed on top. Three promises are made by that arrangement and
all three are asserted here rather than assumed.

  1. **The keys to the building are unreachable.** The permanent tripwire — Rail
     B — walks the whole implied closure of every ability and every role ON THIS
     DATABASE and fails if one of them reaches the system administrator
     permission. It is exposed as a mixin so an application's own catalogue test
     asserts exactly the same thing about exactly the same closure.
  2. **This module seeds nothing.** Not a role, not an ability, not an area
     beyond one neutral word. A generic module that shipped somebody else's
     vocabulary would put the wrong words on the next product's screen.
  3. **No user-visible string here names a product.** Asserted by reading the
     source, because the failure mode is a single sentence somebody added in a
     hurry and nobody read again.
"""
import os
import re

from odoo.exceptions import ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.hooks import catalogue_providers
from odoo.addons.biz_access.models.access_common import (
    FORBIDDEN_GROUP_XMLIDS, NEUTRAL_AREA, default_area, forbidden_group_ids,
    implied_closure, profile_areas)


def _src(*parts):
    with open(os.path.join(get_module_path('biz_access'), *parts),
              encoding='utf-8') as fh:
        return fh.read()


# =========================================================================
#  RAIL B — the reusable tripwire
# =========================================================================
class RailBMixin:
    """Nothing in a catalogue may reach the keys to the building.

    A MIXIN AND NOT A TEST OF ITS OWN, so an application asserts the same thing
    about its own seeds and a second implementation of "walk the closure" never
    comes into existence to disagree with this one.
    """

    def assert_nothing_reaches_the_keys(self, abilities=None, profiles=None):
        forbidden = forbidden_group_ids(self.env)
        self.assertTrue(
            forbidden,
            'neither of the two permissions this rail exists to refuse could '
            'be resolved — the check would pass for the wrong reason')
        abilities = (self.env['pb.role.ability'].sudo()
                     .with_context(active_test=False).search([])
                     if abilities is None else abilities)
        profiles = (self.env['pb.role.profile'].sudo()
                    .with_context(active_test=False).search([])
                    if profiles is None else profiles)
        for ability in abilities:
            reach = implied_closure(ability.group_ids)
            bad = reach.filtered(lambda g: g.id in forbidden)
            self.assertFalse(
                bad, 'the "%s" ability carries %s'
                     % (ability.name, ', '.join(bad.mapped('name'))))
        for profile in profiles:
            reach = implied_closure(profile.group_ids)
            bad = reach.filtered(lambda g: g.id in forbidden)
            self.assertFalse(
                bad, 'the "%s" role carries %s'
                     % (profile.name, ', '.join(bad.mapped('name'))))


@tagged('post_install', '-at_install')
class TestRailB(TransactionCase, RailBMixin):

    def test_nothing_on_this_database_reaches_the_keys_to_the_building(self):
        self.assert_nothing_reaches_the_keys()

    def test_an_ability_that_would_carry_them_is_refused(self):
        keys = self.env.ref(FORBIDDEN_GROUP_XMLIDS[0])
        with self.assertRaises(ValidationError):
            self.env['pb.role.ability'].sudo().create({
                'technical_key': 'generic-test-bad-ability',
                'name': 'A bad idea',
                'area': default_area(),
                'group_ids': [(6, 0, keys.ids)],
            })

    def test_a_permission_that_merely_implies_them_is_refused_too(self):
        keys = self.env.ref(FORBIDDEN_GROUP_XMLIDS[0])
        sneaky = self.env['res.groups'].sudo().create({
            'name': 'Generic test — looks harmless',
            'implied_ids': [(6, 0, keys.ids)],
        })
        with self.assertRaises(ValidationError):
            self.env['pb.role.ability'].sudo().create({
                'technical_key': 'generic-test-sneaky-ability',
                'name': 'Also a bad idea',
                'area': default_area(),
                'group_ids': [(6, 0, sneaky.ids)],
            })


# =========================================================================
#  IT SEEDS NOTHING
# =========================================================================
@tagged('post_install', '-at_install')
class TestItSeedsNothing(TransactionCase):

    def test_this_module_owns_no_role_and_no_ability(self):
        """Every role and ability on a database belongs to an application's
        catalogue or to a person who made one. None is ever this module's."""
        rows = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'biz_access'),
            ('model', 'in', ('pb.role.profile', 'pb.role.ability')),
        ])
        self.assertFalse(
            rows, 'this module has seeded %s catalogue record(s): %s'
                  % (len(rows), ', '.join(rows.mapped('name'))))

    def test_the_catalogue_is_whatever_the_applications_registered(self):
        """The seeding machinery is a registry and never a list. On a database
        with an application installed there is at least one provider; on a bare
        one there are none and an empty board is the honest answer."""
        for key, fn in catalogue_providers():
            self.assertTrue(key and callable(fn))

    def test_there_is_always_at_least_one_area_and_a_default_inside_it(self):
        areas = profile_areas()
        self.assertTrue(areas, 'a Selection with no options is not a screen')
        self.assertIn(default_area(), [key for key, _label in areas])

    def test_the_neutral_area_is_what_a_bare_install_offers(self):
        """Asserted on the constant rather than by uninstalling an application:
        the point is that the fallback EXISTS and is one plain word."""
        key, label = NEUTRAL_AREA
        self.assertEqual(key, 'general')
        self.assertTrue(label and label[0].isupper())


# =========================================================================
#  THE BOARD WITH NOTHING ON IT
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheEmptyHome(TransactionCase):
    """A board with no catalogue must ANSWER, not fall over.

    This is the generic-reusability promise in one test: put this module on a
    database on its own and the home opens, says there is nothing yet, and every
    lens still returns its shape.
    """

    def setUp(self):
        super().setUp()
        # Everything put away, inside the test's own transaction. `active` is
        # written directly rather than through `archive_role`, which refuses
        # while somebody holds the role — here we want the empty board, not the
        # refusal, and the refusal has its own test.
        self.env['pb.role.profile'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        self.env['pb.role.ability'].sudo().with_context(
            active_test=False).search([]).write({'active': False})

    def test_the_roles_lens_answers_with_an_empty_catalogue(self):
        board = self.env['pb.access'].get_board()
        self.assertEqual(board['profiles'], [])
        self.assertIn('kpis', board)
        self.assertIn('areas', board)
        self.assertTrue(board.get('headline'),
                        'an empty board still has to say something')

    def test_the_builder_still_offers_every_registered_area(self):
        """The lens bar only shows areas that HAVE roles, which is right. The
        builder has to offer all of them, or a bare install could not make the
        first one."""
        options = self.env['pb.access'].composer_options()
        keys = [a['key'] for a in options['areas']]
        self.assertEqual(keys, [key for key, _label in profile_areas()])
        self.assertEqual(options['abilities'], [])
        self.assertEqual(options['roles'], [])

    def test_the_people_lens_answers_with_an_empty_catalogue(self):
        people = self.env['pb.access'].people()
        self.assertTrue(isinstance(people, list))
        self.assertTrue(people, 'the reader is always in their own list')
        self.assertIn('role_count', people[0])
        self.assertEqual(people[0]['role_count'], 0)

    def test_the_screens_lens_answers_with_an_empty_catalogue(self):
        board = self.env['pb.access'].screens_board()
        self.assertIn('sections', board)
        self.assertEqual(board['roles'], [])
        self.assertTrue(board.get('headline'))


# =========================================================================
#  THE COPY AUDIT
# =========================================================================
@tagged('post_install', '-at_install')
class TestNoProductNameInTheGenericLayer(TransactionCase):
    """No user-visible string here may name a product.

    Read from the source rather than from the database, because the failure is
    always one sentence added in a hurry — and because a string only shown on an
    error path is exactly the one a running test never renders.
    """

    #: Product names this layer must never speak. The framework's own name is
    #: in the list for the white-label rule; it is allowed in a code COMMENT and
    #: in an import, which is why the scan below only reads quoted user copy.
    BANNED = ('Payobook', 'Odoo', 'odoo.com')

    #: Files whose whole contents are user-facing.
    MARKUP = (
        ('static', 'src', 'xml', 'access_board.xml'),
        ('static', 'src', 'xml', 'mini_rail.xml'),
        ('data', 'mail_template_data.xml'),
    )

    def test_no_python_message_names_a_product(self):
        """Every `_( … )` and every `string=`/`help=` in the models."""
        for name in ('access_common.py', 'pb_role_ability.py',
                     'pb_role_profile.py', 'pb_access_delegation.py',
                     'pb_access_facade.py', 'pb_sidebar_item_ext.py'):
            src = _src('models', name)
            # Strip full-line comments and docstrings: engineering prose is
            # allowed to name anything it likes.
            code = re.sub(r'"""(?:.|\n)*?"""', '', src)
            code = '\n'.join(l for l in code.split('\n')
                             if not l.lstrip().startswith('#'))
            for banned in self.BANNED:
                self.assertNotIn(
                    banned, code,
                    '%s names "%s" outside a comment' % (name, banned))

    def test_no_markup_string_names_a_product(self):
        for parts in self.MARKUP:
            src = _src(*parts)
            # `<odoo>` is the data-file root element, not a word on a screen.
            src = src.replace('<odoo>', '').replace('</odoo>', '')
            src = re.sub(r'<!--(?:.|\n)*?-->', '', src)
            for banned in self.BANNED:
                self.assertNotIn(
                    banned, src,
                    '%s names "%s"' % ('/'.join(parts), banned))

    def test_no_browser_string_names_a_product(self):
        for name in ('access_board.js', 'mini_rail.js', 'access_palette.js'):
            src = _src('static', 'src', 'js', name)
            src = re.sub(r'/\*(?:.|\n)*?\*/', '', src)
            src = '\n'.join(l for l in src.split('\n')
                            if not l.lstrip().startswith('//'))
            # `@odoo/owl` and `@odoo-module` are import machinery.
            src = src.replace('@odoo/owl', '').replace('@odoo-module', '')
            for banned in self.BANNED:
                self.assertNotIn(
                    banned, src, '%s names "%s"' % (name, banned))

    def test_the_manifest_reads_as_a_product_agnostic_module(self):
        manifest = _src('__manifest__.py')
        self.assertNotIn('Payobook', manifest)


# =========================================================================
#  THE SOURCE GATES
#
#  Six habits that produce a broken screen with a clean server log. They
#  travelled with the files (ACCESS P6) rather than staying behind in the
#  module these were extracted from, because a gate that no longer reads the
#  file it was written for passes for the wrong reason.
# =========================================================================
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JS SyntaxError, and the asset pipeline
        concatenates without ever parsing — so one of these blanks the whole
        backend bundle for every user with a clean server log (R2)."""
        for fname in ('access_board.js', 'mini_rail.js', 'access_palette.js'):
            src = _src('static', 'src', 'js', fname)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline' % fname)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into the generated function
        as a bare `<` and the whole template dies, pointing at the template and
        never at the loop (R1)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        for fname in ('access_board.xml', 'mini_rail.xml'):
            src = _src('static', 'src', 'xml', fname)
            for name in re.findall(r't-as="(\w+)"', src):
                self.assertNotIn(name, reserved,
                                 '%s uses the reserved name %s' % (fname, name))

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` falls back to a checkmark for an unknown name, so a typo is a
        wrong icon rather than an error (W2 — never a per-module icon file)."""
        path = get_module_path('pb_import_kit')
        with open(path + '/static/src/js/import_icons.js',
                  encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('key', known, 'the icon registry did not parse')
        used = set()
        for fname in ('access_board.xml', 'mini_rail.xml'):
            used |= set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                                   _src('static', 'src', 'xml', fname)))
        used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"',
                               _src('static', 'src', 'js',
                                    'access_palette.js')))
        for name in used:
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry" % name)

    def test_no_bracketed_plurals(self):
        """"1 role(s)" is how a screen announces it was written by a programme
        rather than by a person (R46)."""
        for parts in (('models', 'pb_access_delegation.py'),
                      ('models', 'pb_access_facade.py'),
                      ('static', 'src', 'xml', 'access_board.xml')):
            src = _src(*parts)
            self.assertFalse(
                re.search(r'\w\(s\)', src),
                '%s has a bracketed plural' % parts[-1])

    def test_the_delegation_snapshot_is_measured_and_not_predicted(self):
        """The single most important line in the module: what was ADDED is read
        back off the user, never computed from the roles."""
        src = _src('models', 'pb_access_delegation.py')
        block = src.split('def _activate_one', 1)[1].split('def _groups_to_hand',
                                                           1)[0]
        self.assertIn('before = set(delegate.group_ids.ids)', block)
        self.assertIn("invalidate_recordset(['group_ids'])", block)
        self.assertIn('added = sorted(after - before)', block)

    def test_the_revert_only_removes_what_is_still_there(self):
        src = _src('models', 'pb_access_delegation.py')
        block = src.split('def _end(', 1)[1].split('def _mail(', 1)[0]
        self.assertIn('still = applied.filtered', block)
        self.assertIn('gone = applied - still', block)

    def test_the_palette_names_actions_that_resolve(self):
        src = _src('static', 'src', 'js', 'access_palette.js')
        for xmlid in set(re.findall(r'xmlid:\s*"([\w.]+)"', src)):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'the palette points at %s, which does not resolve — the row '
                'would render and open nothing (W79)' % xmlid)

    def test_the_home_has_a_door_and_no_menu(self):
        act = self.env.ref('biz_access.action_pb_access_board')
        self.assertEqual(act.tag, 'pb_access_board')
        self.assertEqual(act.name, 'Access & delegation')
        menus = self.env['ir.ui.menu'].sudo().with_context(
            active_test=False).search([('action', '!=', False)])
        hits = [m.complete_name for m in menus
                if m.action._name == 'ir.actions.client'
                and m.action.id == act.id]
        self.assertFalse(hits, 'the Access home must not be on a menu: %s'
                               % hits)
