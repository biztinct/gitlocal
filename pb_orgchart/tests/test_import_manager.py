# -*- coding: utf-8 -*-
"""MANAGERCOL — the pay data file keeps managers up to date
(docs/handovers/orgchart/MANAGERCOL_HANDOVER.md §4, cases 1–9, plus extras).

A company of its own, so the name index sees nobody else:

    Dhruv Boss ─┬─ Hồ Hữu Dư            (Vietnamese name, file writes "Ho Huu Du")
                ├─ Nithya Mary Devadoss  (nithya.m@mc.test)
                ├─ R Nithya              (r.nithya@mc.test)
                ├─ Shreya Gaunekar       + Shreya Prasad (archived)
                └─ Cara Coach
    Sam Subject, Tia Two, Uma Three — the people the file's rows are about.
"""
import json
from unittest.mock import patch

from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.pb_hr_payroll_formula.models.column_role_classifier import (
    ROLE_PROFILE, classify_column, is_manager_email_header, is_manager_header)

MAIL_COL = 'Reporting manager Mail ID'


@tagged('post_install', '-at_install')
class TestImportManager(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'MC Test Co'})
        cls.other = cls.env['res.company'].create({'name': 'MC Other Co'})
        cls.env.user.company_ids = [(4, cls.co.id), (4, cls.other.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.co.id]))
        Emp = cls.env['hr.employee'].with_company(cls.co)

        def mk(name, mgr=None, company=None, **kw):
            vals = {'name': name, 'company_id': (company or cls.co).id}
            if mgr:
                vals['parent_id'] = mgr.id
            vals.update(kw)
            return Emp.create(vals)

        cls.boss = mk('Dhruv Boss', work_email='dhruv@mc.test')
        cls.du = mk('Hồ Hữu Dư', cls.boss, work_email='du.ho@mc.test')
        cls.nithya_m = mk('Nithya Mary Devadoss', cls.boss, work_email='nithya.m@mc.test')
        cls.nithya_r = mk('R Nithya', cls.boss, work_email='r.nithya@mc.test')
        cls.shreya = mk('Shreya Gaunekar', cls.boss)
        cls.shreya_gone = mk('Shreya Prasad', cls.boss)
        cls.shreya_gone.active = False
        cls.coachy = mk('Cara Coach', cls.boss)
        cls.sam = mk('Sam Subject')
        cls.tia = mk('Tia Two')
        cls.uma = mk('Uma Three')
        cls.stranger = mk('Ola Elsewhere', company=cls.other)

        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'MC scheme', 'code': 'MCSCHEME', 'country_code': 'VN',
            'state': 'active'})
        Rule = cls.env['hr.formula.rule']
        cls.r_mgr = Rule.create({'config_id': cls.cfg.id, 'name': 'Reporting Manager',
                                 'code': 'MCREPMGR', 'column_type': 'input', 'sequence': 1})
        cls.r_mail = Rule.create({'config_id': cls.cfg.id, 'name': MAIL_COL,
                                  'code': 'MCREPMAIL', 'column_type': 'input', 'sequence': 2})
        cls.r_email = Rule.create({'config_id': cls.cfg.id, 'name': 'Work email',
                                   'code': 'MCWORKMAIL', 'column_type': 'input', 'sequence': 3})
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.mapping = cls._map(cls.r_mgr, 'parent_id')

    @classmethod
    def _map(cls, rule, field):
        return cls.Mapping.create({
            'salary_structure_id': cls.cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': cls.env['ir.model']._get_id('hr.employee'),
            'target_field_id': cls.env['ir.model.fields']._get('hr.employee', field).id,
        })

    # ------------------------------------------------------------ helpers
    def batch(self):
        return self.env['hr.payroll.import.batch'].create({
            'name': 'MC import', 'source_type': 'excel',
            'formula_config_id': self.cfg.id, 'company_id': self.co.id})

    def process(self, rows, batch=None):
        """rows: [(employee, raw dict)]. Every line exists before the first
        is processed — exactly as an import loads them all, then runs."""
        batch = batch or self.batch()
        Line = self.env['hr.payroll.import.line']
        lines = [Line.create({'batch_id': batch.id, 'employee_id': e.id,
                              'raw_data_json': json.dumps(raw)}) for e, raw in rows]
        for (emp, raw), line in zip(rows, lines):
            batch._update_employee_from_raw_data(emp, raw, line=line)
        self.env.flush_all()
        for e, _r in rows:
            e.invalidate_recordset()
        return batch, lines

    def tracking(self, emp):
        self.env.flush_all()
        self.env.cr.precommit.run()
        return self.env['mail.tracking.value'].search([
            ('field_id.name', '=', 'parent_id'),
            ('mail_message_id.res_id', '=', emp.id),
            ('mail_message_id.model', '=', 'hr.employee')])

    # ------------------------------------------------------------------ 1
    def test_01_headers(self):
        for h in ('Reporting Manager', 'Master Reporting Manager', 'Reporting Manager Name',
                  'Direct manager', 'Người quản lý', 'Quản lý trực tiếp', 'Atasan Langsung'):
            self.assertEqual(classify_column(h)[0], ROLE_PROFILE, h)
            self.assertTrue(is_manager_header(h), h)
        self.assertTrue(is_manager_header('Consolidated|Master Reporting Manager'))
        for h in ('Reporting manager Mail ID', 'Master Reporting Manager mail ID',
                  'Hiring Manager', 'Master Hiring Manager', 'Manager allowance'):
            self.assertFalse(is_manager_header(h), "%s is not the manager" % h)
        self.assertTrue(is_manager_email_header('Consolidated|Reporting manager Mail ID'))
        self.assertFalse(is_manager_email_header('Hiring Manager mail'))
        self.assertFalse(is_manager_email_header('Reporting Manager'))
        # a file with ONLY the mail and hiring columns is not a manager file
        b = self.batch()
        self.env['hr.payroll.import.line'].create({
            'batch_id': b.id, 'employee_id': self.sam.id,
            'raw_data_json': json.dumps({MAIL_COL: 'x@y.z', 'Hiring Manager': 'Dhruv Boss'})})
        self.assertEqual(b._pb_manager_unmapped_header(), '')

    # ------------------------------------------------------------------ 2
    def test_02_exact_name_sets_manager_only(self):
        boss_user = new_test_user(self.env, login='mc_boss', groups='base.group_user',
                                  company_id=self.co.id, company_ids=[self.co.id])
        self.coachy.user_id = boss_user.id
        Emp = self.env['hr.employee']
        before = {f: self.sam[f] for f in ('coach_id', 'leave_manager_id', 'expense_manager_id')
                  if f in Emp._fields}
        b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Cara Coach'})])
        self.assertEqual(self.sam.parent_id, self.coachy)
        self.assertEqual(line.pb_manager_state, 'set')
        self.assertFalse(line.pb_manager_note)
        for f, v in before.items():
            self.assertEqual(self.sam[f], v, "the import changes the manager only, not %s" % f)
        self.assertFalse(self.sam.coach_id, "a manager from the file never sets a coach")
        self.assertEqual(len(self.tracking(self.sam)), 1)
        self.assertEqual(b.pb_manager_set_count, 1)
        # case-insensitive
        self.process([(self.tia, {'Reporting Manager': 'cara COACH'})])
        self.assertEqual(self.tia.parent_id, self.coachy)

    # ------------------------------------------------------------------ 3
    def test_03_accent_insensitive(self):
        _b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Ho Huu Du'})])
        self.assertEqual(self.sam.parent_id, self.du)
        self.assertEqual(line.pb_manager_state, 'set')
        # a reordered and a short name resolve too, when only one person fits
        self.process([(self.tia, {'Reporting Manager': 'Nithya R'}),
                      (self.uma, {'Reporting Manager': 'Devadoss'})])
        self.assertEqual(self.tia.parent_id, self.nithya_r)
        self.assertEqual(self.uma.parent_id, self.nithya_m)

    # ------------------------------------------------------------------ 4
    def test_04_email_breaks_a_tie_only_when_present(self):
        b, (l1, l2) = self.process([
            (self.sam, {'Reporting Manager': 'Nithya', MAIL_COL: 'Nithya.M@mc.test'}),
            (self.tia, {'Reporting Manager': 'Nithya', MAIL_COL: 'r.nithya@mc.test'}),
        ])
        self.assertEqual(self.sam.parent_id, self.nithya_m)
        self.assertEqual(self.tia.parent_id, self.nithya_r)
        self.assertEqual((l1.pb_manager_state, l2.pb_manager_state), ('set', 'set'))
        b2, (line,) = self.process([(self.uma, {'Reporting Manager': 'Nithya'})])
        self.assertFalse(self.uma.parent_id)
        self.assertEqual(line.pb_manager_state, 'unmatched')
        self.assertEqual(line.pb_manager_note, 'Manager not set: “Nithya” fits 2 people.')
        self.assertEqual(b2.pb_manager_unmatched_count, 1)
        self.assertEqual(b2.pb_manager_set_count, 0)

    def test_04b_a_file_whose_emails_disagree_never_breaks_a_tie(self):
        """rize Vietnam: one address beside names that cannot be one person —
        the email column is not trusted for that file (the seed's rule)."""
        _b, (l1, _l2) = self.process([
            (self.sam, {'Reporting Manager': 'Nithya', MAIL_COL: 'nithya.m@mc.test'}),
            (self.tia, {'Reporting Manager': 'Ho Huu Du', MAIL_COL: 'nithya.m@mc.test'}),
        ])
        self.assertFalse(self.sam.parent_id)
        self.assertEqual(l1.pb_manager_note, 'Manager not set: “Nithya” fits 2 people.')
        self.assertEqual(self.tia.parent_id, self.du, "a full name needs no email")

    def test_04c_a_short_name_must_not_contradict_a_trusted_email(self):
        _b, (line,) = self.process([
            (self.sam, {'Reporting Manager': 'Devadoss', MAIL_COL: 'r.nithya@mc.test'})])
        self.assertFalse(self.sam.parent_id)
        self.assertIn('fits Nithya Mary Devadoss', line.pb_manager_note)

    def test_04d_someone_who_has_left_blocks_and_is_never_picked(self):
        b, (l1, l2) = self.process([
            (self.sam, {'Reporting Manager': 'Shreya'}),
            (self.tia, {'Reporting Manager': 'Shreya Prasad'}),
        ])
        self.assertFalse(self.sam.parent_id, "one current + one who has left is not clean")
        self.assertEqual(l1.pb_manager_note,
                         'Manager not set: “Shreya” fits 2 people, and 1 of them has left.')
        self.assertFalse(self.tia.parent_id)
        self.assertEqual(l2.pb_manager_note, 'Manager not set: Shreya Prasad has left.')
        self.assertEqual(b.pb_manager_unmatched_count, 2)

    def test_04e_other_company_and_self(self):
        _b, (l1, l2) = self.process([
            (self.sam, {'Reporting Manager': 'Ola Elsewhere'}),
            (self.tia, {'Reporting Manager': 'Tia Two'}),
        ])
        self.assertFalse(self.sam.parent_id, "a company outside the import is never searched")
        self.assertEqual(l1.pb_manager_note, 'Manager not set: nobody is called “Ola Elsewhere”.')
        self.assertFalse(self.tia.parent_id)
        self.assertEqual(l2.pb_manager_note, 'Manager not set: “Tia Two” is this person.')

    def test_04f_employee_code(self):
        if 'employee_id' not in self.env['hr.employee']._fields:
            self.skipTest('no employee code field on this build')
        self.coachy.employee_id = 'MC0042'
        self.process([(self.sam, {'Reporting Manager': 'mc0042'})])
        self.assertEqual(self.sam.parent_id, self.coachy)

    # ------------------------------------------------------------------ 5
    def test_05_blank_keeps_and_unknown_is_noted(self):
        self.sam.parent_id = self.boss.id
        b, (l1, l2) = self.process([
            (self.sam, {'Reporting Manager': '   '}),
            (self.tia, {'Reporting Manager': 'Board'}),
        ])
        self.assertEqual(self.sam.parent_id, self.boss, "a blank cell never clears a manager")
        self.assertEqual(l1.pb_manager_state, 'blank')
        self.assertFalse(self.tia.parent_id)
        self.assertEqual(l2.pb_manager_state, 'unmatched')
        self.assertEqual(l2.pb_manager_note, 'Manager not set: nobody is called “Board”.')
        self.assertEqual((b.pb_manager_blank_count, b.pb_manager_unmatched_count), (1, 1))
        # a missing column is a blank cell too
        _b, (l3,) = self.process([(self.sam, {'Something else': 1})])
        self.assertEqual(self.sam.parent_id, self.boss)
        self.assertEqual(l3.pb_manager_state, 'blank')

    # ------------------------------------------------------------------ 6
    def test_06_loop_is_refused(self):
        self.tia.parent_id = self.sam.id          # Tia reports to Sam
        _b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Tia Two'})])
        self.assertFalse(self.sam.parent_id)
        self.assertEqual(line.pb_manager_state, 'unmatched')
        self.assertEqual(line.pb_manager_note,
                         "Manager not set: Tia Two is inside Sam Subject's own team.")

    # ------------------------------------------------------------------ 7
    def test_07_reimport_unchanged_writes_nothing(self):
        self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss'})])
        self.assertEqual(len(self.tracking(self.sam)), 1)
        b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss'})])
        self.assertEqual(line.pb_manager_state, 'same')
        self.assertEqual(len(self.tracking(self.sam)), 1, "no second history row")
        self.assertEqual(b.pb_manager_same_count, 1)
        # the file wins: a different name replaces the manager
        self.process([(self.sam, {'Reporting Manager': 'Cara Coach'})])
        self.assertEqual(self.sam.parent_id, self.coachy)
        self.assertEqual(len(self.tracking(self.sam)), 2)

    # ------------------------------------------------------------------ 8
    def test_08_no_mapping_does_nothing(self):
        self.mapping.unlink()
        b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss'})])
        self.assertFalse(self.sam.parent_id)
        self.assertFalse(line.pb_manager_state)
        self.assertFalse(line.pb_manager_note)
        s = b._pb_manager_summary()
        self.assertTrue(s['show'])
        self.assertIn('“Reporting Manager” column', s['hint'])
        self.assertFalse(s['rows'])

    # ------------------------------------------------------------------ 9
    def test_09_generic_path_never_writes_the_manager(self):
        Batch = type(self.env['hr.payroll.import.batch'])
        seen = []
        orig = Batch._coerce_mapped_value

        def spy(this, record, field, value):
            seen.append(getattr(field, 'name', None))
            return orig(this, record, field, value)

        self._map(self.r_email, 'work_email')
        with patch.object(Batch, '_coerce_mapped_value', spy):
            self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss', 'Work email': 's@mc.test'}),
                          (self.tia, {'Reporting Manager': 'Board'})])
        self.assertNotIn('parent_id', seen, "the generic resolver never sees the manager")
        self.assertIn('work_email', seen, "other mapped columns still flow")
        self.assertEqual(self.sam.work_email, 's@mc.test')
        self.assertEqual(self.sam.parent_id, self.boss)
        self.assertEqual(len(self.tracking(self.sam)), 1, "exactly one history row")
        self.assertFalse(self.env['hr.employee'].with_context(active_test=False).search(
            [('name', '=', 'Board')]), "no employee is ever created from a manager cell")

    def test_09b_only_mapping_is_the_manager(self):
        """The empty-remainder trap: `super()` would fetch every mapping again."""
        b = self.batch()
        self.assertEqual(b._get_mapping_updates(self.sam, {'Reporting Manager': 'Dhruv Boss'}), {})

    # -------------------------------------------------------------- extras
    def test_10_step_never_fails_the_row(self):
        Org = type(self.env['pb.orgchart'])
        with patch.object(Org, '_set_managers', side_effect=RuntimeError('boom')):
            _b, (line,) = self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss'})])
        self.assertFalse(self.sam.parent_id)
        self.assertEqual(line.pb_manager_state, 'unmatched')
        self.assertEqual(line.pb_manager_note, 'Manager not set: the change could not be saved.')

    def test_11_summary_and_screens(self):
        b, _lines = self.process([
            (self.sam, {'Reporting Manager': 'Dhruv Boss'}),
            (self.tia, {'Reporting Manager': 'Nithya'}),
            (self.uma, {'Reporting Manager': ''}),
        ])
        s = b._pb_manager_summary()
        self.assertTrue(s['show'])
        self.assertEqual(s['tone'], 'amber')
        self.assertEqual({c['key']: c['n'] for c in s['chips']},
                         {'set': 1, 'same': 0, 'unmatched': 1, 'blank': 1})
        self.assertEqual([r['state'] for r in s['rows']], ['unmatched', 'blank'])
        self.assertEqual(s['rows'][0]['name'], 'Tia Two')
        self.assertEqual(s['toggle'], 'See the 2 rows')
        wiz = self.env['pb.import.wizard'].get_summary(b.id)
        self.assertEqual(wiz['managers']['chips'], s['chips'])
        cockpit = self.env['pb.import.batch.cockpit'].with_context(
            allowed_company_ids=[self.co.id]).get_batch_detail(b.id)
        self.assertEqual(cockpit['managers']['rows'], s['rows'])
        # nothing looked at yet → nothing shown
        self.assertFalse(self.batch()._pb_manager_summary()['show'])

    def test_13_the_file_wins_over_the_record_with_a_declared_source(self):
        """rize Indonesia/Singapore declare the column as an Excel source; the
        shared reader then let the record's own manager win the walk and
        answer "no value", so a changed manager in the file was ignored."""
        self.r_mgr.set_source_binding('excel', 'Reporting Manager')
        self.sam.parent_id = self.boss.id
        self.tia.parent_id = self.boss.id
        b, (l1, l2) = self.process([
            (self.sam, {'Reporting Manager': 'Cara Coach'}),
            (self.tia, {'Reporting Manager': 'Dhruv Boss'}),
        ])
        self.assertEqual(self.sam.parent_id, self.coachy, "the file wins")
        self.assertEqual(l1.pb_manager_state, 'set')
        self.assertEqual(self.tia.parent_id, self.boss)
        self.assertEqual(l2.pb_manager_state, 'same')

    def test_12_new_starter_created_earlier_in_the_file_can_be_a_manager(self):
        b = self.batch()
        self.process([(self.sam, {'Reporting Manager': 'Dhruv Boss'})], batch=b)
        newbie = self.env['hr.employee'].create({'name': 'Nina Newcomer', 'company_id': self.co.id})
        self.process([(self.tia, {'Reporting Manager': 'Nina Newcomer'})], batch=b)
        self.assertEqual(self.tia.parent_id, newbie)
