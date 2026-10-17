# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollAIDashboard(models.Model):
    """AI-configurable dashboard for PayAI with chart widget slots."""

    _name = 'payroll.ai.dashboard'
    _description = 'PayAI Dashboard'
    _order = 'sequence, id'

    name = fields.Char(
        string='Dashboard Name',
        default='PayAI Dashboard',
        required=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        default=lambda self: self.env.user,
        required=True,
    )

    widget_ids = fields.One2many(
        'payroll.ai.dashboard.widget',
        'dashboard_id',
        string='Widgets',
    )

    is_shared = fields.Boolean(
        string='Shared',
        default=False,
        help='If checked, other users can view this dashboard',
    )

    sequence = fields.Integer(default=10)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.model
    def get_or_create_dashboard(self):
        """Get the user's dashboard or create one."""
        dashboard = self.search([
            ('user_id', '=', self.env.user.id),
        ], limit=1)

        if not dashboard:
            dashboard = self.create({
                'name': _("%(user)s's PayAI Dashboard", user=self.env.user.name),
            })

        return dashboard

    def add_widget_from_chat(self, chart_config, title=None, position=None):
        """
        Add a chart widget from AI chat to the dashboard.

        Args:
            chart_config (dict): Chart.js configuration
            title (str): Widget title
            position (int): Grid position (1-12)
        """
        self.ensure_one()

        # Find next available position
        if position is None:
            existing_positions = self.widget_ids.mapped('position')
            for pos in range(1, 13):
                if pos not in existing_positions:
                    position = pos
                    break
            else:
                position = len(self.widget_ids) + 1

        return self.env['payroll.ai.dashboard.widget'].create({
            'dashboard_id': self.id,
            'name': title or chart_config.get('options', {}).get('plugins', {}).get('title', {}).get('text', 'Chart'),
            'chart_config': json.dumps(chart_config),
            'position': position,
            'width': 6,  # Half width default (6 of 12 columns)
            'height': 4,
            'grid_x': 0,
            'grid_y': 0,  # Gridstack auto-positions when y=0
        })

    @api.model
    def rpc_get_dashboard(self):
        """RPC endpoint to get current user's dashboard data."""
        dashboard = self.get_or_create_dashboard()

        widgets = []
        for w in dashboard.widget_ids.sorted('position'):
            widgets.append({
                'id': w.id,
                'name': w.name,
                'chart_config': json.loads(w.chart_config) if w.chart_config else None,
                'position': w.position,
                'width': w.width,
                'height': w.height,
                'grid_x': w.grid_x,
                'grid_y': w.grid_y,
            })

        return {
            'dashboard_id': dashboard.id,
            'name': dashboard.name,
            'widgets': widgets,
        }

    @api.model
    def rpc_add_widget(self, chart_config, title=None):
        """RPC endpoint to add a widget from chat."""
        dashboard = self.get_or_create_dashboard()
        widget = dashboard.add_widget_from_chat(chart_config, title=title)
        return {
            'widget_id': widget.id,
            'position': widget.position,
        }

    @api.model
    def rpc_remove_widget(self, widget_id):
        """RPC endpoint to remove a widget."""
        widget = self.env['payroll.ai.dashboard.widget'].browse(widget_id).exists()
        if widget and widget.dashboard_id.user_id.id == self.env.user.id:
            widget.unlink()
        return True

    @api.model
    def rpc_save_widget_positions(self, positions):
        """
        RPC endpoint to save widget grid positions after drag/resize.

        Args:
            positions (list): [{id, x, y, w, h}, ...]
        """
        Widget = self.env['payroll.ai.dashboard.widget']
        for pos in positions:
            widget = Widget.browse(pos.get('id')).exists()
            if widget and widget.dashboard_id.user_id.id == self.env.user.id:
                widget.write({
                    'grid_x': pos.get('x', 0),
                    'grid_y': pos.get('y', 0),
                    'width': pos.get('w', 6),
                    'height': pos.get('h', 4),
                })
        return True

    @api.model
    def rpc_generate_dashboard(self, prompt):
        """
        RPC endpoint: AI generates a dashboard widget from a prompt.
        Routes through the standard engine so payroll data is queried first.
        """
        dashboard = self.get_or_create_dashboard()

        # Use the AI engine with the user's original prompt
        # This ensures proper intent classification and data querying
        engine = self.env['payroll.ai.engine']
        result = engine.process_message(
            prompt,
            context={'user_id': self.env.user.id},
        )

        # Add the chart widget if AI generated one
        if result.get('chart'):
            dashboard.add_widget_from_chat(
                result['chart'],
                title=result['chart'].get('options', {}).get('plugins', {}).get('title', {}).get('text', prompt),
            )

        return self.rpc_get_dashboard()


class PayrollAIDashboardWidget(models.Model):
    """Individual widget on a PayAI dashboard."""

    _name = 'payroll.ai.dashboard.widget'
    _description = 'PayAI Dashboard Widget'
    _order = 'position, id'

    dashboard_id = fields.Many2one(
        'payroll.ai.dashboard',
        string='Dashboard',
        required=True,
        ondelete='cascade',
    )

    name = fields.Char(string='Widget Title', required=True)

    chart_config = fields.Text(
        string='Chart Configuration',
        help='JSON Chart.js configuration',
    )

    position = fields.Integer(
        string='Grid Position',
        default=1,
    )

    grid_x = fields.Integer(
        string='Grid X',
        default=0,
        help='Horizontal position in the Gridstack grid (0-based)',
    )

    grid_y = fields.Integer(
        string='Grid Y',
        default=0,
        help='Vertical position in the Gridstack grid (0-based)',
    )

    width = fields.Integer(
        string='Width (grid units)',
        default=6,
        help='Width in grid units (1-12)',
    )

    height = fields.Integer(
        string='Height (grid units)',
        default=4,
    )

    refresh_query = fields.Text(
        string='Refresh Query',
        help='Original query to re-execute for data refresh',
    )
