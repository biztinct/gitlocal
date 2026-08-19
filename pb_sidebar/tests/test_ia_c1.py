# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA redesign Cycle 1 — the three audit fixes, asserted in the DATABASE.

Every assertion here reads the RECORD, never the XML. That is not ceremony:
W13.1 has bitten this codebase three times, and each time the repo was correct,
the log was clean, `-u` exited 0, and the rail on screen was still wrong. A
repo-only fix is indistinguishable from a real one unless something reads the
database back.

  A1  "Employee/Contract Mapping" was retired in a comment and never in the data:
      `<field name="active">False</field>` is the STRING "False", which Odoo's
      Boolean converter coerces to True.
  A2  `pb_sidebar.item_menu_cfg` and `pb_audit.item_audit_console` both claimed
      ADMIN sequence 30, from different modules — so the rail's order depended on
      install order (W8/W18).
  A3  `item_import` and `item_integrations` both claimed
      `hr.integration.connector` in `match_models`. `pb_sidebar.js::_buildIndex`
      builds ONE FLAT map for every match dimension, last writer wins, so the
      connector cockpit lit up Integrations and Import Data never lit up at all.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIaCycle1Sidebar(TransactionCase):

    def _item(self, xmlid):
        # active_test=False: a retired item still EXISTS, and its `active` value
        # is exactly what half of these tests are about.
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.with_context(active_test=False) if rec else rec

    # ============================================================ A1
    def test_a1_employee_contract_mapping_is_off_the_rail(self):
        item = self._item('pb_sidebar.item_emp_mapping')
        self.assertTrue(item, 'the record must still exist — retired, not deleted')
        self.assertFalse(
            item.active,
            'Employee/Contract Mapping is still active. The data file writes '
            '`active` with eval="False"; if the record disagrees, suspect a '
            'frozen ir_model_data.noupdate (W13.1) — the pre-migrate clears it.')

    def test_a1_the_rail_no_longer_serves_the_mapping_item(self):
        """The payload the rail actually renders, not the record behind it.

        `get_sidebar_data()` filters on `active = True`, so this is the
        end-to-end proof: even an admin (who bypasses every group gate) must not
        see the item anywhere.

        CYCLE 5 WIDENED THIS FROM "not in SETUP" TO "not on the rail". The
        original assertion also demanded that a SETUP section still exist, which
        was the right way to phrase it while SETUP was four live items; the rail
        cutover retired the whole section into the Settings hub, so a test that
        insisted on finding it would now fail for the opposite of the reason it
        was written. The claim that mattered — the retired item is not served —
        is stronger stated over the whole payload.
        """
        labels = []
        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            for item in section['items']:
                labels.append(item['name'])
                labels.extend(c['name'] for c in item['children'])
        self.assertNotIn('Employee/Contract Mapping', labels,
                         'the rail still serves the retired item: %s' % labels)

    # ============================================================ A2
    def test_a2_the_admin_collision_pair_is_still_separated(self):
        """The specific collision, named, so a failure says which pair broke.

        CYCLE 5 RENUMBERED ALL THREE. A1's fix put `item_menu_cfg` on 50 and
        `item_section_cfg` on 55 to get them off `pb_audit.item_audit_console`'s
        30; the rail cutover then retired every one of them into the 900 band,
        where they are 972, 973 and 974. Pinning the old numbers would now be
        pinning a state the product deliberately left, so what is asserted is the
        PROPERTY A2 was about — those three records do not share a sequence, and
        they never will again — with the exact values owned by Cycle 5's own
        table (`test_ia_c5.RETIRED_ITEMS`).
        """
        items = [self._item(x) for x in ('pb_sidebar.item_menu_cfg',
                                         'pb_sidebar.item_section_cfg',
                                         'pb_audit.item_audit_console')]
        present = [i for i in items if i]
        self.assertTrue(len(present) >= 2, 'the A2 pair no longer exists')
        seqs = [i.sequence for i in present]
        self.assertEqual(len(set(seqs)), len(seqs),
                         'the A2 collision is back: %s'
                         % {i.name: i.sequence for i in present})

    def test_a2_no_section_has_two_items_on_one_sequence(self):
        """W8/W18 over the WHOLE table, retired items included.

        `active = False` takes an item off the rail but not out of the section,
        and a duplicate only has to matter the moment an admin re-enables one.
        Siblings are keyed by (section, parent) because a sub-item's sequence
        orders it among its siblings, not among the section's top level.
        """
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

    # ============================================================ A3
    def test_a3_only_integrations_claims_the_connector_model(self):
        """The highlight-steal, asserted where it is decided.

        The rail resolves the active item by xmlid -> tag -> res_model against a
        FLAT index (`_buildIndex`), so a model claimed twice does not produce a
        tie or a warning; it produces whichever item was indexed last. The fix is
        to make the claim unique, and that is what this asserts.
        """
        claimers = []
        for item in self.env['pb.sidebar.item'].search([]):
            models = {m.strip() for m in (item.match_models or '').split(',')}
            if 'hr.integration.connector' in models:
                claimers.append(item)
        self.assertEqual(
            len(claimers), 1,
            'hr.integration.connector must be claimed by exactly one live rail '
            'item; claimed by: %s' % ', '.join('%s/%s' % (
                i.section_id.technical_key, i.name) for i in claimers))
        # CYCLE 5: `item_integrations` retired with the rest of SETUP and the
        # claim moved to the Settings hub, which is the one door to connectors
        # now. The RULE is unchanged — exactly one live claimant — and it is the
        # rule that A3 was about.
        settings = self._item('pb_settings.item_settings')
        expected = settings or self._item('pb_sidebar.item_integrations')
        self.assertEqual(claimers[0], expected)

    def test_a3_the_import_claim_survived_the_cutover(self):
        """Fixing a steal must not create a hole: something still lights up for
        the import batches Import Data used to own.

        CYCLE 5 moved the claim rather than keeping it. `item_import` is retired
        (its cockpit is the Pay Run hub's Import lens), and a retired item is not
        in `_buildIndex` at all — so the assertion follows the claim to the live
        item that inherited it.
        """
        claimers = [i for i in self.env['pb.sidebar.item'].search([])
                    if 'hr.payroll.import.batch'
                    in {m.strip() for m in (i.match_models or '').split(',')}]
        self.assertEqual(len(claimers), 1,
                         'hr.payroll.import.batch is claimed by %s live items'
                         % len(claimers))
        tags = {t.strip() for t in (claimers[0].match_action_tags or '').split(',')}
        self.assertIn('pb_import', tags,
                      'the item that claims the batches must also claim the '
                      'cockpit tag, or a bookmark lights nothing')

    def test_a3_there_are_no_double_claims_left_at_all(self):
        """The general form of A3 — and the two more instances it found.

        Written as an equality rather than an emptiness check (W59's shape:
        assert the WORLD, not the delta). Cycle 1 pinned two doubly-claimed
        models it could not fix without changing the rail:

          `hr.payslip.run`  Approvals (OVERVIEW, seq 20) and Pay Runs (PAY RUN)
          `hr.contract`     Employees (PEOPLE, seq 10) and Contracts (seq 20)

        `_buildIndex` walks sections in sequence order and items in sequence
        order, so the LAST writer won: Pay Runs and Contracts respectively —
        which is the item a user would expect in both cases. They were benign
        TODAY and fragile FOREVER, since the winner was a side effect of the
        ordering rather than a decision.

        CYCLE 5 IS THE RAIL CHANGE, and it resolved both by making the claim a
        decision: `hr.payslip.run` belongs to the Pay Run hub and `hr.contract`
        to the People hub, each claimed once, with the four old items retired.
        The expected set is therefore EMPTY — and it stays an equality so that a
        new duplicate fails just as loudly as a resurrected old one.
        """
        known = {}
        claims = {}
        for item in self.env['pb.sidebar.item'].search([]):
            for model in (item.match_models or '').split(','):
                model = model.strip()
                if model:
                    claims.setdefault(model, []).append(item)
        dupes = {m: {i.name for i in v} for m, v in claims.items() if len(v) > 1}
        self.assertEqual(
            dupes, known,
            'the set of doubly-claimed res_models changed. A model claimed by '
            'more than one rail item silently picks a winner (_buildIndex is '
            'flat), which is the A3 defect:\n%s'
            % '\n'.join('%s -> %s' % (m, ', '.join(sorted(v)))
                        for m, v in sorted(dupes.items())))

    def test_action_tags_are_claimed_once_too(self):
        """Same index, same failure mode, other dimension."""
        claims = {}
        for item in self.env['pb.sidebar.item'].search([]):
            tags = list((item.match_action_tags or '').split(','))
            if item.action_tag:
                tags.append(item.action_tag)
            for tag in tags:
                tag = tag.strip()
                if tag:
                    claims.setdefault(tag, []).append(item)
        dupes = {t: v for t, v in claims.items() if len(set(v)) > 1}
        self.assertFalse(dupes, 'an action tag claimed by more than one rail '
                                'item:\n%s' % '\n'.join(
                                    '%s -> %s' % (t, ', '.join(i.name for i in v))
                                    for t, v in dupes.items()))

    # ========================================================= hygiene
    def test_none_of_the_four_touched_records_is_frozen(self):
        """W13.1: a stored `ir_model_data.noupdate` makes `-u` a silent no-op.

        The pre-migrate clears it; this reads the column back, because that is
        the only thing that can tell a real fix from a repo-only one.
        """
        frozen = []
        for name in ('item_emp_mapping', 'item_menu_cfg', 'item_section_cfg',
                     'item_import'):
            imd = self.env['ir.model.data'].search([
                ('module', '=', 'pb_sidebar'), ('name', '=', name),
                ('model', '=', 'pb.sidebar.item'),
            ], limit=1)
            self.assertTrue(imd, 'pb_sidebar.%s has no ir.model.data row' % name)
            if imd.noupdate:
                frozen.append(name)
        self.assertFalse(frozen, 'frozen records — the data file cannot reach '
                                 'them and nothing says so: %s' % frozen)

    def test_every_rail_icon_exists_in_the_fixed_set(self):
        """The rail's icon set is a CLOSED dict inlined in pb_sidebar.js; an
        unknown name renders a plain circle and logs nothing."""
        path = os.path.join(get_module_path('pb_sidebar'), 'static', 'src', 'js',
                            'pb_sidebar.js')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        block = re.search(r'const ICONS = \{(.*?)\n\};', body, re.S)
        self.assertTrue(block, 'could not find the ICONS set in pb_sidebar.js')
        known = set(re.findall(r'^\s{4}"?([A-Za-z0-9_-]+)"?\s*:', block.group(1), re.M))
        items = self.env['pb.sidebar.item'].with_context(active_test=False).search([])
        missing = sorted({i.icon for i in items if i.icon and i.icon not in known})
        self.assertFalse(missing, 'rail icons with no path (silent circles): %s'
                                  % missing)
