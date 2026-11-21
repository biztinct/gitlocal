# -*- coding: utf-8 -*-

from odoo import models, fields
from odoo.tools.safe_eval import safe_eval


class SalaryConfigurationWorkflowWizard(models.TransientModel):
    """
    Transient wizard for displaying the Salary Configuration Workflow dashboard.
    This is a standalone interface and doesn't need to store any data.
    """
    _name = 'salary.configuration.workflow.wizard'
    _description = 'Salary Configuration Workflow Wizard'

    name = fields.Char(string='Workflow', default='Salary Configuration Workflow', readonly=True)

    # Helpers to open actions with a create-friendly context and stable breadcrumbs
    def _open_action(self, action_xmlid, preferred_views=None):
        """Return a window action with create enabled and explicit view ordering."""
        self.ensure_one()
        action = self.env.ref(action_xmlid).read()[0]

        # Build views list from preferred view refs (if provided)
        views = []
        if preferred_views:
            for view_xmlid, view_type in preferred_views:
                view_rec = self.env.ref(view_xmlid, raise_if_not_found=False)
                if view_rec:
                    views.append((view_rec.id, view_type))

        # Merge contexts safely
        ctx = dict(self.env.context or {})
        raw_ctx = action.get('context')
        if raw_ctx:
            try:
                ctx.update(raw_ctx if isinstance(raw_ctx, dict) else safe_eval(raw_ctx))
            except Exception:
                pass
        ctx.update({
            'create': True,
            'reload': True,
        })

        # Update action payload
        if views:
            action['views'] = views
            action['view_mode'] = ','.join(v[1] for v in views)
        action['target'] = 'current'
        action['context'] = ctx
        return action

    def action_open_connectors(self):
        """Open HR connectors in kanban with New button visible immediately."""
        preferred_views = [
            ('pb_hr_payroll_formula.view_integration_connector_kanban', 'kanban'),
            ('pb_hr_payroll_formula.view_integration_connector_tree', 'list'),
            ('pb_hr_payroll_formula.view_integration_connector_form', 'form'),
        ]
        return self._open_action('pb_hr_payroll_formula.action_integration_connector_kanban', preferred_views)

    def action_open_structure(self):
        """Open salary structure/formula configs in kanban with create enabled."""
        preferred_views = [
            ('pb_hr_payroll_formula.view_formula_config_kanban', 'kanban'),
            ('pb_hr_payroll_formula.view_formula_config_tree', 'list'),
            ('pb_hr_payroll_formula.view_formula_config_form', 'form'),
        ]
        return self._open_action('pb_hr_payroll_formula.action_formula_config_kanban', preferred_views)

    def action_run_tests(self):
        """Open sample data/tests with kanban first and create enabled."""
        preferred_views = [
            ('pb_hr_payroll_formula.view_formula_sample_data_kanban', 'kanban'),
            ('pb_hr_payroll_formula.view_formula_sample_data_tree', 'list'),
            ('pb_hr_payroll_formula.view_formula_sample_data_form', 'form'),
        ]
        return self._open_action('pb_hr_payroll_formula.action_sample_data', preferred_views)
