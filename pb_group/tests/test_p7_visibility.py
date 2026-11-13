# -*- coding: utf-8 -*-
"""GROUP P7 — who sees what, and the promise that nothing else changed.

T1  `scope_for` answers each kind; NO ROW is the switcher, unchanged; a scope
    whose record has gone falls back to everything and warns the administrator
T2  the record rules and every GROUP facade narrow to the reader's own part of
    the group, and an "Everything" reader is byte-for-byte unchanged
T3  the "as this person" preview equals what that person actually gets
T4  the Vietnamese catalogue is complete, loads, and says "Odoo" nowhere
T5  ticking many departments writes them all in ONE call
T6  nothing in this module names the retired planning module

THE ONE THING THIS FILE EXISTS TO PROVE
---------------------------------------
`test_t1_nobody_is_narrowed_until_somebody_says_so` and
`test_t2_an_everything_reader_is_unchanged` are the phase's safety rail. Every
other test here can fail and the product still works the way it did yesterday;
if either of those two fails, an install of this phase changes what a live
payroll customer can see, and that is the one thing it may never do.
"""

import os
import re

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.basename(HERE)


@tagged('post_install', '-at_install')
class TestP7Visibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Visibility = cls.env['pb.group.visibility'].sudo()
        cls.Room = cls.env['pb.group.room']
        Company = cls.env['res.company'].sudo()
        cls.country_a = cls.env['res.country'].sudo().search(
            [('code', '=', 'VN')], limit=1) or cls.env[
                'res.country'].sudo().create({'name': 'ZQ Landia',
                                              'code': 'ZQ'})
        cls.country_b = cls.env['res.country'].sudo().search(
            [('code', '=', 'SG')], limit=1) or cls.env[
                'res.country'].sudo().create({'name': 'ZQ Otherland',
                                              'code': 'ZY'})
        cls.co_a = Company.create({'name': 'ZQ P7 Alpha'})
        cls.co_a.partner_id.country_id = cls.country_a
        cls.co_b = Company.create({'name': 'ZQ P7 Beta'})
        cls.co_b.partner_id.country_id = cls.country_b

        cls.group = cls.env['pb.group'].sudo().create({
            'name': 'ZQ P7 Group',
            'presentation_currency_id': cls.co_a.currency_id.id,
        })
        (cls.co_a | cls.co_b).write({'pb_group_id': cls.group.id})

        Department = cls.env['hr.department'].sudo()
        cls.dept_a = Department.create({'name': 'ZQ P7 Alpha Top',
                                        'company_id': cls.co_a.id})
        cls.dept_a_child = Department.create({'name': 'ZQ P7 Alpha Inner',
                                              'company_id': cls.co_a.id,
                                              'parent_id': cls.dept_a.id})
        cls.dept_b = Department.create({'name': 'ZQ P7 Beta Top',
                                        'company_id': cls.co_b.id})

        Division = cls.env['pb.division'].sudo()
        cls.div_one = Division.create({'name': 'ZQ P7 Retail'})
        cls.div_two = Division.create({'name': 'ZQ P7 Logistics'})
        Link = cls.env['pb.division.link'].sudo()
        cls.link_one = Link.create({'division_id': cls.div_one.id,
                                    'department_id': cls.dept_a.id,
                                    'date_from': '2020-01-01'})
        cls.link_two = Link.create({'division_id': cls.div_two.id,
                                    'department_id': cls.dept_b.id,
                                    'date_from': '2020-01-01'})

        cls.plain = new_test_user(cls.env, login='zq_p7_plain',
                                  groups='base.group_user,hr.group_hr_user')
        cls.plain.write({'company_ids': [(6, 0, [cls.co_a.id, cls.co_b.id])],
                         'company_id': cls.co_a.id})

        cls.head = new_test_user(cls.env, login='zq_p7_head',
                                 groups='base.group_user,hr.group_hr_user')
        cls.head.write({'company_ids': [(6, 0, [cls.co_a.id, cls.co_b.id])],
                        'company_id': cls.co_a.id})

        cls.country_hr = new_test_user(
            cls.env, login='zq_p7_country',
            groups='base.group_user,hr.group_hr_user')
        cls.country_hr.write({
            'company_ids': [(6, 0, [cls.co_a.id, cls.co_b.id])],
            'company_id': cls.co_a.id})

    def _as(self, user):
        return self.env(user=user, context=dict(
            self.env.context,
            allowed_company_ids=user.company_ids.ids))

    # ================================================================== T1
    def test_t1_nobody_is_narrowed_until_somebody_says_so(self):
        """T1. THE SAFETY RAIL. No row means the switcher, exactly as before.

        Every helper this phase adds has to be a no-op for a person nobody has
        limited — that is what makes it safe to install on a live payroll
        database, and it is asserted here rather than assumed.
        """
        scope = self.Visibility.scope_for(self.plain)
        self.assertFalse(scope['has_row'])
        self.assertFalse(scope['restricted'])
        self.assertEqual(sorted(scope['company_ids']),
                         sorted(self.plain.company_ids.ids))
        self.assertEqual(scope['division_ids'], [])
        self.assertEqual(scope['department_ids'], [])
        # and the narrowing helpers hand the list straight back
        wanted = [self.co_a.id, self.co_b.id, 1]
        self.assertEqual(
            self.Visibility.narrow_companies(wanted, self.plain), wanted)
        self.assertEqual(self.Visibility.visible_division_ids(self.plain), [])
        self.assertEqual(self.Visibility.scope_note(self.plain), '')

    def test_t1b_each_kind_answers_what_it_says(self):
        """T1. Everything, one country, one company, one division."""
        self.Visibility.set_for(self.head.id, 'all')
        scope = self.Visibility.scope_for(self.head)
        self.assertTrue(scope['has_row'])
        self.assertFalse(scope['restricted'],
                         '"Everything" must narrow nothing')

        self.Visibility.set_for(self.head.id, 'company', self.co_a.id)
        scope = self.Visibility.scope_for(self.head)
        self.assertTrue(scope['restricted'])
        self.assertEqual(scope['company_ids'], [self.co_a.id])

        self.Visibility.set_for(self.country_hr.id, 'country',
                                self.country_b.id)
        scope = self.Visibility.scope_for(self.country_hr)
        self.assertEqual(scope['company_ids'], [self.co_b.id],
                         'a country scope is the companies in that country')

        self.Visibility.set_for(self.head.id, 'division', self.div_one.id)
        scope = self.Visibility.scope_for(self.head)
        self.assertEqual(scope['division_ids'], [self.div_one.id])
        self.assertEqual(scope['company_ids'], [self.co_a.id])
        # an attachment at the top of a branch carries everything under it
        self.assertIn(self.dept_a.id, scope['department_ids'])
        self.assertIn(self.dept_a_child.id, scope['department_ids'])
        self.assertNotIn(self.dept_b.id, scope['department_ids'])

    def test_t1c_never_wider_than_the_companies_they_hold(self):
        """T1. A visibility row may only ever TAKE AWAY."""
        self.head.write({'company_ids': [(6, 0, [self.co_a.id])],
                         'company_id': self.co_a.id})
        self.Visibility.set_for(self.head.id, 'country', self.country_b.id)
        scope = self.Visibility.scope_for(self.head)
        self.assertEqual(scope['company_ids'], [],
                         'a scope may not hand out a company nobody gave them')

    def test_t1d_a_scope_that_is_gone_falls_back_and_warns(self):
        """T1. A dead scope is never a silent lock-out."""
        self.Visibility.set_for(self.head.id, 'division', self.div_two.id)
        self.div_two.write({'active': False})
        self.env.registry.clear_cache()
        scope = self.Visibility.scope_for(self.head)
        self.assertTrue(scope['has_row'])
        self.assertFalse(scope['ref_ok'])
        self.assertFalse(scope['restricted'],
                         'a dead scope falls back to what they saw before')
        self.assertTrue(scope['warning'], 'the administrator is warned')
        self.assertIn(self.head.name, scope['warning'])
        self.div_two.write({'active': True})

    def test_t1e_a_person_has_one_row_and_lifting_it_is_a_removal(self):
        self.Visibility.set_for(self.head.id, 'company', self.co_a.id)
        self.Visibility.set_for(self.head.id, 'company', self.co_b.id)
        rows = self.Visibility.search([('user_id', '=', self.head.id)])
        self.assertEqual(len(rows), 1, 'one person, one row')
        self.Visibility.set_for(self.head.id, False)
        self.assertFalse(
            self.Visibility.search([('user_id', '=', self.head.id)]))
        with self.assertRaises(UserError):
            self.Visibility.set_for(self.head.id, 'division')

    # ================================================================== T2
    def test_t2_the_record_rules_narrow_to_the_division(self):
        """T2. A division head reads their own division's rows and no others."""
        self.Visibility.set_for(self.head.id, 'division', self.div_one.id)
        self.env.registry.clear_cache()
        env = self._as(self.head)
        links = env['pb.division.link'].search([
            ('id', 'in', (self.link_one | self.link_two).ids)])
        self.assertEqual(links.ids, [self.link_one.id],
                         'the other division is not theirs to read')
        self.assertEqual(env.user.pb_vis_kind, 'division')
        self.assertEqual(env.user.pb_vis_division_ids.ids, [self.div_one.id])

    def test_t2b_an_everything_reader_is_unchanged(self):
        """T2. THE SAFETY RAIL, at the record-rule level."""
        before = self.env['pb.division.link'].with_user(self.plain).search([
            ('id', 'in', (self.link_one | self.link_two).ids)]).ids
        self.Visibility.set_for(self.plain.id, 'all')
        self.env.registry.clear_cache()
        after = self.env['pb.division.link'].with_user(self.plain).search([
            ('id', 'in', (self.link_one | self.link_two).ids)]).ids
        self.assertEqual(sorted(before), sorted(after))
        self.assertFalse(self.plain.with_user(self.plain).pb_vis_kind)
        self.Visibility.set_for(self.plain.id, False)

    def test_t2c_every_group_facade_narrows(self):
        """T2. The same answer on every screen, or the model is a fiction.

        Each surface is skipped when its module is not on the database, so
        this runs in full on the rehearsal clone and degrades honestly
        anywhere else.
        """
        self.Visibility.set_for(self.head.id, 'company', self.co_a.id)
        self.env.registry.clear_cache()
        env = self._as(self.head)
        checks = 0

        # every facade inherits the same mixin, so one loop answers them all
        for model in ('pb.group.room', 'pb.scheme.board', 'pb.explorer',
                      'pb.insights', 'pb.decision.room', 'pb.assignments',
                      'pb.pay.bands', 'pb.pay.fairness', 'pb.pay.reviews'):
            if model not in env:
                continue
            narrowed = env[model]._visible_companies(
                [self.co_a.id, self.co_b.id])
            self.assertEqual(narrowed, [self.co_a.id],
                             '%s did not narrow to the reader' % model)
            checks += 1
        self.assertGreaterEqual(checks, 4, 'no GROUP facade was reachable')

        # and the sentence a narrowed reader is shown
        note = env['pb.group.room']._visibility_note()
        self.assertTrue(note)
        self.assertIn(self.co_a.name, note)

    def test_t2d_the_group_screen_counts_only_their_part(self):
        self.Visibility.set_for(self.head.id, 'company', self.co_a.id)
        self.env.registry.clear_cache()
        room = self._as(self.head)['pb.group.room'].get_room()
        self.assertTrue(room['allowed'])
        self.assertTrue(room.get('scope_note'))

    # ================================================================== T3
    def test_t3_the_preview_equals_what_they_actually_get(self):
        """T3. The hero. A preview that is a second implementation lies."""
        self.Visibility.set_for(self.head.id, 'division', self.div_one.id)
        self.env.registry.clear_cache()
        preview = self.Room.preview_visibility(self.head.id)
        self.assertEqual([c['id'] for c in preview['companies']],
                         [self.co_a.id])
        self.assertEqual([d['id'] for d in preview['divisions']],
                         [self.div_one.id])
        self.assertIn(self.head.name, preview['headline'])
        self.assertIn(self.div_one.name, preview['headline'])
        self.assertTrue(preview['surfaces'],
                        'the preview names the screens it is about')

        # what the person actually gets, read as them
        env = self._as(self.head)
        actual = env['pb.group.room']._visible_companies(
            [self.co_a.id, self.co_b.id])
        self.assertEqual(actual, [c['id'] for c in preview['companies']],
                         'the preview and the screen disagree')

    def test_t3b_a_scope_with_nothing_in_it_says_so(self):
        """T3. Zero dead ends: an empty answer is a sentence, not a blank."""
        self.head.write({'company_ids': [(6, 0, [self.co_a.id])],
                         'company_id': self.co_a.id})
        self.Visibility.set_for(self.head.id, 'company', self.co_b.id)
        self.env.registry.clear_cache()
        preview = self.Room.preview_visibility(self.head.id)
        self.assertEqual(preview['companies'], [])
        self.assertTrue(preview['headline'])
        self.assertTrue(preview['surfaces'][0]['line'])

    # ================================================================== T5
    def test_t5_many_departments_attach_in_one_call(self):
        """T5 (polish item P1). Tick many, press once."""
        Link = self.env['pb.division.link'].sudo()
        before = Link.search_count([('division_id', '=', self.div_two.id)])
        room = self.Room.attach_departments(
            self.div_two.id, [self.dept_a_child.id, self.dept_b.id])
        self.assertEqual(room['attached'], 2)
        self.assertEqual(room['attach_failed'], 0)
        after = Link.search_count([('division_id', '=', self.div_two.id),
                                   ('date_to', '=', False)])
        self.assertEqual(after, before + 1,
                         'both departments are now in the division')
        with self.assertRaises(UserError):
            self.Room.attach_departments(self.div_two.id, [])

    # ================================================================== T6
    def test_t6_nothing_here_names_the_retired_planning_module(self):
        found = []
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs
                       if d not in ('__pycache__', 'tests', 'i18n')]
            for name in files:
                if not name.endswith(('.py', '.js', '.xml', '.scss', '.csv')):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as fh:
                    if re.search(r'\bwfp[._]', fh.read()):
                        found.append(path)
        self.assertFalse(found, 'a retired reference survives: %s' % found)


@tagged('post_install', '-at_install')
class TestP7Vietnamese(TransactionCase):
    """T4. Every word this module can print exists in Vietnamese.

    The shape WFPLAN P3 established and every GROUP module now copies: the
    exported template is the question, the catalogue is the answer, and a
    survivor is a screen that reads as BROKEN to a Vietnamese reader rather
    than as foreign. Skipped where no template has been exported yet, so a
    fresh checkout does not fail on a file that is generated.
    """

    def test_t4_every_word_of_this_module_exists_in_vietnamese(self):
        import polib
        po_path = os.path.join(HERE, 'i18n', 'vi_VN.po')
        self.assertTrue(os.path.exists(po_path), 'the translation is missing')
        po = polib.pofile(po_path)
        self.assertEqual(po.metadata.get('Language'), 'vi_VN')
        self.assertEqual(po.metadata.get('Project-Id-Version'),
                         'Payobook 19.0')

        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        empty = [k for k, v in done.items() if not (v or '').strip()]
        self.assertFalse(empty[:20],
                         '%s terms are still English: %s'
                         % (len(empty), empty[:20]))

        # GR5 — an entry with no `#. module:` comment takes the WHOLE DATABASE
        # down on install (`translate.py` calls `.groups()` on a None match).
        nameless = [e.msgid[:60] for e in po
                    if e.msgid and not re.match(r'(module[s]?): (\w+)',
                                                e.comment or '')]
        self.assertFalse(nameless[:10],
                         'an entry carries no module comment: %s'
                         % nameless[:10])

        # the white-label rule reaches into the translations
        said = [k for k, v in done.items() if 'odoo' in (v or '').lower()]
        self.assertFalse(said, 'a translated string says "Odoo": %s' % said)

        # a sentence that loses its placeholder renders a gap where the
        # number should be
        broken = []
        for msgid, text in done.items():
            if not text:
                continue
            for hit in set(re.findall(r'%\([^)]+\)s', msgid)):
                if hit not in text:
                    broken.append('%s -> %s' % (msgid[:40], hit))
            if msgid.count('%s') != text.count('%s'):
                broken.append('%s -> %%s count' % msgid[:40])
        self.assertFalse(broken[:10],
                         'a translation lost a placeholder: %s' % broken[:10])

    def test_t4c_the_catalogue_covers_the_whole_exported_template(self):
        """The completeness half: a term the module EXPORTS and the catalogue
        has never seen is a survivor, and a survivor reads as a broken screen
        rather than as a foreign one."""
        import polib
        pot_path = os.path.join(HERE, 'i18n', '%s.pot' % MODULE)
        if not os.path.exists(pot_path):
            self.skipTest('no exported template is committed for %s' % MODULE)
        pot = polib.pofile(pot_path)
        po = polib.pofile(os.path.join(HERE, 'i18n', 'vi_VN.po'))
        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        missing = [e.msgid for e in pot
                   if e.msgid and not (done.get(e.msgid) or '').strip()]
        self.assertFalse(
            missing[:20],
            '%s of %s exported terms are still English: %s'
            % (len(missing), len(pot), missing[:20]))

    def test_t4b_the_catalogue_is_loaded_on_this_database(self):
        """A file on disk is not a translation until the platform holds it."""
        vi = self.env['res.lang'].with_context(active_test=False).search(
            [('code', '=', 'vi_VN')], limit=1)
        if not vi or not vi.active:
            self.skipTest('vi_VN is not active on this database')
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'pb.group'), ('name', '=', 'name')], limit=1)
        self.assertTrue(field)
        english = field.with_context(lang='en_US').field_description
        vietnamese = field.with_context(lang='vi_VN').field_description
        self.assertTrue(vietnamese)
        self.assertNotEqual(vietnamese, english,
                            'the Vietnamese catalogue has not been loaded')
