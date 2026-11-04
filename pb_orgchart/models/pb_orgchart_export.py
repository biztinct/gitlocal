# -*- coding: utf-8 -*-
"""ORG CHART P4 — the reads behind the Export menu and the move sheet.

* ``export_rows`` — the spreadsheet of EVERYONE the user may read, not only
  what a cut chart has loaded (P1 deviation 11). Same search as the chart
  (`_graph`, access rules apply, no `sudo()` for employees), same row builder
  (`_rows`), same projection when a plan or another day is on screen.
* ``approvers_of`` — who approves a person's leave and expenses today, so the
  move sheet can say by name that they stay (owner ruling 3).

Both are reads: nothing is written.
"""
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class PbOrgChartExport(models.AbstractModel):
    _inherit = 'pb.orgchart'

    @api.model
    def export_rows(self, plan_id=None, as_of=None):
        """Every person (and open role) as spreadsheet rows, tree order.

        Returns ``{columns, rows, people, roles}``; in a plan ``plan_name`` and
        an extra "In the plan" column; on another day ``as_of``. A refused
        plan answers ``{'error': sentence}`` like `get_chart`."""
        view, extra = self._view_for(plan_id, as_of)
        if extra.get('error'):
            return {'error': extra['error']}
        graph = self._graph(view)
        ids = graph['ids']
        depts = self._departments()
        rows = {r['id']: r for r in self._rows(ids, graph, depts, view)}
        roles = self._open_roles(depts, set(ids), view)

        # tree order: the biggest teams first, each depth first, then the
        # people with no manager and no team
        kids = graph['kids']
        tops = sorted([i for i in graph['roots'] if kids.get(i)],
                      key=lambda i: (-graph['total'].get(i, 0), i))
        lone = [i for i in graph['roots'] if not kids.get(i)]
        order, seen = [], set()
        for top in tops + lone:
            stack = [top]
            while stack:
                i = stack.pop()
                if i in seen:
                    continue
                seen.add(i)
                order.append(i)
                stack.extend(reversed(kids.get(i, ())))
        order += [i for i in ids if i not in seen]

        in_plan = bool(plan_id) and bool(extra.get('plan'))
        changed = set((view or {}).get('changed') or ()) if in_plan else set()
        columns = [_("Name"), _("Title"), _("Team"), _("Reports to"), _("Also reports to"),
                   _("Location"), _("Employment"), _("Joined")]
        if in_plan:
            columns.append(_("In the plan"))
        changed_word = _("Changed")
        role_word = _("Open role")
        out = []
        for i in order:
            r = rows.get(i)
            if not r:
                continue
            m = rows.get(r['manager_id']) if r['manager_id'] else None
            dm = rows.get(r['dotted_id']) if r['dotted_id'] else None
            line = [r['name'], r['title'], r['dept'], m['name'] if m else '',
                    dm['name'] if dm else '', r['loc'], r['type'], r['joined'] or '']
            if in_plan:
                line.append(changed_word if i in changed else '')
            out.append(line)
        n_people = len(out)
        for o in roles:
            m = rows.get(o['manager_id']) if o['manager_id'] else None
            title = o['title'] if (o.get('count') or 1) == 1 else '%s × %s' % (o['title'], o['count'])
            line = [role_word, title, o['dept'], m['name'] if m else '', '', o['loc'], '', '']
            if in_plan:
                line.append(changed_word if o.get('changed') else '')
            out.append(line)
        res = {'columns': columns, 'rows': out, 'people': n_people, 'roles': len(roles)}
        if in_plan:
            res['plan_name'] = extra['plan'].get('name') or ''
        if as_of and not plan_id:
            res['as_of'] = as_of
        return res

    @api.model
    def approvers_of(self, emp_id):
        """``{'leave': name, 'expense': name}`` — who approves this person's
        time off and expenses today. A field the user may not read (or a
        module that is not installed) is simply left out."""
        try:
            emp = self.env['hr.employee'].browse(int(emp_id)).exists()
        except (TypeError, ValueError):
            return {}
        if not emp:
            return {}
        out = {}
        Emp = self.env['hr.employee']
        for key, fname in (('leave', 'leave_manager_id'), ('expense', 'expense_manager_id')):
            if not self._readable(Emp, fname):
                continue
            try:
                user = emp[fname]
                out[key] = (user.name or '') if user else ''
            except Exception as e:  # noqa: BLE001 — a refused read is "unknown", not an error
                _logger.debug("pb_orgchart: %s of %s unreadable: %s", fname, emp.id, e)
        return out

    @api.model
    def chain_of(self, emp_id):
        """The managers above a person, top first — so a shared link can open
        the teams down to them on a cut chart. Only people this user's chart
        holds; anyone else answers an empty list."""
        try:
            i = int(emp_id)
        except (TypeError, ValueError):
            return []
        graph = self._graph()
        if i not in graph['depth']:
            return []
        chain, m, seen = [], graph['mgr'].get(i), {i}
        while m and m not in seen:
            seen.add(m)
            chain.append(m)
            m = graph['mgr'].get(m)
        return list(reversed(chain))
