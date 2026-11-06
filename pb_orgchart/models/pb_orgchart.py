# -*- coding: utf-8 -*-
"""ORG CHART P1/P2 — the payload behind People › Org chart.

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
    def _graph(self, view=None):
        """The whole tree's shape from one light read.

        Returns ``{ids, mgr, kids, depth, total, roots, dotted}``: `mgr` maps a person
        to a manager who is ALSO active in the allowed companies (an archived
        or out-of-company manager makes the person a root, ledger §4 rail);
        `depth` 0 = top; `total` = everyone under a person, any depth. A loop
        in `parent_id` (the constraint should forbid it, but a raw import can
        write one) is broken by making the unreachable people roots.

        `view` (P3) draws another day or a plan instead of today:
        ``parents`` / ``dotted`` replace the columns for the people they name,
        ``hide`` takes people off the chart — and a manager who is hidden is
        skipped up the chain, so nobody hangs from someone who was not there
        (the POC's `effMgr` rule).
        """
        Emp = self.env['hr.employee']
        # WHO is in the chart is the ORM's answer (access rules, multi-company,
        # archived); only the parent column of those ids is read in SQL. A
        # `search_read(['parent_id'])` of 4,500 people spends 450 ms naming
        # managers the shape never shows (G11).
        ids = Emp.search([('company_id', 'in', self._company_ids())], order='id').ids
        Emp.flush_model(['parent_id', 'pb_dotted_manager_id'])
        parent = {}
        dot_raw = {}
        if ids:
            self.env.cr.execute(
                "SELECT id, parent_id, pb_dotted_manager_id FROM hr_employee WHERE id = ANY(%s)", [ids])
            for i, p, dm in self.env.cr.fetchall():
                parent[i] = p
                if dm:
                    dot_raw[i] = dm
        if view:
            over = view.get('parents')
            if over:
                for i in ids:
                    if i in over:
                        parent[i] = over[i] or None
            if view.get('dotted') is not None:
                dots = view['dotted']
                dot_raw = {i: dots[i] for i in ids if dots.get(i)}
            hide = view.get('hide')
            if hide:
                ids = [i for i in ids if i not in hide]
                for i in ids:
                    m, seen = parent.get(i), set()
                    while m and m in hide and m not in seen:
                        seen.add(m)
                        m = parent.get(m) if m in parent else (over or {}).get(m)
                    parent[i] = m
        idset = set(ids)
        # the dotted line (ledger D2) counts only between two people on the chart
        dotted = {i: dm for i, dm in dot_raw.items() if dm in idset and dm != i}
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
                'total': total, 'roots': roots, 'dotted': dotted}

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

        The job's own `pb_manager_id` first (P2), else its department's
        manager. A manager who is not an active person of the allowed
        companies is no manager (the role waits in the lane).
        """
        own = _m2o_id(job.get('pb_manager_id'))
        if own and own in active:
            return own
        dept = depts.get(_m2o_id(job.get('department_id')))
        m = dept and dept.get('manager_id')
        return m if (m and m in active) else False

    @api.model
    def _open_roles(self, depts, active, view=None):
        """Open roles, as today — or as a plan or a later day leaves them
        (`view['roles']` overrides a role's count and manager; `virtual` are
        roles a plan adds). A past day shows none: they are today's
        vacancies."""
        if view and view.get('no_roles'):
            return []
        out = self._open_roles_live(depts, active)
        if not view or not (view.get('roles') or view.get('virtual')):
            return out
        over = view.get('roles') or {}
        kept = []
        for o in out:
            r = over.get(o['job_id'])
            if r is not None:
                if r['count'] <= 0:
                    continue
                m = r['mgr'] if (r['mgr'] and r['mgr'] in active) else False
                if r['count'] != o['count'] or m != o['manager_id']:
                    o = dict(o, count=r['count'], manager_id=m, changed=True,
                             hiring=_("Open · %(n)s to fill", n=r['count']))
            kept.append(o)
        reasons = dict(self.env['hr.job']._fields['pb_reason']._description_selection(self.env))
        for v in view.get('virtual') or ():
            dept_id = v.get('dept_id') or False
            kept.append({
                'id': v['id'], 'job_id': False, 'virtual': True, 'changed': True,
                'title': v['title'], 'dept_id': dept_id,
                'dept': (depts.get(dept_id) or {}).get('name', ''),
                'loc': '', 'count': 1,
                'manager_id': v['mgr'] if (v['mgr'] and v['mgr'] in active) else False,
                'hiring': _("New in this plan"),
                'reason': v.get('reason') or False,
                'reason_label': reasons.get(v.get('reason')) or '',
            })
        return kept

    @api.model
    def _open_roles_live(self, depts, active):
        Job = self.env['hr.job']
        dom = [('no_of_recruitment', '>', 0),
               ('company_id', 'in', self._company_ids() + [False])]
        flds = ['name', 'department_id', 'no_of_recruitment', 'company_id',
                'pb_manager_id', 'pb_reason']
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
        reasons = dict(Job._fields['pb_reason']._description_selection(self.env))
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
                    'reason': j.get('pb_reason') or False,
                    'reason_label': reasons.get(j.get('pb_reason')) or '',
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
            try:
                vers = {v['id']: v for v in Ver.browse(vids).read(vfields, load=None)}
            except AccessError:
                # G29 (P4): a roster reader who is not an HR officer (a Records
                # viewer) may read the people but not their versions, and the
                # employee's own title/team fields are related through the
                # HR-only `version_id`, so both reads refused and the chart
                # did not open for them at all. The title, team and location
                # are what the roster already shows them: read those columns
                # of the versions of the people THEY could read (`emps` came
                # from their own search). The HR-only columns were left out
                # by `_readable` above.
                vers = {v['id']: v for v in Ver.sudo().browse(vids).read(vfields, load=None)}
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
    def _rows(self, ids, graph, depts, view=None):
        """Full rows for these employee ids, in the order given.

        With a `view` (P3) the statuses are worked out for the day shown
        (`ref_day`), a plan's new titles replace today's, and the people a
        plan changes carry `changed`."""
        if not ids:
            return []
        Emp = self.env['hr.employee']
        recs = self._employee_data(ids, depts)
        want = next(iter(recs.values()), {}).keys() if recs else ()
        photos = self._photo_ids(ids)

        real_today = fields.Date.context_today(self)
        today = (view or {}).get('ref_day') or real_today
        titles = (view or {}).get('titles') or {}
        changed = (view or {}).get('changed') or ()
        # Who is away today (hr_holidays): one search, never a per-row compute.
        absent = set()
        if 'is_absent' in Emp._fields and today == real_today:
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
                    'title': titles.get(i) or r.get('job_title') or _m2o_name(r.get('job_id')) or '',
                    'changed': i in changed,
                    'dept_id': dept_id,
                    'dept': (depts.get(dept_id) or {}).get('name') or _m2o_name(r['department_id']),
                    'loc': loc or '',
                    'type': self._type_label(r.get('employee_type'),
                                             _m2o_name(r.get('contract_type_id'))),
                    'type_key': self._type_key(r.get('employee_type'),
                                               _m2o_name(r.get('contract_type_id'))),
                    'joined': fields.Date.to_string(joined) if joined else False,
                    'manager_id': graph['mgr'].get(i) or False,
                    'dotted_id': graph['dotted'].get(i) or False,
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
    def get_chart(self, plan_id=None, as_of=None, expand=None):
        """Everything the chart draws, in one call (ledger D4).

        P3: ``plan_id`` draws that plan's projection over the live chart
        (with `changed_ids`, `ghost_edges`, virtual roles and the plan);
        ``as_of`` ('YYYY-MM-DD') draws another day — the past from field
        tracking, the future from approved plans, leavers and accepted
        offers. ``expand`` lists managers whose teams were opened on a cut
        chart, so a redraw keeps them. A read: nothing is written."""
        t0 = time.time()
        view, extra = self._view_for(plan_id, as_of)
        if extra.get('error'):
            return {'error': extra['error']}
        graph = self._graph(view)
        ids = graph['ids']
        active = set(ids)
        depts = self._departments()
        limit = self._limit()

        me_emp = self.env.user.employee_id
        me = me_emp.id if (me_emp and me_emp.id in active) else False

        def chain(i, into):
            while i and i not in into:
                into.add(i)
                i = graph['mgr'].get(i)

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
            must = set()
            chain(me, must)
            # A plan's changes are always on screen, with where they came from.
            if view:
                for i in view.get('changed') or ():
                    if i in active:
                        chain(i, must)
                for g in view.get('ghost') or ():
                    chain(g['from_manager_id'], must)
            # Teams opened before a redraw stay open (bounded by the limit).
            for m in expand or ():
                try:
                    m = int(m)
                except (TypeError, ValueError):
                    continue
                if m in active:
                    chain(m, must)
                    must.update(graph['kids'].get(m, ()))
            keep_set |= must
            keep = [i for i in ids if i in keep_set]
            if len(keep) > limit:
                # Even the top level is too many: the biggest teams first.
                keep = sorted(keep, key=lambda x: -graph['total'][x])[:limit]
                keep += [i for i in ids if i in must and i not in set(keep)]
        rows = self._rows(keep, graph, depts, view)
        loaded = {r['id'] for r in rows}
        all_roles = self._open_roles(depts, active, view)
        roles = [o for o in all_roles
                 if not o['manager_id'] or o['manager_id'] in loaded]

        # Numbers over the WHOLE company, whatever was cut.
        new = sum(1 for r in rows if r['status'] == 'new') if (not truncated or view) else \
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
            'counts': dict(self._shape_counts(graph, len(all_roles)),
                           people=len(ids), new=new,
                           teams=self._team_count(ids, rows)),
        }
        if extra:
            payload.update(extra)
            # ghost lines are drawn only between people who are on screen
            if extra.get('ghost_edges'):
                payload['ghost_edges'] = [g for g in extra['ghost_edges']
                                          if g['emp_id'] in loaded and g['from_manager_id'] in loaded]
            if extra.get('changed_ids'):
                payload['changed_ids'] = [i for i in extra['changed_ids'] if i in active]
            if extra.get('starters'):
                payload['starters'] = [dict(s, manager_id=s['manager_id'] if s['manager_id'] in loaded else False)
                                       for s in extra['starters']]
        if payload['may_write'] and not view:
            payload['my_draft'] = self._my_draft_summary()
        ms = int((time.time() - t0) * 1000)
        payload['build_ms'] = ms
        _logger.debug("pb_orgchart: payload of %s people (%s sent) built in %s ms",
                      len(ids), len(rows), ms)
        return payload

    @api.model
    def _shape_counts(self, graph, n_open):
        """The numbers that only depend on who reports to whom (and the open
        roles). A write in P2 can change these and nothing else, so the
        write RPCs send them back with their refresh."""
        ids = graph['ids']
        managers = [i for i in ids if graph['kids'].get(i)]
        lone_roots = [i for i in graph['roots'] if not graph['kids'].get(i)]
        has_tree = any(graph['kids'].get(i) for i in graph['roots'])
        if not has_tree and len(ids) == 1:
            lone_roots = []  # a one-person company: that person IS the chart
        return {
            'open': n_open,
            'no_manager': len(lone_roots),
            'levels': (max(graph['depth'].values()) + 1) if ids else 0,
            'managers': len(managers),
            'avg_span': round(sum(len(graph['kids'][m]) for m in managers) / len(managers), 1)
            if managers else 0,
            'wide': sum(1 for m in managers if len(graph['kids'][m]) >= WIDE_SPAN),
            'dotted': len(graph['dotted']),
        }

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
    def get_branch(self, manager_id, plan_id=None, as_of=None):
        """Everyone under this manager, any depth — same row shape.

        Used when a "+N" is pressed on a chart that was cut to its top levels.
        Bounded by the same limit (nearest people first); `truncated` says so.
        `plan_id` / `as_of` as `get_chart` (P3).
        """
        try:
            manager_id = int(manager_id)
        except (TypeError, ValueError):
            return {'people': [], 'open_roles': [], 'truncated': False}
        view, extra = self._view_for(plan_id, as_of)
        if extra.get('error'):
            return {'people': [], 'open_roles': [], 'truncated': False}
        graph = self._graph(view)
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
        rows = self._rows(under, graph, depts, view)
        branch = set(under) | {manager_id}
        roles = [o for o in self._open_roles(depts, set(graph['ids']), view)
                 if o['manager_id'] and o['manager_id'] in branch]
        return {'people': rows, 'open_roles': roles, 'truncated': truncated}
