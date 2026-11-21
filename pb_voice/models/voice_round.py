# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.voice.round`` — one employee survey: who is asked, which questions,
when it closes. HR sets it up; employees answer on My Payobook.

The answers themselves never touch these tables — see ``voice_box.py`` for
the privacy contract. A round holds:

  * its questions (``pb.voice.question``), locked once it is sent out;
  * the audience snapshot taken when it is sent out (``pb.voice.invite``:
    WHO WAS ASKED, never who answered), each person with the group "cell"
    their answers will be counted in;
  * the groups results can be shown for (``pb.voice.group``), fixed at the
    same moment, each covering at least the floor of invited people;
  * one sealed box (``pb.voice.box``).

Nothing here is written by an employee's answer: the round's own
``write_uid`` / ``write_date`` therefore never say when anybody answered.
"""

import json
import logging
from collections import Counter
from datetime import timedelta

from markupsafe import escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .voice_common import (ACTION_STATES, FLOOR, KINDS, MAX_COMMENT,
                           MAX_QUESTIONS, RESULT_STATES, ROUND_STATES,
                           SCALE_WORDS, THEMES, VOICE_GATE)

_logger = logging.getLogger(__name__)

#: Coarsening order: the finest key is dropped first.
_FINEST_FIRST = ('team', 'department', 'company')


class PbVoiceRound(models.Model):
    _name = 'pb.voice.round'
    _description = 'Employee survey round'
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Name', required=True,
                       default=lambda self: self.env._('How are we doing?'))
    intro = fields.Text(
        string='A word to everyone',
        help='Shown at the top of the survey on My Payobook.')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company', 'pb_voice_round_company_rel', 'round_id', 'company_id',
        string='Companies asked', required=True,
        default=lambda self: self.env.company)
    department_ids = fields.Many2many(
        'hr.department', 'pb_voice_round_department_rel', 'round_id',
        'department_id', string='Only these departments',
        help='Leave empty to ask everyone in the companies above.')
    state = fields.Selection(ROUND_STATES, string='Status', default='draft',
                             required=True, index=True, copy=False)
    result_state = fields.Selection(RESULT_STATES, string='Results',
                                    default='none', required=True, copy=False)
    date_start = fields.Date(string='Sent out on', copy=False, readonly=True)
    date_end = fields.Date(
        string='Closes on', required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=14),
        help='Answers are taken until the end of this day. Results open the '
             'day after, or when you close it earlier.')
    date_closed = fields.Date(string='Closed on', copy=False, readonly=True)
    floor = fields.Integer(
        string='Smallest group shown', default=FLOOR, required=True,
        help='Results and comments show only for groups with at least this '
             'many answers. It can never be lower than 5.')
    remind = fields.Boolean(
        string='Remind people who have not answered', default=True,
        help='By email when this system sends email; on My Payobook the '
             '"Needs you" row stays until they answer, either way.')
    remind_every = fields.Integer(string='Every (days)', default=3)
    last_reminded = fields.Date(string='Last reminder', copy=False,
                                readonly=True)
    question_ids = fields.One2many('pb.voice.question', 'round_id',
                                   string='Questions', copy=True)
    invite_ids = fields.One2many('pb.voice.invite', 'round_id',
                                 string='People asked', copy=False)
    group_ids = fields.One2many('pb.voice.group', 'round_id',
                                string='Groups', copy=False)
    action_ids = fields.One2many('pb.voice.action', 'round_id',
                                 string='Action plans', copy=False)
    invited_count = fields.Integer(string='Asked', copy=False, readonly=True)
    answered_count = fields.Integer(
        string='Answered (at close)', copy=False, readonly=True,
        help='How many people answered, counted when the round closed.')
    question_count = fields.Integer(compute='_compute_question_count')

    @api.depends('question_ids')
    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)

    # ------------------------------------------------------------ checks
    @api.constrains('floor')
    def _check_floor(self):
        for rec in self:
            if rec.floor < FLOOR:
                raise ValidationError(self.env._(
                    "The smallest group shown can never be lower than %(n)s.",
                    n=FLOOR))

    @api.constrains('remind_every')
    def _check_remind_every(self):
        for rec in self:
            if not 1 <= rec.remind_every <= 30:
                raise ValidationError(self.env._(
                    "Remind every 1 to 30 days."))

    @api.constrains('company_id', 'company_ids')
    def _check_companies(self):
        for rec in self:
            if rec.company_id not in rec.company_ids:
                raise ValidationError(self.env._(
                    "The round's own company must be one of the companies "
                    "asked."))

    #: what may still change once the round is sent out
    _OPEN_WRITABLE = frozenset({
        'name', 'intro', 'date_end', 'remind', 'remind_every',
        'last_reminded', 'state', 'result_state', 'date_closed',
        'answered_count', 'action_ids',
    })

    def write(self, vals):
        if not self.env.su and any(r.state != 'draft' for r in self):
            locked = set(vals) - self._OPEN_WRITABLE
            if locked:
                raise UserError(self.env._(
                    "This round has been sent out, so its questions and who "
                    "is asked can no longer change. Make a copy to ask again."))
        if 'date_end' in vals and any(r.state == 'closed' for r in self):
            raise UserError(self.env._("This round is closed."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_drafts(self):
        if any(r.state != 'draft' for r in self):
            raise UserError(self.env._(
                "Only a round that has not been sent out can be deleted."))

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        if not (default or {}).get('name'):
            for rec, vals in zip(self, vals_list):
                vals['name'] = self.env._('%s (copy)', rec.name)
        return vals_list

    # ------------------------------------------------------- the audience
    def _audience_employees(self):
        """The people a round asks, as of now (sudo): active employees of the
        companies asked (and the departments, if any), one per person."""
        self.ensure_one()
        dom = [('company_id', 'in', self.company_ids.ids)]
        if self.department_ids:
            dom.append(('department_id', 'in', self.department_ids.ids))
        emps = self.env['hr.employee'].sudo().search(dom, order='company_id, id')
        seen, keep = set(), []
        for emp in emps:
            pkey = self._person_key(emp)
            if pkey in seen:
                continue
            seen.add(pkey)
            keep.append(emp.id)
        return self.env['hr.employee'].sudo().browse(keep)

    @api.model
    def _person_key(self, emp):
        """One key per PERSON: somebody employed in two companies of a group
        is one person (pb_workseg's person link, when installed)."""
        person = 'pb_person_id' in emp._fields and emp.pb_person_id
        return 'p%d' % person.id if person else 'e%d' % emp.id

    # ----------------------------------------------------------- the cells
    @api.model
    def _voice_cells(self, employees, floor):
        """Fix the groups and give each person a cell.

        Returns ``(rows, keys)``: ``rows`` is ``[(employee, frozenset(keys))]``
        and ``keys`` the group keys that survive. A key is
        ``('company', cid)``, ``('department', cid, did)`` or
        ``('team', cid, manager_id)``.

        Guarantee (tested): every group that survives covers at least
        ``floor`` invited people AND every distinct combination of keys a
        person carries (their cell) is shared by at least ``floor`` invited
        people. A small department or team is therefore never written next
        to an answer: those people are counted one level up instead.
        """
        rows = []
        for emp in employees:
            cid = emp.company_id.id
            keys = {'company': ('company', cid)}
            if emp.department_id:
                keys['department'] = ('department', cid, emp.department_id.id)
            if emp.parent_id:
                keys['team'] = ('team', cid, emp.parent_id.id)
            rows.append([emp, keys])
        guard = 0
        while True:
            guard += 1
            if guard > 10000:              # pragma: no cover — cannot happen
                raise UserError(self.env._("The groups could not be worked out."))
            sizes = Counter(k for _e, keys in rows for k in keys.values())
            dropped = False
            for _e, keys in rows:
                for kind, key in list(keys.items()):
                    if sizes[key] < floor:
                        del keys[kind]
                        dropped = True
            if dropped:
                continue
            cells = Counter(frozenset(keys.values()) for _e, keys in rows)
            small = sorted((n, sorted(cell)) for cell, n in cells.items()
                           if cell and n < floor)
            if small:
                cell = frozenset(tuple(k) for k in small[0][1])
                kinds = {k[0] for k in cell}
                if kinds != {'company'}:
                    # move these people up one level (finest key first)
                    for _e, keys in rows:
                        if frozenset(keys.values()) == cell:
                            for kind in _FINEST_FIRST:
                                if kind in keys:
                                    del keys[kind]
                                    break
                else:
                    # a small company-only remainder: fold the company's
                    # smallest other cell into it (keeps the company), or,
                    # when there is none, drop the company key too
                    comp = next(iter(cell))
                    siblings = sorted((n, sorted(c)) for c, n in cells.items()
                                      if comp in c and c != cell)
                    if siblings:
                        sib = frozenset(tuple(k) for k in siblings[0][1])
                        for _e, keys in rows:
                            if frozenset(keys.values()) == sib:
                                for kind in ('team', 'department'):
                                    keys.pop(kind, None)
                    else:
                        for _e, keys in rows:
                            if frozenset(keys.values()) == cell:
                                keys.clear()
                continue
            rest = cells.get(frozenset(), 0)
            if 0 < rest < floor:
                keyed = sorted((n, sorted(cell)) for cell, n in cells.items()
                               if cell)
                if not keyed:
                    break
                victim = frozenset(tuple(k) for k in keyed[0][1])
                for _e, keys in rows:
                    if frozenset(keys.values()) == victim:
                        keys.clear()
                continue
            break
        out = [(emp, frozenset(keys.values())) for emp, keys in rows]
        surviving = sorted({k for _e, cell in out for k in cell})
        return out, surviving

    # -------------------------------------------------------- sending out
    def _check_can_open(self, employees):
        self.ensure_one()
        _ = self.env._
        if self.state != 'draft':
            raise UserError(_("This round has already been sent out."))
        scored = self.question_ids.filtered(lambda q: q.kind != 'text')
        if not scored:
            raise UserError(_("Add at least one question people answer with "
                              "a rating or a choice."))
        if len(self.question_ids) > MAX_QUESTIONS:
            raise UserError(_("A round can hold at most %(n)s questions.",
                              n=MAX_QUESTIONS))
        for q in self.question_ids:
            if q.kind == 'choice' and len(q._options()) < 2:
                raise UserError(_('The question "%(q)s" needs at least two '
                                  'options, one per line.', q=q.text))
        if self.date_end < fields.Date.context_today(self):
            raise UserError(_("The closing date is in the past."))
        if len(employees) < self.floor:
            raise UserError(_(
                "A round needs at least %(n)s people, so nobody's answers can "
                "be picked out. This one would ask %(m)s.",
                n=self.floor, m=len(employees)))
        if not set(self.company_ids.ids) <= set(self.env.user.company_ids.ids):
            raise AccessError(_("You can only ask people in companies you can "
                                "see."))

    def action_open(self):
        """Send the round out: fix the audience, the groups and the cells,
        make the sealed box and its key, and invite people."""
        self._voice_require_hr()
        for rec in self:
            employees = rec._audience_employees()
            rec._check_can_open(employees)
            rows, keys = self._voice_cells(employees, rec.floor)
            Group = self.env['pb.voice.group'].sudo()
            gid = {}
            # companies first, so departments and teams can name their parent
            for key in sorted(keys, key=lambda k: _FINEST_FIRST[::-1].index(k[0])):
                vals = {'round_id': rec.id, 'kind': key[0],
                        'company_id': key[1]}
                if key[0] == 'department':
                    vals['department_id'] = key[2]
                elif key[0] == 'team':
                    vals['manager_id'] = key[2]
                vals['parent_id'] = gid.get(('company', key[1]), False) \
                    if key[0] != 'company' else False
                gid[key] = Group.create(vals).id
            counts = Counter()
            Invite = self.env['pb.voice.invite'].sudo()
            invite_vals = []
            for emp, cell in rows:
                ids = sorted(gid[k] for k in cell)
                for g in ids:
                    counts[g] += 1
                invite_vals.append({'round_id': rec.id, 'employee_id': emp.id,
                                    'cell': '.'.join(str(i) for i in ids)})
            Invite.create(invite_vals)
            for g in Group.browse(list(gid.values())):
                g.invited = counts[g.id]
            self.env['pb.voice.box'].sudo().create({'round_id': rec.id})
            Box = self.env['pb.voice.box']
            Box._voice_key(rec.id, create=True)
            # a send-out that rolls back must not leave a key behind
            rid = rec.id
            self.env.cr.postrollback.add(lambda: Box._voice_destroy(rid))
            rec.sudo().write({
                'state': 'open',
                'date_start': fields.Date.context_today(rec),
                'invited_count': len(rows),
                'last_reminded': fields.Date.context_today(rec),
            })
            rec._voice_send_mail('invite')
        return True

    # ------------------------------------------------------------ closing
    def action_close(self):
        self._voice_require_hr()
        for rec in self:
            if rec.state != 'open':
                raise UserError(self.env._("Only an open round can be closed."))
            rec._voice_seal()
        return True

    def _voice_seal(self):
        """Close the round: the ONE write of answers into the database.

        Every sealed answer is read, counted into its cell, and the comments
        are kept sorted by cell, question and text. If fewer than the floor
        answered, nothing is kept. The "has answered" list is wiped, and the
        key and the sealed files are destroyed once this commits."""
        self.ensure_one()
        Box = self.env['pb.voice.box'].sudo()
        box = Box.search([('round_id', '=', self.id)], limit=1)
        if box:
            # one at a time with a person answering this round
            self.env.cr.execute('SELECT id FROM pb_voice_box WHERE id = %s '
                                'FOR UPDATE', (box.id,))
        payloads = Box._seal_read_all(self.id) if box else []
        n = len(payloads)
        valid_q = {str(q.id): q for q in self.question_ids}
        sealed = None
        if n >= self.floor:
            cells = {}
            notes = []
            for pl in payloads:
                cell = str(pl.get('k') or '')
                slot = cells.setdefault(cell, {'n': 0, 'q': {}})
                slot['n'] += 1
                for qid, value in (pl.get('a') or {}).items():
                    if qid not in valid_q:
                        continue
                    counts = slot['q'].setdefault(qid, {})
                    counts[str(value)] = counts.get(str(value), 0) + 1
                for qid, text in (pl.get('t') or {}).items():
                    if qid in valid_q and text:
                        notes.append([cell, qid, str(text)[:MAX_COMMENT]])
            notes.sort()
            sealed = json.dumps({'cells': cells, 'notes': notes},
                                sort_keys=True, ensure_ascii=False)
        if box:
            self.env.cr.execute(
                'UPDATE pb_voice_box SET marks = %s, sealed = %s WHERE id = %s',
                ('[]', sealed, box.id))
            box.invalidate_recordset(['marks', 'sealed'])
        self.sudo().write({
            'state': 'closed',
            'result_state': 'kept' if sealed else 'too_few',
            'answered_count': n,
            'date_closed': fields.Date.context_today(self),
        })
        rid = self.id
        self.env.cr.postcommit.add(lambda: Box._voice_destroy(rid))

    # ------------------------------------------------------------ the gate
    @api.model
    def _voice_is_hr(self, user=None):
        user = user or self.env.user
        return any(user.has_group(g) for g in VOICE_GATE)

    def _voice_require_hr(self):
        if not self._voice_is_hr():
            raise AccessError(self.env._("Employee surveys are run by HR."))

    # ------------------------------------------------------ the audience panel
    def voice_who_can_answer(self):
        """What the "who can answer" panel shows: how many are asked, how
        many can sign in to My Payobook, and who cannot (names, so HR can
        make them a sign-in slip). Read under sudo after the HR gate."""
        self.ensure_one()
        self._voice_require_hr()
        if self.state == 'draft':
            emps = self._audience_employees()
        else:
            emps = self.sudo().invite_ids.mapped('employee_id')
        emps = emps.sudo().with_context(active_test=False)
        with_login = emps.filtered(lambda e: e.user_id and e.user_id.active)
        without = emps - with_login
        no_email = with_login.filtered(
            lambda e: not (e.work_email or e.user_id.email))
        return {
            'asked': len(emps),
            'with_login': len(with_login),
            'without_login': len(without),
            'without_names': [{'id': e.id, 'name': e.name,
                               'department': e.department_id.name or ''}
                              for e in without[:60]],
            'without_more': max(0, len(without) - 60),
            'no_email': len(no_email),
            'floor': self.floor,
            'mail_on': self._voice_mail_on(),
        }

    # ------------------------------------------------------------ email
    @api.model
    def _voice_mail_on(self):
        """Does this system send email? An active outgoing mail server (the
        QF2 rule, pb_explorer `_pbx_mail_on`). Tenant databases have email
        off on purpose: then nothing is ever queued."""
        return bool(self.env['ir.mail_server'].sudo().search_count(
            [('active', '=', True)]))

    def _voice_unanswered(self):
        """Invites of people who have NOT answered yet (sudo). Needs the key:
        after close there is no answer to this question any more."""
        self.ensure_one()
        Box = self.env['pb.voice.box'].sudo()
        box = Box.search([('round_id', '=', self.id)], limit=1)
        key = Box._voice_key(self.id) if box else None
        if not box or not key:
            return self.env['pb.voice.invite'].sudo().browse()
        marks = box._marks()
        return self.sudo().invite_ids.filtered(
            lambda i: Box._voice_code(key, self._person_key(i.employee_id))
            not in marks)

    def _voice_send_mail(self, kind):
        """Invitation ('invite') or reminder ('remind') emails. On a system
        with no outgoing email NOTHING is queued — the "Needs you" row on My
        Payobook is the reminder. Returns how many were queued."""
        self.ensure_one()
        if not self._voice_mail_on():
            return 0
        invites = self.sudo().invite_ids if kind == 'invite' \
            else self._voice_unanswered()
        Mail = self.env['mail.mail'].sudo()
        company = self.company_id.sudo()
        sender = company.email_formatted or \
            self.env['ir.mail_server'].sudo()._get_default_from_address()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        queued = 0
        for inv in invites:
            emp = inv.employee_id.sudo()
            user = emp.user_id
            to = emp.work_email or (user and user.email)
            if not (to and user and user.active):
                continue
            lang = user.lang or self.env.lang
            me = self.with_context(lang=lang)
            _ = me.env._
            link = '%s/my/voice/%s' % (base.rstrip('/'), self.id)
            if kind == 'invite':
                subject = _('%(company)s would like to hear from you',
                            company=company.name)
                first = _('A short survey is open: %(name)s.', name=me.name)
            else:
                subject = _('A reminder: %(name)s', name=me.name)
                first = _('The survey "%(name)s" is still open.', name=me.name)
            body = (
                '<p>%s</p><p>%s</p><p>%s</p><p><a href="%s">%s</a></p>' % (
                    escape(first),
                    escape(_('Your answers are anonymous: nobody, not even HR, '
                             'can see who said what. Results show only for '
                             'groups of %(n)s or more people.', n=self.floor)),
                    escape(_('Open for answers until %(date)s.',
                             date=fields.Date.to_string(self.date_end))),
                    escape(link), escape(_('Answer the survey'))))
            Mail.create({
                'subject': subject,
                'body_html': body,
                'email_to': to,
                'email_from': sender,
                'auto_delete': True,
            })
            queued += 1
        return queued

    # ------------------------------------------------------------- the job
    @api.model
    def _cron_voice_daily(self):
        """Once a day. Quiet on a database with no round: it reads one empty
        table and stops. Closes rounds whose last day has passed, sends the
        due reminders (only where email is on), and clears any sealed folder
        a closed round left behind."""
        today = fields.Date.context_today(self)
        Round = self.sudo()
        for rec in Round.search([('state', '=', 'open'),
                                 ('date_end', '<', today)]):
            try:
                with self.env.cr.savepoint():
                    rec._voice_seal()
            except Exception:           # noqa: BLE001 — one round, not all
                _logger.warning('pb_voice: round %s could not be closed',
                                rec.id, exc_info=True)
        for rec in Round.search([('state', '=', 'open'), ('remind', '=', True)]):
            last = rec.last_reminded or rec.date_start or today
            if (today - last).days < (rec.remind_every or 3):
                continue
            try:
                with self.env.cr.savepoint():
                    rec._voice_send_mail('remind')
                    rec.write({'last_reminded': today})
            except Exception:           # noqa: BLE001
                _logger.warning('pb_voice: reminders for round %s failed',
                                rec.id, exc_info=True)
        Box = self.env['pb.voice.box']
        for rec in Round.search([('state', '=', 'closed')]):
            Box._voice_destroy(rec.id)

    # ------------------------------------------------------- the employee
    @api.model
    def _voice_own_invites(self, emp):
        """Invites of the caller's own person (every employee record of the
        session user), sudo. ``emp`` must be the caller's own."""
        if not emp or emp._name != 'hr.employee':
            return self.env['pb.voice.invite'].sudo().browse()
        emp = emp.sudo()[:1]
        if not emp or emp.user_id.id != self.env.uid:
            return self.env['pb.voice.invite'].sudo().browse()
        mine = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)])
        return self.env['pb.voice.invite'].sudo().search(
            [('employee_id', 'in', mine.ids)])

    @api.model
    def _voice_has_answered(self, invite):
        """Has the person of this invite answered? (Their own question only.)"""
        rnd = invite.round_id.sudo()
        if rnd.state != 'open':
            return None
        Box = self.env['pb.voice.box'].sudo()
        box = Box.search([('round_id', '=', rnd.id)], limit=1)
        key = Box._voice_key(rnd.id)
        if not box or not key:
            return False
        return Box._voice_code(key, self._person_key(invite.employee_id)) \
            in box._marks()

    @api.model
    def voice_my_rounds(self, emp):
        """The caller's own rounds, newest first: ``[{id, name, state,
        answered, date_end, closes_in}]`` — open ones they are asked in, and
        closed ones they were asked in. ``None`` for anybody else's ``emp``."""
        if not emp or emp._name != 'hr.employee':
            return None
        own = emp.sudo()[:1]
        if not own or own.user_id.id != self.env.uid:
            return None
        today = fields.Date.context_today(self)
        out, seen = [], set()
        for inv in self._voice_own_invites(own).sorted(
                lambda i: (i.round_id.date_start or today), reverse=True):
            rnd = inv.round_id.sudo()
            if rnd.id in seen or rnd.state == 'draft':
                continue
            seen.add(rnd.id)
            answered = self._voice_has_answered(inv) if rnd.state == 'open' else None
            out.append({
                'id': rnd.id, 'name': rnd.name, 'state': rnd.state,
                'answered': bool(answered),
                'date_end': rnd.date_end,
                'closes_in': (rnd.date_end - today).days if rnd.date_end else 0,
                'questions': len(rnd.question_ids),
                'company': rnd.company_id.name,
            })
        return out

    def voice_form(self, emp):
        """What the answer form draws for the caller: the round's words and
        questions in the reader's language, or a refusal sentence."""
        self.ensure_one()
        _ = self.env._
        inv = self._voice_own_invites(emp).filtered(
            lambda i: i.round_id.id == self.id)[:1]
        rnd = self.sudo()
        if not inv:
            return {'ok': False, 'why': _("You are not asked in this survey.")}
        if rnd.state != 'open':
            return {'ok': False, 'closed': True,
                    'why': _("This survey is closed. Thank you.")}
        if self._voice_has_answered(inv):
            return {'ok': False, 'done': True,
                    'why': _("You have answered this survey. Thank you.")}
        qs = []
        for q in rnd.question_ids.sorted(lambda r: (r.sequence, r.id)):
            qs.append(q._portal_dict())
        return {'ok': True, 'id': rnd.id, 'name': rnd.name,
                'intro': rnd.intro or '', 'date_end': rnd.date_end,
                'floor': rnd.floor, 'questions': qs}

    def voice_submit(self, emp, answers, comments):
        """Take ONE answer from the caller's own person. ``answers`` is
        ``{question_id: value}``, ``comments`` ``{question_id: text}``. The
        signature carries no employee of the caller's choosing beyond the
        session's own, checked here.

        What is written to the DATABASE: one code added to the sorted "has
        answered" list. What is written to the FILE STORE: one sealed answer
        under a random name. Nothing else — no log line names the person, no
        message, no activity, no write on the round."""
        self.ensure_one()
        _ = self.env._
        inv = self._voice_own_invites(emp).filtered(
            lambda i: i.round_id.id == self.id)[:1]
        if not inv:
            raise AccessError(_("You are not asked in this survey."))
        rnd = self.sudo()
        if rnd.state != 'open' or (rnd.date_end and rnd.date_end <
                                   fields.Date.context_today(self)):
            raise UserError(_("This survey is closed. Thank you."))
        payload_a, payload_t = {}, {}
        answers = answers or {}
        comments = comments or {}
        for q in rnd.question_ids:
            qid = str(q.id)
            if q.kind == 'text':
                text = (comments.get(qid) or comments.get(q.id) or '')
                text = str(text).strip()[:MAX_COMMENT]
                if text:
                    payload_t[qid] = text
                continue
            raw = answers.get(qid, answers.get(q.id))
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise UserError(_('Please answer: "%(q)s".', q=q.text))
            lo, hi = q._value_range()
            if not lo <= value <= hi:
                raise UserError(_('Please answer: "%(q)s".', q=q.text))
            payload_a[qid] = value
        Box = self.env['pb.voice.box'].sudo()
        box = Box.search([('round_id', '=', rnd.id)], limit=1)
        if not box:
            raise UserError(_("This survey is not open."))
        # One at a time per round: the check and the mark cannot race.
        self.env.cr.execute('SELECT marks FROM pb_voice_box WHERE id = %s '
                            'FOR UPDATE', (box.id,))
        row = self.env.cr.fetchone()
        try:
            marks = set(json.loads(row[0] or '[]'))
        except ValueError:
            marks = set()
        key = Box._voice_key(rnd.id)
        if not key:
            if marks:
                _logger.warning('pb_voice: a round key was missing (database '
                                'restored without its file store?) — a new '
                                'one is made; earlier answers stay counted')
            key = Box._voice_key(rnd.id, create=True)
        code = Box._voice_code(key, self._person_key(inv.employee_id))
        if code in marks:
            raise UserError(_("You have answered this survey. Thank you."))
        path = Box._seal_write(rnd.id, {'k': inv.cell or '', 'a': payload_a,
                                        't': payload_t})
        # If this transaction does not commit, take the sealed answer back.
        self.env.cr.postrollback.add(lambda: Box._seal_unlink(path))
        marks.add(code)
        self.env.cr.execute('UPDATE pb_voice_box SET marks = %s WHERE id = %s',
                            (json.dumps(sorted(marks)), box.id))
        box.invalidate_recordset(['marks'])
        return True

    # ------------------------------------------------------ the HR board
    @api.model
    def can_open(self):
        """The Talent tab's probe: offered exactly to HR."""
        return self._voice_is_hr()

    def voice_answered_so_far(self):
        """Open round: how many people have answered so far (a count only)."""
        self.ensure_one()
        if self.state != 'open':
            return self.answered_count if self.state == 'closed' else 0
        box = self.env['pb.voice.box'].sudo().search(
            [('round_id', '=', self.id)], limit=1)
        return len(box._marks()) if box else 0


class PbVoiceQuestion(models.Model):
    _name = 'pb.voice.question'
    _description = 'Survey question'
    _order = 'sequence, id'

    round_id = fields.Many2one('pb.voice.round', required=True, index=True,
                               ondelete='cascade')
    company_id = fields.Many2one(related='round_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(KINDS, string='Answered as', required=True,
                            default='scale')
    theme = fields.Selection(THEMES, string='Theme', required=True,
                             default='engagement')
    text = fields.Char(string='Question', required=True, translate=True)
    options = fields.Text(
        string='Options', translate=True,
        help='For "Pick one option": one option per line.')
    library_id = fields.Many2one('pb.voice.library', string='From the library',
                                 ondelete='set null')

    def write(self, vals):
        if not self.env.su and any(q.round_id.state != 'draft' for q in self):
            raise UserError(self.env._(
                "This round has been sent out, so its questions can no longer "
                "change."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        rounds = self.env['pb.voice.round'].browse(
            [v.get('round_id') for v in vals_list if v.get('round_id')])
        if not self.env.su and any(r.state != 'draft' for r in rounds):
            raise UserError(self.env._(
                "This round has been sent out, so no question can be added."))
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_in_drafts(self):
        if any(q.round_id.state != 'draft' for q in self):
            raise UserError(self.env._(
                "This round has been sent out, so its questions stay."))

    def _options(self):
        self.ensure_one()
        return [o.strip() for o in (self.options or '').splitlines() if o.strip()]

    def _value_range(self):
        self.ensure_one()
        if self.kind == 'scale':
            return 1, 5
        if self.kind == 'enps':
            return 0, 10
        if self.kind == 'choice':
            return 0, max(0, len(self._options()) - 1)
        return 0, -1

    def _portal_dict(self):
        """One question as the answer form draws it (reader's language)."""
        self.ensure_one()
        _ = self.env._
        data = {'id': self.id, 'kind': self.kind, 'text': self.text}
        if self.kind == 'scale':
            data['steps'] = [{'v': i + 1, 'label': self.env._(w)}
                             for i, w in enumerate(SCALE_WORDS)]
        elif self.kind == 'enps':
            data['steps'] = [{'v': i, 'label': str(i)} for i in range(11)]
            data['low'] = _('Not at all likely')
            data['high'] = _('Extremely likely')
        elif self.kind == 'choice':
            data['steps'] = [{'v': i, 'label': o}
                             for i, o in enumerate(self._options())]
        return data


class PbVoiceInvite(models.Model):
    """WHO WAS ASKED (the audience snapshot), never who answered. Written
    once when the round is sent out and never touched by an answer."""
    _name = 'pb.voice.invite'
    _description = 'Person asked in a survey round'
    _order = 'id'

    round_id = fields.Many2one('pb.voice.round', required=True, index=True,
                               ondelete='cascade')
    company_id = fields.Many2one(related='round_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True,
                                  ondelete='cascade')
    #: the group ids this person's answer is counted under ("12.15.19")
    cell = fields.Char(groups='base.group_system')

    _one_per_round = models.Constraint('unique(round_id, employee_id)',
                                       'A person is asked once per round.')


class PbVoiceGroup(models.Model):
    """A group results can be shown for, fixed when the round is sent out."""
    _name = 'pb.voice.group'
    _description = 'Survey results group'
    _order = 'kind, id'

    round_id = fields.Many2one('pb.voice.round', required=True, index=True,
                               ondelete='cascade')
    kind = fields.Selection([('company', 'Company'),
                             ('department', 'Department'),
                             ('team', 'Team')], required=True)
    company_id = fields.Many2one('res.company', required=True)
    department_id = fields.Many2one('hr.department', ondelete='set null')
    manager_id = fields.Many2one('hr.employee', string='Team of',
                                 ondelete='set null')
    parent_id = fields.Many2one('pb.voice.group', ondelete='cascade')
    invited = fields.Integer(string='Asked')

    @api.depends('kind', 'company_id', 'department_id', 'manager_id')
    def _compute_display_name(self):
        _ = self.env._
        for g in self.sudo():
            if g.kind == 'department':
                g.display_name = g.department_id.name or _('Department')
            elif g.kind == 'team':
                g.display_name = _("%(name)s's team",
                                   name=g.manager_id.name or '')
            else:
                g.display_name = g.company_id.name or _('Company')


ACTION_STATE_LABEL = dict(ACTION_STATES)
