# -*- coding: utf-8 -*-
"""Step 3 — Connect, asserted.

Four promises whose failure is invisible on screen:

  * the coverage line counts the RIGHT THINGS — inputs only, across four
    different ways of saying where a value comes from, and never a calculated
    column that was never waiting for anything;
  * "Done" is earned: the server refuses to store it while nothing is
    connected, however the client asks (ledger rule 9);
  * a task that was finished before the configuration changed says so, and
    names what changed rather than quietly going stale;
  * both doors open BY TAG and carry a way back to this step, because a door
    opened by xmlid drops every parameter and the way back lands on an empty
    journey (BP14).

The last group is source assertions, in the shape
`pb_formula_studio/tests/test_one_mapping_home.py` established: how a screen is
opened has no runtime handle to grab.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _read(*parts):
    return open(os.path.join(get_module_path(parts[0]), *parts[1:]),
                encoding='utf-8').read()


@tagged('post_install', '-at_install')
class TestConnect(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.blueprint.studio']
        cls.Engine = cls.env['pb.formula.studio']
        cls.Rule = cls.env['hr.formula.rule']

    # ------------------------------------------------------------------
    def _draft(self, token, cycle='regular', starter='vn_standard_2026'):
        tpl = self.env['hr.formula.config.template'].sudo().search(
            [('code', '=', starter), ('state', '!=', 'superseded')], limit=1)
        res = self.Studio.bp_start({
            'name': 'Connect %s' % token,
            'country_code': 'VN',
            'cycle_type': cycle,
            'template_key': starter if tpl else 'blank',
            'situations': {},
        }, token)
        self.assertTrue(res.get('ok'), res.get('reason'))
        return self.env['hr.formula.config'].browse(res['config_id'])

    def _inputs(self, config):
        return config.rule_ids.filtered(lambda r: r.column_type == 'input')

    def _connector(self):
        return self.env['hr.integration.connector'].create({
            'name': 'Connect test feed',
            'connector_type': 'demo',
            'company_id': self.env.company.id,
        })

    # ==================================================================
    # 1 — the coverage counts
    # ==================================================================
    def test_readiness_counts_every_lane_and_only_inputs(self):
        config = self._draft('b4-count')
        inputs = self._inputs(config)
        self.assertTrue(len(inputs) >= 3,
                        "the starter should bring inputs to map")

        before = self.Studio.bp_readiness(config.id)
        self.assertTrue(before['ok'])
        self.assertEqual(before['mapping']['inputs'], len(inputs))
        self.assertEqual(before['mapping']['mapped'], 0)
        self.assertEqual(before['mapping']['by_lane'],
                         {'api': 0, 'excel': 0, 'records': 0, 'cycle': 0})

        one, two = inputs[0], inputs[1]
        # ---- the connected system
        self.env['hr.integration.field.mapping'].create({
            'connector_id': self._connector().id,
            'source_field': 'basic_salary',
            'target_rule_id': one.id,
        })
        # ---- an employee record
        model = self.env['ir.model']._get('hr.employee')
        field = self.env['ir.model.fields'].search(
            [('model_id', '=', model.id), ('name', '=', 'name')], limit=1)
        self.env['hr.payslip.import.mapping'].create({
            'destination_type': 'field',
            'target_model_id': model.id,
            'target_field_id': field.id,
            'salary_structure_id': config.id,
            'component_id': two.id,
        })

        after = self.Studio.bp_readiness(config.id)
        self.assertEqual(after['mapping']['mapped'], 2)
        self.assertEqual(after['mapping']['by_lane']['api'], 1)
        self.assertEqual(after['mapping']['by_lane']['records'], 1)
        self.assertEqual(after['mapping']['by_lane']['excel'], 0)

        # ---- a mapping onto a CALCULATED column is not coverage: that column
        # was never waiting for a value, and counting it would inflate the
        # number with components nobody has to connect.
        formula = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula')[:1]
        if formula:
            self.env['hr.integration.field.mapping'].create({
                'connector_id': self._connector().id,
                'source_field': 'something_else',
                'target_rule_id': formula.id,
            })
            again = self.Studio.bp_readiness(config.id)
            self.assertEqual(again['mapping']['mapped'], 2,
                             "a wire onto a calculated column is not an input "
                             "with a source")

    def test_readiness_counts_the_mid_cycle_carry(self):
        """The fourth lane: a component carried in from the mid-month run."""
        end = self._draft('b4-end', cycle='end_cycle')
        mid = self._draft('b4-mid', cycle='mid_cycle')
        target = self._inputs(end)[0]
        source = self._inputs(mid)[0]
        self.env['hr.payroll.cycle.component.mapping'].create({
            'mid_cycle_config_id': mid.id,
            'end_cycle_config_id': end.id,
            'mid_component_id': source.id,
            'end_component_id': target.id,
        })
        res = self.Studio.bp_readiness(end.id)
        self.assertEqual(res['mapping']['by_lane']['cycle'], 1)
        self.assertEqual(res['mapping']['mapped'], 1)

    def test_a_configuration_with_no_inputs_says_so(self):
        config = self._draft('b4-blank', starter='nothing-at-all')
        res = self.Studio.bp_readiness(config.id)
        self.assertTrue(res['ok'])
        self.assertEqual(res['mapping']['inputs'], 0)
        self.assertEqual(res['payslip']['total'], 0)

    # ==================================================================
    # 2 — the payslip placement
    # ==================================================================
    def test_placing_two_components_moves_placed_tray_and_sections(self):
        config = self._draft('b4-slip')
        rules = config.rule_ids.filtered(lambda r: r.appears_on_payslip)[:2]
        self.assertEqual(len(rules), 2,
                         "the starter should show at least two lines on a payslip")
        base = self.Studio.bp_readiness(config.id)['payslip']

        section = self.env['hr.payslip.config'].create({
            'identifier': 'B4SEC',
            'label': 'Earnings',
            'salary_structure_id': config.id,
        })
        for rule in rules:
            self.Engine.move_component(rule.id, section.id, rules.ids)

        placed = self.Studio.bp_readiness(config.id)['payslip']
        self.assertEqual(placed['placed'], 2)
        self.assertEqual(placed['sections'], 1)
        self.assertEqual(placed['tray'], base['on_slip'] - 2)
        self.assertEqual(placed['total'], len(config.rule_ids))

        # Deleting the section drops its lines back into the tray rather than
        # off the payslip — nothing a person arranged is ever destroyed by
        # tidying the page it sat on.
        self.Engine.delete_section(section.id)
        back = self.Studio.bp_readiness(config.id)['payslip']
        self.assertEqual(back['placed'], 0)
        self.assertEqual(back['sections'], 0)
        self.assertEqual(back['tray'], base['on_slip'])

    # ==================================================================
    # 3 — the status machine
    # ==================================================================
    def test_the_status_machine_walks_and_reverses(self):
        config = self._draft('b4-status')
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)

        res = self.Studio.bp_readiness(config.id)
        self.assertEqual(res['status']['mapping'], 'not_started')
        self.assertEqual(res['status']['approvals'], 'info')

        # opened, and nothing connected yet
        res = self.Studio.bp_task_open(config.id, 'mapping')
        self.assertEqual(res['status']['mapping'], 'in_progress')
        self.assertTrue(blueprint.optional_status()['mapping']['opened_at'])

        # connect one input, then mark it done
        target = self._inputs(config)[0]
        self.env['hr.integration.field.mapping'].create({
            'connector_id': self._connector().id,
            'source_field': 'basic_salary',
            'target_rule_id': target.id,
        })
        res = self.Studio.bp_task_set(config.id, 'mapping', 'configured')
        self.assertEqual(res['status']['mapping'], 'configured')
        self.assertEqual(res['mapping']['mapped'], 1)

        # a new input arrives → the task needs another look, and says which one
        added = self.Engine.add_component(config.id, {
            'name': 'Site days this run',
            'code': 'B4SITEDAYS',
            'column_type': 'input',
        })
        self.assertTrue(added.get('rule_id'), added)
        res = self.Studio.bp_readiness(config.id)
        self.assertEqual(res['status']['mapping'], 'needs_review')
        self.assertEqual(res['mapping']['changed_since'], ['B4SITEDAYS'])
        # and the STORED status is still "configured": needs_review is a
        # comparison, never a fifth thing written down.
        self.assertEqual(res['stored_status']['mapping'], 'configured')

        # marking it done again clears it, because the snapshot moves with it
        res = self.Studio.bp_task_set(config.id, 'mapping', 'configured')
        self.assertEqual(res['status']['mapping'], 'configured')
        self.assertEqual(res['mapping']['changed_since'], [])

        # skip and undo
        res = self.Studio.bp_task_set(config.id, 'mapping', 'skipped')
        self.assertEqual(res['status']['mapping'], 'skipped')
        res = self.Studio.bp_task_set(config.id, 'mapping', 'not_started')
        self.assertEqual(res['status']['mapping'], 'not_started')

    def test_skip_the_rest_only_touches_what_nobody_started(self):
        config = self._draft('b4-skiprest')
        self.Studio.bp_task_open(config.id, 'mapping')      # in_progress
        res = self.Studio.bp_skip_rest(config.id)
        self.assertEqual(res['skipped'], ['payslip'])
        self.assertEqual(res['status']['mapping'], 'in_progress')
        self.assertEqual(res['status']['payslip'], 'skipped')

        # a second press has nothing left to do, and says nothing happened
        again = self.Studio.bp_skip_rest(config.id)
        self.assertEqual(again['skipped'], [])
        self.assertEqual(again['status']['payslip'], 'skipped')

    # ==================================================================
    # 4 — done is earned
    # ==================================================================
    def test_done_is_refused_while_nothing_is_connected(self):
        config = self._draft('b4-refuse')
        res = self.Studio.bp_task_set(config.id, 'mapping', 'configured')
        self.assertFalse(res['ok'])
        self.assertIn('Nothing is connected yet', res['reason'])

        res = self.Studio.bp_task_set(config.id, 'payslip', 'configured')
        self.assertFalse(res['ok'])
        self.assertIn('No component has been placed', res['reason'])

        # and nothing was written
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        status = blueprint.optional_status()
        self.assertEqual(status['mapping']['status'], 'not_started')
        self.assertEqual(status['payslip']['status'], 'not_started')

    def test_approvals_cannot_be_set_or_skipped(self):
        config = self._draft('b4-appr')
        for method, args in (('bp_task_open', ('approvals',)),
                             ('bp_task_set', ('approvals', 'skipped'))):
            res = getattr(self.Studio, method)(config.id, *args)
            self.assertFalse(res['ok'])
            self.assertIn('already in place', res['reason'])

    def test_the_approvals_card_names_the_three_stages(self):
        config = self._draft('b4-tiers')
        res = self.Studio.bp_readiness(config.id)
        names = [t['name'] for t in res['approvals']['tiers']]
        self.assertEqual(len(names), 3)
        for name in names:
            self.assertTrue(name.strip())
        self.assertTrue(all(t['what'] for t in res['approvals']['tiers']))

    # ==================================================================
    # 5 — an old draft's one-word statuses still read
    # ==================================================================
    def test_a_draft_from_before_this_phase_still_opens(self):
        """B1 stored one WORD per task. A reader that assumed the new shape
        would raise on the first live draft, so the coercion is asserted."""
        config = self._draft('b4-legacy')
        blueprint = self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)
        blueprint.optional_status_json = (
            '{"mapping": "configured", "payslip": "skipped", '
            '"approvals": "info"}')
        status = blueprint.optional_status()
        self.assertEqual(status['mapping']['status'], 'configured')
        self.assertEqual(status['payslip']['status'], 'skipped')
        self.assertEqual(status['mapping']['snapshot'], [])
        res = self.Studio.bp_readiness(config.id)
        self.assertTrue(res['ok'])
        # An empty snapshot is "we do not know what it looked like", which is
        # not the same as "everything is new" — so it must not shout.
        self.assertEqual(res['mapping']['changed_since'], [])

    # ==================================================================
    # 6 — how the doors are opened (source assertions)
    # ==================================================================
    def test_both_doors_open_by_tag_and_carry_the_way_back(self):
        src = _read('pb_blueprint', 'static', 'src', 'js', 'step_connect.js')

        self.assertIn('tag: "pb_mapping_studio"', src)
        self.assertIn('pb_config: this.props.configId', src)
        self.assertIn('pb_mode: "journey"', src)
        self.assertIn('tag: "pb_formula_studio"', src)
        self.assertIn('pbfs_open_payslip: true', src)

        # the way back: by tag, on this configuration, on THIS step
        back = re.search(r'_back\(task\)\s*{(.*?)\n    }', src, flags=re.S)
        self.assertTrue(back, "step_connect.js no longer builds a return door")
        body = back.group(1)
        self.assertIn('tag: "pb_blueprint"', body)
        self.assertIn('config_id: this.props.configId', body)
        self.assertIn('step: "connect"', body)

        # never by xmlid: an xmlid door drops every parameter (BP14)
        self.assertNotIn('action_pb_mapping_studio', src)

        # the guard, so a database without the mapping screen shows an
        # explanation rather than a dead button
        self.assertIn('registry.category("actions").contains("pb_mapping_studio")',
                      src)

    def test_the_studio_reads_the_payslip_key_from_params_or_context(self):
        src = _read('pb_formula_studio', 'static', 'src', 'js', 'formula_studio.js')
        self.assertIn('a.params && a.params.pbfs_open_payslip', src)
        self.assertIn('a.context && a.context.pbfs_open_payslip', src)

        close = re.search(r'closePayslip\(\)\s*{(.*?)\n    }', src, flags=re.S)
        self.assertTrue(close, "closePayslip is no longer a method")
        body = close.group(1)
        self.assertIn('this.state.psOpen = false', body)
        self.assertIn('this._psBack', body)
        self.assertIn('goBack(this.action', body)

    def test_the_back_chip_and_the_designer_share_one_way_back(self):
        """One implementation, or the two drift and only one of them is
        tested."""
        src = _read('pb_hub', 'static', 'src', 'js', 'hub_nav.js')
        self.assertIn('export function goBack(actionService, back)', src)
        self.assertIn('goBack(this.actionService, this.props.back);', src)

    def test_the_step_is_no_longer_a_placeholder(self):
        shell = _read('pb_blueprint', 'static', 'src', 'xml', 'blueprint.xml')
        self.assertIn("<StepConnect t-elif=\"state.step === 'connect'", shell)
        thin = _read('pb_blueprint', 'static', 'src', 'js', 'step_thin.js')
        self.assertNotIn('case "connect":', thin,
                         "the thin placeholder still claims the Connect step")
