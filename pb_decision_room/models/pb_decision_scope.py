# -*- coding: utf-8 -*-
"""`pb.decision.scope` — what "this plan" is a plan FOR.

Phases 1-3 planned one company, because there was only one thing a plan could
be about. A group has five: the whole group, one country, one company, one
division, or the people one payroll scheme pays. Every one of them is a
different roster, a different set of rules and a different currency, and the
room has to be able to move between them in one motion without the reader ever
learning a new screen.

THE SHAPE OF AN ANSWER

    {kind, ref, label, company_ids, currency, currencies, mixed, group,
     country_code, config_id, division_id}

`mixed` is the load-bearing one. A division whose departments sit in a VND
company and an SGD company has no single currency, and the honest answer is not
to pick one — it is to say so, compute each entity in its own money and add
them up through `pb.fx` at read time, refusing the total when a rate is
missing. Rule 7 of the group ledger: nothing converted is ever stored.

WHOSE COMPANIES

Scope resolution is bounded by `self.env.user.company_ids` — every legal entity
the reader is ENTITLED to, not merely the ones the company switcher happens to
have on. A person planning a group should not have to go and tick five boxes in
a menu before the group appears; and they still cannot reach a company nobody
gave them. Everything downstream of the resolved company list is scoped to it.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: The five things a plan can be about, in the order the picker shows them.
SCOPE_KINDS = ('group', 'country', 'company', 'division', 'scheme')

#: Beyond this a picker is a list, and a list is not a picker.
MAX_NODES = 60


class PbDecisionScope(models.AbstractModel):
    _name = 'pb.decision.scope'
    _description = 'Decision Room scope'

    # ------------------------------------------------------------- helpers
    @api.model
    def _allowed_companies(self):
        """Every company this reader may plan, most useful one first.

        GROUP P7 — narrowed by "who sees what", and unchanged for anybody who
        has not been limited.
        """
        companies = self.env.user.company_ids or self.env.company
        visible = set(self.env['pb.decision.room']._visible_companies(
            companies.ids))
        companies = companies.filtered(lambda c: c.id in visible)
        return companies.sudo().sorted(lambda c: (c.id != self.env.company.id,
                                                  c.id))

    @api.model
    def _held_division(self):
        """The one division this reader is held to, or an empty recordset.

        A division head plans THEIR division. Answering them at the company
        rung would print a head count of four and a half thousand on a screen
        whose whole promise is that they see nine hundred.
        """
        Division = self.env['pb.division']
        held = self.env['pb.decision.room']._visible_divisions()
        if not held:
            return Division.browse()
        return Division.sudo().browse(held[:1]).exists()

    @api.model
    def _group(self):
        """The group this reader can plan, if there is one.

        The reader's OWN company first, because that is the group they are
        standing in. But a person whose default company happens to sit outside
        the group — an administrator whose first company is the head office
        shell, which is exactly what happens on this build — must still be
        able to plan the group they can plainly see. So if their own company
        is in none, the first group any of their companies belongs to is the
        answer, and the chip says which.
        """
        if 'pb.group' not in self.env or 'pb.fx' not in self.env:
            # A database without the group module is one company, and the
            # chip says exactly that.
            return self.env['res.company'].browse()
        Fx = self.env['pb.fx']
        group = Fx.group_for(self.env.company)
        if group:
            return group
        for company in self._allowed_companies():
            group = Fx.group_for(company)
            if group:
                return group
        return self.env['pb.group'].browse()

    @api.model
    def _members(self):
        """The group's companies, narrowed to the ones this reader may see."""
        group = self._group()
        allowed = self._allowed_companies()
        if not group:
            return allowed
        members = group.sudo().company_ids
        return allowed.filtered(lambda c: c.id in set(members.ids))

    @api.model
    def _country_code(self, company):
        # GR20 — country_id is not stored; read it, never search it.
        return (company.sudo().country_id.code or '').upper()

    @api.model
    def _currency_dict(self, currency):
        return {
            'id': currency.id if currency else 0,
            'code': (currency.name or '') if currency else '',
            'symbol': (currency.symbol or '') if currency else '',
            'position': (currency.position or 'before') if currency else 'before',
            'decimals': (currency.decimal_places or 0) if currency else 0,
        }

    @api.model
    def _heads_by_company(self, company_ids):
        """Active employees per company, one query."""
        if not company_ids:
            return {}
        self.env.cr.execute("""
            SELECT company_id, COUNT(*) FROM hr_employee
             WHERE active AND company_id IN %s GROUP BY company_id
        """, (tuple(company_ids),))
        return dict(self.env.cr.fetchall())

    # ------------------------------------------------------------- resolve
    @api.model
    def _blank(self, companies=None):
        companies = companies if companies is not None else \
            self.env.company
        return self.describe('company', str(companies[:1].id))

    @api.model
    def describe(self, kind, ref=None):
        """One scope, fully answered. Never raises; falls back to a company.

        A scope that used to exist and no longer does — a division somebody
        archived, a scheme somebody retired — must not take the room down. It
        falls back to the reader's own company and the chip says which scope it
        could not find.
        """
        kind = kind if kind in SCOPE_KINDS else 'company'
        ref = str(ref or '').strip()
        # GROUP P7 — a rung this reader may not stand on is not a rung. Held
        # to a division, every question is answered at their division whatever
        # was asked for; empty, and this is a no-op.
        held = self._held_division()
        if held:
            kind, ref = 'division', str(held.id)
        allowed = self._allowed_companies()
        lost = ''

        companies = self.env['res.company'].browse()
        label = ''
        config_id = 0
        division_id = 0
        country_code = ''

        if kind == 'group':
            group = self._group()
            companies = self._members()
            label = group.name if group else _("Whole group")
            if not group:
                kind, lost = 'company', _("There is no group on this database "
                                          "yet, so this is one company.")
        elif kind == 'country':
            country_code = ref.upper()
            companies = self._members().filtered(
                lambda c: self._country_code(c) == country_code)
            label = self._country_name(country_code)
            if not companies:
                kind, lost = 'company', _(
                    "No company in the group is in that country any more.")
        elif kind == 'division':
            division = self.env['pb.division'].sudo().browse(
                int(ref or 0)).exists() if 'pb.division' in self.env \
                else None
            if division:
                division_id = division.id
                label = division.name or ''
                dep_companies = division.link_ids.filtered('active').mapped(
                    'company_id')
                companies = allowed.filtered(
                    lambda c: c.id in set(dep_companies.ids))
            if not companies:
                kind, lost = 'company', _("That division has no teams on it "
                                          "any more.")
        elif kind == 'scheme':
            config = self.env['hr.formula.config'].sudo().browse(
                int(ref or 0)).exists() if 'hr.formula.config' in self.env \
                else None
            if config and config.company_id and config.company_id.id in set(
                    allowed.ids):
                config_id = config.id
                label = config.name or ''
                companies = config.company_id
            if not companies:
                kind, lost = 'company', _("That payroll scheme is not here any "
                                          "more.")
        if kind == 'company' or not companies:
            company = None
            if ref.isdigit():
                company = allowed.filtered(lambda c: c.id == int(ref))[:1]
            if not company:
                company = allowed.filtered(
                    lambda c: c.id == self.env.company.id)[:1] or allowed[:1]
            companies = company
            label = company.display_name if company else ''
            ref = str(company.id) if company else ''
            config_id = 0
            division_id = 0

        currencies = companies.mapped('currency_id')
        mixed = len(currencies) > 1
        if mixed:
            group = self._group()
            currency = (group.presentation_currency_id if group
                        else self.env['pb.fx'].presentation_currency(
                            companies[:1]))
        else:
            currency = currencies[:1] or self.env.company.currency_id
        group = self._group()
        return {
            'kind': kind,
            'ref': ref if kind != 'group' else str(group.id if group else 0),
            'label': label,
            'company_ids': companies.ids,
            'company_names': {str(c.id): c.display_name for c in companies},
            'currency': self._currency_dict(currency),
            'currencies': sorted({c.name for c in currencies if c.name}),
            'mixed': mixed,
            'group_id': group.id if group else 0,
            'group_name': group.name if group else '',
            'country_code': country_code,
            'config_id': config_id,
            'division_id': division_id,
            'lost': lost,
            'people': sum(self._heads_by_company(companies.ids).values()),
        }

    @api.model
    def _country_name(self, code):
        if not code:
            return _("Country")
        country = self.env['res.country'].sudo().search(
            [('code', '=', code)], limit=1)
        return country.display_name if country else code

    # ---------------------------------------------------------------- tree
    @api.model
    def get_scopes(self):
        """The picker's whole tree, with a head count on every node.

        Six queries whatever the size of the group: one for headcount per
        company, one for the divisions, one for the schemes, and the division
        helper's own three. A group with eighty companies would be a list and
        not a tree, so the node count is capped and the picker says so.
        """
        allowed = self._allowed_companies()
        heads = self._heads_by_company(allowed.ids)
        group = self._group()
        members = self._members()

        # GROUP P7 — a division head is offered one node: their own division.
        held = self._held_division()
        if held:
            nodes = []
            for company in allowed:
                nodes += [n for n in self._division_nodes(company)
                          if n.get('ref') == str(held.id)]
            return {
                'has_group': bool(group),
                'nodes': nodes,
                'note': _("You plan %(what)s.", what=held.name or ''),
            }

        def company_node(company):
            return {
                'kind': 'company',
                'ref': str(company.id),
                'label': company.display_name,
                'people': heads.get(company.id, 0),
                'currency': (company.currency_id.name or ''),
                'country': self._country_code(company),
                'children': (self._division_nodes(company)
                             + self._scheme_nodes(company)),
            }

        if not group or not members:
            return {
                'has_group': False,
                'nodes': [company_node(c) for c in allowed[:MAX_NODES]],
                'note': _("One company, so a plan is a plan for that "
                          "company."),
            }

        by_country = {}
        for company in members:
            by_country.setdefault(self._country_code(company),
                                  self.env['res.company'].browse())
            by_country[self._country_code(company)] |= company
        countries = []
        for code, companies in sorted(by_country.items()):
            countries.append({
                'kind': 'country',
                'ref': code,
                'label': self._country_name(code),
                'people': sum(heads.get(c.id, 0) for c in companies),
                'children': [company_node(c) for c in companies],
            })
        outside = allowed - members
        nodes = [{
            'kind': 'group',
            'ref': str(group.id),
            'label': group.name or _("Whole group"),
            'people': sum(heads.get(c.id, 0) for c in members),
            'currency': group.presentation_currency_id.name or '',
            'children': countries,
        }]
        nodes += [company_node(c) for c in outside[:MAX_NODES]]
        return {
            'has_group': True,
            'nodes': nodes,
            'note': _("%(companies)s companies in %(group)s.",
                      companies=len(members), group=group.name or ''),
        }

    @api.model
    def _division_nodes(self, company):
        if 'pb.division' not in self.env:
            return []
        Division = self.env['pb.division'].sudo()
        divisions = Division.search([])
        out = []
        for division in divisions:
            links = division.link_ids.filtered(
                lambda link: link.active and link.company_id.id == company.id)
            if not links:
                continue
            out.append({
                'kind': 'division',
                'ref': str(division.id),
                'label': division.name or '',
                'people': self._division_heads(links),
                'children': [],
            })
        return sorted(out, key=lambda n: -n['people'])[:MAX_NODES]

    @api.model
    def _division_heads(self, links):
        """People under a division's departments, branches included."""
        dept_ids = links.mapped('department_id').ids
        if not dept_ids:
            return 0
        ids = self._department_branch(dept_ids)
        if not ids:
            return 0
        self.env.cr.execute("""
            SELECT COUNT(*) FROM hr_employee e
         LEFT JOIN hr_version v ON v.id = e.current_version_id
             WHERE e.active AND v.department_id IN %s
        """, (tuple(ids),))
        return self.env.cr.fetchone()[0] or 0

    @api.model
    def _department_branch(self, dept_ids):
        """Those departments and everything under them, one query.

        `parent_path` is stored and indexed, which is why this is a `LIKE` and
        not a recursive walk in Python over forty departments per company.
        """
        if not dept_ids:
            return []
        self.env.cr.execute(
            "SELECT parent_path FROM hr_department WHERE id IN %s",
            (tuple(dept_ids),))
        paths = [row[0] for row in self.env.cr.fetchall() if row[0]]
        if not paths:
            return list(dept_ids)
        clauses = ' OR '.join(['parent_path LIKE %s'] * len(paths))
        self.env.cr.execute(
            "SELECT id FROM hr_department WHERE " + clauses,
            tuple('%s%%' % p for p in paths))
        return [row[0] for row in self.env.cr.fetchall()] or list(dept_ids)

    @api.model
    def _scheme_nodes(self, company):
        if 'hr.formula.config' not in self.env:
            return []
        configs = self.env['hr.formula.config'].sudo().search(
            [('company_id', '=', company.id), ('state', '=', 'active')],
            limit=MAX_NODES)
        if not configs:
            return []
        counts = {}
        if 'pb_paid_by_id' in self.env['hr.employee']._fields:
            rows = self.env['hr.employee'].sudo()._read_group(
                [('company_id', '=', company.id), ('active', '=', True),
                 ('pb_paid_by_id', 'in', configs.ids)],
                ['pb_paid_by_id'], ['__count'])
            counts = {config.id: count for config, count in rows}
        return [{
            'kind': 'scheme',
            'ref': str(config.id),
            'label': config.name or '',
            'people': counts.get(config.id, 0),
            'children': [],
        } for config in configs]
