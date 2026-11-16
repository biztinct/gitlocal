# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.voice`` — the ONE door to survey results (HR board, Excel download,
the manager's card on My Payobook).

"BELOW THE FLOOR, NOTHING" (the shape of ``get_pulse_tile`` in
pb_ess_workforce): a group with fewer answers than the floor returns no
number, no share, no comment — not a rounded figure, not the count. A client
cannot be trusted to hide a number it has been handed.

NO WORKING IT OUT BY SUBTRACTION. Hiding small groups is not enough: a
company of 40 answers shown next to its departments of 20 and 17 gives the
third department's 3 answers by subtraction. ``_plan`` therefore applies two
more rules to EVERY group anybody can be shown in a round — the companies
and departments on HR's page AND the teams on managers' cards — until
nothing changes:

  * PAIRS: two groups that overlap may not differ by fewer than the floor
    (either way). If they do, the smaller one is hidden too.
  * PARTS: a group minus all of its shown parts of one kind (a company minus
    its shown departments) may not leave fewer than the floor. If it does,
    the smallest shown part is hidden too.

Results open only when the round is CLOSED: figures that move while a round
is open would show one answer at a time to somebody watching.
"""

import io
import json
import logging

from odoo import api, fields, models
from odoo.tools import format_date
from odoo.exceptions import AccessError, UserError

from .voice_common import SCALE_WORDS

_logger = logging.getLogger(__name__)

_KIND_FINENESS = {'all': 0, 'company': 1, 'department': 2, 'team': 3}


class PbVoice(models.AbstractModel):
    _name = 'pb.voice'
    _description = 'Employee voice board and results'

    # ================================================================ gate
    @api.model
    def _gate(self):
        Round = self.env['pb.voice.round']
        if not Round._voice_is_hr():
            raise AccessError(self.env._("Employee surveys are run by HR."))
        return Round

    @api.model
    def _round_for_hr(self, round_id):
        """The round, readable by THIS HR person (record rules apply), and
        only when every company it asked is one they can see — otherwise a
        whole-round figure minus their own company would show another's."""
        Round = self._gate()
        rnd = Round.browse(int(round_id)).exists()
        if not rnd:
            raise UserError(self.env._("This survey no longer exists."))
        rnd.check_access('read')
        if not set(rnd.sudo().company_ids.ids) <= set(self.env.user.company_ids.ids):
            raise AccessError(self.env._(
                "This survey asked people in a company you cannot see."))
        return rnd

    # =============================================================== board
    @api.model
    def get_board(self):
        if not self.env['pb.voice.round']._voice_is_hr():
            return {'allowed': False,
                    'why': self.env._("Employee surveys are run by HR.")}
        Round = self.env['pb.voice.round']
        rounds = Round.search([], order='id desc', limit=80)
        rows = [self._round_row(r) for r in rounds]
        Action = self.env['pb.voice.action']
        open_actions = Action.search_count([('state', '!=', 'done')])
        late = Action.search_count([('state', '!=', 'done'),
                                    ('date_due', '<',
                                     fields.Date.context_today(self))])
        return {
            'allowed': True,
            'rounds': rows,
            'kpis': {
                'draft': sum(1 for r in rows if r['state'] == 'draft'),
                'open': sum(1 for r in rows if r['state'] == 'open'),
                'results': sum(1 for r in rows if r['result_state'] == 'kept'),
                'actions': open_actions,
                'late': late,
            },
            'mail_on': Round._voice_mail_on(),
            'floor': rounds[:1].floor if rounds else 5,
            'has_values': 'pb.company.value' in self.env,
        }

    @api.model
    def _round_row(self, rnd):
        states = dict(rnd._fields['state']._description_selection(self.env))
        rstates = dict(rnd._fields['result_state']._description_selection(self.env))
        answered = rnd.voice_answered_so_far()
        invited = rnd.invited_count
        return {
            'id': rnd.id, 'name': rnd.name, 'state': rnd.state,
            'state_label': states.get(rnd.state, ''),
            'result_state': rnd.result_state,
            'result_label': rstates.get(rnd.result_state, ''),
            'companies': ', '.join(rnd.sudo().company_ids.mapped('name')),
            'date_start': format_date(self.env, rnd.date_start) if rnd.date_start else '',
            'date_end': format_date(self.env, rnd.date_end) if rnd.date_end else '',
            'date_closed': format_date(self.env, rnd.date_closed) if rnd.date_closed else '',
            'questions': rnd.question_count,
            'invited': invited,
            'answered': answered,
            'rate': int(round(100.0 * answered / invited)) if invited else 0,
            'actions': len(rnd.action_ids),
        }

    @api.model
    def get_round(self, round_id):
        rnd = self._round_for_hr(round_id)
        row = self._round_row(rnd)
        kinds = dict(self.env['pb.voice.question']._fields['kind']
                     ._description_selection(self.env))
        themes = dict(self.env['pb.voice.question']._fields['theme']
                      ._description_selection(self.env))
        row.update({
            'intro': rnd.intro or '',
            'remind': rnd.remind, 'remind_every': rnd.remind_every,
            'last_reminded': format_date(self.env, rnd.last_reminded) if rnd.last_reminded else '',
            'floor': rnd.floor,
            'questions_list': [{
                'id': q.id, 'text': q.text, 'kind': q.kind,
                'kind_label': kinds.get(q.kind, ''),
                'theme_label': themes.get(q.theme, ''),
            } for q in rnd.question_ids],
            'who': rnd.voice_who_can_answer(),
            'actions_list': [a._voice_dict() for a in rnd.action_ids],
            'themes': [{'key': k, 'label': v} for k, v in themes.items()],
        })
        return row

    @api.model
    def round_move(self, round_id, verb):
        rnd = self._round_for_hr(round_id)
        _ = self.env._
        if verb == 'open':
            rnd.action_open()
            return {'msg': _("Sent out. People see it on My Payobook now.")}
        if verb == 'close':
            rnd.action_close()
            if rnd.result_state == 'kept':
                return {'msg': _("Closed. The results are ready.")}
            return {'msg': _("Closed. Fewer than %(n)s people answered, so "
                             "nothing was kept.", n=rnd.floor)}
        if verb == 'copy':
            new = rnd.copy()
            return {'msg': _("Copied. Change it, then send it out."),
                    'id': new.id}
        if verb == 'delete':
            rnd.unlink()
            return {'msg': _("Deleted."), 'deleted': True}
        raise UserError(_("That cannot be done here."))

    # ============================================================ results
    @api.model
    def _sealed(self, rnd):
        box = self.env['pb.voice.box'].sudo().search(
            [('round_id', '=', rnd.id)], limit=1)
        if not box or not box.sealed:
            return None
        try:
            return json.loads(box.sealed)
        except ValueError:
            return None

    @api.model
    def _plan(self, rnd, sealed):
        """Which groups may be shown. Returns ``(groups, cells_of, resp,
        visible)``: ``groups`` {gid: pb.voice.group | 'all'}, ``cells_of``
        {gid: frozenset(cell keys)}, ``resp`` {gid: answers}, ``visible``
        set of gids. The whole round is gid ``'all'``."""
        floor = max(rnd.floor, 5)
        cells = sealed.get('cells') or {}
        n_of = {c: int(v.get('n') or 0) for c, v in cells.items()}
        member = {c: {int(x) for x in c.split('.') if x} for c in cells}
        groups = {'all': 'all'}
        for g in rnd.sudo().group_ids:
            groups[g.id] = g
        cells_of = {'all': frozenset(cells)}
        for gid in groups:
            if gid != 'all':
                cells_of[gid] = frozenset(c for c in cells if gid in member[c])

        def resp(cs):
            return sum(n_of[c] for c in cs)

        r = {gid: resp(cs) for gid, cs in cells_of.items()}
        kind = {gid: ('all' if gid == 'all' else groups[gid].kind)
                for gid in groups}
        visible = {gid for gid in groups if r[gid] >= floor}

        def hide_smaller(a, b):
            # hide the one with fewer answers; on a tie the finer group
            if (r[a], -_KIND_FINENESS[kind[a]]) <= (r[b], -_KIND_FINENESS[kind[b]]):
                loser = a
            else:
                loser = b
            if loser == 'all':
                loser = b if a == 'all' else a
            visible.discard(loser)

        changed = True
        guard = 0
        while changed:
            guard += 1
            if guard > 5000:            # pragma: no cover
                break
            changed = False
            vis = sorted(visible, key=lambda g: (str(type(g)), g if g != 'all' else -1))
            # PAIRS
            for i, a in enumerate(vis):
                for b in vis[i + 1:]:
                    ca, cb = cells_of[a], cells_of[b]
                    if not (ca & cb):
                        continue
                    d1, d2 = resp(ca - cb), resp(cb - ca)
                    if 0 < d1 < floor or 0 < d2 < floor:
                        hide_smaller(a, b)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                continue
            # PARTS
            for p in sorted(visible, key=lambda g: (str(type(g)), g if g != 'all' else -1)):
                cp = cells_of[p]
                for k in ('company', 'department', 'team'):
                    if _KIND_FINENESS[k] <= _KIND_FINENESS[kind[p]]:
                        continue
                    kids = [g for g in visible if g != p and kind[g] == k
                            and cells_of[g] <= cp]
                    if not kids:
                        continue
                    rem = r[p] - sum(r[g] for g in kids)
                    if 0 < rem < floor:
                        visible.discard(min(kids, key=lambda g: (r[g], g)))
                        changed = True
                        break
                if changed:
                    break
        return groups, cells_of, r, visible

    @api.model
    def _figures(self, rnd, sealed, cells, comments=False):
        """The figures of ONE shown group (its cells): per question and per
        theme; comments only when asked (HR)."""
        _ = self.env._
        data = sealed.get('cells') or {}
        themes = dict(self.env['pb.voice.question']._fields['theme']
                      ._description_selection(self.env))
        questions = []
        theme_fav = {}
        enps = None
        for q in rnd.question_ids.sorted(lambda x: (x.sequence, x.id)):
            qid = str(q.id)
            if q.kind == 'text':
                continue
            counts = {}
            for c in cells:
                for v, n in ((data.get(c) or {}).get('q', {}).get(qid) or {}).items():
                    counts[int(v)] = counts.get(int(v), 0) + int(n)
            total = sum(counts.values())
            row = {'id': q.id, 'text': q.text, 'kind': q.kind,
                   'theme': q.theme, 'theme_label': themes.get(q.theme, ''),
                   'answers': total}
            pct = (lambda n: int(round(100.0 * n / total)) if total else 0)
            if q.kind == 'scale':
                row['dist'] = [{'v': i + 1, 'label': self.env._(w),
                                'n': counts.get(i + 1, 0),
                                'pct': pct(counts.get(i + 1, 0))}
                               for i, w in enumerate(SCALE_WORDS)]
                fav = counts.get(4, 0) + counts.get(5, 0)
                row['favourable'] = pct(fav)
                row['avg'] = round(sum(v * n for v, n in counts.items()) / total, 1) \
                    if total else 0
                theme_fav.setdefault(q.theme, []).append(row['favourable'])
            elif q.kind == 'enps':
                pro = sum(n for v, n in counts.items() if v >= 9)
                det = sum(n for v, n in counts.items() if v <= 6)
                pas = total - pro - det
                row.update({'promoters': pct(pro), 'passives': pct(pas),
                            'detractors': pct(det),
                            'score': pct(pro) - pct(det)})
                if enps is None:
                    enps = dict(row)
            elif q.kind == 'choice':
                opts = q._options()
                row['dist'] = [{'v': i, 'label': o, 'n': counts.get(i, 0),
                                'pct': pct(counts.get(i, 0))}
                               for i, o in enumerate(opts)]
            questions.append(row)
        theme_rows = [{'theme': t, 'label': themes.get(t, ''),
                       'favourable': int(round(sum(v) / len(v))),
                       'questions': len(v)}
                      for t, v in theme_fav.items()]
        theme_rows.sort(key=lambda x: x['favourable'])
        out = {'questions': questions, 'themes': theme_rows, 'enps': enps}
        if comments:
            texts = {str(q.id): q.text for q in rnd.question_ids
                     if q.kind == 'text'}
            notes = [n for n in sealed.get('notes') or [] if n[0] in cells]
            by_q = []
            for qid, label in texts.items():
                items = sorted(n[2] for n in notes if n[1] == qid)
                if items:
                    by_q.append({'question': label, 'items': items})
            out['comments'] = by_q
        return out

    @api.model
    def get_results(self, round_id, group=None):
        """HR's results page for one round and one group (``'all'``, or a
        company/department group id). Hidden groups carry no figure."""
        rnd = self._round_for_hr(round_id)
        _ = self.env._
        base = {'round': self._round_row(rnd), 'floor': rnd.floor}
        if rnd.state != 'closed':
            return dict(base, state='not_closed', why=_(
                "Results open when the round closes, so nobody can work out "
                "an answer by watching the numbers change."))
        if rnd.result_state != 'kept':
            return dict(base, state='too_few', why=_(
                "Fewer than %(n)s people answered, so nothing was kept and "
                "there are no results.", n=rnd.floor))
        sealed = self._sealed(rnd)
        if not sealed:
            return dict(base, state='too_few', why=_("There are no results."))
        groups, cells_of, resp, visible = self._plan(rnd, sealed)
        choices = []
        for gid, g in groups.items():
            if gid != 'all' and g.kind == 'team':
                continue        # teams: managers' cards only (first build)
            shown = gid in visible
            choices.append({
                'id': gid,
                'kind': 'all' if gid == 'all' else g.kind,
                'name': _('Everyone asked') if gid == 'all' else g.display_name,
                'parent': '' if gid == 'all' or not g.parent_id
                else g.parent_id.display_name,
                'invited': rnd.invited_count if gid == 'all' else g.invited,
                'shown': shown,
                'answered': resp[gid] if shown else None,
            })
        choices.sort(key=lambda c: (_KIND_FINENESS[c['kind']], c['parent'],
                                    c['name']))
        pick = 'all' if group in (None, '', 'all') else int(group)
        if pick not in groups or (pick != 'all' and groups[pick].kind == 'team'):
            pick = 'all'
        chosen = next(c for c in choices if c['id'] == pick)
        res = dict(base, state='shown', groups=choices, group=chosen)
        if pick in visible:
            fig = self._figures(rnd, sealed, cells_of[pick], comments=True)
            invited = chosen['invited'] or 0
            fig['rate'] = int(round(100.0 * resp[pick] / invited)) if invited else 0
            res['figures'] = fig
        else:
            res['figures'] = None
            res['hidden_why'] = _(
                "Hidden to keep answers private: fewer than %(n)s answers, or "
                "the figures could be worked out from the groups shown beside "
                "it.", n=rnd.floor)
        res['actions'] = [a._voice_dict() for a in rnd.action_ids]
        return res

    # ===================================================== action plans
    @api.model
    def save_action(self, round_id, vals, action_id=None):
        rnd = self._round_for_hr(round_id)
        clean = {k: vals.get(k) for k in ('name', 'theme', 'owner_id',
                                          'date_due', 'state', 'progress')
                 if k in vals}
        if 'owner_id' in clean:
            clean['owner_id'] = int(clean['owner_id'] or 0) or False
        if not clean.get('date_due'):
            clean.pop('date_due', None)
        Action = self.env['pb.voice.action']
        if action_id:
            act = Action.browse(int(action_id)).exists()
            if not act or act.round_id != rnd:
                raise UserError(self.env._("This action plan no longer exists."))
            act.write(clean)
        else:
            if not (clean.get('name') or '').strip():
                raise UserError(self.env._("Say what will be done, in a few "
                                           "words."))
            act = Action.create(dict(clean, round_id=rnd.id))
        return act._voice_dict()

    @api.model
    def owner_options(self, term=''):
        self._gate()
        users = self.env['res.users'].sudo().search(
            [('share', '=', False), ('active', '=', True),
             ('name', 'ilike', term or '')], limit=20, order='name')
        return [{'id': u.id, 'name': u.name} for u in users]

    # ============================================================ export
    @api.model
    def results_xlsx(self, round_id):
        """The Excel download: the SAME plan as the screen — hidden groups say
        "Hidden" and carry no figure; comments only for the whole round."""
        import xlsxwriter
        res = self.get_results(round_id)
        _ = self.env._
        rnd = self._round_for_hr(round_id)
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})
        head = wb.add_format({'bold': True, 'bg_color': '#EDEAF8'})
        ws = wb.add_worksheet(_('Results')[:31])
        ws.write_row(0, 0, [rnd.name], head)
        if res.get('state') != 'shown':
            ws.write(2, 0, res.get('why') or '')
            wb.close()
            return buf.getvalue()
        ws.write_row(2, 0, [_('Group'), _('Part of'), _('Asked'),
                            _('Answered'), _('Question'), _('Theme'),
                            _('Answers'), _('Favourable %'),
                            _('Average (1 to 5)'), _('Score')], head)
        row = 3
        sealed = self._sealed(rnd)
        groups, cells_of, resp, visible = self._plan(rnd, sealed)
        for ch in res['groups']:
            if not ch['shown']:
                ws.write_row(row, 0, [ch['name'], ch['parent'], ch['invited'],
                                      _('Hidden')])
                row += 1
                continue
            fig = self._figures(rnd, sealed, cells_of[ch['id']])
            for q in fig['questions']:
                score = q.get('score', '')
                ws.write_row(row, 0, [ch['name'], ch['parent'], ch['invited'],
                                      ch['answered'], q['text'],
                                      q['theme_label'], q['answers'],
                                      q.get('favourable', ''),
                                      q.get('avg', ''), score])
                row += 1
        ws.set_column(0, 1, 24)
        ws.set_column(4, 4, 60)
        overall = self._figures(rnd, sealed, cells_of['all'], comments=True)
        if overall.get('comments'):
            wc = wb.add_worksheet(_('Comments')[:31])
            wc.write_row(0, 0, [_('Question'), _('Comment')], head)
            r = 1
            for block in overall['comments']:
                for text in block['items']:
                    wc.write_row(r, 0, [block['question'], text])
                    r += 1
            wc.set_column(0, 0, 40)
            wc.set_column(1, 1, 90)
        wb.close()
        return buf.getvalue()

    # ==================================================== manager's card
    @api.model
    def manager_card(self, emp):
        """The "Team voice" card on /my/team for the caller's OWN employee:
        the latest closed round whose results can be shown for their team —
        or, when their team is too small, their department. Numbers only,
        never comments. ``None`` (no card) when they have never been near a
        round."""
        if not emp or emp._name != 'hr.employee':
            return None
        me = emp.sudo()[:1]
        if not me or me.user_id.id != self.env.uid:
            return None
        _ = self.env._
        Group = self.env['pb.voice.group'].sudo()
        Round = self.env['pb.voice.round'].sudo()
        rounds = Round.search([('state', '=', 'closed'),
                               ('company_ids', 'in', me.company_id.ids)],
                              order='date_closed desc, id desc', limit=6)
        if not rounds:
            return None
        plans = self.env['pb.voice.action'].sudo().search(
            [('owner_id', '=', self.env.uid), ('state', '!=', 'done')])
        for rnd in rounds:
            if rnd.result_state != 'kept':
                continue
            sealed = self._sealed(rnd)
            if not sealed:
                continue
            groups, cells_of, resp, visible = self._plan(rnd, sealed)
            team = Group.search([('round_id', '=', rnd.id), ('kind', '=', 'team'),
                                 ('manager_id', '=', me.id)], limit=1)
            dept = Group.search([('round_id', '=', rnd.id),
                                 ('kind', '=', 'department'),
                                 ('company_id', '=', me.company_id.id),
                                 ('department_id', '=', me.department_id.id)],
                                limit=1) if me.department_id else Group
            pick, scope = None, ''
            if team and team.id in visible:
                pick, scope = team, 'team'
            elif dept and dept.id in visible:
                pick, scope = dept, 'department'
            base = {'round': rnd.name,
                    'closed': rnd.date_closed,
                    'floor': rnd.floor,
                    'plans': [p._voice_dict() for p in plans]}
            if not pick:
                return dict(base, shown=False, sentence=_(
                    "Your team's answers are counted in the company's "
                    "results. Results show only for groups of %(n)s or more "
                    "answers, so nobody's answers can be picked out.",
                    n=rnd.floor))
            fig = self._figures(rnd, sealed, cells_of[pick.id])
            return dict(base, shown=True, scope=scope,
                        label=(_('Your team') if scope == 'team'
                               else pick.display_name),
                        answered=resp[pick.id], invited=pick.invited,
                        rate=int(round(100.0 * resp[pick.id] / pick.invited))
                        if pick.invited else 0,
                        enps=fig['enps'], themes=fig['themes'])
        return {'round': rounds[0].name, 'closed': rounds[0].date_closed,
                'floor': rounds[0].floor, 'shown': False,
                'plans': [p._voice_dict() for p in plans],
                'sentence': _("Too few people answered the last survey to "
                              "show any results.")}
