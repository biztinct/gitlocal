# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json


class WfpScenarioVersion(models.Model):
    """Track versioned snapshots of scenario data.

    Each version stores a JSON snapshot of the scenario's key metrics
    at a point in time, enabling compare-versions and rollback.
    """
    _name = 'wfp.scenario.version'
    _description = 'Scenario Version Snapshot'
    _order = 'version_number desc'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='scenario_id.company_id', store=True,
    )
    version_number = fields.Integer(
        string='Version #',
        required=True,
    )
    name = fields.Char(
        string='Version Label',
        help="e.g. 'Initial Draft', 'Post Finance Review', 'Board Approved'",
    )
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
    )
    create_date = fields.Datetime(
        string='Created On',
        default=fields.Datetime.now,
    )
    note = fields.Text(
        string='Version Notes',
        help="Describe what changed in this version.",
    )

    # JSON snapshot
    snapshot_data = fields.Text(
        string='Snapshot (JSON)',
        help="Full JSON snapshot of scenario KPIs, forecasts, and projections.",
    )

    # Summary fields (computed from snapshot for quick display)
    total_headcount = fields.Integer(string='Headcount')
    total_cost = fields.Float(string='Total Cost')
    avg_increase_pct = fields.Float(string='Avg Increase %')

    @api.model
    def create_version(self, scenario_id, label=None, note=None):
        """Create a new version snapshot of the scenario."""
        scenario = self.env['wfp.planning.scenario'].sudo().browse(scenario_id)
        if not scenario.exists():
            return False

        # Get next version number
        last = self.search([
            ('scenario_id', '=', scenario_id)
        ], order='version_number desc', limit=1)
        next_version = (last.version_number + 1) if last else 1

        # Build snapshot
        forecasts = scenario.forecast_ids
        snapshot = {
            'scenario_name': scenario.name,
            'state': scenario.state,
            'fiscal_year': scenario.fiscal_year,
            'headcount': len(forecasts),
            'total_current_cost': sum(
                f.current_total_cost for f in forecasts
            ),
            'total_forecast_cost': sum(
                f.forecast_total_cost for f in forecasts
            ),
            'total_increase': sum(
                f.increase_amount for f in forecasts
            ),
            'avg_increase_pct': round(
                sum(f.increase_pct for f in forecasts) / len(forecasts), 2
            ) if forecasts else 0,
            'departments': {},
            'projections_count': len(scenario.monthly_projection_ids),
        }

        # Department breakdown
        for f in forecasts:
            dept = f.department_id.name or 'Unassigned'
            if dept not in snapshot['departments']:
                snapshot['departments'][dept] = {
                    'count': 0,
                    'current_cost': 0,
                    'forecast_cost': 0,
                }
            snapshot['departments'][dept]['count'] += 1
            snapshot['departments'][dept]['current_cost'] += (
                f.current_total_cost
            )
            snapshot['departments'][dept]['forecast_cost'] += (
                f.forecast_total_cost
            )

        version = self.create({
            'scenario_id': scenario_id,
            'version_number': next_version,
            'name': label or _('Version %d') % next_version,
            'note': note or '',
            'snapshot_data': json.dumps(snapshot, default=str),
            'total_headcount': snapshot['headcount'],
            'total_cost': snapshot['total_forecast_cost'],
            'avg_increase_pct': snapshot['avg_increase_pct'],
        })

        return {
            'id': version.id,
            'version': next_version,
            'name': version.name,
        }

    def get_comparison(self, version_id_a, version_id_b):
        """Compare two versions side-by-side."""
        va = self.browse(version_id_a)
        vb = self.browse(version_id_b)
        if not va.exists() or not vb.exists():
            return {}

        snap_a = json.loads(va.snapshot_data or '{}')
        snap_b = json.loads(vb.snapshot_data or '{}')

        return {
            'version_a': {
                'number': va.version_number,
                'name': va.name,
                'date': str(va.create_date),
                'data': snap_a,
            },
            'version_b': {
                'number': vb.version_number,
                'name': vb.name,
                'date': str(vb.create_date),
                'data': snap_b,
            },
            'deltas': {
                'headcount': (
                    snap_b.get('headcount', 0) -
                    snap_a.get('headcount', 0)
                ),
                'total_cost': (
                    snap_b.get('total_forecast_cost', 0) -
                    snap_a.get('total_forecast_cost', 0)
                ),
                'avg_increase': round(
                    snap_b.get('avg_increase_pct', 0) -
                    snap_a.get('avg_increase_pct', 0), 2
                ),
            },
        }
