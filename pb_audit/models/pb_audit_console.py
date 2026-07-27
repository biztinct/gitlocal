# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RPC facade for the Audit & Compliance console (Sudima Phase J §3).

An AbstractModel (no table) exposing a normalized, filterable, day-grouped
stream over EVERY audit source already flowing in the platform, plus the salary
and login lenses, KPIs and the retention setting. It is READ-ONLY: no method
here creates/writes/unlinks a foreign record. The two writes the whole module is
permitted (safety rail 1) live elsewhere — the export wizard's own transient
Binary (pb.audit.export) and the manager-gated retention param (set_retention
below, which writes only an ir.config_parameter).

Access model (C18.17 — one permission world): every public method calls
``_require_manager()`` first (the Payroll Manager + System tier is the whole
authorization boundary), then reads each source UNIFORMLY via ``sudo()``. A
compliance console must see the consolidated trail regardless of which log
model a given manager individually holds an ACL on; PII is the concern, and it
is handled by MASKING (safety rail 3), not by withholding rows. Navigation OUT
of the console (the employee/record deep-links the cockpit builds) uses plain
act_window and therefore respects each target's own access rules (safety rail
6) — the sudo here never leaks a full value, only a masked, already-authorized
overview.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_MANAGER_GROUP = 'om_hr_payroll.group_hr_payroll_manager'
_SYSTEM_GROUP = 'base.group_system'

# Per-source scan ceiling for the live stream page. We fetch this many newest
# rows per source (after pushing date/actor/employee/model filters into the
# domain), merge, sort, apply the free-text filter, then page. Beyond this the
# page is honestly flagged ``capped`` (C18 no-silent-caps) — a compliance user
# narrows with filters rather than paging into the far past.
_STREAM_SCAN = 600
_PAGE = 50

# The export hard cap (handover §3 / §5.4) — surfaced in the UI, never silent.
_EXPORT_CAP = 50000

_RETENTION_PARAM = 'biz_audit_trail.retention_days'
_AMBER_PARAM = 'pb_audit.salary_amber_pct'
_ROSE_PARAM = 'pb_audit.salary_rose_pct'
_AMBER_DEFAULT = 10.0
_ROSE_DEFAULT = 25.0

# Source-colored rail dots (handover §4.1). Kept server-side so the palette is
# one source of truth shared by the stream and the KPI pills.
_SOURCE_META = {
    'field':    {'label': 'Field change', 'icon': 'fileText',   'color': 'indigo'},
    'approval': {'label': 'Approval',     'icon': 'checkCircle', 'color': 'violet'},
    'bank':     {'label': 'Bank master',  'icon': 'landmark',    'color': 'teal'},
    'export':   {'label': 'Bank export',  'icon': 'download',    'color': 'slate'},
    'delivery': {'label': 'Payslip sent', 'icon': 'mail',        'color': 'green'},
    'login':    {'label': 'Login',        'icon': 'logIn',       'color': 'cyan'},
}
# Display / filter order.
_SOURCE_ORDER = ['field', 'approval', 'bank', 'export', 'delivery', 'login']


class PbAuditConsole(models.AbstractModel):
    _name = 'pb.audit.console'
    _description = 'Audit & Compliance Console'

    # ================================================================= gate
    def _require_manager(self):
        u = self.env.user
        if (self.env.su or u._is_admin()
                or u.has_group(_MANAGER_GROUP) or u.has_group(_SYSTEM_GROUP)):
            return
        raise AccessError(_(
            "The Audit & Compliance console is restricted to Payroll Managers "
            "and administrators."))

    def _can_see_wage(self):
        # The console gate already guarantees the manager tier; the two-tier
        # serializer is kept so a future gate widening cannot leak wage values.
        u = self.env.user
        return self.env.su or u._is_admin() or u.has_group(_MANAGER_GROUP)

    # =============================================================== helpers
    @staticmethod
    def _mask(number):
        """Mask an account number to '•••• 1234' (safety rail 3 — reuse of the
        pb_bank_ocr_cockpit pattern)."""
        digits = ''.join(ch for ch in (number or '') if ch.isdigit())
        return ('•••• ' + digits[-4:]) if len(digits) >= 4 else (digits or '')

    @staticmethod
    def _dt_bounds(filters):
        """(datetime_from, datetime_to) inclusive, from YYYY-MM-DD strings."""
        df = dt = None
        raw_from = (filters or {}).get('date_from')
        raw_to = (filters or {}).get('date_to')
        if raw_from:
            df = fields.Datetime.to_datetime(raw_from + ' 00:00:00')
        if raw_to:
            dt = fields.Datetime.to_datetime(raw_to + ' 23:59:59')
        return df, dt

    def _avatar(self, model, res_id):
        return '/web/image/%s/%s/avatar_128' % (model, res_id) if res_id else ''

    def _actor(self, user):
        if not user:
            return {'id': False, 'name': _('System'), 'avatar': ''}
        return {'id': user.id, 'name': user.name,
                'avatar': self._avatar('res.users', user.id)}

    def _employee(self, emp):
        if not emp:
            return None
        return {'id': emp.id, 'name': emp.name,
                'avatar': self._avatar('hr.employee', emp.id)}

    def _row(self, source, rid, stamp, actor_user, title, old, new,
             ref_model, ref_id, employee=None):
        stamp_dt = fields.Datetime.to_datetime(stamp) if stamp else None
        meta = _SOURCE_META[source]
        return {
            'key': '%s-%s' % (source, rid),
            'source': source,
            'source_label': meta['label'],
            'icon': meta['icon'],
            'color': meta['color'],
            'stamp': fields.Datetime.to_string(stamp_dt) if stamp_dt else '',
            'stamp_display': stamp_dt.strftime('%H:%M') if stamp_dt else '',
            'day': stamp_dt.strftime('%Y-%m-%d') if stamp_dt else '',
            'sort': (stamp_dt.isoformat() if stamp_dt else '', source, rid),
            'actor': self._actor(actor_user),
            'employee': self._employee(employee) if employee else None,
            'title': title or '',
            'old': old or '',
            'new': new or '',
            'ref': {'model': ref_model, 'res_id': ref_id} if ref_model and ref_id else None,
        }

    # ================================================= per-source availability
    def _source_available(self, key):
        model = {
            'field': 'biz.audit.entry',
            'approval': 'biz.approval.step.log',
            'bank': 'pb.employee.bank.history',
            'export': 'bank.export.log',
            'delivery': 'pb.payslip.delivery',
            'login': 'res.users.log',
        }[key]
        return model in self.env

    # ============================================================ source fetch
    # Each fetcher returns a list of normalized rows for the given filters,
    # capped at ``limit`` newest. Callers pass sudo'd env implicitly (we sudo the
    # searches here). Filters honoured in the domain: date range, actor, employee
    # (where the source carries one), model (ref model). Free text is applied by
    # the caller across the merged set.

    def _emp_filter(self, filters):
        return (filters or {}).get('employee_id') or None

    def _actor_filter(self, filters):
        return (filters or {}).get('actor_id') or None

    def _model_filter(self, filters):
        return (filters or {}).get('model') or None

    def _fetch_field(self, filters, limit):
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('stamp', '>=', df))
        if dt:
            dom.append(('stamp', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('user_id', '=', self._actor_filter(filters)))
        if self._model_filter(filters):
            dom.append(('model_name', '=', self._model_filter(filters)))
        entries = self.env['biz.audit.entry'].sudo().search(
            dom, order='stamp desc, id desc', limit=limit)
        # Batch-resolve the employee behind each entry (contract/employee/version).
        emp_map = self._entry_employee_map(entries)
        emp_want = self._emp_filter(filters)
        rows = []
        for e in entries:
            emp = emp_map.get(e.id)
            if emp_want and (not emp or emp.id != emp_want):
                continue
            title = _('%(field)s on %(rec)s') % {
                'field': e.field_label or e.field_name,
                'rec': e.res_display or ('%s#%s' % (e.model_name, e.res_id))}
            old, new = e.old_value, e.new_value
            if self._is_account_field(e.field_name):
                old, new = self._mask(old), self._mask(new)
            rows.append(self._row(
                'field', e.id, e.stamp, e.user_id, title, old, new,
                e.model_name, e.res_id, employee=emp))
        return rows

    def _fetch_approval(self, filters, limit):
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('stamp', '>=', df))
        if dt:
            dom.append(('stamp', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('user_id', '=', self._actor_filter(filters)))
        if self._model_filter(filters):
            dom.append(('res_model', '=', self._model_filter(filters)))
        logs = self.env['biz.approval.step.log'].sudo().search(
            dom, order='stamp desc, id desc', limit=limit)
        emp_map = self._approval_employee_map(logs)
        emp_want = self._emp_filter(filters)
        rows = []
        for l in logs:
            emp = emp_map.get(l.id)
            if emp_want and (not emp or emp.id != emp_want):
                continue
            model_label = self._model_label(l.res_model)
            title = _('%(model)s #%(rid)s') % {'model': model_label, 'rid': l.res_id}
            rows.append(self._row(
                'approval', l.id, l.stamp, l.user_id, title,
                self._state_label(l.from_state), self._state_label(l.to_state),
                l.res_model, l.res_id, employee=emp))
        return rows

    def _fetch_bank(self, filters, limit):
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('changed_at', '>=', df))
        if dt:
            dom.append(('changed_at', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('changed_by', '=', self._actor_filter(filters)))
        if self._emp_filter(filters):
            dom.append(('employee_id', '=', self._emp_filter(filters)))
        # bank rows carry no ref model; a model filter that isn't hr.employee
        # excludes them.
        mf = self._model_filter(filters)
        if mf and mf != 'hr.employee':
            return []
        hist = self.env['pb.employee.bank.history'].sudo().search(
            dom, order='changed_at desc, id desc', limit=limit)
        rows = []
        for h in hist:
            src = dict(h._fields['change_source'].selection).get(
                h.change_source, h.change_source)
            title = _('Bank account · %(src)s') % {'src': src}
            rows.append(self._row(
                'bank', h.id, h.changed_at, h.changed_by, title,
                self._mask(h.old_account_number), self._mask(h.new_account_number),
                'hr.employee', h.employee_id.id, employee=h.employee_id))
        return rows

    def _fetch_export(self, filters, limit):
        if 'bank.export.log' not in self.env:
            return []
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('export_date', '>=', df))
        if dt:
            dom.append(('export_date', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('created_by', '=', self._actor_filter(filters)))
        if self._emp_filter(filters):  # export is period-level, no employee
            return []
        mf = self._model_filter(filters)
        if mf and mf != 'bank.export.log':
            return []
        logs = self.env['bank.export.log'].sudo().search(
            dom, order='export_date desc, id desc', limit=limit)
        rows = []
        for x in logs:
            title = _('Bank file · %(period)s') % {'period': x.period_name or ''}
            fmt = x.export_format or ''
            new = _('%(n)s records') % {'n': x.total_records or 0}
            rows.append(self._row(
                'export', x.id, x.export_date, x.created_by, title,
                fmt, new, 'bank.export.log', x.id, employee=None))
        return rows

    def _fetch_delivery(self, filters, limit):
        if 'pb.payslip.delivery' not in self.env:
            return []
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('create_date', '>=', df))
        if dt:
            dom.append(('create_date', '<=', dt))
        if self._emp_filter(filters):
            dom.append(('employee_id', '=', self._emp_filter(filters)))
        # delivery lines record no actor user; an actor filter excludes them.
        if self._actor_filter(filters):
            return []
        mf = self._model_filter(filters)
        if mf and mf != 'hr.payslip':
            return []
        lines = self.env['pb.payslip.delivery'].sudo().search(
            dom, order='create_date desc, id desc', limit=limit)
        rows = []
        for d in lines:
            state = dict(d._fields['state'].selection).get(d.state, d.state)
            title = _('Payslip → %(email)s') % {'email': d.email or _('(no email)')}
            rows.append(self._row(
                'delivery', d.id, d.create_date, None, title,
                '', state, 'hr.payslip', d.slip_id.id, employee=d.employee_id))
        return rows

    def _fetch_login(self, filters, limit):
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('create_date', '>=', df))
        if dt:
            dom.append(('create_date', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('create_uid', '=', self._actor_filter(filters)))
        if self._emp_filter(filters):  # a login has no employee subject
            return []
        mf = self._model_filter(filters)
        if mf and mf != 'res.users':
            return []
        logs = self.env['res.users.log'].sudo().search(
            dom, order='create_date desc, id desc', limit=limit)
        rows = []
        for lg in logs:
            u = lg.create_uid
            if u and u.share:  # internal users only (handover §3)
                continue
            rows.append(self._row(
                'login', lg.id, lg.create_date, u, _('Session started'),
                '', '', 'res.users', u.id if u else False, employee=None))
        return rows

    _FETCHERS = {
        'field': '_fetch_field',
        'approval': '_fetch_approval',
        'bank': '_fetch_bank',
        'export': '_fetch_export',
        'delivery': '_fetch_delivery',
        'login': '_fetch_login',
    }

    # --------------------------------------------------- employee resolution
    def _entry_employee_map(self, entries):
        """Map biz.audit.entry id -> hr.employee, resolving through the audited
        record (contract/version/employee). Batched by model to avoid N+1."""
        out = {}
        by_model = defaultdict(list)
        for e in entries:
            by_model[e.model_name].append(e)
        for model_name, recs in by_model.items():
            ids = [e.res_id for e in recs]
            if model_name == 'hr.employee':
                emps = self.env['hr.employee'].sudo().browse(ids).exists()
                emap = {emp.id: emp for emp in emps}
                for e in recs:
                    out[e.id] = emap.get(e.res_id)
            elif model_name in ('hr.contract', 'hr.version') and model_name in self.env:
                targets = self.env[model_name].sudo().browse(ids).exists()
                tmap = {t.id: t for t in targets}
                for e in recs:
                    t = tmap.get(e.res_id)
                    out[e.id] = t.employee_id if t and t.employee_id else None
            else:
                for e in recs:
                    out[e.id] = None
        return out

    def _approval_employee_map(self, logs):
        out = {}
        by_model = defaultdict(list)
        for l in logs:
            by_model[l.res_model].append(l)
        for model_name, recs in by_model.items():
            if model_name in self.env and 'employee_id' in self.env[model_name]._fields:
                targets = self.env[model_name].sudo().browse(
                    [l.res_id for l in recs]).exists()
                tmap = {t.id: t for t in targets}
                for l in recs:
                    t = tmap.get(l.res_id)
                    out[l.id] = t.employee_id if t and t.employee_id else None
            else:
                for l in recs:
                    out[l.id] = None
        return out

    # ----------------------------------------------------------- label helpers
    def _model_label(self, model_name):
        if model_name in self.env:
            return self.env['ir.model']._get(model_name).name or model_name
        return model_name

    @staticmethod
    def _state_label(state):
        if not state:
            return ''
        return str(state).replace('_', ' ').title()

    @staticmethod
    def _is_account_field(field_name):
        fn = (field_name or '').lower()
        return 'account_number' in fn or fn.endswith('account')

    # =============================================================== the stream
    def _collect_stream(self, filters, scan_limit):
        """Merge every present source, newest-first. Returns (rows, capped,
        source_status). Rows are normalized + PII-masked; the caller pages."""
        filters = filters or {}
        want_source = filters.get('source')
        text = (filters.get('text') or '').strip().lower()
        rows = []
        capped = False
        status = []
        for key in _SOURCE_ORDER:
            installed = self._source_available(key)
            status.append({
                'key': key, 'label': _SOURCE_META[key]['label'],
                'icon': _SOURCE_META[key]['icon'], 'color': _SOURCE_META[key]['color'],
                'installed': installed,
            })
            if not installed:
                continue
            if want_source and want_source != 'all' and want_source != key:
                continue
            try:
                fetched = getattr(self, self._FETCHERS[key])(filters, scan_limit)
            except Exception:
                # Soft-hook fail closed-and-visible (safety rail 5): log, mark
                # the source unavailable, keep the stream.
                _logger.exception("pb.audit.console: source %s failed", key)
                status[-1]['error'] = True
                continue
            if len(fetched) >= scan_limit:
                capped = True
            rows.extend(fetched)
        if text:
            rows = [r for r in rows if self._row_matches_text(r, text)]
        rows.sort(key=lambda r: r['sort'], reverse=True)
        return rows, capped, status

    @staticmethod
    def _row_matches_text(row, text):
        hay = ' '.join([
            row['title'], row['old'], row['new'],
            row['actor']['name'] or '',
            (row['employee'] or {}).get('name', '') if row['employee'] else '',
            row['source_label'],
        ]).lower()
        return text in hay

    @api.model
    def get_stream(self, filters=None, offset=0):
        self._require_manager()
        offset = max(0, int(offset or 0))
        # Scan enough to serve this page from the newest rows of each source.
        scan = min(_STREAM_SCAN, offset + _PAGE + _PAGE)
        rows, capped, status = self._collect_stream(filters, scan)
        page = rows[offset:offset + _PAGE]
        # Strip the internal sort tuple before returning.
        for r in page:
            r.pop('sort', None)
        return {
            'rows': page,
            'offset': offset,
            'page_size': _PAGE,
            'has_more': len(rows) > offset + _PAGE,
            'total_scanned': len(rows),
            'capped': capped,
            'sources': status,
        }

    # ================================================================ salary lens
    @api.model
    def get_salary_lens(self, filters=None):
        self._require_manager()
        filters = filters or {}
        can_see = self._can_see_wage()
        df, dt = self._dt_bounds(filters)
        dom = [('model_name', '=', 'hr.contract'), ('field_name', '=', 'wage')]
        if df:
            dom.append(('stamp', '>=', df))
        if dt:
            dom.append(('stamp', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('user_id', '=', self._actor_filter(filters)))
        entries = self.env['biz.audit.entry'].sudo().search(
            dom, order='stamp desc, id desc', limit=_STREAM_SCAN)
        emp_map = self._entry_employee_map(entries)
        emp_want = self._emp_filter(filters)
        amber = self._get_float_param(_AMBER_PARAM, _AMBER_DEFAULT)
        rose = self._get_float_param(_ROSE_PARAM, _ROSE_DEFAULT)
        rows = []
        month_counts = defaultdict(int)
        for e in entries:
            emp = emp_map.get(e.id)
            if emp_want and (not emp or emp.id != emp_want):
                continue
            old_v = self._to_float(e.old_value)
            new_v = self._to_float(e.new_value)
            delta_pct = None
            if old_v not in (None, 0) and new_v is not None:
                delta_pct = (new_v - old_v) / old_v * 100.0
            band = ''
            if delta_pct is not None:
                mag = abs(delta_pct)
                band = 'rose' if mag >= rose else ('amber' if mag >= amber else 'green')
            stamp_dt = e.stamp
            if stamp_dt:
                month_counts[stamp_dt.strftime('%Y-%m')] += 1
            rows.append({
                'key': 'wage-%s' % e.id,
                'employee': self._employee(emp) if emp else {
                    'id': False, 'name': e.res_display or _('(deleted contract)'),
                    'avatar': ''},
                'old': self._fmt_money(old_v) if can_see else '••••',
                'new': self._fmt_money(new_v) if can_see else '••••',
                'delta_pct': round(delta_pct, 1) if delta_pct is not None else None,
                'band': band,
                'actor': self._actor(e.user_id),
                'stamp': fields.Datetime.to_string(stamp_dt) if stamp_dt else '',
                'stamp_display': stamp_dt.strftime('%Y-%m-%d %H:%M') if stamp_dt else '',
                'ref': {'model': 'hr.contract', 'res_id': e.res_id},
            })
        spark = self._month_series(month_counts, 12)
        return {
            'rows': rows,
            'sparkline': spark,
            'thresholds': {'amber': amber, 'rose': rose},
            'can_see_values': can_see,
            'capped': len(entries) >= _STREAM_SCAN,
        }

    # ================================================================= login lens
    @api.model
    def get_login_lens(self, filters=None):
        self._require_manager()
        filters = filters or {}
        Log = self.env['res.users.log'].sudo()
        df, dt = self._dt_bounds(filters)
        dom = []
        if df:
            dom.append(('create_date', '>=', df))
        if dt:
            dom.append(('create_date', '<=', dt))
        if self._actor_filter(filters):
            dom.append(('create_uid', '=', self._actor_filter(filters)))
        # Aggregate session count per user over the filtered window.
        grouped = Log.read_group(dom, ['create_uid'], ['create_uid'],
                                 orderby='create_uid')
        today = fields.Date.context_today(self)
        window_start = fields.Datetime.now() - timedelta(days=30)
        cards = []
        for g in grouped:
            uid_tuple = g.get('create_uid')
            if not uid_tuple:
                continue
            user = self.env['res.users'].sudo().browse(uid_tuple[0])
            if not user.exists() or user.share:
                continue
            # last-30-day daily sparkline + last login for this user.
            recent = Log.search([
                ('create_uid', '=', user.id),
                ('create_date', '>=', window_start),
            ], order='create_date desc')
            day_counts = defaultdict(int)
            for r in recent:
                day_counts[r.create_date.date()] += 1
            spark = []
            for i in range(29, -1, -1):
                d = today - timedelta(days=i)
                spark.append(day_counts.get(d, 0))
            last = Log.search([('create_uid', '=', user.id)],
                              order='create_date desc', limit=1)
            cards.append({
                'user_id': user.id,
                'name': user.name,
                'login': user.login,
                'avatar': self._avatar('res.users', user.id),
                'sessions': g.get('create_uid_count') or g.get('__count') or 0,
                'sessions_30d': sum(spark),
                'sparkline': spark,
                'last': last.create_date.strftime('%Y-%m-%d %H:%M') if last else '',
            })
        cards.sort(key=lambda c: c['sessions'], reverse=True)
        return {'cards': cards, 'note': _(
            "Odoo records sessions started at login only — it does not log "
            "logouts, so no session-duration data is shown.")}

    # ====================================================================== kpis
    @api.model
    def get_kpis(self):
        self._require_manager()
        now = fields.Datetime.now()
        today_start = fields.Datetime.to_datetime(
            fields.Date.context_today(self).strftime('%Y-%m-%d') + ' 00:00:00')
        week_start = now - timedelta(days=7)
        today = week = 0
        sources = []
        for key in _SOURCE_ORDER:
            installed = self._source_available(key)
            entry = {
                'key': key, 'label': _SOURCE_META[key]['label'],
                'icon': _SOURCE_META[key]['icon'], 'color': _SOURCE_META[key]['color'],
                'installed': installed, 'count': 0,
            }
            if installed:
                model, date_field = self._source_date_field(key)
                Model = self.env[model].sudo()
                entry['count'] = Model.search_count([])
                today += Model.search_count([(date_field, '>=', today_start)])
                week += Model.search_count([(date_field, '>=', week_start)])
            sources.append(entry)
        # Top actors over the last 30 days across the actor-bearing sources.
        top = self._top_actors(now - timedelta(days=30))
        oldest = self.env['biz.audit.entry'].sudo().search(
            [], order='stamp asc, id asc', limit=1)
        return {
            'events_today': today,
            'events_week': week,
            'top_actors': top,
            'sources': sources,
            'oldest': oldest.stamp.strftime('%Y-%m-%d') if oldest else '',
            'retention_days': self._retention_days(),
            'can_edit_retention': True,  # every reader of KPIs is a manager
        }

    def _top_actors(self, since):
        counts = defaultdict(int)
        # field-change entries
        for g in self.env['biz.audit.entry'].sudo().read_group(
                [('stamp', '>=', since)], ['user_id'], ['user_id']):
            if g.get('user_id'):
                counts[g['user_id'][0]] += g.get('user_id_count') or g.get('__count') or 0
        # approval transitions
        for g in self.env['biz.approval.step.log'].sudo().read_group(
                [('stamp', '>=', since)], ['user_id'], ['user_id']):
            if g.get('user_id'):
                counts[g['user_id'][0]] += g.get('user_id_count') or g.get('__count') or 0
        top_ids = sorted(counts, key=lambda i: counts[i], reverse=True)[:5]
        users = {u.id: u for u in self.env['res.users'].sudo().browse(top_ids)}
        out = []
        for uid in top_ids:
            u = users.get(uid)
            if not u:
                continue
            out.append({'id': u.id, 'name': u.name,
                        'avatar': self._avatar('res.users', u.id),
                        'count': counts[uid]})
        return out

    def _source_date_field(self, key):
        return {
            'field': ('biz.audit.entry', 'stamp'),
            'approval': ('biz.approval.step.log', 'stamp'),
            'bank': ('pb.employee.bank.history', 'changed_at'),
            'export': ('bank.export.log', 'export_date'),
            'delivery': ('pb.payslip.delivery', 'create_date'),
            'login': ('res.users.log', 'create_date'),
        }[key]

    # ================================================================ retention
    @api.model
    def _retention_days(self):
        return self.env['biz.audit.entry']._retention_days()

    @api.model
    def set_retention(self, days):
        """Manager-gated write of the audit-trail retention param — the ONLY
        config write this console performs (safety rail 1). A non-manager raises
        (test 10)."""
        self._require_manager()
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 0
        if days <= 0:
            # bad input, not a permissions failure (review J-6)
            raise UserError(_("Retention must be a positive number of days."))
        self.env['ir.config_parameter'].sudo().set_param(
            _RETENTION_PARAM, str(days))
        return {'retention_days': days}

    # ================================================================== export
    @api.model
    def export_stream(self, filters=None, kind='stream'):
        """Build a filtered XLSX (same filters, same masking) and return a
        download URL for the transient wizard's Binary. Streams up to the hard
        cap, surfaced in the return (never a silent truncation)."""
        self._require_manager()
        wiz = self.env['pb.audit.export'].create({})
        return wiz.build(filters or {}, kind or 'stream')

    # ================================================================== utils
    def _get_float_param(self, param, default):
        raw = self.env['ir.config_parameter'].sudo().get_param(param, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(raw):
        if raw in (None, '', False):
            return None
        try:
            return float(str(raw).replace(',', '').strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fmt_money(v):
        if v is None:
            return ''
        return '{:,.0f}'.format(v)

    @staticmethod
    def _month_series(month_counts, months):
        """Return an ordered [{month, count}] for the last N calendar months.
        Uses the newest key present as the anchor to avoid Date.now in tests."""
        if not month_counts:
            return []
        keys = sorted(month_counts)
        # Build a contiguous window ending at the latest month seen.
        latest = keys[-1]
        y, m = int(latest[:4]), int(latest[5:7])
        series = []
        for _i in range(months - 1, -1, -1):
            mm = m - _i
            yy = y
            while mm <= 0:
                mm += 12
                yy -= 1
            k = '%04d-%02d' % (yy, mm)
            series.append({'month': k, 'count': month_counts.get(k, 0)})
        return series
