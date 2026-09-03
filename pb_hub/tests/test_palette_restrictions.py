# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA Cycle 6 — the ⌘K palette obeys the rail's locks.

Cycle 5 moved pb_demo's demo lock up to the SYSTEM section, because a
`restricted` flag on an UNGATED item is inert (W106). That closed the rail and
left the palette wide open: a demo persona could not reach Formula Engine,
Structures, Statutory or Integrations from the sidebar, and could reach all four
with ⌘K. The lock was a property of one surface rather than of the door.

The repair is client-side — the palette asks `get_sidebar_data` and refuses to
navigate to a locked ref — so most of it is proven live. What Python can prove,
and what this file therefore proves, is the two halves nothing else pins:

  * the SERVER CONTRACT the client harvests from. If `get_sidebar_data` ever
    stops shipping a locked section's items, or starts stripping their
    `match_action_tags`, the palette silently unlocks and nothing anywhere else
    would notice.
  * the CLIENT INVARIANTS that must not be "simplified" away: the fail-open
    catch, the dialog-instead-of-navigate branch, and the fact that nothing
    re-decides the admin exemption in the browser.
"""

import os
import re

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICE = os.path.join(HERE, 'static', 'src', 'js', 'hub_palette_service.js')


def _strip_comments(src):
    """JS source with /* … */ and // … removed.

    Deliberately crude — it also blanks a comment marker inside a string
    literal. That is the safe direction here: every assertion below either
    looks for code that must exist (and no such string lives in a literal) or
    for code that must NOT exist (where over-removal can only make the gate
    stricter about real code, never laxer).
    """
    src = re.sub(r'/\*[\s\S]*?\*/', '', src)
    return re.sub(r'//[^\n]*', '', src)


@tagged('post_install', '-at_install')
class TestPaletteRestrictions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(SERVICE, encoding='utf-8') as fh:
            cls.service = fh.read()
        # The CODE, with every comment removed. Three of the assertions below
        # are "this string must not appear", and the prose in this file's own
        # header explains precisely those strings — a gate that fails on its own
        # documentation is one the next reader deletes rather than reads
        # (W48's corollary, and it fired on the first run of this suite).
        cls.code = _strip_comments(cls.service)

    # ----------------------------------------------------- client invariants

    def test_01_the_palette_asks_the_rail_rather_than_deciding_for_itself(self):
        self.assertIn('"pb.sidebar.item", "get_sidebar_data"', self.service,
                      'the palette no longer reads the rail\'s own payload — a '
                      'second copy of the lock rule will drift from the first')

    def test_02_a_locked_row_opens_a_dialog_and_does_not_navigate(self):
        """The whole point. The `return` has to come BEFORE the openHub call."""
        # FLEET P4 renamed this one variable, because there are now TWO reasons
        # a row may be locked and the older one needed a name of its own: the
        # demo lock, and a part of the product this company has not bought.
        # Amended at the site rather than loosened into a regex — the rule is
        # still "the check happens, and it returns, before openHub".
        body = self.code
        lock_at = body.find('const demoLock = restrictionFor(entry);')
        open_at = body.find('openHub(actionService, {', lock_at)
        self.assertNotEqual(lock_at, -1, 'the restriction check is gone from run()')
        self.assertNotEqual(open_at, -1)
        between = body[lock_at:open_at]
        self.assertIn('AlertDialog', between)
        self.assertIn('return;', between,
                      'run() falls through to openHub after showing the upsell')

    def test_03_the_lookup_fails_open(self):
        """A palette that locked rows because a lookup failed would hide the
        product from the people who paid for it — a worse failure than the one
        it is guarding against."""
        self.assertRegex(
            self.service,
            r'catch \(e\)[\s\S]{0,400}?console\.warn\([\s\S]{0,200}?restrictions',
            'loadRestrictions no longer reports and continues on failure')
        self.assertIn('if (!lockedRefs || !lockedRefs.size) { return ""; }',
                      self.service,
                      'restrictionFor no longer short-circuits on an empty set — '
                      'unrestricted databases must take no new code path at all')

    def test_04_the_admin_exemption_is_not_re_decided_in_the_browser(self):
        """`sec_locked = restricted AND NOT is_admin` is computed server-side.
        A second is-admin test in the palette would be a gate with two owners,
        and the browser's copy is the one an attacker can lie to."""
        self.assertNotIn('base.group_system', self.code)
        self.assertNotIn('is_admin', self.code)

    # ------------------------------------------------------ server contract

    def test_05_a_locked_section_still_ships_the_refs_the_palette_harvests(self):
        """The contract, exercised against a real locked section.

        Built and torn down here rather than assuming pb_demo is installed: this
        must hold on every database, and a test that only runs on the demo world
        is a test of the demo world.
        """
        Section = self.env['pb.sidebar.section']
        Item = self.env['pb.sidebar.item']
        section = Section.create({
            'name': 'C6 Locked Probe', 'technical_key': 'c6_locked_probe',
            'sequence': 990, 'show_label': True,
            'restricted': True,
            'restriction_reason': 'C6 upsell text',
        })
        Item.create({
            'name': 'C6 Locked Item', 'section_id': section.id, 'sequence': 10,
            'icon': 'settings', 'action_tag': 'c6_probe_tag',
            'match_action_tags': 'c6_probe_claimed,c6_probe_claimed_2',
            'match_action_xmlids': 'c6_probe.action_claimed',
        })
        probe = self.env['res.users'].create({
            'name': 'C6 palette probe', 'login': 'c6_palette_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        payload = Item.with_user(probe).get_sidebar_data()
        mine = next((s for s in payload if s['key'] == 'c6_locked_probe'), None)
        self.assertTrue(mine, 'a locked section is not served at all')
        self.assertTrue(mine['restricted'])
        self.assertEqual(mine['restriction_reason'], 'C6 upsell text')
        self.assertTrue(mine['items'], 'a locked section serves no items — the '
                                       'palette has nothing to harvest')
        item = mine['items'][0]
        # The refs the palette matches an entry on, all four dimensions.
        self.assertEqual(item['action_tag'], 'c6_probe_tag')
        self.assertIn('c6_probe_claimed', item['match_action_tags'])
        self.assertIn('c6_probe.action_claimed', item['match_action_xmlids'])

        # …and an administrator gets the same section UNLOCKED, which is why
        # the palette never has to ask who it is talking to.
        admin_payload = Item.with_user(self.env.ref('base.user_admin')).get_sidebar_data()
        theirs = next((s for s in admin_payload if s['key'] == 'c6_locked_probe'), None)
        self.assertTrue(theirs)
        self.assertFalse(theirs['restricted'],
                         'an administrator is served the lock — every palette '
                         'row under it would padlock for them too')

    def test_06_an_unrestricted_database_produces_no_locked_refs_at_all(self):
        """Zero behaviour change where nothing is restricted: the harvest over
        the real rail must be empty unless something on it is actually locked."""
        Item = self.env['pb.sidebar.item']
        payload = Item.get_sidebar_data()
        locked_sections = [s['key'] for s in payload if s.get('restricted')]
        locked_items = [i['name'] for s in payload for i in s['items']
                        if i.get('restricted')]
        if not locked_sections and not locked_items:
            return                      # the ordinary case; nothing to assert
        # Something IS locked here (a demo database). Then the lock must carry a
        # reason, or the dialog would open blank.
        for s in payload:
            if s.get('restricted'):
                self.assertTrue(s['restriction_reason'],
                                'locked section %s has no upsell text' % s['key'])
            for i in s['items']:
                if i.get('restricted'):
                    self.assertTrue(i['restriction_reason'],
                                    'locked item %s has no upsell text' % i['name'])

    def test_07_the_padlock_is_rendered_from_the_same_flag(self):
        """A lock that stops the click but draws nothing is a dead row; a lock
        that draws but does not stop the click is worse."""
        tpl = os.path.join(HERE, 'static', 'src', 'xml', 'hub_palette.xml')
        with open(tpl, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('row.row.restricted', body)
        self.assertRegex(body, r'pbhub-pal-row__lock')
        # FLEET P4 feeds a SECOND reason into the same field on purpose: the
        # palette already knows how to draw a padlock and how to answer a click
        # on one, and two mechanisms for two reasons would be two things to
        # keep in step. The demo lock still wins where both apply.
        self.assertIn('restricted: restrictionFor(e) || featureOf(e).text,',
                      self.service,
                      'the row no longer carries the flag the template reads')
        self.assertFalse(
            re.search(r'restricted:\s*(true|false)\b', self.service),
            'the restricted flag is being hard-coded rather than resolved')
