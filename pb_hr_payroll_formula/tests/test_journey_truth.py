# -*- coding: utf-8 -*-
"""JOURNEY J3 — the four places the plumbing lied, and the broom.

Every test here is about a claim the CODE was making and could not keep:

  * **the empty-feed guard (S2).** The connector pre-pass assigned a component's
    slot whenever the feed's key was present, empty or not — and the resolver's
    `if rule.code not in input_values` skip then locked out every rung below it.
    So "keep the spreadsheet as a fallback" (owner decision J-D3) was not
    implementable: the fallback could never fire. `test_02*` is the guard, in its
    three interesting shapes, plus the neutrality proof that a feed which DID
    deliver still outranks everything (J-D5 — nothing is reordered).
  * **per-feed pulls ran no transformation rules (S3).** `computed_data` stayed
    empty after the one-feed sync button, so a rule-fed component read nothing —
    and the full "Pull Data" button then fixed it, which is the worst shape a bug
    can take. `test_03*`.
  * **batch-free payslips could not read API data (S4).** A literal `TODO … pass`.
    `test_04*`.
  * **a source nothing could load (S5).** `test_05*` is a source gate: the value
    is gone from the selection, from the gates and from the doors together, or it
    is not gone at all.

The resolver is exercised through `_transform_data_to_formula_inputs` directly
rather than through a batch run, deliberately: `action_process` WRITES BACK onto
employee and contract records, and a resolver assertion has no business creating
that risk. Nothing here calls it.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_py_comments(src):
    return re.sub(r'^\s*#.*$', '', src, flags=re.M)


def _strip_xml_comments(src):
    return re.sub(r'<!--.*?-->', '', src, flags=re.S)


@tagged('post_install', '-at_install')
class TestJourneyTruth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.Store = cls.env['hr.api.data.store']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        cfg = self.Config.create({
            'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        self.basic = self.Rule.create({
            'config_id': cfg.id, 'name': 'Basic Salary', 'code': 'BASIC',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        })
        self.othours = self.Rule.create({
            'config_id': cfg.id, 'name': 'Overtime Hours', 'code': 'OTHOURS',
            'column_type': 'input', 'sequence': 2, 'default_value': 0.0,
        })
        return cfg

    def _connector(self, name='J3 Demo'):
        return self.Connector.create({
            'name': name, 'connector_type': 'demo',
        })

    def _wire(self, connector, rule, source_field, **extra):
        vals = {'connector_id': connector.id, 'target_rule_id': rule.id,
                'source_field': source_field, 'active_state': 'active'}
        vals.update(extra)
        return self.FieldMapping.create(vals)

    def _batch(self, cfg, connector, source_type='api_data_store'):
        return self.Batch.create({
            'name': 'J3 %s' % source_type, 'source_type': source_type,
            'formula_config_id': cfg.id, 'connector_id': connector.id,
        })

    def _resolve(self, batch, raw, topup=None, employee=None):
        prov = {}
        vals = batch._transform_data_to_formula_inputs(
            raw, employee=employee, provenance=prov, topup_data=topup or {})
        return vals, prov

    # =====================================================================
    # 1 — the shared "what did the feed deliver" helper
    # =====================================================================
    def test_01a_emptiness_is_the_resolvers_own_test_and_zero_is_a_value(self):
        """`0` is not silence. Zero overtime hours is a fact somebody sent."""
        FM = self.FieldMapping
        for empty in (None, '', '   ', '\t\n'):
            self.assertTrue(FM._feed_value_is_empty(empty), repr(empty))
        for present in (0, 0.0, False, '0', 'x', [], {}):
            self.assertFalse(
                FM._feed_value_is_empty(present),
                "%r must count as a delivery — the resolver's bound branch has "
                "always treated it as one, and the two tests must not diverge"
                % (present,))

    def test_01b_a_wire_whose_key_is_absent_or_empty_delivers_nothing(self):
        cfg = self._config('J3 Deliver')
        conn = self._connector()
        wire = self._wire(conn, self.basic, 'Base')
        FM = self.FieldMapping
        self.assertEqual(len(FM._feed_values_for(wire, {'Base': 4200})), 1)
        self.assertEqual(FM._feed_values_for(wire, {'Base': 4200})[0]['value'], 4200)
        self.assertEqual(FM._feed_values_for(wire, {'Base': 0})[0]['value'], 0,
                         "zero is delivered, not swallowed")
        self.assertEqual(FM._feed_values_for(wire, {}), [],
                         "an absent key was never a delivery")
        self.assertEqual(FM._feed_values_for(wire, {'Base': ''}), [],
                         "an EMPTY key is the case J3 fixes")
        self.assertEqual(FM._feed_values_for(wire, {'Base': '  '}), [])
        # …and the reason the SOURCE has to be tested, not just the transformed
        # result: `transform_value` short-circuits an empty input to
        # `default_value`, a Float defaulting to 0.0. Testing only the output
        # would see a perfectly good number and hand over the slot.
        self.assertEqual(wire.default_value, 0.0)
        self.assertEqual(wire.transform_value('', {}), 0.0,
                         "the transform CANNOT tell you the source was empty")
        wire.default_value = 777
        self.assertEqual(FM._feed_values_for(wire, {'Base': ''})[0]['value'], 777,
                         "a STATED default is an answer")
        self.assertTrue(cfg)

    # =====================================================================
    # 2 — the empty-feed guard, in the resolver (test case 8)
    # =====================================================================
    def test_02a_a_feed_that_delivers_still_wins_everything(self):
        """J-D5: the ladder is NOT reordered. This is the neutrality proof."""
        cfg = self._config('J3 Wins')
        conn = self._connector()
        cfg.connector_id = conn.id
        self._wire(conn, self.basic, 'Base')
        # an explicit spreadsheet binding on the same component…
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        batch = self._batch(cfg, conn)
        # …and the spreadsheet column arriving in the top-up blob
        vals, prov = self._resolve(batch, {'Base': 4200},
                                   topup={'Basic Salary': 9999})
        self.assertEqual(vals['BASIC'], 4200,
                         "the feed delivered, so the feed wins — unchanged by J3")
        self.assertEqual(prov['BASIC']['src'], 'feed')
        self.assertEqual(prov['BASIC']['via'], 'connector_mapping')

    def test_02b_an_empty_feed_falls_through_to_the_binding(self):
        """The whole point: "keep as fallback" is now a true sentence."""
        cfg = self._config('J3 Falls')
        conn = self._connector()
        cfg.connector_id = conn.id
        self._wire(conn, self.basic, 'Base')
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        batch = self._batch(cfg, conn)
        vals, prov = self._resolve(batch, {'Base': ''},
                                   topup={'Basic Salary': 9999})
        self.assertEqual(
            vals['BASIC'], 9999,
            "the feed sent nothing, so the spreadsheet column speaks. Before J3 "
            "this was the component's DEFAULT with provenance reading 'feed'")
        self.assertEqual(prov['BASIC']['src'], 'excel')
        self.assertIn(prov['BASIC']['via'], ('binding', 'fallback'))

    def test_02c_an_empty_feed_falls_through_to_the_employee_field(self):
        """The other fallback rung: a mapped employee/contract field."""
        cfg = self._config('J3 EmpField')
        conn = self._connector()
        cfg.connector_id = conn.id
        self._wire(conn, self.basic, 'Base')
        emp = self.env['hr.employee'].create({'name': 'J3 Subject'})
        model = self.env['ir.model']._get('hr.employee')
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'hr.employee'), ('name', '=', 'job_title')], limit=1)
        if not (model and field):
            self.skipTest("hr.employee.job_title is not in this build")
        emp.job_title = 'Welder'
        self.env['hr.payslip.import.mapping'].create({
            'salary_structure_id': cfg.id, 'component_id': self.basic.id,
            'destination_type': 'field',
            'target_model_id': model.id, 'target_field_id': field.id,
        })
        batch = self._batch(cfg, conn)
        # The employee is an ARGUMENT to the resolver, not something it looks up:
        # `get_mapped_input_value` reads the record it was handed, so a fixture
        # that omits it exercises the "no record" branch and proves nothing.
        vals, prov = self._resolve(batch, {'Base': ''}, employee=emp)
        self.assertEqual(vals['BASIC'], 'Welder',
                         "the employee record answered, because the feed did not")
        self.assertEqual(prov['BASIC']['via'], 'employee_mapping')

    def test_02d_a_default_if_empty_transform_counts_as_a_delivery(self):
        """A STATED default is an answer; an unstated one is a silence."""
        cfg = self._config('J3 Default')
        conn = self._connector()
        cfg.connector_id = conn.id
        self._wire(conn, self.basic, 'Base', default_value=777)
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        batch = self._batch(cfg, conn)
        vals, prov = self._resolve(batch, {'Base': ''},
                                   topup={'Basic Salary': 9999})
        self.assertEqual(vals['BASIC'], 777,
                         "the wire's own default is a value the feed supplied")
        self.assertEqual(prov['BASIC']['src'], 'feed')

    def test_02e_an_absent_key_behaved_this_way_before_j3_too(self):
        """Guard against over-claiming: absence already fell through."""
        cfg = self._config('J3 Absent')
        conn = self._connector()
        cfg.connector_id = conn.id
        self._wire(conn, self.basic, 'Base')
        batch = self._batch(cfg, conn)
        vals, prov = self._resolve(batch, {'Basic Salary': 5100})
        self.assertEqual(vals['BASIC'], 5100)
        self.assertEqual(prov['BASIC']['src'], 'feed',
                         "primary blob on a data-store run is the feed")
        self.assertEqual(prov['BASIC']['via'], 'header')

    def test_02f_the_guard_is_not_a_reorder(self):
        """A source gate on the sacred rule (J-D5)."""
        src = _src('pb_hr_payroll_formula', 'models/payroll_import_batch.py')
        body = src.split('def _transform_data_to_formula_inputs', 1)[1]
        prepass = body.index('_feed_values_for')
        bound = body.index('if bound_kind:')
        loop = body.index("if rule.code not in input_values:")
        self.assertLess(prepass, loop,
                        "the pre-pass still runs BEFORE the input loop")
        self.assertLess(loop, bound,
                        "the bound branch still sits inside the loop, below it")

    # =====================================================================
    # 3 — per-feed pulls run transformation rules (test case 9)
    # =====================================================================
    def test_03a_one_helper_serves_all_three_call_sites(self):
        src = _strip_py_comments(
            _src('pb_hr_payroll_formula', 'models/integration_connector.py'))
        self.assertEqual(
            src.count('_execute_for_records'), 1,
            "there is exactly ONE invocation, inside `_run_transformation_rules`")
        for site in ('def action_pull_endpoint', 'def action_pull_data',
                     'def action_recompute_transformations'):
            body = src.split(site, 1)[1].split('\n    def ', 1)[0]
            self.assertIn('_run_transformation_rules', body,
                          "%s must run the rules" % site)

    def test_03b_the_helper_scopes_to_what_it_is_given(self):
        conn = self._connector()
        cfg = self._config('J3 Rules')
        rule = self.env['hr.api.transformation.rule'].create({
            'connector_id': conn.id, 'name': 'Count salary rows',
            'output_key': 'SALARYROWS', 'source_data_type': 'salary',
            'rule_type': 'count', 'active': True,
        })
        emp = self.env['hr.employee'].create({'name': 'J3 Pulled'})
        row = self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'E1',
            'raw_payload': {'Base': 100}, 'extracted_data': {'Base': 100},
            'state': 'extracted',
        })
        untouched = self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'E2',
            'raw_payload': {'Base': 5}, 'extracted_data': {'Base': 5},
            'state': 'extracted',
        })
        conn._run_transformation_rules(row)
        self.assertTrue(rule)
        self.assertFalse(
            untouched.computed_data,
            "a row that was not pulled must not be recomputed — the cost of one "
            "feed refresh may not grow with the age of the store")

    def test_03c_nothing_to_do_is_not_an_error_on_a_pull(self):
        conn = self._connector()
        self.assertFalse(conn._run_transformation_rules(self.Store.browse()))
        row = self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'raw_payload': {}, 'state': 'extracted',
        })
        # no active rules configured — a pull must sail straight through
        self.assertFalse(conn._run_transformation_rules(row))

    # =====================================================================
    # 4 — batch-free payslips read API data (test case 10)
    # =====================================================================
    def _payslip_fixture(self):
        cfg = self._config('J3 Live')
        conn = self._connector()
        cfg.connector_id = conn.id
        emp = self.env['hr.employee'].create({'name': 'J3 Live Subject'})
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', emp.id)], limit=1)
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'J3 Live Slip',
            'formula_config_id': cfg.id,
        })
        return cfg, conn, emp, contract, slip

    def test_04a_a_payslip_with_no_batch_reads_the_store(self):
        cfg, conn, emp, _c, slip = self._payslip_fixture()
        self._wire(conn, self.othours, 'OT')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'L1',
            'raw_payload': {'OT': 12}, 'extracted_data': {'OT': 12},
            'state': 'extracted',
        })
        prov = {}
        values = slip._get_formula_input_values(cfg, provenance=prov)
        self.assertEqual(values['OTHOURS'], 12,
                         "before J3 this was the component's default and the "
                         "connector branch was a literal `pass`")
        self.assertEqual(prov['OTHOURS']['src'], 'feed')
        self.assertEqual(prov['OTHOURS']['via'], 'connector_mapping')

    def test_04b_computed_data_overrides_extracted_and_reads_as_a_rule(self):
        cfg, conn, emp, _c, slip = self._payslip_fixture()
        # The rule exists so that OTTOTAL is a KNOWN computed key; the value
        # itself is staged on the store row below, because what this test is
        # about is the vocabulary (`rule` vs `feed`), not the arithmetic.
        self.env['hr.api.transformation.rule'].create({
            'connector_id': conn.id, 'name': 'OT total',
            'output_key': 'OTTOTAL', 'source_data_type': 'salary',
            'rule_type': 'count', 'active': True,
        })
        self._wire(conn, self.othours, 'OTTOTAL')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'L2',
            'raw_payload': {'OT': 3}, 'extracted_data': {'OT': 3},
            'computed_data': {'OTTOTAL': 6}, 'state': 'extracted',
        })
        prov = {}
        values = slip._get_formula_input_values(cfg, provenance=prov)
        self.assertEqual(values['OTHOURS'], 6)
        self.assertEqual(prov['OTHOURS']['src'], 'rule',
                         "a transformation-rule output is a `rule`, not a `feed` "
                         "— that distinction is the whole source vocabulary")

    def test_04c_an_empty_store_leaves_the_existing_tail_untouched(self):
        cfg, conn, emp, _c, slip = self._payslip_fixture()
        self._wire(conn, self.othours, 'OT')
        prov = {}
        values = slip._get_formula_input_values(cfg, provenance=prov)
        self.assertEqual(values['OTHOURS'], self.othours.default_value)
        self.assertEqual(prov['OTHOURS']['via'], 'default',
                         "no data, no claim — the fallback tail is unchanged")

    def test_04d_an_empty_feed_value_does_not_claim_the_slot_here_either(self):
        """The S2 guard, applied identically on the batch-free path."""
        cfg, conn, emp, _c, slip = self._payslip_fixture()
        self._wire(conn, self.othours, 'OT')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'salary',
            'employee_id': emp.id, 'employee_external_id': 'L3',
            'raw_payload': {'OT': ''}, 'extracted_data': {'OT': ''},
            'state': 'extracted',
        })
        prov = {}
        values = slip._get_formula_input_values(cfg, provenance=prov)
        self.assertEqual(values['OTHOURS'], self.othours.default_value)
        self.assertEqual(prov['OTHOURS']['via'], 'default')

    def test_04e_there_is_one_implementation_of_what_the_feed_said(self):
        payslip = _strip_py_comments(
            _src('pb_hr_payroll_formula', 'models/hr_payslip_formula.py'))
        batch = _strip_py_comments(
            _src('pb_hr_payroll_formula', 'models/payroll_import_batch.py'))
        self.assertIn('_feed_values_for', payslip)
        self.assertIn('_feed_values_for', batch)
        self.assertNotIn('TODO: Get actual value from synced data', payslip,
                         "the TODO is closed, not moved")

    # =====================================================================
    # 5 — the broom (test case 11)
    # =====================================================================
    def test_05a_the_source_nothing_could_load_is_gone(self):
        selection = dict(
            self.Batch._fields['source_type'].selection)
        self.assertNotIn('connector', selection)
        self.assertEqual(set(selection), {'excel', 'api_data_store', 'manual'})

    def test_05b_no_gate_or_door_still_names_it(self):
        for module, path in (
                ('pb_hr_payroll_formula', 'models/payroll_import_batch.py'),
                ('pb_hr_payroll_formula', 'models/integration_connector.py'),
                ('pb_import', 'models/pb_import.py'),
                ('pb_import_wizard', 'models/pb_import_wizard.py')):
            src = _strip_py_comments(_src(module, path))
            self.assertNotIn(
                "'connector', 'api_data_store'", src,
                "%s still gates on the retired value" % path)
            self.assertNotIn("source_type = 'connector'", src, path)
        views = _strip_xml_comments(
            _src('pb_hr_payroll_formula', 'views/payroll_import_views.xml'))
        self.assertNotIn("'source_type', '=', 'connector'", views)
        self.assertNotIn("source_type not in ('connector'", views)
        wiz = _strip_xml_comments(
            _src('pb_import_wizard', 'static/src/xml/import_wizard.xml'))
        self.assertNotIn("source_type === 'connector'", wiz)

    def test_05c_the_migration_converts_rather_than_orphans(self):
        mig = _src('pb_hr_payroll_formula',
                   'migrations/19.0.1.81.0/post-a_source_nothing_could_load.py')
        self.assertIn("table_exists(cr, 'hr_payroll_import_batch')", mig)
        self.assertIn("SET source_type = 'api_data_store'", mig)
        self.assertIn('_logger.info', mig, "per-DB counts are logged")
        self.assertNotIn('connector_id = NULL', mig,
                         "the field api_data_store needs must not be cleared")

    def test_05d_the_dead_grid_widget_is_gone(self):
        path = os.path.join(get_module_path('pb_hr_payroll_formula'),
                            'static/src/js/excel_grid_widget.js')
        self.assertFalse(os.path.exists(path),
                         "nothing imported it and its registration was already "
                         "commented out — the file goes with the method")
        manifest = _src('pb_hr_payroll_formula', '__manifest__.py')
        self.assertNotIn('excel_grid_widget', manifest)
        # No LOADED asset may call the method that does not exist. The sweep is
        # over the manifest's live bundles rather than over the folder, and that
        # is a deliberate narrowing: `grid_actions.js` is a SECOND uncalled file
        # calling the same nonexistent `hr.formula.config.add_rule`, also already
        # commented out of the manifest. It is out of J3's scope (nothing this
        # phase touched imports it) and is recorded in the ledger rather than
        # swept in silently — deleting code nobody asked about is how a phase
        # acquires a regression it did not need (MF39's lesson).
        manifest_src = _src('pb_hr_payroll_formula', '__manifest__.py')
        live = [ln for ln in manifest_src.splitlines()
                if '.js' in ln and not ln.strip().startswith('#')]
        for line in live:
            self.assertNotIn('excel_grid_widget', line)
            self.assertNotIn('grid_actions', line,
                             "a file calling a nonexistent method must not be "
                             "in a live bundle")

    # =====================================================================
    # 6 — white label + translation (test case 12)
    # =====================================================================
    def test_06_no_user_visible_odoo_in_anything_j3_touched(self):
        targets = [
            ('pb_hr_payroll_formula', 'models/payroll_import_batch.py'),
            ('pb_hr_payroll_formula', 'models/integration_connector.py'),
            ('pb_hr_payroll_formula', 'models/integration_field_mapping.py'),
            ('pb_hr_payroll_formula', 'models/hr_payslip_formula.py'),
            ('pb_hr_payroll_formula', 'views/payroll_import_views.xml'),
            ('pb_formula_studio', 'models/pb_formula_studio.py'),
            ('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'),
            ('pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'),
            ('pb_formula_studio', 'static/src/xml/mapping_studio.xml'),
            ('pb_formula_studio', 'static/src/xml/mapping_canvas.xml'),
            ('pb_import_wizard', 'static/src/xml/import_wizard.xml'),
        ]
        for module, path in targets:
            src = _src(module, path)
            if path.endswith('.py'):
                strings = re.findall(r'_\(\s*"([^"]*)"', src)
                strings += re.findall(r"_\(\s*'([^']*)'", src)
            elif path.endswith('.js'):
                strings = re.findall(r'_t\(\s*"([^"]*)"', src)
            else:
                strings = re.findall(r'>([^<>{}]+)<', _strip_xml_comments(src))
            for text in strings:
                self.assertNotIn(
                    'Odoo', text,
                    "%s ships a user-visible string saying Odoo: %r"
                    % (path, text))
