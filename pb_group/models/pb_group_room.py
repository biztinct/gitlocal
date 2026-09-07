# -*- coding: utf-8 -*-
"""`pb.group.room` — the only server surface the Group screen talks to.

The shape is the one `pb_assets` and `pb.decision.room` established: an
`AbstractModel` facade, `@api.model` reads, every independent number inside its
own `_safe()` so one failing figure answers zero instead of taking the screen
down, a row cap on anything a caller controls, and a SERVER-SIDE gate that is
the boundary.

A reader with no permission gets an EMPTY, EXPLAINED screen (`allowed: False`)
rather than an access dialog — a dialog is a dead end, and this screen's whole
job is to tell somebody what a group is and who can set one up.

WHY THE READS RUN UNDER `sudo()` (WFPLAN WF10, restated for this screen)
-----------------------------------------------------------------------
Setting a group up is an administrator's job, not an HR job, and the person who
does it very often does not hold `hr.group_hr_user`. Without sudo the screen
would be locked out of its own headcounts by an HR permission it has no
business needing. So the four reads that touch people run under `sudo()` AFTER
the gate above, and every one of them returns an AGGREGATE — a count per
department, never a person, never a wage. The company list is read the same way
for the same reason: a group is made of legal entities, and you cannot tick a
company you are not allowed to see the name of.
"""

import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_division import COLOUR_COUNT, fold

_logger = logging.getLogger(__name__)

GROUP_ADMIN = 'pb_group.group_group_admin'
READ_GROUPS = (
    'pb_group.group_group_admin',
    'hr.group_hr_user',
    'pb_decision_room.group_decision_user',
)

#: Caps on lists a caller controls — this facade is reachable over JSON-RPC.
MAX_COMPANIES = 200
MAX_DIVISIONS = 200
MAX_SUGGESTIONS = 60
MAX_NAME = 120
MAX_USERS = 400

#: The surfaces the "as this person" preview walks, in the order a person
#: would meet them. `model` is checked against the registry first, so a
#: database without a module simply does not list its screen.
PREVIEW_SURFACES = [
    ('pb.group.room', 'Group'),
    ('pb.scheme.board', 'Who is paid by what'),
    ('pb.explorer', 'Explorer'),
    ('pb.decision.room', 'Decision Room'),
    ('pb.assignments', 'Assignments'),
    ('pb.pay.bands', 'Pay'),
]


class PbGroupRoom(models.AbstractModel):
    _name = 'pb.group.room'
    # GROUP P7 — every read on this screen goes through `who sees what`.
    # A reader with no visibility row is narrowed by nothing at all.
    _inherit = ['pb.group.scoped']
    _description = 'Group screen data'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('Group screen figure failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        for name in READ_GROUPS:
            if self._safe(lambda n=name: user.has_group(n), default=False):
                return True
        return False

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user._is_admin()
                or self._safe(lambda: user.has_group(GROUP_ADMIN),
                              default=False))

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at the group, but setting it up is for an "
                "administrator. Ask one of them to make the change."))
        return True

    # ============================================================== the read
    @api.model
    def get_room(self):
        started = time.time()
        if not self._can_read():
            return {
                'allowed': False, 'can_edit': False, 'group': None,
                'groups': [], 'companies': [], 'currencies': [],
                'policies': self._policies(), 'coverage': {'pairs': []},
                'split_policies': [], 'has_workseg': False,
                'divisions': [], 'suggestions': [], 'unassigned': 0,
                'year': fields.Date.context_today(self).year,
                'rate_action': 'pb_group.action_pb_exchange_rates',
                'ms': 0,
            }
        Group = self.env['pb.group'].sudo()
        Division = self.env['pb.division'].sudo()

        group = Group.search([], order='id', limit=1)
        groups = [{'id': g.id, 'name': g.name}
                  for g in Group.search([], limit=MAX_DIVISIONS)]

        members = group.company_ids if group else self.env['res.company']
        member_ids = members.ids
        # Divisions are group-level, but the departments that make them up
        # live in companies. When there is no group yet, the screen still has
        # to be useful, so the companies the reader can see stand in.
        scope_ids = member_ids or (self.env.companies.ids
                                   or [self.env.company.id])
        # GROUP P7. Somebody held to one country or one division counts the
        # people of THEIR part of the group, not of all of it. Untouched for
        # everybody else.
        scope_ids = self._visible_companies(scope_ids)

        heads = self._safe(
            lambda: Division._heads_by_department(scope_ids), default={})
        chains = self._safe(
            lambda: Division._department_chains(scope_ids), default={})
        links_on = self._safe(lambda: Division._links_on(), default={})

        # GROUP P7. A division head's screen is THEIR division: the counts
        # stop at their own teams, and the board draws their own card rather
        # than eleven they cannot act on. Both lists are empty for anybody who
        # has not been limited, and the two lines below are then no-ops.
        only_departments = set(self._safe(lambda: self._visible_departments(),
                                          default=[]) or [])
        only_divisions = set(self._safe(lambda: self._visible_divisions(),
                                        default=[]) or [])
        narrowed = bool(self._safe(
            lambda: self.env['pb.group.visibility'].is_restricted(),
            default=False))
        if only_departments:
            heads = {d: n for d, n in heads.items() if d in only_departments}
        rolled = self._rollup(heads, chains)

        divisions = self._divisions(Division, heads, chains, links_on)
        if only_divisions:
            divisions = [d for d in divisions if d['id'] in only_divisions]
        assigned = sum(d['people'] for d in divisions)
        total = sum(heads.values())

        payload = {
            'allowed': True,
            'can_edit': self._can_write(),
            'group': self._group(group),
            'groups': groups,
            'companies': self._companies(group, scope_ids, heads,
                                         only_departments, narrowed),
            'currencies': self._currencies(),
            'policies': self._policies(),
            'coverage': self._safe(lambda: self._coverage(group),
                                   default={'pairs': []}),
            'divisions': divisions,
            'suggestions': self._safe(
                lambda: Division.suggest(scope_ids)[:MAX_SUGGESTIONS],
                default=[]),
            'unassigned': max(total - assigned, 0),
            'people_total': total,
            'year': fields.Date.context_today(self).year,
            'rate_action': 'pb_group.action_pb_exchange_rates',
            # GROUP P7 — one sentence at the top of a narrowed screen, and ''
            # for everybody else, so the strip is simply not drawn.
            'scope_note': self._scope_note(),
            # GROUP P5 — the two split-month patterns, and whether the module
            # that acts on them is even here. The card is drawn only when it
            # is, so a database without it sees a screen unchanged.
            'split_policies': self._split_policies(),
            'has_workseg': 'pb.work.segment' in self.env,
            # GROUP P7 — who sees what. Drawn for an administrator only: it is
            # a list of named people and what each of them is held to, which
            # is not a thing every reader of this screen should have.
            'visibility': self._safe(lambda: self._visibility(group),
                                     default={'rows': [], 'people': [],
                                              'kinds': [], 'countries': [],
                                              'divisions': [], 'warnings': []}),
        }
        payload['ms'] = int((time.time() - started) * 1000)
        # `rolled` is the department roll-up the pickers use so a person can
        # see how many people an attachment brings before they make it.
        payload['departments'] = self._departments(scope_ids, rolled, links_on,
                                                   divisions, only_departments)
        return payload

    # ------------------------------------------------------------ the pieces
    @api.model
    def _rollup(self, heads, chains):
        """department id -> people in it and everything under it."""
        out = {}
        for dept_id, count in heads.items():
            for candidate in (chains.get(dept_id) or [dept_id]):
                out[candidate] = out.get(candidate, 0) + count
        return out

    @api.model
    def _group(self, group):
        if not group:
            return None
        currency = group.presentation_currency_id
        return {
            'id': group.id,
            'name': group.name or '',
            'code': group.code or '',
            'currency_id': currency.id if currency else 0,
            'currency': currency.name if currency else '',
            'currency_symbol': currency.symbol if currency else '',
            'fx_policy': group.fx_policy,
            'split_pay_policy': group.split_pay_policy or 'each_pays',
            'fiscal_start_month': group.fiscal_start_month or 1,
            'note': group.note or '',
            'company_ids': group.company_ids.ids,
        }

    @api.model
    def _companies(self, group, scope_ids=None, heads=None,
                   only_departments=None, narrowed=False):
        # `active_test=False` on purpose. A company that has been switched off
        # is still a legal entity a group can be made of, and on a real
        # database the second-currency subsidiary is very often exactly that —
        # set up, then parked. Hiding it would leave the person who came here
        # to build a group with no way to build theirs, which is the dead end
        # this screen exists to remove. It is shown, labelled "not in use", and
        # ticking it says in words that it will be switched back on.
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)
        companies = Company.search([], order='id', limit=MAX_COMPANIES)
        people = self._safe(lambda: self._people_by_company(companies.ids),
                            default={})
        # GROUP P7 — A NARROWED READER'S TREE COUNTS THEIR OWN PEOPLE.
        #
        # The card said "4,533 people" under a heading that said 902, which is
        # the kind of contradiction that makes somebody stop believing the
        # rest of the screen. When the reader is held to a set of teams, each
        # company's figure is the people of THOSE teams inside it.
        if only_departments:
            people = self._safe(
                lambda: self._people_by_company_for(heads or {},
                                                    only_departments),
                default={})
        schemes = self._safe(lambda: self._schemes_by_company(companies.ids),
                             default={})
        out = []
        # A company this reader may not see is not drawn in their tree at all
        # — whichever kind of scope narrowed them.
        allowed = set(scope_ids or []) if narrowed else None
        for company in companies:
            if allowed is not None and company.id not in allowed:
                continue
            other = company.pb_group_id
            out.append({
                'id': company.id,
                'name': company.name or '',
                'country': company.country_id.name or '',
                'flag_code': (company.country_id.code or '')[:2].upper(),
                'currency_id': company.currency_id.id,
                'currency': company.currency_id.name or '',
                'people': people.get(company.id, 0),
                'schemes': schemes.get(company.id, 0),
                'member': bool(group and other and other.id == group.id),
                'group_id': other.id if other else 0,
                'group_name': other.name if other else '',
                'active': bool(company.active),
                # GROUP P5 — day-based pay for mid-month joiners and leavers.
                # Absent on a database without `pb_workseg`, in which case the
                # card that shows it is not drawn at all.
                'prorate': bool(getattr(company, 'prorate_joiners_leavers',
                                        False)),
            })
        return out

    @api.model
    def _people_by_company_for(self, heads, department_ids):
        """company id -> people, counted over a named set of teams only."""
        wanted = [int(d) for d in department_ids if d]
        if not wanted:
            return {}
        rows = self.env['hr.department'].sudo().with_context(
            active_test=False).search_read(
            [('id', 'in', wanted)], ['company_id'])
        by_company = {}
        for row in rows:
            company = (row['company_id'] or [0])[0]
            if company:
                by_company[company] = (by_company.get(company, 0)
                                       + heads.get(row['id'], 0))
        return by_company

    @api.model
    def _people_by_company(self, company_ids):
        if not company_ids:
            return {}
        self.env.cr.execute("""
            SELECT company_id, COUNT(*) FROM hr_employee
             WHERE active AND company_id = ANY(%s) GROUP BY 1
        """, ([int(c) for c in company_ids],))
        return dict(self.env.cr.fetchall())

    @api.model
    def _schemes_by_company(self, company_ids):
        if 'hr.formula.config' not in self.env:
            return {}
        rows = self.env['hr.formula.config'].sudo()._read_group(
            [('company_id', 'in', list(company_ids))],
            ['company_id'], ['__count'])
        return {company.id: count for company, count in rows if company}

    @api.model
    def _currencies(self):
        rows = self.env['res.currency'].sudo().search_read(
            [('active', '=', True)], ['name', 'symbol'], order='name',
            limit=MAX_COMPANIES)
        return [{'id': r['id'], 'name': r['name'], 'symbol': r['symbol'] or ''}
                for r in rows]

    @api.model
    def _policies(self):
        """The three ways a rate can be picked, in words a person can choose
        between. The labels are the field's own, so there is one list."""
        # GR58 — the labels are written HERE with `_()` and not read out of
        # `fields_get`. A selection's translated label lives in
        # `ir.model.fields.selection` and reaches a screen through
        # `_get_fields_cached`, which is `ormcache`d on the language and is
        # not filled by a `.po` import in another process: three of these
        # labels stayed English on a Vietnamese screen while every other word
        # on it was translated. A label a person reads is a string this
        # module owns.
        labels = {
            'month_end': _("The last rate of the month"),
            'payment_date': _("The rate on the day the pay run ends"),
            'month_avg': _("The average rate for the month"),
        }
        helps = {
            'month_end': _("The last rate on or before the end of the month."),
            'payment_date': _("The rate on or before the day the pay run "
                              "ends."),
            'month_avg': _("The average of that month's rates. If there are "
                           "none, the figure is shown unconverted."),
        }
        return [{'key': key, 'label': labels.get(key, key),
                 'help': helps.get(key, '')} for key in labels]

    @api.model
    def _split_policies(self):
        """The two ways a split month can be paid, in words (ruling G8)."""
        # GR58 — written here, not read from `fields_get`.
        labels = {
            'each_pays': _("Each entity pays its own days"),
            'home_pays': _("Home pays, the other entity is charged"),
        }
        helps = {
            'each_pays': _("The home entity's payslip is reduced to the days "
                           "that stayed at home, and the other entity runs "
                           "its own payslip for its own days, in its own "
                           "money."),
            'home_pays': _("The home entity pays the whole month and the "
                           "other entity is charged its share as an internal "
                           "cost line. One payslip."),
        }
        return [{'key': key, 'label': labels.get(key, key),
                 'help': helps.get(key, '')} for key in labels]

    @api.model
    def set_split_policy(self, group_id, policy):
        """Which pattern this group uses when a month is split."""
        self._require_write()
        Group = self.env['pb.group'].sudo()
        group = Group.browse(int(group_id or 0)).exists()
        if not group:
            raise UserError(_("That group is no longer here."))
        if policy not in dict(Group._fields['split_pay_policy'].selection):
            raise UserError(_("Pick one of the two patterns."))
        group.write({'split_pay_policy': policy})
        return self.get_room()

    @api.model
    def set_prorate_joiners(self, company_id, enabled):
        """Turn day-based pay for mid-month joiners and leavers on or off.

        Refuses in words rather than silently doing nothing on a database
        without the module that acts on it — a switch that does not switch
        anything is a dead end with a tick in it.
        """
        self._require_write()
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)
        company = Company.browse(int(company_id or 0)).exists()
        if not company:
            raise UserError(_("That company is no longer here."))
        if 'prorate_joiners_leavers' not in company._fields:
            raise UserError(_(
                "Day-based pay for people who join or leave part-way through "
                "a month is not switched on for this database yet."))
        company.write({'prorate_joiners_leavers': bool(enabled)})
        return self.get_room()

    @api.model
    def _coverage(self, group):
        """One row per currency pair the group actually needs."""
        if not group:
            return {'pairs': [], 'year': fields.Date.context_today(self).year,
                    'policy': ''}
        target = group.presentation_currency_id
        pairs = []
        seen = set()
        for company in group.company_ids:
            currency = company.currency_id
            if not currency or not target or currency == target:
                continue
            if currency.id in seen:
                continue
            seen.add(currency.id)
            pairs.append({'src': currency.id, 'dst': target.id})
        member = group.company_ids[:1] or self.env.company
        return self.env['pb.fx'].coverage(
            pairs, fields.Date.context_today(self).year, member,
            group.fx_policy)

    @api.model
    def _divisions(self, Division, heads, chains, links_on):
        divisions = Division.search([], limit=MAX_DIVISIONS)
        rows = {}
        for division in divisions:
            rows[division.id] = {
                'id': division.id, 'name': division.name or '',
                'code': division.code or '', 'color': division.color or 0,
                'note': division.note or '', 'people': 0, 'links': [],
            }
        # People land on the division that covers them, walking upward, so an
        # attachment at the top of a branch carries everything under it.
        for dept_id, count in heads.items():
            for candidate in reversed(chains.get(dept_id) or [dept_id]):
                key = links_on.get(candidate)
                if key and key in rows:
                    rows[key]['people'] += count
                    break
        rolled = self._rollup(heads, chains)
        links = self.env['pb.division.link'].sudo().search(
            [('division_id', 'in', list(rows))], limit=MAX_DIVISIONS * 10)
        for link in links:
            row = rows.get(link.division_id.id)
            if not row:
                continue
            row['links'].append({
                'id': link.id,
                'department_id': link.department_id.id,
                'department': link.department_id.name or '',
                'complete_name': (link.department_id.complete_name
                                  or link.department_id.name or ''),
                'company_id': link.company_id.id,
                'company': link.company_id.name or '',
                'date_from': fields.Date.to_string(link.date_from) or '',
                'date_to': fields.Date.to_string(link.date_to) or '',
                'heads': rolled.get(link.department_id.id, 0),
            })
        return list(rows.values())

    @api.model
    def _departments(self, company_ids, rolled, links_on, divisions,
                     only_departments=None):
        """Every department a person can attach, and what it already belongs
        to — so the picker never offers a move without saying it is one."""
        names = {d['id']: d['name'] for d in divisions}
        # ORDERED BY `name`, and sorted by the full path afterwards.
        # `hr.department.complete_name` is a NON-STORED compute on this
        # release, so naming it in `order=` is a hard ValueError rather than a
        # slow query — the ordering that matters to a reader is done in Python.
        rows = self.env['hr.department'].sudo().search_read(
            [('company_id', 'in', list(company_ids))],
            ['complete_name', 'name', 'company_id', 'parent_id'],
            order='company_id, name', limit=1000)
        rows.sort(key=lambda r: ((r['company_id'] or [0, ''])[1] or '',
                                 r['complete_name'] or r['name'] or ''))
        out = []
        for row in rows:
            # GROUP P7 — a picker may not offer a team this reader cannot see.
            if only_departments and row['id'] not in only_departments:
                continue
            taken = links_on.get(row['id'], 0)
            out.append({
                'id': row['id'],
                'name': row['name'],
                'complete_name': row['complete_name'] or row['name'],
                'company_id': row['company_id'][0] if row['company_id'] else 0,
                'company': row['company_id'][1] if row['company_id'] else '',
                'top': not row['parent_id'],
                'heads': rolled.get(row['id'], 0),
                'division_id': taken,
                'division': names.get(taken, ''),
            })
        return out

    @api.model
    def _scope_note(self):
        """One sentence at the top of a narrowed screen, and '' otherwise.

        Its own guard rather than `_safe`, which logs at DEBUG: a sentence
        that silently becomes an empty string is a screen that quietly stops
        telling somebody they are only seeing part of the group, and that is
        worth a line in the log.
        """
        try:
            return self._visibility_note() or ''
        except Exception as e:      # noqa: BLE001 - never take the screen down
            _logger.warning('Group screen scope sentence failed: %s', e)
            return ''

    # ======================================================= who sees what
    # GROUP P7. The card answers three questions in one place: who has been
    # limited, to what, and — the hero — WHAT WOULD I SEE IF I WERE THEM. The
    # last one is the only honest way to hand somebody a permission model: not
    # a matrix of ticks, but the screen they will actually get.
    @api.model
    def _visibility(self, group):
        Visibility = self.env['pb.group.visibility'].sudo()
        rows = Visibility.search([], limit=MAX_USERS)
        members = (group.company_ids if group
                   else self.env['res.company'].sudo().browse(
                       self.env.companies.ids))
        out, warnings = [], []
        for row in rows:
            scope = Visibility.scope_for(row.user_id)
            out.append({
                'id': row.id,
                'user_id': row.user_id.id,
                'user': row.user_id.name or '',
                'login': row.user_id.login or '',
                'kind': row.kind,
                'kind_label': scope.get('kind_label') or '',
                'ref_id': scope.get('ref_id') or 0,
                'ref_name': scope.get('ref_name') or '',
                'sentence': scope.get('sentence') or '',
                'ok': bool(scope.get('ref_ok')),
                'note': row.note or '',
                'companies': len(scope.get('company_ids') or []),
            })
            if scope.get('warning'):
                warnings.append(scope['warning'])
        held = {r['user_id'] for r in out}
        # Every person who could be given one. Internal users only: a portal
        # account has no group screen to be limited on.
        people = self.env['res.users'].sudo().search_read(
            [('share', '=', False), ('active', '=', True)],
            ['name', 'login'], order='name', limit=MAX_USERS)
        countries = []
        seen = set()
        for company in members:
            country = company.country_id
            if country and country.id not in seen:
                seen.add(country.id)
                countries.append({'id': country.id, 'name': country.name})
        return {
            'rows': sorted(out, key=lambda r: (r['user'] or '').lower()),
            'people': [{'id': p['id'], 'name': p['name'],
                        'login': p['login'] or '',
                        'held': p['id'] in held} for p in people],
            'kinds': self._visibility_kinds(),
            'countries': sorted(countries, key=lambda c: c['name'] or ''),
            'companies': [{'id': c.id, 'name': c.name} for c in members],
            'divisions': [{'id': d.id, 'name': d.name}
                          for d in self.env['pb.division'].sudo().search(
                              [], limit=MAX_DIVISIONS)],
            'warnings': warnings,
            'mine': Visibility.scope_for(self.env.user).get('sentence') or '',
        }

    @api.model
    def _visibility_kinds(self):
        # GR58 — written here, not read from `fields_get`.
        # A DICT and not a list of tuples: the string extractor reading
        # `('country', _("One country"))` also collects the bare key
        # `"country"` as a term somebody has to translate, and a catalogue
        # full of one-word junk is a catalogue nobody trusts.
        labels = {
            'all': _("Everything"),
            'country': _("One country"),
            'company': _("One company"),
            'division': _("One division"),
        }
        described = [(key, labels[key]) for key in
                     ('all', 'country', 'company', 'division')]
        helps = {
            'all': _("Every company in the group."),
            'country': _("Every company of the group in one country."),
            'company': _("One legal entity."),
            'division': _("One division, in whatever company it sits in."),
        }
        return [{'key': key, 'label': label, 'help': helps.get(key, '')}
                for key, label in described]

    @api.model
    def set_visibility(self, user_id, kind, ref_id=None, note=None):
        """Limit somebody, change what they are limited to, or lift it."""
        self._require_write()
        self.env['pb.group.visibility'].set_for(user_id, kind, ref_id, note)
        return self.get_room()

    @api.model
    def preview_visibility(self, user_id):
        """THE HERO: what this person would see, everywhere, in one answer.

        Built from the SAME `scope_for` every facade in this programme calls,
        so the preview cannot drift away from the screens it describes — a
        permission preview that is a second implementation of the rule is a
        preview that lies the first time somebody changes one of them.

        The counts run under `sudo()` after the gate above (WFPLAN WF10): they
        are aggregates — a company, a division and a number — never a person
        and never a wage.
        """
        if not self._can_read():
            raise AccessError(_(
                "You can look at the group, but this is for an "
                "administrator."))
        Visibility = self.env['pb.group.visibility'].sudo()
        Division = self.env['pb.division'].sudo()
        who = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        if not who:
            raise UserError(_("That person is no longer here."))
        scope = Visibility.scope_for(who)

        entitled = who.company_ids.ids
        company_ids = (scope['company_ids'] if scope['restricted']
                       else entitled)
        heads = self._safe(lambda: self._people_by_company(company_ids),
                           default={})
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)
        # A DIVISION SCOPE DOES NOT GET A COMPANY HEAD COUNT.
        #
        # Retail is 902 people inside a company of 4,533, and printing "4,533"
        # under a headline that says 902 is the kind of contradiction that
        # makes a reader stop trusting the screen. When the scope is a
        # division the company rows say WHERE the division sits and nothing
        # else; the number belongs to the division above them.
        by_company = scope['kind'] != 'division'
        companies = [{'id': c.id, 'name': c.name or '',
                      'country': c.country_id.name or '',
                      'currency': c.currency_id.name or '',
                      'people': heads.get(c.id, 0) if by_company else -1}
                     for c in Company.browse(sorted(company_ids)).exists()]

        by_division = self._safe(lambda: Division._heads_by_division(),
                                 default={})
        wanted = scope['division_ids']
        division_rows = Division.search(
            [('id', 'in', wanted)] if wanted else [], limit=MAX_DIVISIONS)
        divisions = [{'id': d.id, 'name': d.name or '',
                      'people': by_division.get(d.id, 0)}
                     for d in division_rows]

        people = (sum(d['people'] for d in divisions)
                  if scope['kind'] == 'division'
                  else sum(c['people'] for c in companies))
        return {
            'user_id': who.id,
            'user': who.name or '',
            'kind': scope['kind'],
            'kind_label': scope['kind_label'],
            'ref_name': scope['ref_name'],
            'sentence': scope['sentence'],
            'warning': scope['warning'],
            'restricted': scope['restricted'],
            'headline': self._preview_headline(scope, people, companies,
                                               divisions),
            'companies': companies,
            'divisions': divisions,
            'people': people,
            'surfaces': self._preview_surfaces(scope, companies, divisions),
        }

    @api.model
    def _preview_headline(self, scope, people, companies, divisions):
        """The one sentence at the top of the preview — the whole point."""
        name = scope['user_name'] or _("this person")
        if not scope['restricted']:
            return _(
                "As %(name)s, you would see everything in %(count)s "
                "%(word)s.", name=name, count=len(companies),
                word=(_("company") if len(companies) == 1
                      else _("companies")))
        if scope['kind'] == 'division':
            return _("As %(name)s, you would see: %(what)s · %(count)s "
                     "%(word)s.", name=name,
                     what=scope['ref_name'] or _("one division"),
                     count=people,
                     word=(_("person") if people == 1 else _("people")))
        return _("As %(name)s, you would see: %(what)s · %(count)s %(word)s.",
                 name=name,
                 what=(scope['ref_name']
                       or ', '.join(c['name'] for c in companies[:3])),
                 count=people,
                 word=(_("person") if people == 1 else _("people")))

    @api.model
    def _preview_surfaces(self, scope, companies, divisions):
        """One line per screen, so the answer is not an abstraction.

        A screen whose module is not on this database is simply not listed —
        naming a door that does not exist is the dead end this preview is here
        to remove.
        """
        labels = {
            'pb.group.room': _("Group"),
            'pb.scheme.board': _("Who is paid by what"),
            'pb.explorer': _("Explorer"),
            'pb.decision.room': _("Decision Room"),
            'pb.assignments': _("Assignments"),
            'pb.pay.bands': _("Pay"),
        }
        if scope['restricted'] and scope['kind'] == 'division':
            line = _("%(what)s only", what=', '.join(
                d['name'] for d in divisions) or _("one division"))
        elif scope['restricted']:
            names = ', '.join(c['name'] for c in companies[:3])
            line = (_("%(what)s only", what=names) if names
                    else _("nothing yet — no company matches"))
        else:
            line = _("everything they already have")
        out = []
        for model, _english in PREVIEW_SURFACES:
            if model not in self.env:
                continue
            out.append({'key': model, 'label': labels.get(model, model),
                        'line': line})
        return out

    # ============================================================= the write
    @api.model
    def _clean_name(self, value):
        name = (value or '').strip()[:MAX_NAME]
        if not name:
            raise UserError(_("Give it a name first."))
        return name

    @api.model
    def save_group(self, vals):
        """Create the group, or change it. One door for both."""
        self._require_write()
        vals = vals or {}
        Group = self.env['pb.group'].sudo()
        currency = int(vals.get('presentation_currency_id') or 0)
        if not currency:
            raise UserError(_("Pick the currency the group reads in."))
        policy = vals.get('fx_policy')
        if policy not in dict(Group._fields['fx_policy'].selection):
            raise UserError(_("Pick how exchange rates should be chosen."))
        month = int(vals.get('fiscal_start_month') or 1)
        if not 1 <= month <= 12:
            raise UserError(_("Pick the month your financial year starts in."))
        payload = {
            'name': self._clean_name(vals.get('name')),
            'code': (vals.get('code') or '').strip()[:32] or False,
            'presentation_currency_id': currency,
            'fx_policy': policy,
            'fiscal_start_month': month,
            'note': (vals.get('note') or '').strip() or False,
        }
        split = vals.get('split_pay_policy')
        if split in dict(Group._fields['split_pay_policy'].selection):
            payload['split_pay_policy'] = split
        group_id = int(vals.get('id') or 0)
        if group_id:
            group = Group.browse(group_id).exists()
            if not group:
                raise UserError(_("That group is no longer here."))
            group.write(payload)
        else:
            group = Group.create(payload)
        if 'company_ids' in vals:
            self.set_members(group.id, vals.get('company_ids') or [])
        return self.get_room()

    @api.model
    def set_members(self, group_id, company_ids):
        """Who is in the group. Ticking a company that belongs to ANOTHER
        group MOVES it, which is the honest reading of the tick — and the
        screen says so before it is made."""
        self._require_write()
        Group = self.env['pb.group'].sudo()
        group = Group.browse(int(group_id or 0)).exists()
        if not group:
            raise UserError(_("That group is no longer here."))
        wanted = {int(c) for c in (company_ids or []) if c}
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)
        current = set(group.company_ids.ids)
        joining = Company.browse(sorted(wanted - current)).exists()
        leaving = Company.browse(sorted(current - wanted)).exists()
        if joining:
            # A company in your group is a company you are using, so one that
            # was switched off is switched back on as it joins. The screen says
            # so on the tick, before it happens — never a silent side effect.
            payload = {'pb_group_id': group.id}
            parked = joining.filtered(lambda c: not c.active)
            joining.write(payload)
            if parked:
                parked.write({'active': True})
        if leaving:
            leaving.write({'pb_group_id': False})
        return self.get_room()

    @api.model
    def create_division(self, vals):
        self._require_write()
        vals = vals or {}
        payload = {
            'name': self._clean_name(vals.get('name')),
            'code': (vals.get('code') or '').strip()[:32] or False,
            'color': int(vals.get('color') or 0) % COLOUR_COUNT,
            'note': (vals.get('note') or '').strip() or False,
        }
        self.env['pb.division'].sudo().create(payload)
        return self.get_room()

    @api.model
    def update_division(self, division_id, vals):
        self._require_write()
        division = self.env['pb.division'].sudo().browse(
            int(division_id or 0)).exists()
        if not division:
            raise UserError(_("That division is no longer here."))
        payload = {}
        if 'name' in (vals or {}):
            payload['name'] = self._clean_name(vals.get('name'))
        if 'code' in (vals or {}):
            payload['code'] = (vals.get('code') or '').strip()[:32] or False
        if 'color' in (vals or {}):
            payload['color'] = int(vals.get('color') or 0) % COLOUR_COUNT
        if 'note' in (vals or {}):
            payload['note'] = (vals.get('note') or '').strip() or False
        if payload:
            division.write(payload)
        return self.get_room()

    @api.model
    def archive_division(self, division_id):
        self._require_write()
        division = self.env['pb.division'].sudo().browse(
            int(division_id or 0)).exists()
        if division:
            division.write({'active': False})
        return self.get_room()

    @api.model
    def _attach(self, division_id, department_id, date_from=None):
        """The attachment itself, with no screen payload attached to it.

        A department already in another division is MOVED rather than
        refused: the old attachment is closed the day before this one starts,
        so the history says what was true when, which is what a report reading
        last quarter needs. Accepting twenty suggestions calls this twenty
        times and rebuilds the screen once.
        """
        Link = self.env['pb.division.link'].sudo()
        division = self.env['pb.division'].sudo().browse(
            int(division_id or 0)).exists()
        department = self.env['hr.department'].sudo().browse(
            int(department_id or 0)).exists()
        if not division or not department:
            raise UserError(_("Pick a division and a department first."))
        day = fields.Date.to_date(date_from) if date_from else \
            fields.Date.context_today(self)
        open_links = Link.search([
            ('department_id', '=', department.id),
            '|', ('date_to', '=', False), ('date_to', '>=', day)])
        for link in open_links:
            if link.division_id.id == division.id and link.date_from <= day:
                # Already there, from an earlier date. Nothing to do, and
                # nothing to apologise for.
                return link
            if link.date_from >= day:
                link.unlink()
            else:
                link.write({'date_to': fields.Date.subtract(day, days=1)})
        return Link.create({'division_id': division.id,
                            'department_id': department.id,
                            'date_from': day})

    @api.model
    def attach_department(self, division_id, department_id, date_from=None):
        self._require_write()
        self._attach(division_id, department_id, date_from)
        return self.get_room()

    @api.model
    def attach_departments(self, division_id, department_ids, date_from=None):
        """GROUP P7 — many at once, in ONE call and ONE rebuild.

        The picker used to be one department per press, which on a real
        company is forty presses and forty rebuilds of a screen that draws
        four thousand people. Ticking is the gesture people already expect
        from a list with checkboxes in it; this is the door behind it.

        A department that cannot be attached does not take the others down
        with it: the failures are counted and named back, because "18 of 20
        attached, these two are already in Retail" is a sentence somebody can
        act on and a stack trace is not.
        """
        self._require_write()
        wanted = [int(d) for d in (department_ids or []) if d][:MAX_DIVISIONS]
        if not wanted:
            raise UserError(_("Tick at least one department first."))
        done, failed = 0, []
        for department_id in wanted:
            try:
                self._attach(division_id, department_id, date_from)
                done += 1
            except Exception as e:      # noqa: BLE001 - one bad row, not all
                _logger.info('Attach refused for department %s: %s',
                             department_id, e)
                failed.append(department_id)
        room = self.get_room()
        room['attached'] = done
        room['attach_failed'] = len(failed)
        return room

    @api.model
    def detach(self, link_id, date_to=None):
        """Close an attachment with a date. The row stays: it is history."""
        self._require_write()
        link = self.env['pb.division.link'].sudo().browse(
            int(link_id or 0)).exists()
        if not link:
            raise UserError(_("That attachment is no longer here."))
        day = fields.Date.to_date(date_to) if date_to else \
            fields.Date.context_today(self)
        if day < link.date_from:
            # An attachment that has not started yet never happened, so there
            # is no history to keep and the row goes. One that HAS started
            # cannot be ended before it began — and the refusal names the day
            # it began, so the person can just use it.
            if link.date_from > fields.Date.context_today(self):
                link.unlink()
            else:
                raise UserError(_(
                    "%(department)s joined %(division)s on %(since)s. Pick "
                    "that day or a later one to take it out.",
                    department=link.department_id.complete_name
                    or link.department_id.name,
                    division=link.division_id.name,
                    since=fields.Date.to_string(link.date_from)))
        else:
            link.write({'date_to': day})
        return self.get_room()

    @api.model
    def accept_suggestions(self, suggestions):
        """Create the divisions a person ticked, and attach their departments.

        A suggestion that matches a division already here ADDS to it instead
        of making a second one with the same name.
        """
        self._require_write()
        Division = self.env['pb.division'].sudo()
        existing = {fold(d.name): d for d in Division.search([])}
        colour = Division.search_count([]) or 0
        for item in (suggestions or [])[:MAX_SUGGESTIONS]:
            name = self._clean_name((item or {}).get('name'))
            department_ids = [int(d) for d in (item.get('departments') or [])
                              if d]
            if not department_ids:
                continue
            division = existing.get(fold(name))
            if not division:
                division = Division.create({
                    'name': name,
                    'color': colour % COLOUR_COUNT,
                    'sequence': 10 + colour,
                })
                existing[fold(name)] = division
                colour += 1
            for department_id in department_ids:
                self._safe(
                    lambda d=division, p=department_id: self._attach(d.id, p),
                    default=None)
        return self.get_room()
