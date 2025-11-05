# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
import json


class HrAnalyticsCache(models.Model):
    """Cache mechanism for analytics data with TTL support"""

    _name = 'hr.analytics.cache'
    _description = 'HR Analytics Cache'
    _order = 'created_at DESC'

    # Cache Key Fields
    cache_key = fields.Char(
        string='Cache Key',
        required=True,
        help='Unique identifier for cached data (e.g., personnel_costs_VN_2024_01_department)'
    )
    model_name = fields.Char(
        string='Model Name',
        help='Target model name (e.g., hr.analytics.personnel.costs)'
    )

    # Cached Data
    cached_data = fields.Text(
        string='Cached Data (JSON)',
        help='Stored JSON data'
    )
    data_size = fields.Integer(
        string='Data Size (bytes)',
        compute='_compute_data_size',
        store=True
    )

    # Timestamp Management
    created_at = fields.Datetime(
        string='Created At',
        default=lambda self: fields.Datetime.now(),
        readonly=True
    )
    expires_at = fields.Datetime(
        string='Expires At',
        help='Cache expiration timestamp'
    )
    last_accessed = fields.Datetime(
        string='Last Accessed',
        default=lambda self: fields.Datetime.now()
    )

    # Status Fields
    is_valid = fields.Boolean(
        string='Is Valid',
        compute='_compute_is_valid',
        store=False
    )
    ttl_minutes = fields.Integer(
        string='TTL (Minutes)',
        default=30,
        help='Time-to-live in minutes'
    )

    # Optional context
    context_data = fields.Text(
        string='Context (JSON)',
        help='Associated context (country, date range, etc.)'
    )

    @api.depends('data_size')
    def _compute_data_size(self):
        """Compute cached data size in bytes"""
        for record in self:
            if record.cached_data:
                record.data_size = len(record.cached_data.encode('utf-8'))
            else:
                record.data_size = 0

    def _compute_is_valid(self):
        """Check if cache is still valid (not expired)"""
        for record in self:
            if record.expires_at:
                record.is_valid = fields.Datetime.now() <= record.expires_at
            else:
                record.is_valid = True

    @api.model
    def get_cached_data(self, cache_key):
        """
        Retrieve cached data if valid

        Args:
            cache_key: Unique cache identifier

        Returns:
            dict: Parsed JSON data or None if expired/not found
        """
        cache = self.search([
            ('cache_key', '=', cache_key),
            ('expires_at', '>', fields.Datetime.now())
        ], limit=1)

        if cache:
            cache.last_accessed = fields.Datetime.now()
            try:
                return json.loads(cache.cached_data)
            except (json.JSONDecodeError, ValueError):
                cache.unlink()
                return None

        return None

    @api.model
    def set_cache(self, cache_key, data, ttl_minutes=30, context_data=None, model_name=None):
        """
        Store data in cache with expiration

        Args:
            cache_key: Unique cache identifier
            data: Dictionary to cache (will be JSON serialized)
            ttl_minutes: Time-to-live in minutes (default 30)
            context_data: Optional context dictionary
            model_name: Optional model name for reference

        Returns:
            hr.analytics.cache: Created cache record
        """
        expires_at = fields.Datetime.now() + timedelta(minutes=ttl_minutes)

        # Remove old cache with same key
        self.search([('cache_key', '=', cache_key)]).unlink()

        cache_data = {
            'cache_key': cache_key,
            'cached_data': json.dumps(data),
            'expires_at': expires_at,
            'ttl_minutes': ttl_minutes,
            'model_name': model_name,
            'context_data': json.dumps(context_data) if context_data else None,
        }

        return self.create(cache_data)

    @api.model
    def clear_cache(self, pattern=None):
        """
        Clear caches matching pattern

        Args:
            pattern: Wildcard pattern (e.g., 'personnel_costs_*')
                   If None, clears expired caches only

        Returns:
            int: Number of records deleted
        """
        if pattern:
            # Pattern-based clearing
            domain = [('cache_key', 'ilike', pattern.replace('*', '%'))]
        else:
            # Clear expired caches
            domain = [('expires_at', '<', fields.Datetime.now())]

        records_to_delete = self.search(domain)
        count = len(records_to_delete)
        records_to_delete.unlink()

        return count

    @api.model
    def invalidate_analytics_cache(self, country=None, model_pattern=None):
        """
        Invalidate analytics caches when payslips change

        Args:
            country: Optional country code to filter by
            model_pattern: Optional model pattern (e.g., 'personnel*')
        """
        domain = []

        if country:
            domain.append(('context_data', 'ilike', country))

        if model_pattern:
            domain.append(('model_name', 'ilike', model_pattern))

        if domain:
            caches = self.search(domain)
        else:
            caches = self.search([('model_name', 'like', 'hr.analytics')])

        count = len(caches)
        caches.unlink()

        return count

    @api.model
    def cleanup_expired_caches(self):
        """
        Cleanup job - remove all expired caches

        Returns:
            int: Number of expired caches removed
        """
        return self.clear_cache()

    def _get_cache_stats(self):
        """Get cache statistics for monitoring"""
        total_size = sum(record.data_size for record in self.search([]))
        valid_caches = len(self.search([('expires_at', '>', fields.Datetime.now())]))
        expired_caches = len(self.search([('expires_at', '<=', fields.Datetime.now())]))

        return {
            'total_size_mb': total_size / (1024 * 1024),
            'valid_caches': valid_caches,
            'expired_caches': expired_caches,
            'total_caches': len(self),
        }
