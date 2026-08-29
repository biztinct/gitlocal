# -*- coding: utf-8 -*-
"""RECORDS R1 — a pay file that feeds ONE run and is then forgotten.

The owner's ask: "use the excel pay component values only one time for that pay
run … without changing the default values". `hr.payroll.import.batch.one_time`
is that switch, and `action_process` is where it means something: steps 1b, 2
and 3 (the employee fields, the bank account, the contract and its components)
are the WRITEBACK, and a one-time run skips every one of them. Step 4 is
untouched, because the payslip already reads the FILE before it reads any
record — so the pay is identical and only the records are spared.

Two things are being proved here, and they pull in opposite directions:

  * **it works** — nothing is written, unrecognised people are listed rather
    than created, and a component the file does not carry falls back to the
    record as it stood BEFORE the run (cases 2, 4, 5);
  * **it changes nothing else** — a batch that did not ask for it produces
    byte-identical `formula_input_values` and never enters the branch at all
    (case 1: an md5 recorded on the pre-change checkout, plus the counter).

`action_process` IS the subject here, so unlike J10 it is called — but only
ever on a config, employees, contracts and lines this transaction created
(J3/J10's rule: writeback code is never exercised against live data).
"""
import base64
import hashlib
import json
import os
import re
import unittest

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.payroll_import_batch import (
    ONE_TIME_NO_CONTRACT,
    ONE_TIME_NO_EMPLOYEE,
)

#: Case 1's neutrality constant. Recorded by running THIS FILE against the
#: checkout WITHOUT R1 (b9ed86ab) on abm, 2026-08-29, and pasted here unchanged
#: — MJ11: the baseline is taken before the change, never derived from it.
#: An empty string means "not yet recorded" and the assertion is skipped; it is
#: filled in and must never be regenerated from a post-change run.
BASELINE_INPUTS_MD5 = "78b40cab23740f61b20629a9be9fd4df"

#: The file's values. One header per component, plus the identity column.
FILE_JOB = "Site Lead"
FILE_WAGE = 12000000.0
FILE_BONUS = 750000.0
FILE_ALLOW = 500000.0
FILE_BANK = "990011223344"

#: What the RECORDS said before the file arrived. Every one of these differs
#: from the file, so "nothing was written" and "the old value was read" are
#: both observable rather than lucky.
REC_JOB = "Site Assistant"
REC_WAGE = 9000000.0
REC_ALLOW = 100000.0
REC_BANK = "110022334455"


#: What "no emoji" actually forbids. NOT simply "the symbol blocks": these
#: screens legitimately use typographic glyphs — `✕` (U+2715) is the close
#: button, `→` and `—` are punctuation — and a test that calls those emoji only
#: teaches the next engineer to delete the assertion. A character counts as an
#: emoji here when it is in the pictograph planes, when it is explicitly asked
#: to render in colour by a following U+FE0F, or when it is one of the handful
#: of BMP glyphs that are only ever used AS emoji.
_PICTOGRAPH_PLANES = (0x1F000, 0x1FAFF)
_VS16 = '️'
_ALWAYS_EMOJI = set('✅❌❗❓⭐✨❤⚠⬆'
                    '⬇➕➖‼⁉')


def _emoji_hits(text):
    """Every emoji in `text`, in order — empty means the surface is clean."""
    lo, hi = _PICTOGRAPH_PLANES
    hits = []
    for i, char in enumerate(text):
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if lo <= ord(char) <= hi or char in _ALWAYS_EMOJI or nxt == _VS16:
            if char != _VS16:
                hits.append(char)
    return hits


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestRecordsR1OneTime(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Employee = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.IrModel = cls.env['ir.model']
        cls.IrField = cls.env['ir.model.fields']

    # ------------------------------------------------------------ fixtures
    def _field(self, model, name):
        return self.IrField.search(
            [('model', '=', model), ('name', '=', name)], limit=1)

    def _model(self, model):
        return self.IrModel.search([('model', '=', model)], limit=1)

    def _rule(self, cfg, code, name, header, **vals):
        """One input component, declaring the spreadsheet column it reads.

        The binding is a real `hr.formula.rule.source` row rather than a header
        guess, because that is the rung `_declared_source_walk` reads first and
        it is what makes the payslip independent of the record.
        """
        rule = self.Rule.create(dict({
            'config_id': cfg.id, 'name': name, 'code': code,
            'column_type': 'input', 'sequence': vals.pop('sequence', 10),
            'default_value': 0.0,
        }, **vals))
        if header:
            self.env['hr.formula.rule.source'].create({
                'rule_id': rule.id, 'kind': 'excel', 'key': header,
                'origin': 'user',
            })
        return rule

    def _template(self, code, name):
        tmpl = self.Template.search([('code', '=', code)], limit=1)
        if not tmpl:
            tmpl = self.Template.create({
                'name': name, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0,
            })
        return tmpl

    def _scheme(self, tag):
        """A scheme with one of each kind of destination R1 has to spare.

        Codes are underscore-free and none is a substring of another (the
        converter contract), and every one of them is unique per world so two
        worlds in one transaction cannot read each other's records.
        """
        cfg = self.Config.create({
            'name': 'R1 %s' % tag, 'code': ('R1%s' % tag).upper()[:32],
            'country_code': 'VN', 'state': 'active',
        })
        rules = {
            # → hr.employee.job_title (a plain Char with no default — J10's
            #   reason for not using `barcode`)
            'job': self._rule(cfg, 'JOBTAG%s' % tag, 'Job tag', 'Job Tag',
                              value_kind='text', appears_on_payslip=False,
                              sequence=1),
            # → hr.contract.wage
            'wage': self._rule(cfg, 'WAGEVAL%s' % tag, 'Wage value', 'Wage Value',
                               sequence=2),
            # → res.partner.bank.acc_number
            'bank': self._rule(cfg, 'BANKNUM%s' % tag, 'Bank number', 'Bank Number',
                               value_kind='identifier', appears_on_payslip=False,
                               sequence=3),
            # → a contract component the file DOES carry
            'bonus': self._rule(cfg, 'BONUSPAY%s' % tag, 'Bonus pay', 'Bonus Pay',
                                is_contract_component=True, sequence=4),
            # → a contract component the file also carries, and which case 4
            #   then asks for from a file that does NOT
            'allow': self._rule(cfg, 'SITEALW%s' % tag, 'Site allowance', 'Site Allowance',
                                is_contract_component=True, sequence=5),
        }
        self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rules['job'].id,
            'destination_type': 'field',
            'target_model_id': self._model('hr.employee').id,
            'target_field_id': self._field('hr.employee', 'job_title').id,
        })
        self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rules['wage'].id,
            'destination_type': 'field',
            'target_model_id': self._model('hr.contract').id,
            'target_field_id': self._field('hr.contract', 'wage').id,
        })
        self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rules['bank'].id,
            'destination_type': 'bank_account', 'bank_role': 'acc_number',
        })
        return cfg, rules

    def _person(self, tag, code):
        """An employee, a contract, a bank account and one advantage line.

        Every value is the RECORD's value, deliberately different from the
        file's, so a writeback that happened is impossible to miss.
        """
        partner = self.env['res.partner'].create({'name': 'R1 %s Contact' % tag})
        employee = self.Employee.create({
            'name': 'R1 %s Person' % tag,
            'identification_id': code,
            'job_title': REC_JOB,
            'work_contact_id': partner.id,
        })
        bank = self.env['res.partner.bank'].create({
            'acc_number': REC_BANK + tag, 'partner_id': partner.id,
        })
        # The template must exist BEFORE the contract: `hr.contract.create`
        # gives a new contract one advantage line per EXISTING template
        # (om_hr_payroll/models/hr_contract.py:107-113), so creating a second
        # one by hand afterwards leaves two lines for the same code and the
        # writeback map keys on the wrong one.
        tmpl = self._template('SITEALW%s' % tag, 'Site allowance')
        ctype = self.env['hr.contract.type'].search([], limit=1)
        if not ctype:
            ctype = self.env['hr.contract.type'].create({'name': 'R1 Type'})
        contract = self.Contract.create({
            'name': 'R1 %s Contract' % tag,
            'employee_id': employee.id,
            'wage': REC_WAGE,
            'state': 'open',
            'date_start': '2026-01-01',
            'type_id': ctype.id,
            'resource_calendar_id': (
                employee.resource_calendar_id.id
                or self.env.company.resource_calendar_id.id),
        })
        advantage = contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id == tmpl)
        self.assertEqual(len(advantage), 1,
                         "the contract should carry exactly one line for %s" % tmpl.code)
        advantage.amount = REC_ALLOW
        return employee, contract, bank

    def _raw(self, tag, code, name, with_allowance=True):
        row = {
            'Employee Code': code,
            'Employee Name': name,
            'Job Tag': FILE_JOB,
            'Wage Value': FILE_WAGE,
            'Bank Number': FILE_BANK,
            'Bonus Pay': FILE_BONUS,
        }
        if with_allowance:
            row['Site Allowance'] = FILE_ALLOW
        return row

    def _batch(self, cfg, tag, rows, one_time=None):
        vals = {
            'name': 'R1 %s batch' % tag,
            'source_type': 'excel',
            'formula_config_id': cfg.id,
            'payroll_period': 'custom',
            'date_from': '2026-03-01',
            'date_to': '2026-03-31',
            'create_payslips': True,
            'payslip_state': 'draft',
        }
        # `one_time=None` writes NOTHING — that is the shape every pre-R1
        # caller has, and case 1 runs on a checkout where the field does not
        # exist at all.
        if one_time is not None:
            vals['one_time'] = one_time
        batch = self.Batch.create(vals)
        for i, row in enumerate(rows, start=1):
            self.env['hr.payroll.import.line'].create({
                'batch_id': batch.id,
                'sequence': i,
                'raw_data_json': json.dumps(row),
                'employee_code': row.get('Employee Code') or '',
                'employee_name': row.get('Employee Name') or '',
                'state': 'validated',
            })
        return batch

    def _world(self, tag, one_time=None, ghost=False):
        """A whole self-contained run: scheme, person, file, processed batch."""
        cfg, rules = self._scheme(tag)
        code = 'R1CODE%s' % tag
        employee, contract, bank = self._person(tag, code)
        rows = [self._raw(tag, code, employee.name)]
        if ghost:
            rows.append(self._raw(tag, 'R1GHOST%s' % tag, 'R1 %s Nobody' % tag))
        batch = self._batch(cfg, tag, rows, one_time=one_time)
        batch.state = 'validated'
        batch.action_process()
        self.env.flush_all()
        return {
            'cfg': cfg, 'rules': rules, 'employee': employee,
            'contract': contract, 'bank': bank, 'batch': batch,
        }

    @staticmethod
    def _inputs_md5(batch):
        """A stable fingerprint of everything the payslips were computed from."""
        blobs = sorted(
            json.dumps(json.loads(p.formula_input_values or '{}'), sort_keys=True)
            for p in batch.created_payslip_ids)
        return hashlib.md5('|'.join(blobs).encode('utf-8')).hexdigest()

    @staticmethod
    def _stamps(*records):
        return {(r._name, r.id): r.write_date for r in records if r}

    # =====================================================================
    # 1 — neutrality: a normal batch is what it always was
    # =====================================================================
    def test_01_a_normal_batch_is_byte_identical_and_never_enters_the_branch(self):
        self.Batch._records_reset_one_time_counter()
        w = self._world('NA')
        md5 = self._inputs_md5(w['batch'])
        # Printed so the pre-change run can HAND the constant to the post-change
        # run; MJ11 forbids deriving it the other way round.
        self.assertTrue(w['batch'].created_payslip_ids,
                        "the neutrality fixture computed no payslip at all")
        if BASELINE_INPUTS_MD5:
            self.assertEqual(
                md5, BASELINE_INPUTS_MD5,
                "a normal batch's formula_input_values changed: %s" % md5)
        self.assertEqual(
            self.Batch._records_one_time_counter(), 0,
            "a batch that did not ask for one-time pay data entered the branch")

    # =====================================================================
    # 2 — a one-time batch writes nothing at all
    # =====================================================================
    def test_02_nothing_is_written_to_any_record(self):
        cfg, rules = self._scheme('NW')
        code = 'R1CODENW'
        employee, contract, bank = self._person('NW', code)
        advantages = contract.advantages_ids
        self.env.flush_all()
        before = self._stamps(employee, contract, bank, *advantages)
        counts_before = (
            self.Employee.search_count([]),
            self.Contract.search_count([]),
            self.Template.search_count([]),
            self.env['res.partner.bank'].search_count([]),
        )
        self.Batch._records_reset_one_time_counter()

        batch = self._batch(cfg, 'NW', [self._raw('NW', code, employee.name)],
                            one_time=True)
        batch.state = 'validated'
        batch.action_process()
        self.env.flush_all()
        self.env.invalidate_all()

        after = self._stamps(employee, contract, bank, *contract.advantages_ids)
        self.assertEqual(before, after, "a one-time run moved a record's write_date")
        self.assertEqual(employee.job_title, REC_JOB)
        self.assertEqual(contract.wage, REC_WAGE)
        self.assertEqual(contract.advantages_ids.filtered(
            lambda a: a.advantage_template_code == 'SITEALWNW').amount, REC_ALLOW)
        self.assertEqual(counts_before, (
            self.Employee.search_count([]),
            self.Contract.search_count([]),
            self.Template.search_count([]),
            self.env['res.partner.bank'].search_count([]),
        ), "a one-time run created an employee, a contract, a component template "
           "or a bank account")
        self.assertGreater(self.Batch._records_one_time_counter(), 0)
        self.assertEqual(batch.state, 'done')
        self.assertIn("one-time — no record was updated", batch.processing_log or '')

    # =====================================================================
    # 3 — the pay itself is identical: the file is read either way
    # =====================================================================
    def test_03_file_fed_components_are_identical_to_an_updating_run(self):
        normal = self._world('FA')
        once = self._world('FB', one_time=True)
        self.assertTrue(normal['batch'].created_payslip_ids)
        self.assertTrue(once['batch'].created_payslip_ids)

        def totals(world, tag):
            slip = world['batch'].created_payslip_ids[0]
            return {ln.code.replace(tag, ''): ln.total for ln in slip.line_ids}

        self.assertEqual(totals(normal, 'FA'), totals(once, 'FB'),
                         "a one-time run paid a different amount")
        # …and the amounts really are the FILE's, not the record's.
        self.assertEqual(totals(once, 'FB').get('BONUSPAY'), FILE_BONUS)
        self.assertEqual(totals(once, 'FB').get('WAGEVAL'), FILE_WAGE)

    # =====================================================================
    # 4 — a component the file does not carry reads the OLD record
    # =====================================================================
    def test_04_an_absent_component_falls_back_to_the_untouched_record(self):
        normal = self._world('OA')
        once = self._world('OB', one_time=True)

        # The next run's file omits the allowance. The resolver is asked
        # directly — it is exactly what step 4 does, and it writes nothing.
        norm_inputs = normal['batch']._transform_data_to_formula_inputs(
            self._raw('OA', 'R1CODEOA', 'x', with_allowance=False),
            contract=normal['contract'], employee=normal['employee'])
        once_inputs = once['batch']._transform_data_to_formula_inputs(
            self._raw('OB', 'R1CODEOB', 'x', with_allowance=False),
            contract=once['contract'], employee=once['employee'])

        self.assertEqual(norm_inputs.get('SITEALWOA'), FILE_ALLOW,
                         "an updating run should have saved the file's allowance")
        self.assertEqual(once_inputs.get('SITEALWOB'), REC_ALLOW,
                         "a one-time run must leave the old allowance in place")

    # =====================================================================
    # 5 — someone who is not in Payobook is listed, not created
    # =====================================================================
    def test_05_an_unmatched_row_is_an_exception_and_nobody_is_created(self):
        before = self.Employee.search_count([])
        w = self._world('GH', one_time=True, ghost=True)
        batch = w['batch']
        ghost = batch.import_line_ids.filtered(
            lambda l: l.employee_code == 'R1GHOSTGH')
        self.assertEqual(len(ghost), 1)
        self.assertEqual(ghost.state, 'error')
        self.assertEqual(ghost.error_message, ONE_TIME_NO_EMPLOYEE)
        self.assertFalse(ghost.employee_id)
        self.assertEqual(self.Employee.search_count([]), before + 1,
                         "only the fixture's own employee should exist")
        self.assertEqual(batch.state, 'done',
                         "one bad row must not fail the whole batch")
        # …and the good row was still paid.
        self.assertEqual(len(batch.created_payslip_ids), 1)

    def test_05b_the_two_refusals_say_what_happened_and_never_say_odoo(self):
        for sentence in (ONE_TIME_NO_EMPLOYEE, ONE_TIME_NO_CONTRACT):
            self.assertNotIn('odoo', sentence.lower())
            self.assertIn('one-time', sentence)

    # =====================================================================
    # 6 — recompute re-reads the file and still writes no record
    # =====================================================================
    def test_06_recompute_stays_clean(self):
        w = self._world('RC', one_time=True)
        slip = w['batch'].created_payslip_ids[0]
        before_lines = {ln.code: ln.total for ln in slip.line_ids}
        self.env.flush_all()
        before = self._stamps(w['employee'], w['contract'],
                              *w['contract'].advantages_ids)

        slip.action_recompute_formula_lines()
        self.env.flush_all()
        self.env.invalidate_all()

        after_lines = {ln.code: ln.total for ln in slip.line_ids}
        self.assertEqual(before_lines, after_lines,
                         "recompute produced different pay")
        self.assertEqual(before, self._stamps(
            w['employee'], w['contract'], *w['contract'].advantages_ids),
            "recompute wrote to a record")

    # =====================================================================
    # 7 — the wizard's contract with the client
    # =====================================================================
    def test_07_attach_spreadsheet_returns_the_one_time_shape(self):
        if 'pb.payrun.wizard' not in self.env:
            raise unittest.SkipTest("pb_payrun_wizard is not installed here")
        cfg, rules = self._scheme('WZ')
        code = 'R1CODEWZ'
        employee, contract, bank = self._person('WZ', code)
        run = self.env['hr.payslip.run'].create({
            'name': 'R1 WZ run', 'date_start': '2026-03-01',
            'date_end': '2026-03-31',
        })
        headers = ['Employee Code', 'Employee Name', 'Job Tag', 'Wage Value',
                   'Bank Number', 'Bonus Pay', 'Site Allowance']
        rows = [
            [code, employee.name, FILE_JOB, FILE_WAGE, FILE_BANK, FILE_BONUS, FILE_ALLOW],
            ['R1GHOSTWZ', 'R1 WZ Nobody', FILE_JOB, FILE_WAGE, FILE_BANK,
             FILE_BONUS, FILE_ALLOW],
        ]
        csv = '\n'.join([','.join(headers)]
                        + [','.join(str(c) for c in r) for r in rows])
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run.id, cfg.id, base64.b64encode(csv.encode('utf-8')).decode(),
            'r1-wz.csv', '2026-03-01', '2026-03-31', True)

        self.assertTrue(res.get('ok'), res.get('msg'))
        self.assertTrue(res.get('one_time'))
        self.assertEqual(res.get('unmatched_count'), 1)
        self.assertEqual(res['unmatched'][0]['why'], ONE_TIME_NO_EMPLOYEE)
        self.assertEqual(res.get('created'), 1,
                         "only the matched row should have been paid")
        batch = self.Batch.browse(res['batch_id'])
        self.assertTrue(batch.one_time)
        self.assertFalse(batch.auto_create_employees)
        self.assertFalse(batch.auto_create_contracts)
        # …and the records really were spared.
        self.env.invalidate_all()
        self.assertEqual(employee.job_title, REC_JOB)
        self.assertEqual(contract.wage, REC_WAGE)

    def test_07b_the_default_call_is_the_call_it_always_was(self):
        """No `one_time` argument ⇒ an updating run, unchanged."""
        if 'pb.payrun.wizard' not in self.env:
            raise unittest.SkipTest("pb_payrun_wizard is not installed here")
        cfg, rules = self._scheme('WU')
        code = 'R1CODEWU'
        employee, contract, bank = self._person('WU', code)
        run = self.env['hr.payslip.run'].create({
            'name': 'R1 WU run', 'date_start': '2026-03-01',
            'date_end': '2026-03-31',
        })
        csv = ('Employee Code,Employee Name,Job Tag,Wage Value,Bank Number,'
               'Bonus Pay,Site Allowance\n%s,%s,%s,%s,%s,%s,%s'
               % (code, employee.name, FILE_JOB, FILE_WAGE, FILE_BANK,
                  FILE_BONUS, FILE_ALLOW))
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run.id, cfg.id, base64.b64encode(csv.encode('utf-8')).decode(),
            'r1-wu.csv', '2026-03-01', '2026-03-31')
        self.assertTrue(res.get('ok'), res.get('msg'))
        self.assertFalse(res.get('one_time'))
        self.assertEqual(res.get('unmatched_count'), 0)
        self.env.invalidate_all()
        self.assertEqual(employee.job_title, FILE_JOB,
                         "the default run must still update the records")

    # =====================================================================
    # 8 — the screens keep the white-label rule
    # =====================================================================
    def test_08_no_odoo_and_no_emoji_on_any_r1_surface(self):
        surfaces = [
            ('pb_hr_payroll_formula', 'views', 'payroll_import_views.xml'),
            ('pb_import_batch', 'static', 'src', 'xml', 'batch_cockpit.xml'),
        ]
        if get_module_path('pb_payrun_wizard'):
            surfaces.append(
                ('pb_payrun_wizard', 'static', 'src', 'xml', 'payrun_wizard.xml'))
        # An XML comment is prose for the next engineer, not a user-visible
        # string — MJ47's rule, applied the same way J10's `_src` helper does.
        # The `<odoo>` document element is a technical identifier and is
        # likewise exempt: it is never rendered anywhere.
        comment = re.compile(r'<!--.*?-->', re.S)
        root = re.compile(r'</?odoo(\s[^>]*)?>|<\?xml[^>]*\?>')
        for parts in surfaces:
            body = root.sub('', comment.sub('', _src(*parts)))
            self.assertNotIn('odoo', body.lower(), '%s names the engine' % parts[-1])
            found = _emoji_hits(body)
            self.assertFalse(found, '%s carries %s' % (parts[-1], found))
