# -*- coding: utf-8 -*-
"""One add-only seam on the inbox for work that is not an approval (WF2 P4a).

Workflow Studio's waiting tasks (D1) go into this one inbox, beside the
approvals and never mixed into them:

  * `_extra_items(scope, search=None)` — cards other modules add (default
    none). They come back under their own key, `tasks`, on the FIRST page only:
    approvals keep their own SQL paging, filters, sort and totals exactly as
    before, so nothing an approval card shows moves, renames or recounts.
  * `_extra_counts(scope)` — `{'mine': n, 'late': n}` (default zeros), returned
    beside the approval counts as `tasks` / `tasks_late`; the approval numbers
    themselves (`mine`, `all`, `returned`, `done`) are untouched.

An extra card carries the approval card's keys plus `source` (who made it),
`kind` ('task') and `open` ({type, id}: how the screen opens it). It has no
route: a task is not an approval.

Method-only file: a restart loads it (no version bump, ledger G29).
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbApprovalInboxExtra(models.AbstractModel):
    _inherit = 'pb.approval.inbox'

    # ------------------------------------------------------------ the seam
    @api.model
    def _extra_items(self, scope='me', search=None):
        """Cards that are not approval requests, for one scope. Default: []."""
        return []

    @api.model
    def _extra_counts(self, scope='me'):
        """How many extra cards wait on me, and how many of them are late."""
        return {'mine': 0, 'late': 0}

    # ------------------------------------------------------- where it shows
    @api.model
    def _extra_safe(self, fn, default):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception:  # noqa: BLE001 — another area never blanks the inbox
            _logger.warning('Approvals inbox: extra items failed', exc_info=True)
            return default

    @api.model
    def get_inbox_head(self):
        head = super().get_inbox_head()
        scope = head.get('scope') or 'me'
        counts = self._extra_safe(lambda: self._extra_counts(scope), {'mine': 0, 'late': 0})
        head['task_counts'] = {'mine': int(counts.get('mine') or 0), 'late': int(counts.get('late') or 0)}
        return head

    @api.model
    def get_inbox_page(self, filters=None, search=None, sort=None, offset=0, limit=60):
        page = super().get_inbox_page(filters=filters, search=search, sort=sort,
                                      offset=offset, limit=limit)
        try:
            first = int(offset or 0) <= 0
        except (TypeError, ValueError):
            first = True
        page['tasks'] = self._extra_safe(
            lambda: list(self._extra_items(self._pbf_scope(), search) or []), []) if first else []
        return page

    def _counts(self, scope='me'):
        counts = super()._counts(scope)
        extra = self._extra_safe(lambda: self._extra_counts(scope), {'mine': 0, 'late': 0})
        counts['tasks'] = int(extra.get('mine') or 0)
        counts['tasks_late'] = int(extra.get('late') or 0)
        return counts

    @api.model
    def get_team_data(self, recursive=True, scope='team', queues_only=True):
        data = super().get_team_data(recursive=recursive, scope=scope, queues_only=queues_only)
        extra = self._extra_safe(lambda: self._extra_counts('me'), {'mine': 0, 'late': 0})
        data.setdefault('queues', {})['tasks'] = int(extra.get('mine') or 0)
        return data
