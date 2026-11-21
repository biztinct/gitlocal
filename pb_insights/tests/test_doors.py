# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA Cycle 6 — every number on this board is a door, and no door is a trapdoor.

Phase O made the board drillable. Five of its drills opened a bare native list
or form with ``target: "current"`` — which replaces the cockpit, renders no
Payobook chrome, and offers nothing to click to get back (W5). Cycle 4
enumerated them and left them; Cycle 6 converts them:

  openRun          → Pay Run hub · runs lens, the run in `pb_focus`
  openLeave        → Workforce · timeoff lens
  openOvertime()   → Workforce · overtime lens
  openBonusHours   → Workforce · overtime lens, `pb_cmd: bonus`
  the two id lists → an in-cockpit ledger + drawer, here

The gate below is written the way the door tests in pb_time_hub / pb_today /
pb_schedule are written, and for the same reason: the rule has to be checkable
without a browser, and it has to survive somebody adding a sixth drill.
"""

import os
import re

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, 'static', 'src')


def _js_files():
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for name in files:
            if name.endswith('.js'):
                yield os.path.join(root, name)


@tagged('post_install', '-at_install')
class TestInsightsDoors(TransactionCase):

    # -------------------------------------------------------------- the gate

    def test_01_no_drill_escapes_into_a_bare_native_list(self):
        """W5: no `target: "current"` anywhere in this cockpit.

        Comment lines are exempt so the rule may be NAMED in prose — a
        word-shaped gate that fails on its own documentation is a gate people
        delete (W48's corollary).
        """
        bad = []
        for path in _js_files():
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'target:\s*["\']current["\']', line):
                        bad.append('%s:%s: %s'
                                   % (os.path.relpath(path, HERE), n, stripped))
        self.assertFalse(
            bad, 'W5 violated — a drill replaces the cockpit with no way '
                 'back:\n%s' % '\n'.join(bad))

    def test_02_no_drill_opens_an_ad_hoc_act_window(self):
        """The other half of the same rule.

        `target:"new"` is a legitimate escape (a dialog you can close), but an
        inline `ir.actions.act_window` built in the browser carries no name, no
        rail highlight and no breadcrumb (W98) — and every population this
        board drills into now has either a hub lens or a ledger of its own. So
        the honest gate here is stronger than the generic one: this cockpit
        builds no act_window at all.
        """
        bad = []
        for path in _js_files():
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith(('//', '*', '/*')):
                        continue
                    if 'ir.actions.act_window' in line:
                        bad.append('%s:%s: %s'
                                   % (os.path.relpath(path, HERE), n, stripped))
        self.assertFalse(bad, 'an ad-hoc act_window survives:\n%s' % '\n'.join(bad))

    def test_03_the_hub_drills_all_carry_a_back_chip(self):
        """A door with no return path is the defect this cycle is closing, so
        every `openHub` call in this module has to name where it came from."""
        with open(os.path.join(SRC, 'js', 'insights.js'), encoding='utf-8') as fh:
            body = fh.read()
        calls = body.count('openHub(this.action,')
        self.assertTrue(calls, 'no hub drill at all — the conversion regressed')
        self.assertEqual(
            calls, body.count('back:'),
            'an openHub call in insights.js does not pass a back chip')
        self.assertIn('_backToInsights', body)
        self.assertIn('pb_insights_hub.action_pb_insights_hub', body,
                      'the back chip must name the hub by XMLID — a bare tag '
                      'gives the breadcrumb no name (W98)')

    def test_04_the_workforce_deep_links_use_the_shells_own_lens_key(self):
        """pb_mission reads `pb_shell_lens`, not `pb_lens`. A deep link with
        the wrong key opens the workspace on its remembered lens and looks like
        the click did nothing."""
        with open(os.path.join(SRC, 'js', 'insights.js'), encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('lensKey: "pb_shell_lens"', body)

    # ------------------------------------------------------- the new ledgers

    def test_05_the_people_ledgers_ship_the_shape_the_grid_expects(self):
        for kind in ('att_late', 'att_missing_punch', 'att_missing_checkout',
                     'att_early_leave', 'ot_near_cap'):
            data = self.env['pb.insights'].get_people_ledger(kind)
            self.assertEqual(data['kind'], kind)
            for key in ('title', 'subtitle', 'search_ph', 'empty', 'columns',
                        'facets', 'rows', 'total', 'shown'):
                self.assertIn(key, data, '%s is missing %s' % (kind, key))
            width = len(data['columns'])
            for row in data['rows']:
                self.assertEqual(
                    len(row['cells']), width,
                    '%s row %s has %s cells for %s columns'
                    % (kind, row['id'], len(row['cells']), width))
                self.assertIn('_f', row)
                self.assertIn('_s', row)

    def test_06_every_facet_chip_matches_at_least_one_loaded_row(self):
        """Facets are built FROM the rows, so a chip that matches nothing is a
        bug in the builder, not an empty result the user caused."""
        for kind in ('att_late', 'ot_near_cap'):
            data = self.env['pb.insights'].get_people_ledger(kind)
            for facet in data['facets']:
                for chip in facet['chips']:
                    hits = [r for r in data['rows']
                            if str((r['_f'] or {}).get(facet['key'])) == str(chip['id'])]
                    self.assertTrue(
                        hits, '%s facet %s chip %r matches no row'
                        % (kind, facet['key'], chip['id']))

    def test_07_an_unknown_ledger_is_refused_rather_than_guessed(self):
        with self.assertRaises(UserError):
            self.env['pb.insights'].get_people_ledger('att_not_a_kind')
        with self.assertRaises(UserError):
            self.env['pb.insights'].get_people_detail('nope', 1)

    def test_08_the_ledgers_are_behind_the_same_gate_as_the_board(self):
        """The facade collects under sudo. The gate is the only thing between a
        reader and 900 employees' departments, so it is asserted on the NEW
        doors too, not only on the one the cockpit already had."""
        probe = self.env['res.users'].create({
            'name': 'C6 insights probe',
            'login': 'c6_insights_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        facade = self.env['pb.insights'].with_user(probe)
        with self.assertRaises(AccessError):
            facade.get_people_ledger('att_late')
        with self.assertRaises(AccessError):
            facade.get_people_detail('att_late', 1)

    def test_09_the_detail_door_asks_the_orm_not_the_tile(self):
        """The ledger runs sudo, so the drawer must re-ask whether THIS reader
        may read THIS employee. A drawer that trusted the row it was opened
        from would be a sudo read with a click in front of it."""
        import inspect
        src = inspect.getsource(type(self.env['pb.insights']).get_people_detail)
        self.assertIn("check_access('read')", src)

    def test_10_the_facade_is_still_write_free(self):
        """pb_insights' founding rule, re-asserted because this cycle added
        two public methods to it."""
        model_dir = os.path.join(HERE, 'models')
        bad = []
        for name in os.listdir(model_dir):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(model_dir, name), encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    if re.search(r'\.(create|write|unlink)\(', line):
                        bad.append('%s:%s: %s' % (name, n, stripped))
        self.assertFalse(bad, 'pb_insights writes:\n%s' % '\n'.join(bad))
