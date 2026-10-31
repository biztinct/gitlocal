# -*- coding: utf-8 -*-
"""`pb.pay.review.sheet` — the pay review worksheet on the shared filter
panel (pb_filter_kit, FILTER wave 8).

The worksheet used to be `pb.pay.reviews._filtered_lines`: six fixed
filters as Python lambdas over `review.line_ids`, then a 120-row window.
It is now a domain over `pb.pay.review.line` (the kit's `pbf_domain`),
counted beside every value, with the same 120-row page and the same
"team, then name" order as the default sort. The review rides on every
call as `pbf_ctx.review_id`.

Privacy is unchanged: a reader who may not see names (`can_names` in
`open_review`) gets "Person 123" in the rows, cannot search by name, cannot
sort by name, and no section lists the people in the review.

"Stops approval" is a fact inside the `chips` JSON, not a field: it is read
for the whole review in one query and memoised on the cursor for the
request (F18/F25), behind a `domain_method`.
"""
import logging
import time

from odoo import _, api, models

from .pb_pay_review import GROUP_CEO, GROUP_FINANCE, GROUP_MANAGER

_logger = logging.getLogger(__name__)

#: Worksheet rows per page — the same window `open_review` always used.
SHEET_PAGE = 120
#: "Select everything matching" never hands more than this many rows to
#: one bulk call; the screen says so when it is capped.
MATCH_CAP = 5000


class PbPayReviewSheet(models.AbstractModel):
    _name = 'pb.pay.review.sheet'
    _description = 'Pay review worksheet'
    _inherit = ['pb.filter.mixin']

    # ------------------------------------------------------------ the review
    @api.model
    def _reviews(self):
        return self.env['pb.pay.reviews']

    @api.model
    def _can_names(self):
        return self._reviews()._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                                    'hr.group_hr_manager', 'base.group_system')

    @api.model
    def _review(self):
        Reviews = self._reviews()
        try:
            rid = int(self._pbf_ctx().get('review_id') or 0)
        except (TypeError, ValueError):
            rid = 0
        if not rid or not Reviews._can_read():
            return self.env['pb.pay.review']
        # read with every company the reader is entitled to (GR27)
        return Reviews._wide().env['pb.pay.review'].browse(rid).exists()

    def _pbf_records(self):
        # the same widened company context the review itself is read with
        return self._reviews()._wide().env['pb.pay.review.line']

    def _pbf_model(self):
        return 'pb.pay.review.line'

    def _pbf_screen(self):
        # one key for every review: a view saved on 2026 opens on 2027 too
        return 'payreview'

    def _pbf_base_domain(self):
        review = self._review()
        if not review:
            return [('id', '=', 0)]
        return [('review_id', '=', review.id)]

    def _pbf_search_fields(self):
        fields_ = ['job_id.name', 'department_id.name']
        if self._can_names():
            fields_.insert(0, 'employee_id.name')
        return fields_

    def _pbf_layout_extra(self):
        review = self._review()
        currency = review.currency_id if review else False
        return {'currency': (currency.symbol if currency else '') or '',
                'can_names': self._can_names()}

    def _pbf_sorts(self):
        sorts = [
            # the worksheet's own order, first so it stays the default
            {'key': 'team', 'label': _('Team, then name'),
             'order': 'department_id, employee_id, id'},
            {'key': 'rise_desc', 'label': _('Biggest rise first'),
             'order': 'proposal_pct desc, department_id, employee_id, id'},
            {'key': 'rise_asc', 'label': _('Smallest rise first'),
             'order': 'proposal_pct asc, department_id, employee_id, id'},
            {'key': 'score', 'label': _('Highest score first'),
             'order': 'rating desc, department_id, employee_id, id'},
            {'key': 'band', 'label': _('Lowest in the band first'),
             'order': 'has_band desc, position_pct asc, department_id, employee_id, id'},
            {'key': 'paid', 'label': _('Paid most first'),
             'order': 'current_wage desc, department_id, employee_id, id'},
        ]
        if self._can_names():
            sorts.insert(1, {'key': 'name', 'label': _('Name, A to Z'),
                             'order': 'employee_id, id'})
        return sorts

    def _pbf_spec(self):
        me = self.env.user.employee_ids.ids or [0]
        no_rise = ['|', ('proposal_pct', '=', False), ('proposal_pct', '=', 0)]
        return [
            # ---- pinned: the three questions a worksheet is opened with
            {'key': 'team', 'label': _('Team'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id', 'pinned': True,
             'none_label': _('No team')},
            {'key': 'score', 'label': _('Score'), 'icon': 'star',
             'group': 'pay', 'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'unscored', 'label': _('Not scored'), 'tone': 'amber',
                  'domain': ['|', ('rating', '=', False), ('rating', '<=', 0)]},
                 {'value': 'scored', 'label': _('Scored'), 'tone': 'green',
                  'domain': [('rating', '>', 0)]},
             ]},
            {'key': 'band', 'label': _('In the band'), 'icon': 'scale',
             'group': 'pay', 'type': 'choice', 'pinned': True,
             'options': [
                 {'value': 'below', 'label': _('Paid below the band'), 'tone': 'rose',
                  'domain': [('has_band', '=', True), ('position_pct', '<', 0)]},
                 {'value': 'in', 'label': _('Inside the band'), 'tone': 'green',
                  'domain': [('has_band', '=', True), ('position_pct', '>=', 0),
                             ('position_pct', '<=', 100)]},
                 {'value': 'above', 'label': _('Paid above the band'), 'tone': 'amber',
                  'domain': [('has_band', '=', True), ('position_pct', '>', 100)]},
                 {'value': 'none', 'label': _('No band for this job yet'), 'tone': 'slate',
                  'domain': [('has_band', '=', False)]},
             ]},
            # ---- more filters
            {'key': 'stops', 'label': _('Stops approval'), 'icon': 'alert',
             'group': 'pay', 'type': 'choice',
             'help': _('A row breaks a limit that blocks approval.'),
             'options': [
                 {'value': 'blocked', 'label': _('Stops approval'), 'tone': 'rose',
                  'domain_method': '_pbf_dm_blocked'},
                 {'value': 'clear', 'label': _('Nothing stops it'), 'tone': 'green',
                  'domain_method': '_pbf_dm_clear'},
             ]},
            {'key': 'mine', 'label': _('Whose team'), 'icon': 'users',
             'group': 'people', 'type': 'choice',
             'options': [
                 {'value': 'mine', 'label': _('My team'), 'tone': 'blue',
                  'domain': [('manager_id', 'in', me)]},
                 {'value': 'others', 'label': _('Other teams'), 'tone': 'slate',
                  'domain': ['|', ('manager_id', '=', False), ('manager_id', 'not in', me)]},
             ]},
            {'key': 'risen', 'label': _('Rise or not'), 'icon': 'trendingUp',
             'group': 'pay', 'type': 'choice',
             'options': [
                 {'value': 'none', 'label': _('No rise'), 'tone': 'slate', 'domain': no_rise},
                 {'value': 'up', 'label': _('A rise'), 'tone': 'green',
                  'domain': [('proposal_pct', '>', 0)]},
                 {'value': 'down', 'label': _('Less pay'), 'tone': 'rose',
                  'domain': [('proposal_pct', '<', 0)]},
             ]},
            {'key': 'manager', 'label': _('Manager'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'manager_id',
             'none_label': _('No manager')},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'work', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position')},
            {'key': 'division', 'label': _('Division'), 'icon': 'layers',
             'group': 'work', 'type': 'many2one', 'path': 'division_id',
             'none_label': _('No division')},
            {'key': 'band_id', 'label': _('Pay band'), 'icon': 'barChart',
             'group': 'pay', 'type': 'many2one', 'path': 'band_id',
             'none_label': _('No band')},
            {'key': 'rise', 'label': _('Proposed rise (%)'), 'icon': 'percent',
             'group': 'pay', 'type': 'number', 'path': 'proposal_pct'},
            {'key': 'state', 'label': _('Where the row is'), 'icon': 'workflow',
             'group': 'other', 'type': 'choice',
             'options': [
                 {'value': 'open', 'label': _('Open'), 'tone': 'slate',
                  'domain': ['|', ('state', '=', 'open'), ('state', '=', False)]},
                 {'value': 'submitted', 'label': _('Sent on'), 'tone': 'green',
                  'domain': [('state', '=', 'submitted')]},
                 {'value': 'returned', 'label': _('Sent back'), 'tone': 'amber',
                  'domain': [('state', '=', 'returned')]},
             ]},
        ]

    def _pbf_builtin_views(self):
        # the worksheet's six filters, same words, same order (the lessons
        # name them)
        return [
            {'key': 'all', 'label': _('Everybody'), 'icon': 'users', 'filters': {}},
            {'key': 'mine', 'label': _('My team'), 'filters': {'mine': ['mine']}},
            {'key': 'unrated', 'label': _('Not scored'), 'filters': {'score': ['unscored']}},
            {'key': 'blocked', 'label': _('Stops approval'), 'filters': {'stops': ['blocked']}},
            {'key': 'below_band', 'label': _('Paid below the band'), 'filters': {'band': ['below']}},
            {'key': 'no_rise', 'label': _('No rise'), 'filters': {'risen': ['none']}},
        ]

    # ------------------------------------------------- "stops approval"
    @api.model
    def _blocked_ids(self):
        """Rows of the review whose chips say they block approval — the
        rule `_filtered_lines` and `_blockers` use, for the whole review in
        one read, once per request."""
        review = self._review()
        key = ('pb.pay.review.sheet:blocked', review.id, self.env.uid)
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        started = time.time()
        blocked = set()
        if review:
            Line = self.env['pb.pay.review.line']
            Line.flush_model(['review_id', 'chips'])
            self.env.cr.execute(
                "SELECT id, chips FROM pb_pay_review_line WHERE review_id = %s "
                "AND chips IS NOT NULL", (review.id,))
            for line_id, chips in self.env.cr.fetchall():
                if isinstance(chips, list) and any(
                        isinstance(c, dict) and c.get('blocks') for c in chips):
                    blocked.add(line_id)
        _logger.info("Pay review worksheet: blocked rows of review %s in %s ms",
                     review.id if review else '-', int((time.time() - started) * 1000))
        cache[key] = blocked
        return blocked

    def _pbf_dm_blocked(self):
        return [('id', 'in', sorted(self._blocked_ids()) or [0])]

    def _pbf_dm_clear(self):
        return [('id', 'not in', sorted(self._blocked_ids()) or [0])]

    # ------------------------------------------------------------ the API
    @api.model
    def pbf_layout(self):
        if not self._reviews()._can_read():
            return {'refused': _("Pay reviews are read by the pay roles. Your "
                                 "account holds none of them.")}
        return super().pbf_layout()

    @api.model
    def get_sheet_page(self, filters=None, search=None, sort=None, offset=0,
                       limit=SHEET_PAGE):
        """One page of the worksheet for the panel's state."""
        started = time.time()
        self._reviews()._require_read()
        if not self._review():
            return {'rows': [], 'total': 0, 'offset': 0, 'ms': 0}
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or SHEET_PAGE), 500))
        except (TypeError, ValueError):
            offset, limit = 0, SHEET_PAGE
        Line = self._pbf_records()
        domain = self.pbf_domain(filters or {}, search)
        lines = Line.search(domain, order=self.pbf_order(sort) or 'department_id, employee_id, id',
                            offset=offset, limit=limit)
        can_names = self._can_names()
        return {
            'rows': [line.payload(can_names) for line in lines],
            'total': Line.search_count(domain),
            'offset': offset,
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def matching_line_ids(self, filters=None, search=None):
        """Every row the panel's filters match, for a bulk verb on the whole
        filtered set (R6) — capped, and the answer says when it is."""
        self._reviews()._require_read()
        if not self._review():
            return {'ids': [], 'capped': False, 'cap': MATCH_CAP}
        Line = self._pbf_records()
        domain = self.pbf_domain(filters or {}, search)
        lines = Line.search(domain, order=self.pbf_order(None) or 'id',
                            limit=MATCH_CAP + 1)
        return {'ids': lines[:MATCH_CAP].ids, 'capped': len(lines) > MATCH_CAP,
                'cap': MATCH_CAP}
