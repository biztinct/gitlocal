# -*- coding: utf-8 -*-

from odoo import models, api
import json
import logging

_logger = logging.getLogger(__name__)

# PayAI color palette
PAYAI_COLORS = [
    '#6366f1',  # Indigo
    '#22c55e',  # Green
    '#f59e0b',  # Amber
    '#ef4444',  # Red
    '#06b6d4',  # Cyan
    '#8b5cf6',  # Violet
    '#ec4899',  # Pink
    '#f97316',  # Orange
    '#14b8a6',  # Teal
    '#64748b',  # Slate
    '#a78bfa',  # Light Violet
    '#4ade80',  # Light Green
]

PAYAI_COLORS_ALPHA = [c + '80' for c in PAYAI_COLORS]  # 50% opacity versions


class PayrollChartSchema(models.Model):
    """
    Chart schema builder and validator for PayAI.
    Ensures AI-generated chart configs are valid Chart.js v4 format.
    """

    _name = 'payroll.chart.schema'
    _description = 'PayAI Chart Schema Builder'

    @api.model
    def build_chart_config(self, chart_type, title, labels, datasets, options=None):
        """
        Build a validated Chart.js configuration.

        Args:
            chart_type (str): bar, line, pie, doughnut, radar, scatter, bubble
            title (str): Chart title
            labels (list): X-axis labels
            datasets (list): [{label, data, backgroundColor, ...}]
            options (dict): Additional Chart.js options

        Returns:
            dict: Valid Chart.js v4 configuration
        """
        # Assign colors if not provided
        for i, ds in enumerate(datasets):
            if 'backgroundColor' not in ds:
                if chart_type in ('pie', 'doughnut'):
                    ds['backgroundColor'] = PAYAI_COLORS[:len(labels)]
                else:
                    ds['backgroundColor'] = PAYAI_COLORS[i % len(PAYAI_COLORS)]
            if chart_type == 'line' and 'borderColor' not in ds:
                ds['borderColor'] = ds.get('backgroundColor', PAYAI_COLORS[i % len(PAYAI_COLORS)])
                ds.setdefault('fill', False)
                ds.setdefault('tension', 0.3)

        config = {
            'type': chart_type,
            'data': {
                'labels': labels,
                'datasets': datasets,
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'title': {
                        'display': bool(title),
                        'text': title or '',
                        'font': {'size': 14, 'weight': 'bold'},
                        'color': '#1e293b',
                    },
                    'legend': {
                        'position': 'bottom',
                        'labels': {'usePointStyle': True, 'padding': 15},
                    },
                    'tooltip': {
                        'enabled': True,
                        'mode': 'index',
                        'intersect': False,
                    },
                },
            },
        }

        # Chart-type-specific defaults
        if chart_type in ('bar', 'line'):
            config['options']['scales'] = {
                'y': {
                    'beginAtZero': True,
                    'grid': {'color': '#e2e8f0'},
                    'ticks': {'color': '#64748b'},
                },
                'x': {
                    'grid': {'display': False},
                    'ticks': {'color': '#64748b'},
                },
            }

        # Merge custom options
        if options:
            self._deep_merge(config['options'], options)

        return config

    @api.model
    def validate_chart_config(self, config):
        """
        Validate a Chart.js configuration dict.

        Args:
            config (dict): Chart configuration to validate

        Returns:
            dict: Validated config (with defaults applied) or None if invalid
        """
        if not config or not isinstance(config, dict):
            return None

        # Must have type and data
        if 'type' not in config:
            return None
        if 'data' not in config or not isinstance(config['data'], dict):
            return None

        valid_types = ['bar', 'line', 'pie', 'doughnut', 'radar', 'scatter',
                       'bubble', 'polarArea']
        if config['type'] not in valid_types:
            _logger.warning("Invalid chart type: %s", config['type'])
            config['type'] = 'bar'  # Fallback

        # Ensure datasets exist
        if 'datasets' not in config['data'] or not config['data']['datasets']:
            return None

        # Apply colors if missing
        for i, ds in enumerate(config['data'].get('datasets', [])):
            if 'backgroundColor' not in ds:
                if config['type'] in ('pie', 'doughnut', 'polarArea'):
                    num_labels = len(config['data'].get('labels', []))
                    ds['backgroundColor'] = PAYAI_COLORS[:num_labels]
                else:
                    ds['backgroundColor'] = PAYAI_COLORS[i % len(PAYAI_COLORS)]

        # Ensure options exist
        config.setdefault('options', {})
        config['options'].setdefault('responsive', True)
        config['options'].setdefault('maintainAspectRatio', False)

        return config

    def _deep_merge(self, base, override):
        """Deep merge override into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
