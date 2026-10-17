# -*- coding: utf-8 -*-
"""Divisions — the line of business, which does not stop at a company border.

WHY A DIVISION IS NOT A DEPARTMENT
----------------------------------
"Retail" is one business. It has a department in Vietnam, another in Singapore,
and on a bigger group a third in a country nobody has bought yet. Odoo's
department tree cannot say that: `hr.department.parent_id` carries
`check_company=True`, so a department may not have a parent in another company.

So a division is a GROUP-level record and departments ATTACH to it, with dates,
through `pb.division.link` (ruling G2). Two consequences that matter:

  * a department belongs to at most ONE division on any given date, enforced in
    Python with a sentence a person can act on rather than a database error;
  * attaching the TOP of a department tree covers everything under it —
    "Retail" attached once covers Groceries and Bread — because `division_for`
    walks `parent_path` upward and takes the first attachment it meets.

WHY THE HEADCOUNT IS ONE QUERY (WFPLAN WF10 / WF12)
---------------------------------------------------
The roster is 4,500 people on the demo company and the room needs a count per
department. The ORM costs ~800 ms for that; one join costs ~70. The query runs
under `sudo()` AFTER the caller has been gated, and it returns COUNTS ONLY —
never a person, never a wage — because the group screen is not an HR screen and
the people who set a group up do not all hold `hr.group_hr_user`.
"""

import logging
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

#: The card colours a division can wear, by index. EIGHT, and every one of
#: them is a `--pbim-*` token rather than a hex somebody picked: a colour
#: invented here is a second palette, and a board of twenty divisions in twenty
#: shades is a board nobody can read.
COLOUR_COUNT = 8


def fold(text):
    """A name with its accents and its case removed, for comparing only.

    "Ban Kế toán" and "BAN KE TOAN" are the same division to a person, and a
    suggestion list that offers both is a suggestion list nobody trusts.
    """
    raw = unicodedata.normalize('NFKD', (text or '').strip())
    return ''.join(c for c in raw if not unicodedata.combining(c)).lower()


class PbDivision(models.Model):
    _name = 'pb.division'
    _description = 'Division'
    _order = 'sequence, name'

    name = fields.Char(string='Division', required=True)
    code = fields.Char(string='Short code')
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Colour', default=0)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    link_ids = fields.One2many(
        'pb.division.link', 'division_id', string='Departments')
    people_count = fields.Integer(
        string='People', compute='_compute_people_count')
    company_ids = fields.Many2many(
        'res.company', string='Companies', compute='_compute_company_ids')

    _code_uniq = models.Constraint(
        'unique(code)',
        'Another division already uses that short code. Give this one a code '
        'of its own, or leave it empty.')

    # --------------------------------------------------------------- compute
    @api.depends('link_ids.department_id', 'link_ids.active')
    def _compute_company_ids(self):
        for division in self:
            division.company_ids = division.link_ids.filtered(
                'active').mapped('company_id')

    @api.depends('link_ids.department_id', 'link_ids.active')
    def _compute_people_count(self):
        if not self:
            return
        heads = self._heads_by_division(self)
        for division in self:
            division.people_count = heads.get(division.id, 0)

    # ------------------------------------------------------- the attachments
    @api.model
    def _links_on(self, on_date=None, divisions=None):
        """department id -> division id, for the attachments live on a date."""
        day = fields.Date.to_date(on_date) if on_date else \
            fields.Date.context_today(self)
        domain = [('date_from', '<=', day),
                  '|', ('date_to', '=', False), ('date_to', '>=', day)]
        if divisions is not None:
            domain.append(('division_id', 'in', divisions.ids))
        rows = self.env['pb.division.link'].sudo().search_read(
            domain, ['department_id', 'division_id'])
        return {r['department_id'][0]: r['division_id'][0]
                for r in rows if r['department_id'] and r['division_id']}

    @api.model
    def division_for(self, department, on_date=None):
        """The division covering this department, or an empty recordset.

        Walks the department tree UPWARD, so an attachment at the top of a
        branch covers everything under it and nobody has to attach forty
        departments one at a time.
        """
        Department = self.env['hr.department']
        if isinstance(department, models.BaseModel):
            department = department[:1]
        elif department:
            department = Department.sudo().browse(int(department)).exists()
        if not department:
            return self.browse()
        by_department = self._links_on(on_date)
        if not by_department:
            return self.browse()
        # `parent_path` is "1/5/12/" — the chain from the root down to here.
        path = (department.sudo().parent_path or '').strip('/')
        chain = [int(p) for p in path.split('/') if p] if path else [department.id]
        for dept_id in reversed(chain):
            if dept_id in by_department:
                return self.browse(by_department[dept_id]).exists()
        return self.browse()

    # ------------------------------------------------------------ the counts
    @api.model
    def _heads_by_department(self, company_ids):
        """department id -> active people, as ONE query. Counts only.

        The team a person is in comes from their open contract when it names
        one and from their current record otherwise — one code path that
        answers both databases (WFPLAN WF7).
        """
        company_ids = [int(c) for c in (company_ids or []) if c]
        if not company_ids:
            return {}
        cr = self.env.cr
        if 'hr.contract' in self.env:
            cr.execute("""
                WITH open_contract AS (
                    SELECT DISTINCT ON (employee_id)
                           employee_id, department_id
                      FROM hr_contract
                     WHERE company_id = ANY(%s) AND state = 'open'
                     ORDER BY employee_id, wage DESC NULLS LAST, id DESC
                )
                SELECT COALESCE(c.department_id, v.department_id) AS dep,
                       COUNT(*)
                  FROM hr_employee e
             LEFT JOIN hr_version v    ON v.id = e.current_version_id
             LEFT JOIN open_contract c ON c.employee_id = e.id
                 WHERE e.company_id = ANY(%s) AND e.active
              GROUP BY 1
            """, (company_ids, company_ids))
        else:
            cr.execute("""
                SELECT v.department_id, COUNT(*)
                  FROM hr_employee e
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE e.company_id = ANY(%s) AND e.active
              GROUP BY 1
            """, (company_ids,))
        return {row[0] or 0: row[1] for row in cr.fetchall()}

    @api.model
    def _department_chains(self, company_ids):
        """department id -> the chain of ids from the root down to it."""
        rows = self.env['hr.department'].sudo().with_context(
            active_test=False).search_read(
            [('company_id', 'in', [int(c) for c in (company_ids or []) if c])],
            ['id', 'parent_path'])
        out = {}
        for row in rows:
            path = (row['parent_path'] or '').strip('/')
            out[row['id']] = ([int(p) for p in path.split('/') if p]
                              if path else [row['id']])
        return out

    @api.model
    def _heads_by_division(self, divisions=None, on_date=None):
        """division id -> people, rolled up the department tree."""
        by_department = self._links_on(on_date, divisions)
        if not by_department:
            return {}
        Division = self.env['pb.division'].sudo()
        used = Division.browse(sorted(set(by_department.values()))).exists()
        company_ids = self.env['pb.division.link'].sudo().search(
            [('division_id', 'in', used.ids)]).mapped('company_id').ids
        # A division's people are counted across every company its
        # departments live in, which is the whole point of a division.
        heads = self._heads_by_department(set(company_ids))
        chains = self._department_chains(set(company_ids))
        out = {}
        for dept_id, count in heads.items():
            chain = chains.get(dept_id) or [dept_id]
            for candidate in reversed(chain):
                if candidate in by_department:
                    key = by_department[candidate]
                    out[key] = out.get(key, 0) + count
                    break
        return out

    # ------------------------------------------------------- the suggestions
    @api.model
    def suggest(self, company_ids=None, on_date=None):
        """One candidate division per top-level department name in the group.

        Names are compared with their accents and their case removed, so a
        department called "Retail" in one company and "RETAIL" in another
        becomes ONE suggestion carrying both — which is exactly the merge a
        person would otherwise do by hand. Anything already covered by a
        division is left out: a suggestion you have already accepted is noise.
        """
        Department = self.env['hr.department'].sudo()
        company_ids = [int(c) for c in (company_ids or []) if c]
        if not company_ids:
            return []
        covered = set(self._links_on(on_date))
        rows = Department.search(
            [('company_id', 'in', company_ids), ('parent_id', '=', False)],
            order='company_id, name')
        buckets = {}
        for dept in rows:
            if dept.id in covered:
                continue
            key = fold(dept.name)
            if not key:
                continue
            bucket = buckets.setdefault(key, {'name': dept.name,
                                              'departments': []})
            bucket['departments'].append(dept)
        existing = {fold(d.name): d.id
                    for d in self.sudo().search([])}
        heads = self._heads_by_department(company_ids)
        chains = self._department_chains(company_ids)
        rolled = {}
        for dept_id, count in heads.items():
            for candidate in reversed(chains.get(dept_id) or [dept_id]):
                rolled[candidate] = rolled.get(candidate, 0) + count
        out = []
        for key, bucket in buckets.items():
            out.append({
                'key': key,
                'name': bucket['name'],
                'existing_id': existing.get(key, 0),
                'people': sum(rolled.get(d.id, 0) for d in bucket['departments']),
                'departments': [{
                    'id': d.id,
                    'name': d.name,
                    'complete_name': d.complete_name or d.name,
                    'company_id': d.company_id.id,
                    'company': d.company_id.name,
                    'heads': rolled.get(d.id, 0),
                } for d in bucket['departments']],
            })
        out.sort(key=lambda s: (-s['people'], s['name']))
        return out


class PbDivisionLink(models.Model):
    _name = 'pb.division.link'
    _description = 'Department in a division'
    _order = 'date_from desc, id desc'

    division_id = fields.Many2one(
        'pb.division', string='Division', required=True, ondelete='cascade',
        index=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='department_id.company_id',
        store=True, index=True)
    date_from = fields.Date(
        string='From', required=True,
        default=lambda self: fields.Date.context_today(self))
    date_to = fields.Date(string='Until')
    active = fields.Boolean(default=True)

    @api.constrains('department_id', 'date_from', 'date_to', 'active',
                    'division_id')
    def _check_no_overlap(self):
        """One department, one division, on any given day.

        A history is kept rather than overwritten — "Retail until March, then
        Trade" is a real thing — so the rule is about OVERLAP and not about
        existence, and the sentence names the division that is already there
        and the date it started.
        """
        for link in self:
            if not link.active or not link.department_id:
                continue
            if link.date_to and link.date_from and link.date_to < link.date_from:
                raise ValidationError(_(
                    "The end date is before the start date. A department "
                    "cannot leave a division before it joins it."))
            domain = [
                ('id', '!=', link.id),
                ('department_id', '=', link.department_id.id),
                ('active', '=', True),
                '|', ('date_to', '=', False),
                ('date_to', '>=', link.date_from),
            ]
            if link.date_to:
                domain.append(('date_from', '<=', link.date_to))
            clash = self.sudo().search(domain, limit=1)
            if clash:
                raise ValidationError(_(
                    "%(department)s is already in %(division)s from "
                    "%(since)s. A department can only be in one division at a "
                    "time — give the first one an end date, or start this one "
                    "later.",
                    department=link.department_id.complete_name
                    or link.department_id.name,
                    division=clash.division_id.name,
                    since=fields.Date.to_string(clash.date_from)))
