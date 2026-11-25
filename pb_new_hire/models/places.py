# -*- coding: utf-8 -*-
"""NEWHIRE P7 — step 2 starts with the Country of work (owner request
2026-11-25: "based on the value of that field the remaining fields get
populated… the teams should be only those belonging to India. Same with job.
And 'What this decides' follows it").

WHICH TEAMS BELONG TO A COUNTRY (the rule, built from what the product knows):
  a. the pay scheme that pays the team is of that country — the team's OWN
     map line or its division's (`pb.scheme.map.resolve_for_teams`, rungs
     department / division). "The company's only scheme" says nothing about a
     team, so it is not counted;
  b. at least one active person of the team has that Country of Work;
  c. (an explicit country on the team) — no such field exists on this build.
A team with neither signal is "Other teams": always offered, never hidden.
A team whose signals all point elsewhere is behind "Show teams from other
countries". Filtering is guidance only: the create path still accepts any
team with any country (ledger D2 as amended by P7).

Everything step 2 needs when the country changes comes from ONE call,
`places()`: the team groups, the jobs held in that country, the managers and
sites first in that country, whether the chosen team and job still fit, and
"What this decides" (the same `decides()`). Three grouped reads and one map
read, whatever the number of teams (no N+1).
"""
import logging

from odoo import _, api, models

from .studio import _int

_logger = logging.getLogger(__name__)

#: The scheme rungs that say something about the TEAM (not "the only scheme").
TEAM_RUNGS = ('department', 'division')


class PbNewHirePlaces(models.AbstractModel):
    _inherit = 'pb.new.hire'

    # ================================================================ reads
    @api.model
    def _people_by(self, field, codes=None, ids=None):
        """`{(<field> id, country code): count}` of the company's active
        people with a Country of Work — one grouped read."""
        company = self._company()
        domain = [('company_id', '=', company.id), ('active', '=', True),
                  ('payroll_country', '!=', False), (field, '!=', False)]
        if ids is not None:
            domain.append((field, 'in', list(ids)))
        if codes:
            domain.append(('payroll_country', 'in', list(codes)))
        out = {}
        for rec, code, count in self.env['hr.employee'].sudo()._read_group(
                domain, [field, 'payroll_country'], ['__count']):
            out[(rec.id, code)] = count
        return out

    @api.model
    def _country_counts(self):
        """`{code: active people}` of the company, by Country of Work."""
        company = self._company()
        out = {}
        for code, count in self.env['hr.employee'].sudo()._read_group(
                [('company_id', '=', company.id), ('active', '=', True),
                 ('payroll_country', '!=', False)], ['payroll_country'], ['__count']):
            out[code] = count
        return out

    @api.model
    def _team_scheme_countries(self, team_ids):
        """`{team id: scheme country}` for the teams their own map line (or
        their division's) pays — rule (a)."""
        if not team_ids:
            return {}
        company = self._company()
        answers = self.env['pb.scheme.map'].sudo().resolve_for_teams(list(team_ids), company.id)
        config_ids = {a['config_id'] for a in answers.values()
                      if a.get('config_id') and a.get('rung') in TEAM_RUNGS}
        codes = {c.id: c.country_code for c in
                 self.env['hr.formula.config'].sudo().browse(sorted(config_ids)).exists()}
        return {t: codes.get(a['config_id']) for t, a in answers.items()
                if a.get('rung') in TEAM_RUNGS and codes.get(a.get('config_id'))}

    @api.model
    def _team_ids(self):
        company = self._company()
        return self.env['hr.department'].sudo().search(
            [('company_id', 'in', [company.id, False])], limit=5000).ids

    # ================================================================ the rule
    @api.model
    def _team_groups(self, code, team_ids=None):
        """`(mine, other, unknown, counts)`: team ids that belong to `code`,
        that clearly belong elsewhere, that say nothing; and `{team id: people
        in code}`."""
        team_ids = self._team_ids() if team_ids is None else list(team_ids)
        schemes = self._team_scheme_countries(team_ids)
        people = self._people_by('department_id', ids=team_ids)
        countries_of = {}
        for (team_id, ccode), count in people.items():
            countries_of.setdefault(team_id, {})[ccode] = count
        mine, other, unknown, counts = [], [], [], {}
        for team_id in team_ids:
            theirs = countries_of.get(team_id, {})
            counts[team_id] = theirs.get(code, 0)
            if schemes.get(team_id) == code or theirs.get(code):
                mine.append(team_id)
            elif schemes.get(team_id) or theirs:
                other.append(team_id)
            else:
                unknown.append(team_id)
        return mine, other, unknown, counts

    @api.model
    def _team_country(self, team):
        """The country a team's new person most likely works in (P7 §1.7):
        the scheme that pays the team (any rung, as `team_defaults` always
        said), else where most of its active people work, else ''."""
        if not team:
            return ''
        codes = dict(self._countries())
        answer = self.env['pb.scheme.map'].sudo().resolve_for_team(team.id, self._company().id)
        config = self.env['hr.formula.config'].sudo().browse(answer.get('config_id') or 0).exists()
        if config and config.country_code in codes:
            return config.country_code
        people = self._people_by('department_id', ids=[team.id])
        best = sorted(((n, c) for (t, c), n in people.items() if c in codes), reverse=True)
        return best[0][1] if best else ''

    @api.model
    def _default_country(self):
        """`(code, why)` — step 2's starting country (P7 §1.2): the company's
        country when the company works in one country; otherwise the country
        most of its active people work in. (The screen puts the user's last
        pick in this browser session first.)"""
        codes = dict(self._countries())
        company_code = self._company().country_id.code or ''
        used = {c: n for c, n in self._country_counts().items() if c in codes}
        if company_code in codes and (not used or set(used) == {company_code}):
            return company_code, 'company'
        if used:
            best = max(used, key=lambda c: (used[c], c == company_code))
            return best, 'most'
        return (company_code, 'company') if company_code in codes else ('', '')

    @api.model
    def _known_countries(self):
        """Countries the company already has people, pay schemes or its own
        papers list for (they come first in the list)."""
        codes = dict(self._countries())
        company = self._company()
        known = {c for c in self._country_counts() if c in codes}
        Config = self.env['hr.formula.config'].sudo()
        for code in Config.search([('state', '=', 'active'), '|', ('company_id', '=', False),
                                   ('company_id', '=', company.id)]).mapped('country_code'):
            if code in codes:
                known.add(code)
        Paper = self.env['pb.new.hire.paper'].sudo().with_context(active_test=False)
        for code in Paper.search([('company_id', '=', company.id)]).mapped('country_code'):
            if code in codes:
                known.add(code)
        return known

    # ================================================================ places
    @api.model
    def places(self, country_code, department_id=False, job_id=False, date_start=False,
               contract_kind='permanent', clear=False):
        """Step 2 for one Country of work, in one call. `clear`: the person
        just CHANGED the country — "What this decides" is then worked out
        without a team that does not fit (the screen clears it, with Undo);
        otherwise with the chosen team, whatever its country (a team picked
        from "other countries" keeps the mismatch warning)."""
        self._gate()
        codes = dict(self._countries())
        code = country_code if country_code in codes else ''
        out = {'country': code, 'country_name': codes.get(code, ''),
               'teams': {'mine': [], 'other': [], 'unknown': []}, 'team_people': {},
               'jobs': [], 'managers': [], 'sites': [],
               'team_fits': None, 'job_fits': None, 'team_reason': '', 'decides': False}
        team = self._team(department_id)
        job = self._job(job_id)
        if code:
            mine, other, unknown, counts = self._team_groups(code)
            out['teams'] = {'mine': mine, 'other': other, 'unknown': unknown}
            out['team_people'] = {str(k): v for k, v in counts.items() if v}
            held = self._people_by('job_id', codes=[code])
            out['jobs'] = sorted(j for (j, _c) in held)
            out['sites'] = sorted(s for (s, _c) in self._people_by('work_location_id', codes=[code])) \
                if 'work_location_id' in self.env['hr.employee']._fields else []
            out['managers'] = self._managers_in(code)
            if team:
                out['team_fits'] = team.id not in other
                if not out['team_fits']:
                    out['team_reason'] = _("%(team)s has no one in %(country)s.",
                                           team=team.name or '', country=codes[code])
                    out['job_fits'] = not (job and job.department_id == team)
                else:
                    out['job_fits'] = True
        keep = team if (team and (not clear or out['team_fits'] is not False)) \
            else self.env['hr.department']
        if code or keep:
            out['decides'] = self.decides(keep.id or False, code or False, date_start, contract_kind)
        return out

    @api.model
    def _managers_in(self, code, limit=20):
        """The manager picker's first list: people working in that country."""
        company = self._company()
        people = self.env['hr.employee'].sudo().search(
            [('active', '=', True), ('company_id', '=', company.id), ('payroll_country', '=', code)],
            order='name, id', limit=limit)
        return [{'id': e.id, 'name': e.name or '', 'job': e.job_title or e.job_id.name or '',
                 'team': e.department_id.name or ''} for e in people]
