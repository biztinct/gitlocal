# -*- coding: utf-8 -*-
"""SCHEMECTX P2, case 12 — the pay package follows the scheme too.

A contract can still hold components belonging to a scheme that does not pay
this person; the create-time fan-out put them there and the clean-up has not
necessarily run yet. Two rules, and they pull in opposite directions on
purpose:

* an EMPTY out-of-scheme component contributes nothing to a package — it never
  did, and it still does not;
* a component that HOLDS money is never dropped, whichever scheme it came from.
  It is money written on this contract. It is labelled instead, so a reader can
  see the scheme does not use it.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxP2Package(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Comp = cls.env['pb.employee.comp']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Config = cls.env.get('hr.formula.config')
        cls.Rule = cls.env.get('hr.formula.rule')
        cls.company = cls.env.company
        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'CB2 Type'})

        cls.codes = ('CBMINE', 'CBTHEIRSPAID', 'CBTHEIRSEMPTY')
        cls.templates = {}
        for code in cls.codes:
            cls.templates[code] = cls.Template.create({
                'name': 'CB2 %s' % code, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0})

        cls.employee = cls.Employee.create(
            {'name': 'CB2 Package Person', 'company_id': cls.company.id})
        cls.contract = cls.Contract.create({
            'name': 'CB2 Package Person - 2026-06-01',
            'employee_id': cls.employee.id, 'wage': 20000000.0,
            'state': 'open', 'date_start': '2026-06-01',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id})
        cls._line('CBMINE', 1000000.0)
        cls._line('CBTHEIRSPAID', 250000.0)
        cls._line('CBTHEIRSEMPTY', 0.0)

        cls.scoped = False
        if cls.Config is not None and cls.Rule is not None \
                and 'pb_paid_by_id' in cls.Employee._fields:
            cls.cfg = cls.Config.create({
                'name': 'CB2 Scheme', 'code': 'CB2SCHEME',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls.Rule.create({
                'config_id': cls.cfg.id, 'name': 'CB2 Mine', 'code': 'CBMINE',
                'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
                'is_contract_component': True})
            cls.employee.sudo().write({'pb_paid_by_id': cls.cfg.id,
                                       'pb_paid_by_stale': False})
            cls.scoped = True

    @classmethod
    def _line(cls, code, amount):
        return cls.Advantage.create({
            'contract_id': cls.contract.id,
            'advantage_template_id': cls.templates[code].id,
            'amount': amount})

    def _lines(self):
        # `_lines_from_contract` is a method OF a package, not a class method:
        # it asks "what would this package read off that contract".
        package = self.Comp.create({'employee_id': self.employee.id,
                                    'effective_date': '2026-06-01'})
        return package._lines_from_contract(self.contract)

    # ==================================================================== 12
    def test_12_the_package_keeps_the_money_and_drops_the_empties(self):
        if not self.scoped:
            self.skipTest("no scheme map or formula engine on this database")
        notes = {}
        for vals in self._lines():
            notes[round(vals['amount'], 2)] = vals.get('note') or ''
        self.assertIn(1000000.0, notes, "the scheme's own component is missing")
        self.assertIn(250000.0, notes,
                      "a component holding 250,000 was dropped from the "
                      "package because of the scheme it came from")
        self.assertNotIn(0.0, notes,
                         "an empty component became a package line")
        self.assertIn('does not use it', notes[250000.0],
                      "the out-of-scheme value is not labelled: %s"
                      % notes[250000.0])
        self.assertNotIn('does not use it', notes[1000000.0])
        for note in notes.values():
            self.assertNotIn('odoo', note.lower())
