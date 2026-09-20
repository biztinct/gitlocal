# -*- coding: utf-8 -*-
"""`pb.scheme.map` — the one answer to "which scheme pays this person?".

WHY THIS EXISTS
---------------
Until now nothing on a person said which payroll scheme paid them. The pay run
took everybody with a running contract and each payslip worked its scheme out
afterwards, on its own, down a ladder that ended in "the first active scheme I
can find" (`hr.payslip._find_formula_config`). On one company with one scheme
that is right every time. On a group with fifteen it is a coin toss, and the
tell is that a payslip and the person beside it can disagree.

So the map becomes the truth, and this model is the only thing that reads it.
Every caller — the pay run's population, the payslip ladder, the "Paid by"
field on a person, the exceptions queue, the canvas' coverage rings — asks the
same question here and gets the same answer with the same reason attached.

THE LADDER, AND WHY IT ENDS WHERE IT DOES
-----------------------------------------
    1. segment       P5. A confirmed stretch of days says where this person
                     worked and, when somebody named one, which scheme pays
                     those days. It is the most specific statement there is —
                     a person went to the trouble of drawing it on a calendar
                     — so nothing below it can beat it. It answers only for
                     the employments a segment actually names; everybody else
                     falls straight through to rung 2 exactly as before, which
                     is what keeps this rung free on every database that has
                     never written a segment.
    2. department    the person's own team, then its parent, then its parent's
                     parent. Attaching at the top of a branch covers the branch;
                     a team further down overrides it, because the more specific
                     statement is the one somebody went to the trouble of making.
    3. division      the part of the business the team belongs to (P1's
                     `pb.division`), which is how one attachment covers the same
                     line of business in four countries.
    4. rule          the advanced escape hatch that already existed: an employee
                     domain, in `sequence` order.
    5. only scheme   the company has exactly one active scheme. THIS RUNG IS THE
                     WHOLE OF LEDGER RULE 8: a company that has never drawn a map
                     must behave exactly as it did before this module existed.
    6. nobody        and it says so by name, rather than picking something.

WHY `resolve_many` IS NOT A LOOP
--------------------------------
Company 5 has 4,533 people. Resolving them one at a time is 4,533 department
reads, 4,533 map searches and a division walk each. `resolve_many` does the
department read as ONE query, the map as ONE search, the division links as ONE
search, and then walks `parent_path` strings in Python — which is where the
walk always belonged, because a chain is four integers.

NOTHING HERE WRITES except `accept_draft`, which is the one method a person
presses a button for.
"""

import logging
import time
from collections import defaultdict

from odoo import _, api, fields, models

from .formula_scheme_assignment import CYCLE_WORDS

_logger = logging.getLogger(__name__)

#: The rungs, in the order they are tried. Exported so a test can assert the
#: order rather than a behaviour that happens to look like it.
RUNGS = ('segment', 'department', 'division', 'rule', 'only', 'none')

#: Caps on anything a caller controls — this model is reachable over JSON-RPC.
MAX_EMPLOYEES = 20000
MAX_NAMED = 200
MAX_SLIPS = 200000
MAX_DRAFT_ROWS = 200

#: How far back "what you actually paid" looks, and how many runs count.
DRAFT_MONTHS = 24
DRAFT_RUNS = 3
#: Below this share of agreement a proposal is amber and says what disagreed.
DRAFT_CONFIDENT = 0.9


class PbSchemeMap(models.AbstractModel):
    _name = 'pb.scheme.map'
    _description = 'Who is paid by what'

    # ==================================================================== bits
    @api.model
    def _as_company_id(self, company=None):
        if isinstance(company, models.BaseModel):
            return company[:1].id
        if isinstance(company, (int, float)) and int(company):
            return int(company)
        return self.env.company.id

    @api.model
    def cycle_words(self, cycle_type):
        """The kind of run, in words a person uses."""
        return _(CYCLE_WORDS.get(cycle_type or 'any', 'any kind of run'))

    # ============================================================ the roster
    @api.model
    def _departments_for(self, employee_ids=None, company_ids=None):
        """`{employee_id: (department_id, company_id)}` as ONE query.

        The team comes from the open contract when it names one and from the
        person's current record otherwise — one code path that answers both
        databases (WFPLAN WF7). Counts and ids only; no pay, no names.
        """
        cr = self.env.cr
        where, args = ['e.active'], []
        if employee_ids:
            where.append('e.id = ANY(%s)')
            args.append([int(i) for i in employee_ids])
        if company_ids:
            where.append('e.company_id = ANY(%s)')
            args.append([int(c) for c in company_ids])
        if 'hr.contract' in self.env:
            sql = """
                WITH open_contract AS (
                    SELECT DISTINCT ON (employee_id)
                           employee_id, department_id
                      FROM hr_contract
                     WHERE state = 'open'
                     ORDER BY employee_id, wage DESC NULLS LAST, id DESC
                )
                SELECT e.id,
                       COALESCE(c.department_id, v.department_id),
                       e.company_id
                  FROM hr_employee e
             LEFT JOIN hr_version v    ON v.id = e.current_version_id
             LEFT JOIN open_contract c ON c.employee_id = e.id
                 WHERE {where}
            """.format(where=' AND '.join(where))
        else:
            sql = """
                SELECT e.id, v.department_id, e.company_id
                  FROM hr_employee e
             LEFT JOIN hr_version v ON v.id = e.current_version_id
                 WHERE {where}
            """.format(where=' AND '.join(where))
        cr.execute(sql, args)
        return {row[0]: (row[1] or 0, row[2] or 0)
                for row in cr.fetchall()[:MAX_EMPLOYEES]}

    @api.model
    def _chains(self, company_ids=None):
        """`{department_id: [root_id, …, own_id]}` for every department."""
        cr = self.env.cr
        if company_ids:
            cr.execute("SELECT id, parent_path, company_id, parent_id "
                       "FROM hr_department WHERE company_id = ANY(%s)",
                       ([int(c) for c in company_ids],))
        else:
            cr.execute("SELECT id, parent_path, company_id, parent_id "
                       "FROM hr_department")
        out, meta = {}, {}
        for dept_id, path, company_id, parent_id in cr.fetchall():
            clean = (path or '').strip('/')
            out[dept_id] = ([int(p) for p in clean.split('/') if p]
                            if clean else [dept_id])
            meta[dept_id] = {'company_id': company_id or 0,
                             'parent_id': parent_id or 0}
        return out, meta

    @api.model
    def _department_names(self, dept_ids):
        if not dept_ids:
            return {}
        rows = self.env['hr.department'].sudo().with_context(
            active_test=False).browse(sorted({int(d) for d in dept_ids if d}))
        return {d.id: (d.complete_name or d.name or '')
                for d in rows.exists()}

    # ============================================================== the map
    @api.model
    def _map_rows(self, company_ids):
        """The active map, read once.

        A scheme with no company is shared, so its rows travel with it — the
        same reasoning `_find_formula_config` already applies to configs.
        """
        domain = [('active', '=', True), ('config_id.state', '=', 'active')]
        if company_ids:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', [int(c) for c in company_ids])]
        return self.env['hr.formula.scheme.assignment'].sudo().search(
            domain, order='sequence, id')

    @api.model
    def _by_department(self, rows):
        """`{department_id: {cycle_type: row}}`, first row wins."""
        out = defaultdict(dict)
        for row in rows:
            if not row.department_id:
                continue
            out[row.department_id.id].setdefault(row.cycle_type, row)
        return out

    @api.model
    def _by_division(self, rows):
        out = defaultdict(dict)
        for row in rows:
            if not row.division_id:
                continue
            out[row.division_id.id].setdefault(row.cycle_type, row)
        return out

    @api.model
    def _division_of_department(self, on_date=None):
        """`{department_id: division_id}` for the attachments live on a date."""
        if 'pb.division' not in self.env:
            return {}
        try:
            return self.env['pb.division'].sudo()._links_on(on_date)
        except Exception:       # noqa: BLE001 — a missing division board is
            _logger.debug('Divisions could not be read for the scheme map')
            return {}

    @staticmethod
    def _pick(bucket, cycle_type):
        """The line on the map that answers this question.

        Asked about a KIND of run, the line naming that kind wins and a line
        that says "any kind" is the fallback — the specific statement beats the
        general one, which is the whole reason the field exists.

        Asked about NO PARTICULAR kind ("who pays this person?"), a line saying
        "any kind" is still the best answer, but a map made entirely of
        specific lines must not read as no map at all. That is exactly what
        happened on the demo company the first time the map was drafted: every
        line was end-of-month or mid-month, nothing said "any", and the board
        reported 0 of 4,533 people covered over a map it had just written. So
        the fallback runs down a ladder of what "the scheme that pays you"
        normally means, and a MID-MONTH ADVANCE is last on it — an advance is
        never the answer to "who pays this person" unless somebody asked for
        the advance.
        """
        if not bucket:
            return None
        if cycle_type and cycle_type != 'any':
            if cycle_type in bucket:
                return bucket[cycle_type]
            return bucket.get('any')
        for kind in ('any', 'end_cycle', 'regular', 'full_final', 'mid_cycle'):
            if kind in bucket:
                return bucket[kind]
        return None

    # ========================================================= the only scheme
    @api.model
    def _only_scheme(self, company_id, cycle_type='any'):
        """The company's single active scheme, or an empty recordset.

        LEDGER RULE 8 LIVES HERE. A company with one scheme and no map must
        behave exactly as it did before this module existed, and the way that
        is guaranteed is that the ladder reaches this rung before it reaches
        "nobody".
        """
        Config = self.env['hr.formula.config'].sudo()
        domain = [('state', '=', 'active')]
        if company_id:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', int(company_id))]
        if cycle_type and cycle_type != 'any':
            domain.append(('cycle_type', '=', cycle_type))
        configs = Config.search(domain, limit=2)
        return configs if len(configs) == 1 else Config.browse()

    # =============================================================== resolve
    @api.model
    def resolve(self, employee, cycle_type='any', on_date=None):
        """`{config_id, config_name, rung, via}` for one person.

        Never raises and never guesses: an employee nobody's map covers comes
        back with `rung='none'` and a sentence saying so.
        """
        if isinstance(employee, models.BaseModel):
            employee_id = employee[:1].id
        else:
            employee_id = int(employee or 0)
        if not employee_id:
            return self._blank()
        answers = self.resolve_many([employee_id], cycle_type, on_date)
        return answers.get(employee_id) or self._blank()

    @api.model
    def _blank(self):
        return {'config_id': 0, 'config_name': '', 'rung': 'none',
                'via': _("No scheme covers this person yet.")}

    # =============================================================== rung 1
    @api.model
    def _segment_schemes(self, employee_ids, on_date=None):
        """`{employee_id: answer}` for the employments a segment names.

        SOFT, like every other cross-module read in this file: a database
        without `pb_workseg` never reaches the search, and one that has it but
        has never written a segment gets an empty dict for the price of one
        indexed search. Only a segment that NAMES a scheme answers here — a
        stretch of days with no scheme on it is a fact about where somebody
        worked, not a statement about who pays them, and the rungs below know
        how to answer that.
        """
        if 'pb.work.segment' not in self.env or not employee_ids:
            return {}
        day = fields.Date.to_date(on_date) if on_date else \
            fields.Date.context_today(self)
        try:
            rows = self.env['pb.work.segment'].sudo().search([
                ('state', '=', 'confirmed'),
                ('config_id', '!=', False),
                ('date_from', '<=', day), ('date_to', '>=', day),
                ('host_employee_id', 'in', list(employee_ids)),
            ], order='date_from desc, id desc')
        except Exception:       # noqa: BLE001 — a segment that cannot be read
            # must never stop a payslip resolving; the rungs below still
            # answer, exactly as they did before this rung existed.
            _logger.warning('Scheme map: work segments could not be read',
                            exc_info=True)
            return {}
        out = {}
        for row in rows:
            employee_id = row.host_employee_id.id
            if employee_id in out:
                continue
            out[employee_id] = {
                'config_id': row.config_id.id,
                'config_name': row.config_id.name or '',
                'rung': 'segment',
                'via': _("from the days worked in %(company)s",
                         company=row.host_company_id.name or ''),
            }
        return out

    @api.model
    def resolve_many(self, employee_ids, cycle_type='any', on_date=None):
        """The same answer for thousands of people, in a handful of queries."""
        ids = [int(e) for e in (employee_ids or []) if e][:MAX_EMPLOYEES]
        if not ids:
            return {}
        roster = self._departments_for(employee_ids=ids)
        if not roster:
            return {}
        company_ids = sorted({c for _d, c in roster.values() if c})
        chains, _meta = self._chains(company_ids)
        rows = self._map_rows(company_ids)
        by_department = self._by_department(rows)
        by_division = self._by_division(rows)
        division_of = self._division_of_department(on_date)
        rule_rows = [r for r in rows if r.domain and not r.department_id
                     and not r.division_id]
        # Every team a sentence could NAME: the person's own, and every team
        # the map is attached to. Resolving only the person's own team made
        # "from Bread's team map" read "from this team's team map" whenever the
        # attachment was on the team ABOVE them — which is the normal case.
        names = self._department_names(
            {d for d, _c in roster.values() if d} | set(by_department))

        # The rules, once each rather than once per person: an employee domain
        # over 4,500 people is a search, and 4,500 searches is a minute.
        rule_hits = []
        for row in rule_rows:
            try:
                matched = self.env['hr.employee'].sudo().search(
                    [('id', 'in', ids)] + row._employee_domain())
            except Exception:   # noqa: BLE001 — a broken rule is not fatal
                _logger.warning('Scheme map: rule %s could not be read', row.id)
                continue
            if matched:
                rule_hits.append((row, set(matched.ids)))

        # 1 — the segments. Read ONCE for the whole roster and only where the
        # module that owns them is installed; an empty answer costs one
        # search that returns nothing.
        by_segment = self._segment_schemes(ids, on_date)

        only_cache = {}
        out = {}
        for employee_id, (dept_id, company_id) in roster.items():
            chain = chains.get(dept_id) or ([dept_id] if dept_id else [])

            # 1 — a stretch of days somebody drew, naming its own scheme.
            segment = by_segment.get(employee_id)
            if segment:
                out[employee_id] = segment
                continue

            # 2 — the department map, deepest first.
            found = None
            for candidate in reversed(chain):
                found = self._pick(by_department.get(candidate), cycle_type)
                if found:
                    out[employee_id] = {
                        'config_id': found.config_id.id,
                        'config_name': found.config_id.name or '',
                        'rung': 'department',
                        'via': _("from %(team)s's team map",
                                 team=names.get(candidate)
                                 or _("this team")),
                    }
                    break
            if employee_id in out:
                continue

            # 3 — the division the team belongs to.
            division_id = 0
            for candidate in reversed(chain):
                if candidate in division_of:
                    division_id = division_of[candidate]
                    break
            if division_id:
                found = self._pick(by_division.get(division_id), cycle_type)
                if found:
                    out[employee_id] = {
                        'config_id': found.config_id.id,
                        'config_name': found.config_id.name or '',
                        'rung': 'division',
                        'via': _("from the %(division)s division",
                                 division=found.division_id.name or ''),
                    }
                    continue

            # 4 — an advanced rule.
            hit = None
            for row, matched in rule_hits:
                if employee_id in matched:
                    hit = row
                    break
            if hit:
                out[employee_id] = {
                    'config_id': hit.config_id.id,
                    'config_name': hit.config_id.name or '',
                    'rung': 'rule',
                    'via': _("from a rule on the map"),
                }
                continue

            # 5 — the company's only scheme. Rule 8.
            key = (company_id, cycle_type)
            if key not in only_cache:
                only_cache[key] = self._only_scheme(company_id, cycle_type)
            single = only_cache[key]
            if single:
                out[employee_id] = {
                    'config_id': single.id,
                    'config_name': single.name or '',
                    'rung': 'only',
                    'via': _("the only scheme in this company"),
                }
                continue

            # 6 — nobody, and it says so.
            out[employee_id] = self._blank()
        return out

    # ============================================================== coverage
    @api.model
    def coverage(self, company_id=None, cycle_type='any', limit=MAX_NAMED):
        """Who this company's map covers for this kind of run, and who it does not."""
        company_id = self._as_company_id(company_id)
        started = time.time()
        roster = self._departments_for(company_ids=[company_id])
        answers = self.resolve_many(list(roster), cycle_type)
        by_config = defaultdict(int)
        # Uncovered people PER TEAM, uncapped, so the board can say "all
        # covered" or "12 not covered" beside each team rather than putting one
        # number at the top and leaving every row to guess.
        missing_by_department = defaultdict(int)
        not_covered, covered = [], 0
        dept_names = self._department_names({d for d, _c in roster.values()})
        Employee = self.env['hr.employee'].sudo()
        uncovered_ids = []
        for employee_id, answer in answers.items():
            if answer['config_id']:
                covered += 1
                by_config[answer['config_id']] += 1
            else:
                uncovered_ids.append(employee_id)
                missing_by_department[roster.get(employee_id, (0, 0))[0]] += 1
        for employee in Employee.browse(uncovered_ids[:int(limit or MAX_NAMED)]):
            dept_id = roster.get(employee.id, (0, 0))[0]
            not_covered.append({
                'employee_id': employee.id,
                'name': employee.name or '',
                'department_id': dept_id,
                'department': dept_names.get(dept_id, ''),
                'reason': (_("Their team is not attached to a scheme yet.")
                           if dept_id
                           else _("They are not in a team, so no team map "
                                  "can reach them.")),
            })
        return {
            'company_id': company_id,
            'cycle_type': cycle_type,
            'people': len(roster),
            'covered': covered,
            'not_covered_total': len(uncovered_ids),
            'not_covered': not_covered,
            'by_config': {str(k): v for k, v in by_config.items()},
            'by_department': {str(k): v
                              for k, v in missing_by_department.items()},
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def get_exceptions(self, company_id=None, cycle_type='any',
                       limit=MAX_NAMED):
        """The people nobody pays, by name — the queue the canvas shows."""
        answer = self.coverage(company_id, cycle_type, limit)
        return {
            'company_id': answer['company_id'],
            'cycle_type': cycle_type,
            'total': answer['not_covered_total'],
            'people': answer['not_covered'],
        }

    # ================================================================= draft
    @api.model
    def _paid_history(self, company_id):
        """Every payslip that named a scheme, recently. Ids only."""
        cr = self.env.cr
        since = fields.Date.subtract(fields.Date.context_today(self),
                                     months=DRAFT_MONTHS)
        cr.execute("""
            SELECT s.employee_id, s.formula_config_id, fc.cycle_type,
                   COALESCE(s.payslip_run_id, 0), COALESCE(r.date_end, s.date_to)
              FROM hr_payslip s
              JOIN hr_formula_config fc ON fc.id = s.formula_config_id
         LEFT JOIN hr_payslip_run r ON r.id = s.payslip_run_id
             WHERE s.company_id = %s
               AND s.formula_config_id IS NOT NULL
               AND COALESCE(r.date_end, s.date_to) >= %s
             LIMIT %s
        """, (int(company_id), since, MAX_SLIPS))
        return cr.fetchall()

    @api.model
    def draft(self, company_id=None):
        """Propose the map that the last runs say is already true.

        For every team, per kind of run: among the three most recent runs that
        actually contain that team's people, the scheme that paid most of them.
        The share of agreement rides along, so a proposal can say "902 of 902"
        or "410 of 700, and the other 290 were paid under something else".

        Writes NOTHING.
        """
        company_id = self._as_company_id(company_id)
        started = time.time()
        roster = self._departments_for(company_ids=[company_id])
        chains, meta = self._chains([company_id])
        history = self._paid_history(company_id)
        if not history:
            return {'company_id': company_id, 'rows': [], 'ms': 0,
                    'reason': 'no_history'}

        # A payslip belongs to every department up its person's chain, so a
        # scheme attached at the top of a branch can be proposed from what the
        # branch was actually paid.
        # (department, cycle) -> run_id -> date_end
        runs = defaultdict(dict)
        # (department, cycle, run_id) -> {config_id: count}
        tally = defaultdict(lambda: defaultdict(int))
        for employee_id, config_id, cycle, run_id, date_end in history:
            dept_id = roster.get(employee_id, (0, 0))[0]
            if not dept_id:
                continue
            for candidate in (chains.get(dept_id) or [dept_id]):
                runs[(candidate, cycle)][run_id] = date_end
                tally[(candidate, cycle, run_id)][config_id] += 1

        configs = {c.id: c for c in self.env['hr.formula.config'].sudo().browse(
            sorted({row[1] for row in history})).exists()}
        names = self._department_names(set(chains))
        existing = self._by_department(self._map_rows([company_id]))

        stats = {}
        for (dept_id, cycle), seen in runs.items():
            recent = sorted(seen.items(), key=lambda kv: (kv[1] or fields.Date
                                                          .context_today(self),
                                                          kv[0]),
                            reverse=True)[:DRAFT_RUNS]
            counts = defaultdict(int)
            for run_id, _day in recent:
                for config_id, n in tally[(dept_id, cycle, run_id)].items():
                    counts[config_id] += n
            total = sum(counts.values())
            if not total:
                continue
            winner, agree = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
            stats[(dept_id, cycle)] = {
                'config_id': winner, 'agree': agree, 'total': total,
                'share': round(agree / float(total), 4),
                'runs': len(recent),
            }

        cycles = sorted({cycle for _d, cycle in stats})
        rows = []
        for cycle in cycles:
            tops = [d for d in chains
                    if not meta.get(d, {}).get('parent_id')
                    and (d, cycle) in stats]
            for dept_id in sorted(tops, key=lambda d: -stats[(d, cycle)]['total']):
                rows.extend(self._draft_rows(dept_id, cycle, stats, chains,
                                             meta, names, configs, existing))
        rows = rows[:MAX_DRAFT_ROWS]
        return {
            'company_id': company_id, 'rows': rows,
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def _draft_rows(self, dept_id, cycle, stats, chains, meta, names, configs,
                    existing, depth=0):
        """One proposal for this team, and — when its people disagree — one for
        each child team that disagrees with it."""
        stat = stats.get((dept_id, cycle))
        if not stat:
            return []
        rows = [self._draft_row(dept_id, cycle, stat, names, configs, existing)]
        if stat['share'] >= DRAFT_CONFIDENT or depth >= 2:
            return rows
        children = [d for d, m in meta.items()
                    if m.get('parent_id') == dept_id and (d, cycle) in stats]
        for child in sorted(children, key=lambda d: -stats[(d, cycle)]['total']):
            if stats[(child, cycle)]['config_id'] == stat['config_id']:
                continue
            rows.extend(self._draft_rows(child, cycle, stats, chains, meta,
                                          names, configs, existing, depth + 1))
        return rows

    @api.model
    def _draft_row(self, dept_id, cycle, stat, names, configs, existing):
        config = configs.get(stat['config_id'])
        team = names.get(dept_id) or _("this team")
        kind = self.cycle_words(cycle)
        # A headcount in a SENTENCE is read, not calculated: "2,349" is a number
        # a person takes in at a glance and "2349" is a string they have to
        # count the digits of. The row's own figures stay numbers — the screen
        # draws a ring from them.
        agree, total = '{:,}'.format(stat['agree']), '{:,}'.format(stat['total'])
        if stat['agree'] == stat['total']:
            sentence = _(
                "Every one of %(team)s's %(total)s people on the last "
                "%(runs)s %(kind)s runs was paid under %(scheme)s.",
                team=team, total=total, runs=stat['runs'], kind=kind,
                scheme=config.name if config else '')
        else:
            sentence = _(
                "%(agree)s of %(team)s's %(total)s people on the last "
                "%(runs)s %(kind)s runs were paid under %(scheme)s — the rest "
                "were paid under something else.",
                agree=agree, team=team, total=total,
                runs=stat['runs'], kind=kind,
                scheme=config.name if config else '')
        already = (existing.get(dept_id) or {}).get(cycle)
        return {
            'department_id': dept_id,
            'department': team,
            'config_id': stat['config_id'],
            'config': config.name if config else '',
            'cycle_type': cycle,
            'cycle_label': kind,
            'confidence': stat['share'],
            'agree': stat['agree'],
            'total': stat['total'],
            'runs': stat['runs'],
            'confident': stat['share'] >= DRAFT_CONFIDENT,
            'already_id': already.id if already else 0,
            'already': (already.config_id.name or '') if already else '',
            'sentence': sentence,
        }

    @api.model
    def accept_draft(self, rows):
        """Write the proposals somebody ticked. The only writer in this file."""
        Assign = self.env['hr.formula.scheme.assignment']
        made, replaced = 0, 0
        for row in (rows or [])[:MAX_DRAFT_ROWS]:
            config_id = int(row.get('config_id') or 0)
            cycle = row.get('cycle_type') or 'any'
            department_id = int(row.get('department_id') or 0)
            division_id = int(row.get('division_id') or 0)
            if not config_id or not (department_id or division_id):
                continue
            base = [('active', '=', True), ('cycle_type', '=', cycle)]
            base += ([('department_id', '=', department_id)] if department_id
                     else [('division_id', '=', division_id)])
            clash = Assign.sudo().search(base)
            if clash:
                clash.unlink()
                replaced += len(clash)
            Assign.sudo().create({
                'config_id': config_id,
                'department_id': department_id or False,
                'division_id': division_id or False,
                'cycle_type': cycle,
                'source': 'accepted',
                'confidence': float(row.get('confidence') or 0.0),
                'note': (row.get('sentence') or '')[:250],
            })
            made += 1
        return {'created': made, 'replaced': replaced}
