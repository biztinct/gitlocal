# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Which overtime rate row a request picks (WFSETUP P3, handover §2.2).

`hr.overtime.request._compute_overtime_config` used ONE search ordered
`country_id desc, company_id desc`. Postgres sorts NULLs FIRST on DESC (the
same trap `pb.ot.ceiling._for_company` documents), so a GLOBAL row (no country,
no company) could beat the company's own country row: a Vietnam public holiday
paid at the 250 % fallback instead of the 300 % the company set.

The rule pinned here: the most specific row wins —
company + country > company > country > global.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOtConfigResolution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref('base.vn')
        cls.au = cls.env.ref('base.au')
        cls.co = cls.env['res.company'].create({'name': 'OT rate co', 'country_id': cls.vn.id})
        cls.other = cls.env['res.company'].create({'name': 'OT rate other', 'country_id': cls.vn.id})
        cls.Config = cls.env['hr.overtime.config']
        # the seeded / existing rows must not take part in the ranking
        cls.Config.search([]).write({'active': False})
        cls.emp = cls.env['hr.employee'].create({'name': 'OT rate person', 'company_id': cls.co.id})
        cls.emp.sudo().country_id = cls.vn

    def row(self, rate, country=False, company=False, kind='holiday', seq=10):
        return self.Config.create({
            'name': 'Rate %s' % rate, 'overtime_type': kind, 'rate_multiplier': rate, 'sequence': seq,
            'country_id': country.id if country else False,
            'company_id': company.id if company else False})

    def request(self, kind='holiday', emp=None):
        emp = emp or self.emp
        return self.env['hr.overtime.request'].create({
            'employee_id': emp.id, 'company_id': emp.company_id.id, 'date': '2026-09-02',
            'overtime_type': kind, 'planned_hours': 1.0, 'reason': 'rate pick'})

    def test_specific_row_beats_global(self):
        """THE PIN: a global row must not win over the company's country row."""
        self.row(2.5)                                   # global
        specific = self.row(3.0, self.vn, self.co)      # company + country
        req = self.request()
        self.assertEqual(req.overtime_config_id, specific)
        self.assertEqual(req.rate_multiplier, 3.0)

    def test_ranking(self):
        glob = self.row(2.5)
        country = self.row(2.7, self.vn)
        self.assertEqual(self.request().overtime_config_id, country, 'country beats global')
        company = self.row(2.8, False, self.co)
        self.assertEqual(self.request().overtime_config_id, company, 'company beats country')
        both = self.row(3.0, self.vn, self.co)
        self.assertEqual(self.request().overtime_config_id, both, 'company + country beats company')
        # another company's or another country's rows are never candidates
        self.row(9.0, self.vn, self.other)
        self.row(9.0, self.au, self.co)
        self.assertEqual(self.request().overtime_config_id, both)
        # a person without a nationality: country rows are not candidates
        plain = self.env['hr.employee'].create({'name': 'OT rate plain', 'company_id': self.co.id})
        self.assertEqual(self.request(emp=plain).overtime_config_id, company)
        both.active = company.active = False
        self.assertEqual(self.request(emp=plain).overtime_config_id, glob)

    def test_pick_helper_matches_requests(self):
        self.row(2.5)
        mine = self.row(3.0, self.vn, self.co)
        Config = self.Config
        self.assertEqual(Config._pb_pick('holiday', self.vn, self.co), mine)
        self.assertEqual(Config._pb_pick('holiday', self.vn, self.co), self.request().overtime_config_id)
        self.assertFalse(Config._pb_pick('extended', self.au, self.other).filtered(
            lambda r: r.company_id == self.co))
