# -*- coding: utf-8 -*-
"""ORG CHART P1 — the read-only payload behind People › Org chart.

One RPC (`get_chart`) returns every active employee of the allowed companies
in ONE call, with their manager, team, location, status and team sizes; the
client lays the tree out itself (ledger D4). Above `LIMIT` people the payload
is cut to the top levels and `get_branch(manager_id)` loads a team when its
"+N" is pressed.

Rules this file keeps (ORGCHART_LEDGER §0):
* A read RPC never writes, and employees are read as the signed-in user (no
  `sudo()` — the hub's gate already grants read).
* Never block the page on one bad record: each person is built inside its
  own try/except and logged at DEBUG.
* No N+1: one light `search_read` for the whole tree shape, one full
  `search_read` for the rows returned, one for jobs, one for departments.
* Fields a user may not read (`employee_type`, `departure_date`,
  `first_contract_date` are HR-officer only) are never requested for them —
  asking for one would refuse the whole read.
"""
import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: Days a joiner counts as "new" and a departure counts as "leaving".
NEW_DAYS = 30
LEAVING_DAYS = 30
#: A manager with this many direct reports or more runs a "wide" team.
WIDE_SPAN = 10


def _initials(name):
    """Same rule as pb_people._initials: first letter of the first and last word."""
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


def _m2o_id(v):
    return v[0] if v else False


def _m2o_name(v):
    return v[1] if v else ''


class PbOrgChart(models.AbstractModel):
    _name = 'pb.orgchart'
    _description = 'Payobook org chart data'

    LIMIT = 1500
    PALETTE = ['#5A4BB0', '#0F7B4F', '#2563EB', '#B45309', '#0F7C6B',
               '#DC2655', '#7C3AED', '#64748B', '#0E7490', '#9D174D']

    # ------------------------------------------------------------ helpers
    @api.model
    def _readable(self, model, fname):
        """True when the signed-in user may read `model.fname`."""
        field = model._fields.get(fname)
        if not field:
            return False
        if not field.groups:
            return True
        try:
            return self.env.user.has_groups(field.groups)
        except Exception:  # noqa: BLE001 — an odd groups spec is a "no"
            return False

    @api.model
    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _limit(self):
        try:
            return int(self.env.context.get('pb_orgchart_limit') or self.LIMIT)
        except (TypeError, ValueError):
            return self.LIMIT

    @api.model
    def _may_write(self):
        user = self.env.user
        return bool(user.has_group('hr.group_hr_user') or user.has_group('base.group_system'))

    # -------------------------------------------------------- tree shape
    @api.model
    def _graph(self):
        """The whole tree's shape from one light read.

        Returns ``{ids, mgr, kids, depth, total, roots}``: `mgr` maps a person
        to a manager who is ALSO active in the allowed companies (an archived
        or out-of-company manager makes the person a root, ledger §4 rail);
        `depth` 0 = top; `total` = everyone under a person, any depth. A loop
        in `parent_id` (the constraint should forbid it, but a raw import can
        write one) is broken by making the unreachable people roots.
        """
        Emp = self.env['hr.employee']
        # WHO is in the chart is the ORM's answer (access rules, multi-company,
        # archived); only the parent column of those ids is read in SQL. A
        # `search_read(['parent_id'])` of 4,500 people spends 450 ms naming
        # managers the shape never shows (G11).
        ids = Emp.search([('company_id', 'in', self._company_ids())], order='id').ids
        idset = set(ids)
        Emp.flush_model(['parent_id'])
        parent = {}
        if ids:
            self.env.cr.execute("SELECT id, parent_id FROM hr_employee WHERE id = ANY(%s)", [ids])
            parent = dict(self.env.cr.fetchall())
        mgr = {}
        for i in ids:
            m = parent.get(i)
            mgr[i] = m if (m and m in idset and m != i) else False
        kids = {}
        for i in ids:
            m = mgr[i]
            if m:
                kids.setdefault(m, []).append(i)
        depth = {}
        roots = [i for i in ids if not mgr[i]]
        frontier = list(roots)
        for i in frontier:
            depth[i] = 0
        while frontier:
            nxt = []
            for i in frontier:
                for k in kids.get(i, ()):
                    if k not in depth:
                        depth[k] = depth[i] + 1
                        nxt.append(k)
            frontier = nxt
        # Anyone not reached sits on a loop: cut it and make them roots.
        for i in ids:
            if i not in depth:
                old = mgr[i]
                if old and old in kids:
                    kids[old] = [k for k in kids[old] if k != i]
                mgr[i] = False
                roots.append(i)
                depth[i] = 0
                stack = [i]
                while stack:
                    c = stack.pop()
                    for k in kids.get(c, ()):
                        if k not in depth:
                            depth[k] = depth[c] + 1
                            stack.append(k)
        # Everyone under a person (post-order over depth, deepest first).
        total = dict.fromkeys(ids, 0)
        for i in sorted(ids, key=lambda x: -depth[x]):
            m = mgr[i]
            if m:
                total[m] += 1 + total[i]
        return {'ids': ids, 'mgr': mgr, 'kids': kids, 'depth': depth,
                'total': total, 'roots': roots}

    @api.model
    def _team_count(self, ids, rows):
        """Distinct teams across everyone (the subline), from the current versions."""
        try:
            self.env['hr.employee'].flush_model(['current_version_id'])
            self.env['hr.version'].flush_model(['department_id'])
            self.env.cr.execute("""
                SELECT count(DISTINCT v.department_id)
                  FROM hr_employee e JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.id = ANY(%s)""", [list(ids)])
            return self.env.cr.fetchone()[0] or 0
        except Exception as e:  # noqa: BLE001 — fall back to what was sent
            _logger.debug("pb_orgchart: team count failed: %s", e)
            return len({r['dept_id'] for r in rows if r['dept_id']})

    # ---------------------------------------------------- reference data
    @api.model
    def _departments(self):
        """All departments of the allowed companies, coloured by id order.

        The colour is the department's place in id order modulo the palette,
        so it never changes between loads and the first ten are distinct.
        """
        Dept = self.env['hr.department']
        dom = [('company_id', 'in', self._company_ids() + [False])]
        flds = ['name', 'manager_id']
        try:
            rows = Dept.search_read(dom, flds, order='id')
        except AccessError:
            rows = Dept.sudo().search_read(dom, flds, order='id')
            _logger.debug("pb_orgchart: departments read with sudo (no read access)")
        out = {}
        for n, d in enumerate(rows):
            out[d['id']] = {'id': d['id'], 'name': d['name'] or '',
                            'color': self.PALETTE[n % len(self.PALETTE)],
                            'manager_id': _m2o_id(d['manager_id'])}
        return out

    @api.model
    def _job_manager(self, job, depts, active):
        """Who an open role hangs under on the chart (ledger D3).

        P2 adds the job's own `pb_manager_id` as the FIRST branch here; P1
        has only the fallback: the job's department's manager. A manager who
        is not an active person of the allowed companies is no manager.
        """
        dept = depts.get(_m2o_id(job.get('department_id')))
        m = dept and dept.get('manager_id')
        return m if (m and m in active) else False

    @api.model
    def _open_roles(self, depts, active):
        Job = self.env['hr.job']
        dom = [('no_of_recruitment', '>', 0),
               ('company_id', 'in', self._company_ids() + [False])]
        flds = ['name', 'department_id', 'no_of_recruitment', 'company_id']
        if 'address_id' in Job._fields:
            flds.append('address_id')
        try:
            jobs = Job.search_read(dom, flds, order='id')
        except AccessError:
            jobs = Job.sudo().search_read(dom, flds, order='id')
            _logger.debug("pb_orgchart: open roles read with sudo (no hr.job read access)")
        cities = {}
        addr_ids = list({_m2o_id(j.get('address_id')) for j in jobs if j.get('address_id')})
        if addr_ids:
            try:
                for p in self.env['res.partner'].sudo().browse(addr_ids).read(['city']):
                    cities[p['id']] = p['city'] or ''
            except Exception as e:  # noqa: BLE001
                _logger.debug("pb_orgchart: job address cities unreadable: %s", e)
        out = []
        for j in jobs:
            try:
                n = int(j['no_of_recruitment'] or 0)
                dept_id = _m2o_id(j['department_id'])
                out.append({
                    'id': 'job-%s' % j['id'], 'job_id': j['id'],
                    'title': j['name'] or '',
                    'dept_id': dept_id, 'dept': _m2o_name(j['department_id']),
                    'loc': cities.get(_m2o_id(j.get('address_id'))) or _m2o_name(j['company_id']),
                    'count': n,
                    'manager_id': self._job_manager(j, depts, active),
                    'hiring': _("Open · %(n)s to fill", n=n),
                })
            except Exception as e:  # noqa: BLE001 — one bad job never blocks the chart
                _logger.debug("pb_orgchart: open role %s skipped: %s", j.get('id'), e)
        return out

    # ------------------------------------------------------------- rows
    @api.model
    def _type_key(self, code, contract_type):
        """Employment type as a stable key (colour-by reads the key)."""
        if contract_type and 'part' in contract_type.lower():
            return 'parttime'
        if code in ('contractor', 'freelance'):
            return 'contractor'
        if code in ('student', 'trainee'):
            return 'trainee'
        return 'fulltime'

    @api.model
    def _type_label(self, code, contract_type):
        """Employment type in plain words (P1 §1.3)."""
        return {
            'parttime': _("Part-time"),
            'contractor': _("Contractor"),
            'trainee': _("Trainee"),
        }.get(self._type_key(code, contract_type)) or _("Full-time")

    @api.model
    def _names(self, model, id_set):
        """{id: display name} for a handful of many2one targets, one read."""
        id_set = [i for i in id_set if i]
        if not id_set:
            return {}
        M = self.env[model]
        try:
            rows = M.browse(id_set).read(['display_name'])
        except AccessError:
            rows = M.sudo().browse(id_set).read(['display_name'])
        return {r['id']: r['display_name'] for r in rows}

    @api.model
    def _employee_data(self, ids, depts):
        """Each person's fields, keyed by id, in `search_read` shape.

        The team, title and location live on the person's VERSION (Odoo 19
        `_inherits`). Read through the employee they cost ~1.5 ms a person
        (945 ms for 657 on payobook); read from the stored current version in
        one batch they cost a third of that. Both reads are as the user: when
        the user may not read versions directly, the slow path answers.
        """
        Emp = self.env['hr.employee']
        Ver = self.env['hr.version'] if 'hr.version' in self.env else None
        vfields = ['job_title', 'job_id', 'department_id', 'work_location_id', 'address_id']
        for f in ('employee_type', 'departure_date', 'contract_type_id'):
            if self._readable(Emp, f) and (Ver is None or self._readable(Ver, f)):
                vfields.append(f)
        efields = ['name', 'company_id', 'user_id', 'create_date']
        if self._readable(Emp, 'first_contract_date'):
            efields.append('first_contract_date')
        try:
            if Ver is None or 'current_version_id' not in Emp._fields:
                raise AccessError('no versions')
            emps = Emp.search_read([('id', 'in', ids)], efields + ['current_version_id'], load=None)
            vids = [e['current_version_id'] for e in emps if e['current_version_id']]
            vers = {v['id']: v for v in Ver.browse(vids).read(vfields, load=None)}
        except AccessError:
            return {r['id']: r for r in Emp.search_read([('id', 'in', ids)], efields + vfields)}
        m2o = {'job_id': 'hr.job', 'work_location_id': 'hr.work.location',
               'contract_type_id': 'hr.contract.type'}
        names = {f: self._names(model, {v.get(f) for v in vers.values()})
                 for f, model in m2o.items() if f in vfields}
        companies = self._names('res.company', {e['company_id'] for e in emps})
        out = {}
        for e in emps:
            v = vers.get(e['current_version_id']) or {}
            r = dict(e)
            r['company_id'] = (e['company_id'], companies.get(e['company_id'], '')) if e['company_id'] else False
            r['user_id'] = (e['user_id'], '') if e['user_id'] else False
            for f in vfields:
                val = v.get(f, False)
                if f in names:
                    val = (val, names[f].get(val, '')) if val else False
                elif f == 'department_id':
                    val = (val, (depts.get(val) or {}).get('name', '')) if val else False
                elif f == 'address_id':
                    val = (val, '') if val else False
                r[f] = val
            out[e['id']] = r
        return out

    @api.model
    def _photo_ids(self, ids):
        """Employees with a REAL photo.

        Every employee gets an image on file the moment they are created: the
        system draws a letter on a coloured square and stores it as an SVG
        (hr.employee create, `_avatar_generate_svg`). Showing that would hide
        the chart's own colours (team, location, ...) on every card, so only
        a raster image counts as a photo. One read of the image attachments'
        types — `sudo()` because field attachments are not searchable as the
        user; it returns ids the caller has already read, nothing else.
        """
        try:
            rows = self.env['ir.attachment'].sudo().search_read([
                ('res_model', '=', 'hr.employee'), ('res_field', '=', 'image_1920'),
                ('res_id', 'in', list(ids))], ['res_id', 'mimetype'])
        except Exception as e:  # noqa: BLE001 — no photos is a fine answer
            _logger.debug("pb_orgchart: photo lookup failed: %s", e)
            return set()
        return {r['res_id'] for r in rows
                if r['mimetype'] and r['mimetype'].startswith('image/')
                and 'svg' not in r['mimetype']}

    @api.model
    def _rows(self, ids, graph, depts):
        """Full rows for these employee ids, in the order given."""
        if not ids:
            return []
        Emp = self.env['hr.employee']
        recs = self._employee_data(ids, depts)
        want = next(iter(recs.values()), {}).keys() if recs else ()
        photos = self._photo_ids(ids)

        today = fields.Date.context_today(self)
        # Who is away today (hr_holidays): one search, never a per-row compute.
        absent = set()
        if 'is_absent' in Emp._fields:
            try:
                absent = set(Emp.search([('id', 'in', ids), ('is_absent', '=', True)]).ids)
            except Exception as e:  # noqa: BLE001
                _logger.debug("pb_orgchart: absent search failed: %s", e)
        # Best-known join date where first_contract_date is not readable:
        # earliest contract start, one grouped read (pb_people._join_date rule).
        starts = {}
        if 'first_contract_date' not in want and 'hr.contract' in self.env:
            try:
                for g in self.env['hr.contract']._read_group(
                        [('employee_id', 'in', ids)], ['employee_id'], ['date_start:min']):
                    starts[g[0].id] = g[1]
            except Exception as e:  # noqa: BLE001
                _logger.debug("pb_orgchart: contract starts unreadable: %s", e)
        cities = {}
        addr_ids = list({_m2o_id(r['address_id']) for r in recs.values() if r.get('address_id')})
        if addr_ids:
            try:
                for p in self.env['res.partner'].sudo().browse(addr_ids).read(['city']):
                    cities[p['id']] = p['city'] or ''
            except Exception as e:  # noqa: BLE001
                _logger.debug("pb_orgchart: address cities unreadable: %s", e)

        out = []
        for i in ids:
            r = recs.get(i)
            if not r:
                continue
            try:
                joined = r.get('first_contract_date') or starts.get(i) or (
                    r['create_date'].date() if r.get('create_date') else False)
                status, note = '', ''
                dep = r.get('departure_date')
                if dep and today <= dep <= today + timedelta(days=LEAVING_DAYS):
                    status = 'leaving'
                    note = _("Last day %(date)s",
                             date=format_date(self.env, dep, date_format='d MMM'))
                elif i in absent:
                    status, note = 'leave', _("On leave today")
                elif joined and today - timedelta(days=NEW_DAYS) <= joined <= today:
                    status = 'new'
                dept_id = _m2o_id(r['department_id'])
                loc = (_m2o_name(r['work_location_id'])
                       or cities.get(_m2o_id(r['address_id']))
                       or _m2o_name(r['company_id']))
                out.append({
                    'id': i,
                    'name': r['name'] or '',
                    'ini': _initials(r['name']),
                    'title': r.get('job_title') or _m2o_name(r.get('job_id')) or '',
                    'dept_id': dept_id,
                    'dept': (depts.get(dept_id) or {}).get('name') or _m2o_name(r['department_id']),
                    'loc': loc or '',
                    'type': self._type_label(r.get('employee_type'),
                                             _m2o_name(r.get('contract_type_id'))),
                    'type_key': self._type_key(r.get('employee_type'),
                                               _m2o_name(r.get('contract_type_id'))),
                    'joined': fields.Date.to_string(joined) if joined else False,
                    'manager_id': graph['mgr'].get(i) or False,
                    'dotted_id': False,  # P2 fills this (ledger D2)
                    'status': status,
                    'status_note': note,
                    'user_id': _m2o_id(r['user_id']),
                    'avatar': ('/web/image/hr.employee/%s/avatar_128' % i)
                    if i in photos else False,
                    'n_reports': len(graph['kids'].get(i, ())),
                    'n_total': graph['total'].get(i, 0),
                    'depth': graph['depth'].get(i, 0),
                })
            except Exception as e:  # noqa: BLE001 — never block the page on one bad record
                _logger.debug("pb_orgchart: person %s skipped: %s", i, e)
        return out

    # --------------------------------------------------------------- API
    @api.model
    def get_chart(self):
        """Everything the chart draws, in one call (ledger D4)."""
        t0 = time.time()
        graph = self._graph()
        ids = graph['ids']
        active = set(ids)
        depts = self._departments()
        limit = self._limit()

        me_emp = self.env.user.employee_id
        me = me_emp.id if (me_emp and me_emp.id in active) else False

        keep = ids
        truncated = False
        shown_levels = 0
        if len(ids) > limit:
            # The top three levels — fewer when three still exceed the limit,
            # so the payload really is bounded (a flat company of 4,500 has
            # everybody within three levels).
            truncated = True
            d = 2
            while d > 0 and sum(1 for i in ids if graph['depth'][i] <= d) > limit:
                d -= 1
            shown_levels = d + 1
            keep_set = {i for i in ids if graph['depth'][i] <= d}
            # Find me must work: my chain to the top always comes along.
            c = me
            while c:
                keep_set.add(c)
                c = graph['mgr'].get(c)
            keep = [i for i in ids if i in keep_set]
            if len(keep) > limit:
                # Even the top level is too many: the biggest teams first.
                keep = sorted(keep, key=lambda x: -graph['total'][x])[:limit]
                if me and me not in keep:
                    keep.append(me)
        rows = self._rows(keep, graph, depts)
        loaded = {r['id'] for r in rows}
        all_roles = self._open_roles(depts, active)
        roles = [o for o in all_roles
                 if not o['manager_id'] or o['manager_id'] in loaded]

        # Numbers over the WHOLE company, whatever was cut.
        managers = [i for i in ids if graph['kids'].get(i)]
        lone_roots = [i for i in graph['roots'] if not graph['kids'].get(i)]
        has_tree = any(graph['kids'].get(i) for i in graph['roots'])
        if not has_tree and len(ids) == 1:
            lone_roots = []  # a one-person company: that person IS the chart
        new = sum(1 for r in rows if r['status'] == 'new') if not truncated else \
            self._count_new(ids)
        used_depts = {r['dept_id'] for r in rows if r['dept_id']} | \
            {o['dept_id'] for o in roles if o['dept_id']}
        payload = {
            'people': rows,
            'open_roles': roles,
            'departments': [{'id': d['id'], 'name': d['name'], 'color': d['color']}
                            for d in depts.values() if d['id'] in used_depts],
            'locations': sorted({r['loc'] for r in rows if r['loc']}),
            'types': sorted({r['type'] for r in rows if r['type']}),
            'me': me,
            'may_write': self._may_write(),
            'truncated': truncated,
            'shown_levels': shown_levels,
            'counts': {
                'people': len(ids),
                'open': len(all_roles),
                'no_manager': len(lone_roots),
                'levels': (max(graph['depth'].values()) + 1) if ids else 0,
                'managers': len(managers),
                'avg_span': round(sum(len(graph['kids'][m]) for m in managers) / len(managers), 1)
                if managers else 0,
                'wide': sum(1 for m in managers if len(graph['kids'][m]) >= WIDE_SPAN),
                'dotted': 0,  # P2 (ledger D2)
                'new': new,
                'teams': self._team_count(ids, rows),
            },
        }
        ms = int((time.time() - t0) * 1000)
        payload['build_ms'] = ms
        _logger.debug("pb_orgchart: payload of %s people (%s sent) built in %s ms",
                      len(ids), len(rows), ms)
        return payload

    @api.model
    def _count_new(self, ids):
        """New joiners across everyone (the truncated case only)."""
        Emp = self.env['hr.employee']
        if not self._readable(Emp, 'first_contract_date'):
            return 0
        today = fields.Date.context_today(self)
        return Emp.search_count([
            ('id', 'in', ids),
            ('first_contract_date', '>=', today - timedelta(days=NEW_DAYS)),
            ('first_contract_date', '<=', today)])

    @api.model
    def get_branch(self, manager_id):
        """Everyone under this manager, any depth — same row shape.

        Used when a "+N" is pressed on a chart that was cut to its top levels.
        Bounded by the same limit (nearest people first); `truncated` says so.
        """
        try:
            manager_id = int(manager_id)
        except (TypeError, ValueError):
            return {'people': [], 'open_roles': [], 'truncated': False}
        graph = self._graph()
        if manager_id not in graph['depth']:
            return {'people': [], 'open_roles': [], 'truncated': False}
        limit = self._limit()
        under, frontier = [], [manager_id]
        while frontier and len(under) < limit:
            nxt = []
            for i in frontier:
                for k in graph['kids'].get(i, ()):
                    under.append(k)
                    nxt.append(k)
            frontier = nxt
        truncated = len(under) > limit
        under = under[:limit]
        depts = self._departments()
        rows = self._rows(under, graph, depts)
        branch = set(under) | {manager_id}
        roles = [o for o in self._open_roles(depts, set(graph['ids']))
                 if o['manager_id'] and o['manager_id'] in branch]
        return {'people': rows, 'open_roles': roles, 'truncated': truncated}
