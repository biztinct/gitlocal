# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A-series: anonymity by construction (owner ruling P4).

"With full database access as HR there is no path from an answer to a
person": these tests read the DATABASE itself (every text column of every
table, the table definitions, foreign keys), not only the screens."""
import json
import os

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import VoiceCase

MARK = 'S9C-UNIQUE-COMMENT-7f3a'


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoiceAnonymity(VoiceCase):

    def _db_tables_holding(self, needle):
        """Every (table, column) in the whole database whose text holds
        ``needle`` — the "full database access" search."""
        self.env.flush_all()
        cr = self.env.cr
        cr.execute("""
            SELECT c.table_name, c.column_name
              FROM information_schema.columns c
              JOIN information_schema.tables t
                ON t.table_schema = c.table_schema AND t.table_name = c.table_name
             WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
               AND c.data_type IN ('text', 'character varying', 'jsonb')
        """)
        found = []
        for table, column in cr.fetchall():
            cr.execute('SELECT 1 FROM "%s" WHERE "%s"::text LIKE %%s LIMIT 1'
                       % (table, column), ('%' + needle + '%',))
            if cr.fetchone():
                found.append((table, column))
        return found

    # ------------------------------------------------------------------ A1
    def test_A01_answer_table_has_no_person_and_no_time_columns(self):
        cr = self.env.cr
        cr.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_name = 'pb_voice_box'""")
        cols = {r[0] for r in cr.fetchall()}
        self.assertEqual(cols, {'id', 'round_id', 'marks', 'sealed'})
        # no foreign key from the answer table to a person or a login
        cr.execute("""
            SELECT ccu.table_name FROM information_schema.table_constraints tc
              JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
             WHERE tc.table_name = 'pb_voice_box'
               AND tc.constraint_type = 'FOREIGN KEY'""")
        self.assertEqual({r[0] for r in cr.fetchall()}, {'pb_voice_round'})
        self.assertFalse(self.Box._log_access)

    # ------------------------------------------------------------------ A2
    def test_A02_open_round_holds_no_answer_in_the_database(self):
        rnd = self.open_round()
        for i, emp in enumerate(self.team_mai[:6]):
            self.answer(rnd, emp, scale=5, enps=10,
                        text='%s %d' % (MARK, i))
        # the comments are nowhere in the database while the round is open
        self.assertEqual(self._db_tables_holding(MARK), [])
        # ... they are sealed in the file store, outside the database
        paths = self.Box._seal_paths(rnd.id)
        self.assertEqual(len(paths), 6)
        blob = ''.join(open(p, encoding='utf-8').read() for p in paths)
        self.assertIn(MARK, blob)
        # and a sealed file carries no person: no id, name, login or e-mail
        for emp in self.team_mai[:6]:
            user = self.users[emp.id]
            for token in (emp.name, user.login, emp.work_email):
                self.assertNotIn(token, blob)
            self.assertNotIn('"e%d"' % emp.id, blob)
        for p in paths:
            self.assertEqual(set(json.loads(open(p).read())), {'k', 'a', 't'})

    # ------------------------------------------------------------------ A3
    def test_A03_who_has_answered_is_separate_unjoinable_codes(self):
        rnd = self.open_round()
        box = self.Box.sudo().search([('round_id', '=', rnd.id)])
        people = self.team_mai[:5]
        for emp in people:
            self.answer(rnd, emp)
        box.invalidate_recordset()
        marks = json.loads(box.marks)
        self.assertEqual(len(marks), 5)
        self.assertEqual(marks, sorted(marks), 'sorted: no answering order')
        ids = {str(e.id) for e in self.everyone} | {
            str(u.id) for u in self.users.values()}
        for code in marks:
            self.assertEqual(len(code), 40)
            self.assertNotIn(code, ids)
            for emp in people:
                self.assertNotIn(emp.name, code)
        # the key is NOT in the database: no column anywhere holds it
        key = self.Box._voice_key(rnd.id)
        self.assertTrue(key)
        self.assertEqual(self._db_tables_holding(key.hex()), [])
        self.assertTrue(os.path.exists(os.path.join(
            self.Box._voice_dir(rnd.id), 'key')))

    # ------------------------------------------------------------------ A4
    def test_A04_answering_writes_nothing_about_the_person(self):
        rnd = self.open_round()
        emp = self.team_mai[0]
        user = self.users[emp.id]
        self.env.flush_all()
        cr = self.env.cr
        before = {}
        for table in ('mail_message', 'mail_activity', 'mail_mail', 'bus_bus',
                      'mail_followers', 'ir_logging', 'res_device_log'):
            cr.execute('SELECT COALESCE(MAX(id), 0) FROM "%s"' % table)
            before[table] = cr.fetchone()[0]
        cr.execute('SELECT write_date, write_uid FROM pb_voice_round WHERE id=%s',
                   (rnd.id,))
        round_stamp = cr.fetchone()
        cr.execute('SELECT MAX(write_date) FROM pb_voice_invite WHERE round_id=%s',
                   (rnd.id,))
        invite_stamp = cr.fetchone()
        self.answer(rnd, emp, text='nothing about me')
        self.env.flush_all()
        for table, top in before.items():
            cr.execute('SELECT COUNT(*) FROM "%s" WHERE id > %%s' % table, (top,))
            self.assertEqual(cr.fetchone()[0], 0,
                             '%s got a row from an answer' % table)
        cr.execute('SELECT write_date, write_uid FROM pb_voice_round WHERE id=%s',
                   (rnd.id,))
        self.assertEqual(cr.fetchone(), round_stamp, 'the round was not touched')
        cr.execute('SELECT MAX(write_date) FROM pb_voice_invite WHERE round_id=%s',
                   (rnd.id,))
        self.assertEqual(cr.fetchone(), invite_stamp, 'who was asked: untouched')
        self.assertNotIn(user.id, [rnd.sudo().write_uid.id])

    # ------------------------------------------------------------------ A5
    def test_A05_close_writes_counts_once_and_forgets_who_answered(self):
        rnd = self.open_round()
        for i, emp in enumerate(self.team_mai[:6]):
            self.answer(rnd, emp, scale=(i % 5) + 1, enps=i,
                        text='%s z%d' % (MARK, 5 - i))
        self.close(rnd)
        box = self.Box.sudo().search([('round_id', '=', rnd.id)])
        self.assertEqual(box.marks, '[]', 'the has-answered list is wiped')
        sealed = json.loads(box.sealed)
        self.assertEqual(set(sealed), {'cells', 'notes'})
        # counts per cell, never a row per answer
        total = sum(c['n'] for c in sealed['cells'].values())
        self.assertEqual(total, 6)
        notes = sealed['notes']
        self.assertEqual(notes, sorted(notes), 'comments sorted, not by arrival')
        # no person anywhere in what is kept
        blob = box.sealed
        for emp in self.everyone:
            self.assertNotIn(emp.name, blob)
            self.assertNotIn(self.users[emp.id].login, blob)
        # cell keys name groups of the round, never people
        group_ids = set(rnd.sudo().group_ids.ids)
        for cell in sealed['cells']:
            self.assertTrue({int(x) for x in cell.split('.') if x} <= group_ids)
        # the key and the sealed files are gone: nobody can tell who answered
        self.assertIsNone(self.Box._voice_key(rnd.id))
        self.assertEqual(self.Box._seal_paths(rnd.id), [])
        self.assertFalse(rnd.sudo()._voice_unanswered())
        self.assertEqual(rnd.answered_count, 6)

    def test_A05b_close_destroys_the_key_on_commit(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        self.as_hr(self.Round).browse(rnd.id).action_close()
        self.assertTrue(self.Box._voice_key(rnd.id), 'kept until the commit')
        self.env.cr.postcommit.run()
        self.assertIsNone(self.Box._voice_key(rnd.id))
        self.assertFalse(os.path.exists(self.Box._voice_dir(rnd.id)))

    # ------------------------------------------------------------------ A6
    def test_A06_too_few_answers_nothing_is_kept(self):
        rnd = self.open_round()
        for emp in self.team_mai[:4]:
            self.answer(rnd, emp, text=MARK + ' few')
        self.close(rnd)
        self.assertEqual(rnd.result_state, 'too_few')
        box = self.Box.sudo().search([('round_id', '=', rnd.id)])
        self.assertFalse(box.sealed)
        self.assertEqual(self._db_tables_holding(MARK), [])
        res = self.as_hr(self.Voice).get_results(rnd.id)
        self.assertEqual(res['state'], 'too_few')
        self.assertNotIn('figures', res)

    # ------------------------------------------------------------------ A7
    def test_A07_hr_cannot_read_the_answer_table(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        self.env.flush_all()
        self.env.invalidate_all()
        Box = self.as_hr(self.Box)
        with self.assertRaises(AccessError):
            Box.search([])
        with self.assertRaises(AccessError):
            Box.browse(1).read(['marks'])
        # nor a system administrator's ordinary screens
        admin = self.env.ref('base.user_admin')
        with self.assertRaises(AccessError):
            self.Box.with_user(admin).search_read([], ['marks', 'sealed'])
        # who was asked shows no cell to HR (field for system only)
        inv = self.as_hr(self.env['pb.voice.invite']).search(
            [('round_id', '=', rnd.id)], limit=1)
        self.assertNotIn('cell', inv.fields_get())

    # ------------------------------------------------------------------ A8
    def test_A08_cells_are_never_smaller_than_the_floor(self):
        rnd = self.open_round()
        invites = rnd.sudo().invite_ids
        self.assertEqual(len(invites), 27)
        cells = {}
        for inv in invites:
            cells.setdefault(inv.cell, []).append(inv.employee_id)
        for cell, people in cells.items():
            self.assertGreaterEqual(len(people), 5, cell)
        kinds = {(g.kind, g.department_id.name or g.manager_id.name or '')
                 for g in rnd.sudo().group_ids}
        self.assertIn(('team', 'DEMO Mai'), kinds)
        self.assertNotIn(('team', 'DEMO Oanh'), kinds, 'team of 4: no group')
        self.assertNotIn(('department', 'DEMO Tiny'), kinds, '2 people: no group')
        for g in rnd.sudo().group_ids:
            self.assertGreaterEqual(g.invited, 5)

    def test_A08b_cells_algorithm_on_awkward_shapes(self):
        """Random-ish shapes: every cell >= floor, every group >= floor."""
        Emp = self.env['hr.employee']
        emps = Emp.browse([e.id for e in self.everyone])
        for floor in (5, 6, 8, 12):
            rows, keys = self.Round._voice_cells(emps, floor)
            sizes = {}
            for _e, cell in rows:
                sizes[cell] = sizes.get(cell, 0) + 1
            self.assertTrue(all(n >= floor for n in sizes.values()), floor)
            for key in keys:
                self.assertGreaterEqual(
                    sum(1 for _e, c in rows if key in c), floor)

    # ------------------------------------------------------------------ A9
    def test_A09_one_answer_per_person(self):
        rnd = self.open_round()
        emp = self.team_mai[0]
        self.answer(rnd, emp)
        with self.assertRaises(Exception):
            self.answer(rnd, emp)
        self.assertEqual(len(self.Box._seal_paths(rnd.id)), 1)
        self.assertEqual(rnd.sudo().voice_answered_so_far(), 1)
