# -*- coding: utf-8 -*-
"""PSCHEME P2a A, B and D.1 — the Mapping board, now that the pay scheme
belongs to the person.

A. A line on the map is a team's USUAL pay scheme: where new people start and
   what pays anybody without a scheme of their own (ledger R2). Each team row
   counts "N on the usual scheme" and "M have their own" (the names behind M
   are one press away), and the board says, once, how it works.
B. "Set for everyone in this team…" (ledger R8): the people of a team — and of
   the teams below it that have no usual scheme of their own — get a pay
   scheme of their own. People WITHOUT one are ticked and start on the first
   day of this month; people who already HAVE one are moved only when the
   reader ticks "Also move these people", from a date (default the 1st of next
   month, ruling R6). ONE request (`person_set_many`, source `team`), two
   groups when both are ticked. It never writes or changes a line on the map.
D.1 The universal net (ledger A14): a person paid by a scheme of another
   country than their Country of work is never changed silently — every
   screen that shows the pay scheme says so in one amber line, and the board
   lists them with "Change pay scheme" (bulk where one scheme fits them all).
"""

import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_scheme_map import ADVANCE_RUNGS, MAIN_QUESTION, SKIP_PERSON

_logger = logging.getLogger(__name__)

MAIN_KINDS = ('regular', 'end_cycle')
#: A map line that gives a team its USUAL (main) pay scheme. An advance-only
#: line does not: the team still follows the line above it for the month.
MAIN_LINE_KINDS = ('any', 'regular', 'end_cycle')
MAX_TEAM_PEOPLE = 5000
MAX_LISTED = 400


class PbSchemeBoardTeam(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ======================================================= who pays whom
    @api.model
    def _main_answers(self, company_id, employee_ids=None):
        """`(roster, {employee_id: answer})` — the company's main question
        ("who pays this person's month?"), ONE `resolve_many`."""
        Map = self.env['pb.scheme.map'].sudo()
        roster = Map._departments_for(company_ids=[company_id])
        ids = sorted(roster) if employee_ids is None else \
            [int(e) for e in employee_ids if int(e) in roster]
        main_cycle = self.env['hr.employee']._pb_main_cycle(company_id)
        answers = Map.with_context(**{MAIN_QUESTION: True}).resolve_many(
            ids, main_cycle) if ids else {}
        return roster, answers

    @api.model
    def _person_facts(self, company_id):
        """Everything the board's person counts need, read once:
        `{'roster', 'answers', 'own': {emp}, 'countries': {emp: code},
        'configs': {id: (country, kind)}}`."""
        roster, answers = self._main_answers(company_id)
        ids = list(roster)
        own = set()
        if ids:
            for (employee,) in self.env['pb.person.scheme'].sudo()._read_group(
                    [('employee_id', 'in', ids), ('active', '=', True)],
                    ['employee_id']):
                own.add(employee.id)
        countries = {}
        if ids:
            self.env.cr.execute(
                "SELECT id, payroll_country FROM hr_employee WHERE id = ANY(%s)",
                (ids,))
            countries = dict(self.env.cr.fetchall())
        config_ids = sorted({a['config_id'] for a in answers.values() if a.get('config_id')})
        configs = {}
        if config_ids:
            for c in self.env['hr.formula.config'].sudo().with_context(
                    active_test=False).browse(config_ids):
                configs[c.id] = (c.country_code or '', c.cycle_type or '', c.name or '')
        return {'roster': roster, 'answers': answers, 'own': own,
                'countries': countries, 'configs': configs}

    # ============================================================ the board
    @api.model
    def get_board(self, company_id=None, cycle_type='any'):
        board = super().get_board(company_id, cycle_type)
        if not board.get('allowed'):
            return board
        try:
            board['persons'] = self._board_persons(board)
        except Exception:       # noqa: BLE001 — one figure never takes the board down
            _logger.warning('Scheme map: person counts failed', exc_info=True)
            board['persons'] = {}
        return board

    @api.model
    def _board_persons(self, board):
        company_id = board['company_id']
        facts = self._person_facts(company_id)
        roster, answers, own = facts['roster'], facts['answers'], facts['own']
        chains, _meta = self.env['pb.scheme.map'].sudo()._chains([company_id])
        usual, mine = defaultdict(int), defaultdict(int)
        for employee_id, (dept_id, _c) in roster.items():
            answer = answers.get(employee_id) or {}
            bucket = mine if employee_id in own else (
                usual if answer.get('rung') in ('department', 'division') else None)
            if bucket is None or not dept_id:
                continue
            for candidate in (chains.get(dept_id) or [dept_id]):
                bucket[candidate] += 1
        mismatch = self._mismatch_rows(company_id, facts)
        for segment in board.get('segments') or []:
            for item in [segment] + list(segment.get('children') or []):
                if item.get('kind', 'department') != 'department':
                    continue
                item['usual'] = usual.get(item['id'], 0)
                item['own'] = mine.get(item['id'], 0)
        company = self.env['res.company'].sudo().browse(company_id)
        return {
            'people': len(roster),
            'own': len(own),
            'without': len(roster) - len(own),
            'mismatch': len(mismatch),
            'latest_fill': bool(self.env['pb.person.scheme.fill'].sudo().search_count(
                [('company_id', '=', company_id)], limit=1)),
            'can_propose': self._can_propose_person(),
            'lane': self._person_lane(company),
        }

    # ======================================== "M have their own" — the names
    @api.model
    def team_own_people(self, department_id, company_id=None):
        """The people of this team (and the teams below it) who have a pay
        scheme of their own: name, scheme, since when."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this company's people."))
        company_id = self._pick_company(company_id)
        dept = self._team_or_refuse(department_id, company_id)
        Map = self.env['pb.scheme.map'].sudo()
        roster = Map._departments_for(company_ids=[company_id])
        chains, _meta = Map._chains([company_id])
        ids = [e for e, (d, _c) in roster.items()
               if d and dept.id in (chains.get(d) or [d])]
        today = fields.Date.context_today(self)
        by_person = Map._person_schemes(ids, today)
        people = self.env['hr.employee'].sudo().browse(sorted(by_person)).exists()
        names = Map._department_names({roster[e][0] for e in by_person if roster[e][0]})
        out = []
        for person in people.sorted(lambda p: (p.name or '').lower()):
            rows = by_person[person.id]['rows']
            main = rows.get('end_cycle') or rows.get('regular')
            advance = rows.get('mid_cycle')
            out.append({
                'employee_id': person.id, 'name': person.name or '',
                'team': names.get(roster[person.id][0], ''),
                'scheme': main.config_id.name if main else '',
                'since_words': self._day_words(main.date_from) if main else '',
                'advance': advance.config_id.name if advance else '',
            })
        return {'department': dept.name or '', 'people': out[:MAX_LISTED],
                'total': len(out)}

    @api.model
    def _team_or_refuse(self, department_id, company_id):
        dept = self.env['hr.department'].sudo().browse(int(department_id or 0)).exists()
        if not dept or dept.company_id.id not in (company_id, False):
            raise UserError(_("That team is not in this company. Reload the "
                              "screen and try again."))
        return dept

    # ===================================== B. "Set for everyone in this team"
    @api.model
    def _team_members(self, dept, company_id):
        """The team's people, and the people of the teams below it that have
        no usual pay scheme of their own (a team further down with its own
        line is its own business, and so is everything under it)."""
        Map = self.env['pb.scheme.map'].sudo()
        chains, _meta = Map._chains([company_id])
        lines = Map._map_rows([company_id])
        own_line = {r.department_id.id for r in lines if r.department_id
                    and (r.cycle_type or 'any') in MAIN_LINE_KINDS
                    and r.config_id.cycle_type in MAIN_KINDS}
        teams = []
        for dept_id, chain in chains.items():
            if dept.id not in chain:
                continue
            below = chain[chain.index(dept.id) + 1:]
            if any(d in own_line for d in below):
                continue
            teams.append(dept_id)
        roster = Map._departments_for(company_ids=[company_id])
        people = [e for e, (d, _c) in roster.items() if d in set(teams)]
        return teams, people[:MAX_TEAM_PEOPLE], roster

    @api.model
    def team_plan(self, department_id, company_id=None):
        """Everything the "Set for everyone in this team" drawer draws.
        Writes nothing."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this company's people."))
        company_id = self._pick_company(company_id)
        dept = self._team_or_refuse(department_id, company_id)
        company = self.env['res.company'].sudo().browse(company_id)
        Map = self.env['pb.scheme.map'].sudo()
        Config = self.env['hr.formula.config'].sudo()
        teams, ids, roster = self._team_members(dept, company_id)
        today = fields.Date.context_today(self)
        by_person = Map._person_schemes(ids, today)
        people = {}
        if ids:
            for rec in self.env['hr.employee'].sudo().search_read(
                    [('id', 'in', ids)], ['name', 'payroll_country']):
                people[rec['id']] = rec
        countries = defaultdict(int)
        for rec in people.values():
            if rec.get('payroll_country'):
                countries[rec['payroll_country']] += 1
        top = max(countries.items(), key=lambda kv: (kv[1], kv[0]))[0] if countries else ''
        main_cycle = self.env['hr.employee']._pb_main_cycle(company_id)
        usual = Map.resolve_for_team(dept.id, company_id, main_cycle)
        usual_cfg = Config.browse(usual.get('config_id') or 0).exists() \
            if usual.get('rung') in ('department', 'division') else Config
        if usual_cfg and usual_cfg.cycle_type not in MAIN_KINDS:
            usual_cfg = Config
        team_adv = Map.resolve_for_team(dept.id, company_id, 'mid_cycle')
        adv_cfg = Config.browse(team_adv.get('config_id') or 0).exists() \
            if team_adv.get('rung') in ('department', 'division') else Config
        if adv_cfg and (adv_cfg.cycle_type != 'mid_cycle' or adv_cfg.state != 'active'):
            adv_cfg = Config     # ledger A13: a line "for any kind of run" is no advance
        every = Config.search([
            ('state', '=', 'active'), ('cycle_type', 'in', MAIN_KINDS),
            '|', ('company_id', '=', False), ('company_id', '=', company_id)],
            order='name, id', limit=120)
        counts = {}
        for config, n in self.env['hr.employee'].sudo()._read_group(
                [('company_id', '=', company_id), ('active', '=', True),
                 ('pb_paid_by_id', '!=', False)], ['pb_paid_by_id'], ['__count']):
            counts[config.id] = n
        ordered = sorted(every, key=lambda c: (c.country_code != top, c.name or '', c.id))
        default = usual_cfg if usual_cfg and usual_cfg in every else (
            next((c for c in ordered if c.country_code == top), None) if top else None)
        names = Map._department_names(set(teams))
        rows = []
        for employee_id in ids:
            rec = people.get(employee_id) or {}
            entry = by_person.get(employee_id)
            row = {'id': employee_id, 'name': rec.get('name') or '',
                   'team': names.get(roster[employee_id][0], ''),
                   'country': rec.get('payroll_country') or '',
                   'own': None}
            if entry:
                rows_now = entry['rows']
                main = rows_now.get('end_cycle') or rows_now.get('regular')
                advance = rows_now.get('mid_cycle')
                row['own'] = {
                    'config_id': main.config_id.id if main else 0,
                    'scheme': main.config_id.name if main else '',
                    'since_words': self._day_words(main.date_from) if main else '',
                    'advance_id': advance.config_id.id if advance else 0,
                }
            # ticked by default: nobody's own scheme is replaced unasked
            # (R8), and nobody of another Country of work is given this one
            row['fits'] = not (row['country'] and default and default.country_code
                               and default.country_code != row['country'])
            row['tick'] = row['own'] is None and row['fits']
            rows.append(row)
        rows.sort(key=lambda r: (r['own'] is not None, r['team'].lower(), r['name'].lower()))
        labels = dict(Config._fields['country_code']._description_selection(self.env))
        first = today.replace(day=1)
        return {
            'department_id': dept.id,
            'department': dept.name or '',
            'teams': len(teams),
            'company_id': company_id,
            'country': top, 'country_name': labels.get(top, '') if top else '',
            'countries': {c: labels.get(c, c) for c in countries},
            'choices': [self._scheme_card(c, counts) for c in ordered],
            'default_id': default.id if default else 0,
            'usual_id': usual_cfg.id if usual_cfg else 0,
            'team_advance_id': adv_cfg.id if adv_cfg else 0,
            'advances': self._advance_pairs([c.id for c in ordered]),
            'advance_names': {str(c.id): c.name for c in Config.search([
                ('state', '=', 'active'), ('cycle_type', '=', 'mid_cycle'),
                '|', ('company_id', '=', False), ('company_id', '=', company_id)],
                limit=120)},
            'people': rows,
            'fill_date': fields.Date.to_string(first),
            'fill_date_words': self._day_words(first),
            'move_date': fields.Date.to_string(first + relativedelta(months=1)),
            'month_words': self._month_words(today),
            'today': fields.Date.to_string(today),
            'lane': self._person_lane(company),
            'blocked': self._person_blocked(company),
            'can_propose': self._can_propose_person(),
        }

    @api.model
    def team_apply(self, department_id, config_id, advance_config_id=False,
                   fill_ids=None, move_ids=None, move_date=None, company_id=None):
        """Give the ticked people of the team this pay scheme (see B above).
        The plan is worked out again here — the screen's copy is never
        trusted: a person no longer in the team, or who changed since, is
        left out and counted in `left_out`."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        company_id = self._pick_company(company_id)
        dept = self._team_or_refuse(department_id, company_id)
        Map = self.env['pb.scheme.map'].sudo()
        Config = self.env['hr.formula.config'].sudo()
        config = Config.browse(int(config_id or 0)).exists()
        if not config:
            raise UserError(_("Pick the pay scheme first."))
        advance = Config.browse(int(advance_config_id)).exists() \
            if advance_config_id else False
        _teams, ids, _roster = self._team_members(dept, company_id)
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        day = fields.Date.to_date(move_date) if move_date else first + relativedelta(months=1)
        by_person = Map._person_schemes(ids, today)
        without = {e for e in ids if e not in by_person}
        having = {e for e in ids if e in by_person}
        wanted_fill = {int(e) for e in fill_ids or [] if e}
        wanted_move = {int(e) for e in move_ids or [] if e}
        fill = sorted(wanted_fill & without)
        move = []
        # a mover is judged on the day they would move: already exactly this
        # from then on means nothing to do (asking twice writes nothing)
        on_day = Map._person_schemes(sorted(wanted_move & having), day)
        for employee_id in sorted(wanted_move & having):
            rows = (on_day.get(employee_id) or {}).get('rows') or {}
            main = rows.get('end_cycle') or rows.get('regular')
            now_adv = rows.get('mid_cycle')
            same_adv = (now_adv.config_id.id if now_adv else False) == (advance.id if advance else False)
            if main and main.config_id == config and same_adv:
                continue        # already exactly this — nothing to move
            move.append(employee_id)
        left_out = len((wanted_fill - without) | (wanted_move - having))
        groups = []
        if fill:
            groups.append({'employee_ids': fill, 'config_id': config.id,
                           'advance_config_id': advance.id if advance else False,
                           'date_from': fields.Date.to_string(first)})
        if move:
            groups.append({'employee_ids': move, 'config_id': config.id,
                           'advance_config_id': advance.id if advance else False,
                           'date_from': fields.Date.to_string(day)})
        if not groups:
            raise UserError(_("Nobody is ticked who needs this change. Tick "
                              "the people to give this pay scheme first."))
        title = _("Pay %(count)s people of %(team)s by %(scheme)s",
                  count=len(fill) + len(move), team=dept.name or '',
                  scheme=config.name or '')
        answer = self.person_set_many(groups, company_id, source='team', title=title)
        answer.update({'filled': len(fill), 'moved': len(move), 'left_out': left_out})
        return answer

    # ============================================== D.1 the universal net
    @api.model
    def _later_fixes(self, employee_ids, company_id):
        """`{employee_id: {config_id, …}}` — main-kind pay schemes that start
        after today (a later row) or wait for approval for each person."""
        today = fields.Date.context_today(self)
        out = defaultdict(set)
        if employee_ids:
            for row in self.env['pb.person.scheme'].sudo().search([
                    ('employee_id', 'in', list(employee_ids)), ('active', '=', True),
                    ('date_from', '>', today), ('cycle_type', 'in', list(MAIN_KINDS))]):
                out[row.employee_id.id].add(row.config_id.id)
        for employee_id, config_id in self._waiting_by_person(company_id).items():
            if config_id:
                out[employee_id].add(config_id)
        return out

    @api.model
    def _mismatch_rows(self, company_id, facts=None):
        """The people paid by a scheme of another country than their Country
        of work, not already fixed by a later row or a waiting change."""
        facts = facts or self._person_facts(company_id)
        answers, countries, configs = facts['answers'], facts['countries'], facts['configs']
        suspects = []
        for employee_id, answer in answers.items():
            country = countries.get(employee_id) or ''
            config = configs.get(answer.get('config_id') or 0)
            if not country or not config or not config[0] or config[0] == country:
                continue
            if config[1] not in MAIN_KINDS:
                continue
            suspects.append(employee_id)
        if not suspects:
            return []
        fixes = self._later_fixes(suspects, company_id)
        fix_countries = {}
        fix_ids = {c for s in fixes.values() for c in s}
        if fix_ids:
            for c in self.env['hr.formula.config'].sudo().with_context(
                    active_test=False).browse(sorted(fix_ids)):
                fix_countries[c.id] = c.country_code or ''
        out = []
        for employee_id in suspects:
            country = countries[employee_id]
            if any(fix_countries.get(c) == country for c in fixes.get(employee_id, ())):
                continue
            out.append(employee_id)
        return out

    @api.model
    def _country_target(self, company_id, country, team_answer=None):
        """The pay scheme a person of `country` would normally have: their
        team's usual one when it is of that country, else the country's only
        pay scheme; 0 when the reader has to choose."""
        Config = self.env['hr.formula.config'].sudo()
        if team_answer and team_answer.get('config_id') \
                and team_answer.get('rung') in ('department', 'division', 'rule', 'only'):
            config = Config.browse(team_answer['config_id']).exists()
            if config and config.country_code == country and config.cycle_type in MAIN_KINDS \
                    and config.state == 'active':
                return config.id
        schemes = self.env['pb.scheme.map'].sudo()._country_schemes(
            company_id, country).filtered(lambda c: c.cycle_type in MAIN_KINDS)
        return schemes.id if len(schemes) == 1 else 0

    @api.model
    def mismatch_people(self, company_id=None):
        """D.1 — the board's list: each person with today's pay scheme, their
        Country of work and the pay scheme that fits it (when one does)."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this company's people."))
        company_id = self._pick_company(company_id)
        facts = self._person_facts(company_id)
        ids = self._mismatch_rows(company_id, facts)
        Map = self.env['pb.scheme.map'].sudo()
        main_cycle = self.env['hr.employee']._pb_main_cycle(company_id)
        ladder = Map.with_context(**{SKIP_PERSON: True, MAIN_QUESTION: True}).resolve_many(
            ids, main_cycle) if ids else {}
        labels = dict(self.env['hr.formula.config']._fields['country_code']
                      ._description_selection(self.env))
        Config = self.env['hr.formula.config'].sudo()
        names = Map._department_names({facts['roster'][e][0] for e in ids if facts['roster'][e][0]})
        people = self.env['hr.employee'].sudo().browse(ids).exists()
        rows, targets = [], defaultdict(int)
        cache = {}
        for person in people.sorted(lambda p: (p.name or '').lower())[:MAX_LISTED]:
            country = facts['countries'].get(person.id) or ''
            config_id = facts['answers'][person.id]['config_id']
            key = (country, (ladder.get(person.id) or {}).get('config_id'))
            if key not in cache:
                cache[key] = self._country_target(company_id, country, ladder.get(person.id))
            target = cache[key]
            if target:
                targets[target] += 1
            rows.append({
                'employee_id': person.id, 'name': person.name or '',
                'team': names.get(facts['roster'][person.id][0], ''),
                'country': country, 'country_name': labels.get(country, country),
                'scheme': facts['configs'][config_id][2],
                'scheme_country_name': labels.get(facts['configs'][config_id][0], ''),
                'own': person.id in facts['own'],
                'target_id': target,
                'target': Config.browse(target).name if target else '',
            })
        one = list(targets) if len(targets) == 1 and sum(targets.values()) == len(rows) else []
        company = self.env['res.company'].sudo().browse(company_id)
        first_next = fields.Date.context_today(self).replace(day=1) + relativedelta(months=1)
        return {'people': rows, 'total': len(ids),
                'one_target_id': one[0] if one else 0,
                'one_target': Config.browse(one[0]).name if one else '',
                'date': fields.Date.to_string(first_next),
                'date_words': self._day_words(first_next),
                'lane': self._person_lane(company),
                'blocked': self._person_blocked(company),
                'can_propose': self._can_propose_person()}

    @api.model
    def mismatch_change(self, employee_ids, config_id, date_from=None, company_id=None):
        """"Change these N" — every listed person to the one pay scheme that
        fits them, from the 1st of next month, as ONE request. Each person's
        mid-month advance is kept only when it is of the new scheme's country
        (no cross-country advance, ruling R7)."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        company_id = self._pick_company(company_id)
        config = self.env['hr.formula.config'].sudo().browse(int(config_id or 0)).exists()
        if not config:
            raise UserError(_("Pick the pay scheme first."))
        wanted = {int(e) for e in employee_ids or [] if e}
        ids = [e for e in self._mismatch_rows(company_id) if e in wanted]
        if not ids:
            raise UserError(_("Nobody on this list needs the change any more. "
                              "Reload the screen."))
        day = fields.Date.to_date(date_from) if date_from else \
            fields.Date.context_today(self).replace(day=1) + relativedelta(months=1)
        Map = self.env['pb.scheme.map'].sudo()
        advances = Map.resolve_many(ids, 'mid_cycle', on_date=day)
        Config = self.env['hr.formula.config'].sudo()
        buckets = defaultdict(list)
        for employee_id in ids:
            answer = advances.get(employee_id) or {}
            advance = Config.browse(answer.get('config_id') or 0).exists() \
                if answer.get('rung') in ADVANCE_RUNGS else Config
            keep = advance and advance.cycle_type == 'mid_cycle' \
                and advance.country_code in (config.country_code, False)
            buckets[advance.id if keep else False].append(employee_id)
        groups = [{'employee_ids': people, 'config_id': config.id,
                   'advance_config_id': advance_id, 'date_from': fields.Date.to_string(day)}
                  for advance_id, people in buckets.items()]
        return self.person_set_many(groups, company_id, source='hand', title=_(
            "Pay %(count)s people by %(scheme)s, the pay scheme of their Country of work",
            count=len(ids), scheme=config.name or ''))
