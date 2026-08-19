# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""W105 — a payslip LINE is visible exactly when its payslip is.

Why this file exists at all. `hr.payslip.line` carried ACLs for the payroll
tiers and no record rule that admitted them, so the only rule that applied to a
payroll manager was the base.group_user self-service one and they read the lines
of their OWN payslip and nothing else. Every money figure on the Payroll Report
came out zero on a run holding ₫21B, and neither surface was broken: pb_insights
reads under sudo() and showed the money, the ORM-reading report did not. W105 in
docs/WORKFORCE_REDESIGN_CONVENTIONS.md is the write-up.

The repair is a rule per payslip rule, and the risk of the repair is that a
mirror is written WIDER than its twin — which is a money leak, not a bug. So
this file gates it from both ends:

* the FUNCTIONAL gate (test_02..test_06) builds five payslips across three
  departments and asserts, per persona, that the set of slips they can read and
  the set of slips their readable lines belong to are THE SAME SET. Not a
  subset in either direction. That is the owner's sentence, executable.
* the STRUCTURAL gate (test_07..test_09) pins every hr.payslip.line rule to the
  hr.payslip rule it mirrors, by xmlid, and fails on any line rule that is not
  in the table — so a future rule added without a twin cannot ship quietly.

Cheap and deliberate: everything is scoped to the fixture ids, never a bare
search([]), because this suite runs against a database with 30k payslips on it.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


# Each pair is (line rule xmlid, the payslip rule it mirrors). The domain of the
# left is the domain of the right with every leaf re-rooted through slip_id.
# Adding a line rule means adding a row here; that is the point.
MIRROR_PAIRS = [
    ('om_hr_payroll.hr_payslip_line_rule_officer',
     'om_hr_payroll.hr_payroll_rule_officer'),
    ('om_hr_payroll.hr_payslip_line_rule_manager',
     'om_hr_payroll.hr_payslip_rule_manager'),
    ('pb_hr_payroll_base.rule_payslip_line_officer_access',
     'pb_hr_payroll_base.rule_payslip_country_access'),
    ('pb_hr_payroll_base.rule_payslip_line_integration_access',
     'pb_hr_payroll_base.rule_integration_data_access'),
    # Pre-existing twins this cycle did not write, listed so the "no line rule
    # without a twin" gate below covers the whole table rather than only ours.
    ('pb_me_portal.payslip_line_rule_ess_own',
     'pb_hr_payroll_base.rule_payslip_employee_self_service'),
    ('pb_demo.rule_demo_payslip_line_read_all',
     'pb_demo.rule_demo_payslip_read_all'),
]

# Payslip rules with NO line twin, and the reason each one is correct.
# base.group_portal holds no ir.model.access row on hr.payslip at all, so the
# portal payslip rule admits nothing today. Giving lines a portal rule would
# mean adding a portal ACL — i.e. widening money visibility to a tier that has
# none. Mirroring means matching the slip, and the slip is unreachable.
UNMIRRORED_SLIP_RULES = {
    'pb_hr_payroll_base.rule_portal_employee_payslip_access',
}


@tagged('post_install', '-at_install')
class TestPayslipLineAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company

        def group(xmlid):
            return env.ref(xmlid, raise_if_not_found=False)

        cls.g_om_officer = group('om_hr_payroll.group_hr_payroll_user')
        cls.g_om_manager = group('om_hr_payroll.group_hr_payroll_manager')
        cls.g_pb_officer = group('pb_hr_payroll_base.group_payroll_base_officer')
        cls.g_integration = group('pb_hr_payroll_base.group_payroll_integration_user')
        cls.g_user = env.ref('base.group_user')

        def mkuser(login, groups):
            return env['res.users'].create({
                'name': 'W105 %s' % login,
                'login': 'w105_%s' % login,
                'password': 'w105_%s_pw!' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.g_user.id] + [g.id for g in groups if g])],
            })

        # Every persona is an internal user first: base.group_user is what
        # carries the ESS ACL on both models, so a difference below is always
        # the tier's rules talking, never a missing ACL.
        cls.u_plain = mkuser('plain', [])
        cls.u_om_officer = mkuser('om_officer', [cls.g_om_officer])
        cls.u_om_manager = mkuser('om_manager', [cls.g_om_manager])
        cls.u_pb_officer = mkuser('pb_officer', [cls.g_pb_officer])
        cls.u_integration = mkuser('integration', [cls.g_integration])

        Emp = env['hr.employee']
        Dept = env['hr.department']

        def mkemp(name, user=None, dept=None):
            return Emp.create({
                'name': 'W105 %s' % name,
                'company_id': cls.company.id,
                'user_id': user.id if user else False,
                'department_id': dept.id if dept else False,
            })

        # The officer's own employee record — it is also dept_led's manager, so
        # the om officer rule's three OR branches are all exercised: own slip,
        # a managed department's slip, and a departmentless slip.
        cls.e_officer = mkemp('officer self', user=cls.u_om_officer)
        cls.dept_led = Dept.create({'name': 'W105 Led', 'company_id': cls.company.id,
                                    'manager_id': cls.e_officer.id})
        cls.dept_other = Dept.create({'name': 'W105 Other', 'company_id': cls.company.id})

        cls.e_led = mkemp('led', dept=cls.dept_led)
        cls.e_other = mkemp('other', dept=cls.dept_other)
        cls.e_nodept = mkemp('nodept')
        cls.e_plain = mkemp('plain self', user=cls.u_plain, dept=cls.dept_other)

        cls.employees = (cls.e_officer + cls.e_led + cls.e_other
                         + cls.e_nodept + cls.e_plain)

        struct = env['hr.payroll.structure'].create({
            'name': 'W105 Structure', 'code': 'W105STR',
            'company_id': cls.company.id,
        })
        category = env['hr.salary.rule.category'].create({
            'name': 'W105 Cat', 'code': 'W105CAT',
        })
        # `hr.salary.rule` in this om_hr_payroll carries NO struct_id — the
        # link is the structure's own `rule_ids` m2m
        # (om_hr_payroll/models/hr_salary_rule.py:28). Writing the field the
        # upstream module has would raise on create, which is how this fixture
        # first failed.
        cls.rule = env['hr.salary.rule'].create({
            'name': 'W105 Basic', 'code': 'W105BASIC', 'sequence': 1,
            'category_id': category.id, 'amount_select': 'fix',
            'amount_fix': 1000.0,
        })
        struct.write({'rule_ids': [(4, cls.rule.id)]})

        Contract = env['hr.contract']
        Payslip = env['hr.payslip']
        Line = env['hr.payslip.line']

        cls.slip_of = {}
        cls.lines_of = {}
        for emp in cls.employees:
            contract = Contract.create({
                'name': 'W105 %s contract' % emp.name,
                'employee_id': emp.id,
                'wage': 10000.0,
                'date_start': date(2030, 1, 1),
                'struct_id': struct.id,
                'company_id': cls.company.id,
                'state': 'open',
            })
            slip = Payslip.create({
                'name': 'W105 slip %s' % emp.name,
                'employee_id': emp.id,
                'contract_id': contract.id,
                'struct_id': struct.id,
                'date_from': date(2030, 1, 1),
                'date_to': date(2030, 1, 31),
                'company_id': cls.company.id,
            })
            # Two lines per slip: a partial mirror would show up as a count
            # mismatch, not only as a set mismatch.
            lines = Line.browse()
            for n in (1, 2):
                lines |= Line.create({
                    'slip_id': slip.id,
                    'salary_rule_id': cls.rule.id,
                    'employee_id': emp.id,
                    'contract_id': contract.id,
                    'category_id': category.id,
                    'name': 'W105 line %s' % n,
                    'code': 'W105L%s' % n,
                    'sequence': n,
                    'amount': 1000.0 * n,
                    'quantity': 1.0,
                })
            cls.slip_of[emp.id] = slip
            cls.lines_of[emp.id] = lines

        cls.all_slips = Payslip.browse([s.id for s in cls.slip_of.values()])
        cls.all_lines = Line.browse(
            [lid for ls in cls.lines_of.values() for lid in ls.ids])

    # ------------------------------------------------------------------ tools

    def _readable(self, user):
        """(slips, lines) this user can read, scoped to the fixture."""
        slips = self.env['hr.payslip'].with_user(user).search(
            [('id', 'in', self.all_slips.ids)])
        lines = self.env['hr.payslip.line'].with_user(user).search(
            [('id', 'in', self.all_lines.ids)])
        return slips, lines

    def _assert_lines_track_slips(self, user, expected_employees):
        """The owner's sentence, executable.

        Three assertions, not one, because each failure means something
        different: a slip set that moved means the fixture or the payslip rules
        changed; lines whose slip is unreadable is a LEAK; slips whose lines are
        unreadable is the W105 zero-money bug still present.
        """
        slips, lines = self._readable(user)
        self.assertEqual(
            set(slips.ids),
            {self.slip_of[e.id].id for e in expected_employees},
            "%s reads the wrong set of PAYSLIPS — the mirror is being judged "
            "against a moved baseline" % user.login)

        leaked = lines.filtered(lambda ln: ln.slip_id.id not in set(slips.ids))
        self.assertFalse(
            leaked.ids,
            "%s reads payslip LINES of payslips it cannot read: %s — a line "
            "rule is broader than its slip twin" % (user.login, leaked.ids))

        expected_lines = set()
        for emp in expected_employees:
            expected_lines |= set(self.lines_of[emp.id].ids)
        self.assertEqual(
            set(lines.ids), expected_lines,
            "%s can read a payslip but not all of its lines — the W105 money "
            "hole is still open for this tier" % user.login)

    # ------------------------------------------------------------------ tests

    def test_01_the_fixture_really_has_money_on_it(self):
        """A green suite over zero rows is the failure mode W103 warns about."""
        self.assertEqual(len(self.all_slips), 5)
        self.assertEqual(len(self.all_lines), 10)
        self.assertTrue(all(ln.total for ln in self.all_lines))

    def test_02_om_payroll_manager_sees_every_line_of_every_payslip(self):
        self._assert_lines_track_slips(self.u_om_manager, self.employees)

    def test_03_om_payroll_officer_sees_lines_of_exactly_its_own_scope(self):
        # own + the department it manages + the departmentless one; NOT
        # e_other, and NOT e_plain (dept_other).
        self._assert_lines_track_slips(
            self.u_om_officer, self.e_officer + self.e_led + self.e_nodept)

    def test_04_pb_payroll_officer_sees_every_line_of_every_payslip(self):
        self._assert_lines_track_slips(self.u_pb_officer, self.employees)

    def test_05_integration_user_sees_every_line_of_every_payslip(self):
        self._assert_lines_track_slips(self.u_integration, self.employees)

    def test_06_a_plain_employee_sees_only_its_own_lines(self):
        """The no-payslip-access probe. A plain internal user holds no payroll
        group at all: one payslip, two lines, and nothing of the other four."""
        self._assert_lines_track_slips(self.u_plain, self.e_plain)
        _, lines = self._readable(self.u_plain)
        foreign = set(self.lines_of[self.e_other.id].ids)
        self.assertFalse(set(lines.ids) & foreign,
                         "a plain employee can read another employee's payslip lines")

    def test_07_every_line_rule_mirrors_a_payslip_rule(self):
        """No line rule may exist without a named payslip twin.

        A line rule whose twin nobody can point at is an unreviewed money
        decision, whatever its domain says.
        """
        Rule = self.env['ir.rule'].sudo()
        line_model = self.env['ir.model']._get('hr.payslip.line')
        live = Rule.with_context(active_test=False).search(
            [('model_id', '=', line_model.id)])

        known = set()
        for line_xmlid, _slip_xmlid in MIRROR_PAIRS:
            rec = self.env.ref(line_xmlid, raise_if_not_found=False)
            if rec:
                known.add(rec.id)

        unknown = live.filtered(lambda r: r.id not in known)
        self.assertFalse(
            unknown.mapped('name'),
            "hr.payslip.line record rules with no declared payslip twin: %s — "
            "add the pair to MIRROR_PAIRS and justify it, or delete the rule"
            % unknown.mapped('name'))

    def test_08_each_mirror_carries_exactly_its_twins_groups(self):
        """Same groups, or the mirror admits a tier the payslip does not."""
        for line_xmlid, slip_xmlid in MIRROR_PAIRS:
            line_rule = self.env.ref(line_xmlid, raise_if_not_found=False)
            slip_rule = self.env.ref(slip_xmlid, raise_if_not_found=False)
            if not line_rule or not slip_rule:
                # The module owning the pair is not installed here. The pair is
                # still declared, so the gate above keeps covering it.
                continue
            self.assertEqual(
                set(line_rule.sudo().groups.ids), set(slip_rule.sudo().groups.ids),
                "%s and %s do not carry the same groups" % (line_xmlid, slip_xmlid))
            self.assertTrue(
                line_rule.sudo().groups.ids,
                "%s is a GLOBAL rule — a global rule ANDs onto everybody, which "
                "is not what a mirror is" % line_xmlid)

    def test_09_each_mirror_is_its_twins_domain_rerooted_through_slip_id(self):
        """The domain check, textual and deliberately strict.

        A textual comparison is the right strictness here: two domains that
        differ only in whitespace are the same rule, two that differ in a leaf
        are a different policy, and there is no third case worth being lenient
        about on a money model.
        """
        def norm(text):
            return ' '.join((text or '').split())

        for line_xmlid, slip_xmlid in MIRROR_PAIRS:
            line_rule = self.env.ref(line_xmlid, raise_if_not_found=False)
            slip_rule = self.env.ref(slip_xmlid, raise_if_not_found=False)
            if not line_rule or not slip_rule:
                continue
            expected = norm(slip_rule.sudo().domain_force)
            # Re-root: every leaf of the slip domain is reached through slip_id.
            for field in ('employee_id', 'state', 'company_id', 'contract_id'):
                expected = expected.replace("('%s" % field, "('slip_id.%s" % field)
            self.assertEqual(
                norm(line_rule.sudo().domain_force), expected,
                "%s is not %s re-rooted through slip_id" % (line_xmlid, slip_xmlid))

    def test_10_the_unmirrored_payslip_rules_are_still_unreachable(self):
        """A rule left unmirrored on purpose must stay un-mirrorable.

        The portal payslip rule admits nothing because portal users have no
        ir.model.access row on hr.payslip. If somebody adds one, this fails and
        the portal line rule becomes required — which is the conversation that
        should happen before portal users can read money.
        """
        Access = self.env['ir.model.access'].sudo()
        payslip_model = self.env['ir.model']._get('hr.payslip')
        portal = self.env.ref('base.group_portal')
        rows = Access.search([('model_id', '=', payslip_model.id),
                              ('group_id', '=', portal.id),
                              ('perm_read', '=', True)])
        self.assertFalse(
            rows.ids,
            "base.group_portal now has read access to hr.payslip, so %s is live "
            "and needs a line mirror" % ', '.join(sorted(UNMIRRORED_SLIP_RULES)))
