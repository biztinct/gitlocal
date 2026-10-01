# -*- coding: utf-8 -*-
"""RECRUIT phase 3 — what the board and the role page read and press.

The model work is in `requests_p3.py`; this is the facade: the payload each
role row and each role page carries about its request, and the verbs the
screen names ("Open a role", "Ask a manager", "Remind now", "Send in",
"Agree", the budget, Confidential, the advert, and the set-up page's "Who
does what"). The screen never writes a field (the facade doctrine): it names
an intention and the server decides.

API left for P4–P6 (see the phase report):
  * `pb.hiring._sender(company)` — the address every hiring email comes from.
  * `pb.hiring._offer_block_reason(requisition)` — '' or the one sentence.
  * `requisition.request_state` and `_request_facts()` on every row.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from .hiring_common import (
    BUDGET_AGREEMENT, DOCREQ_TRIGGERS, GROUP_MANAGER, GROUP_USER,
    P_DOCREQ_TRIGGER, P_REFERRAL_ANNOUNCE, P_SENDER, REQUEST_STATES,
    REQUEST_WAITING, REQUEST_WITH_HR, as_id, flag, fold, text,
)
from .requests_p3 import SENT_STATES

_logger = logging.getLogger(__name__)


class PbHiringP3(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  The sender (closes the wave-2 "no sender address" item)
    # =====================================================================
    @api.model
    def _sender(self, company=None):
        """The address every hiring email comes from.

        A typed hiring address (`pb_hiring.sender`), then the company's own,
        then its partner's, then the address this build sends everything
        else from. NEVER the person who pressed the button: a reminder from
        whoever happened to be logged in is a reminder people reply to the
        wrong person (the pb_goals precedent, `goal_set._sender`).
        """
        company = (company or self.env.company).sudo()
        name = company._hiring_brand() if hasattr(company, '_hiring_brand') \
            else company.name
        typed = text(self.env, P_SENDER, '')
        if typed:
            return typed if '<' in typed else tools.formataddr(
                (name or '', typed))
        for address in (company.email, company.partner_id.email):
            if address:
                return tools.formataddr((name or '', address))
        try:
            fallback = self.env['ir.mail_server'].sudo() \
                ._get_default_from_address()
        except Exception:               # noqa: BLE001 — a sender, never a crash
            fallback = False
        fallback = fallback or self.env['ir.config_parameter'].sudo() \
            .get_param('mail.default.from') or ''
        if fallback and '@' not in fallback:
            domain = self.env['ir.config_parameter'].sudo().get_param(
                'mail.catchall.domain') or ''
            fallback = '%s@%s' % (fallback, domain) if domain else ''
        return tools.formataddr((name or '', fallback)) if fallback else ''

    @api.model
    def _offer_block_reason(self, requisition):
        """'' when an offer may be sent for this role, else the sentence."""
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(requisition)).exists()
        return req._offer_block_reason() if req else ''

    # =====================================================================
    #  The row, the board, the role page
    # =====================================================================
    @api.model
    def _row(self, req):
        row = super()._row(req)
        row.update(self._safe(lambda: req._request_facts(), default={}))
        row['can_open_role'] = bool(req.state == 'setup'
                                    and self._can_recruit(req))
        return row

    @api.model
    def get_board(self, limit=None):
        board = super().get_board(limit=limit)
        if board.get('allowed'):
            board['request_states'] = [{'key': k, 'label': v}
                                       for k, v in REQUEST_STATES]
            board['can_ask'] = self._can_recruit()
            kpis = board.get('kpis') or {}
            rows = board.get('rows') or []
            kpis['open'] = sum(1 for r in rows if r['state'] in ('setup',
                                                                 'open'))
            kpis['waiting'] = sum(1 for r in rows if r.get('request_state')
                                  in SENT_STATES[:2])
            kpis['no_request'] = sum(
                1 for r in rows if r['state'] in ('setup', 'open')
                and r.get('request_state') in ('none', 'asked', 'writing'))
            board['kpis'] = kpis
        return board

    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(requisition_id))
        row['request'] = self._safe(lambda: self._request_block(req),
                                    default={})
        row['advert'] = self._safe(lambda: self._advert_block(req),
                                   default={})
        return row

    @api.model
    def _request_block(self, req):
        """Everything the Details → Request section draws."""
        rec = req.sudo()
        can_recruit = bool(self._can_recruit(req))
        mine = bool(self._safe(lambda: rec._chain_my_seat(), default=False))
        dormant = not rec._engine_managed()
        can_agree = rec.request_state in REQUEST_WITH_HR and (
            mine or (dormant and self.env.user.has_group(GROUP_MANAGER)))
        people = rec._budget_people()
        now = fields.Datetime.now()
        remind_wait = 0
        if rec.last_reminded_on and now - rec.last_reminded_on < \
                timedelta(hours=1):
            remind_wait = int((3600 - (now - rec.last_reminded_on)
                               .total_seconds()) // 60) + 1
        tone, note = rec._page_budget_note()
        asked = rec.asked_employee_id
        return {
            'state': rec.request_state,
            'label': dict(REQUEST_STATES).get(rec.request_state, ''),
            'chip': rec._request_chip()[0],
            'tone': rec._request_chip()[1],
            'asked': {
                'id': asked.id, 'name': asked.name or '',
                'has_email': bool(asked.work_email or asked.user_id.email),
                'login': ('portal' if asked.user_id.share else 'internal')
                if asked.user_id else 'none',
            } if asked else None,
            'asked_on': str(rec.asked_on or ''),
            'asked_by': rec.asked_by_id.name or '',
            'message': rec.ask_message or '',
            'remind_every': rec.remind_every_days or 2,
            'remind_count': rec.remind_count or 0,
            'reminded_ago': rec._reminded_line(),
            'remind_wait': remind_wait,
            'escalated_on': str(rec.escalated_on or ''),
            'saved_on': str(rec.request_saved_on or ''),
            'manager_agreed_by': rec.manager_agreed_by_id.name or '',
            'manager_agreed_on': str(rec.manager_agreed_on or ''),
            'sent_in_by': rec.sent_in_by_id.name or '',
            'agreed_on': str(rec.agreed_on or ''),
            'not_approved_reason': rec.not_approved_reason or '',
            'trail': self._request_trail(rec),
            'waiting_on': rec._agree_holders_names()
            if rec.request_state in REQUEST_WITH_HR else '',
            'figures': {
                'expected': rec.budget_cost or 0.0,
                'confirmed': rec.budget_confirmed or 0.0,
                'currency': rec.currency_id.name or '',
                'currency_id': rec.currency_id.id,
                'dept_remaining': rec.budget_remaining or 0.0,
                'dept_currency': rec.budget_currency_id.name or '',
                'status': rec.budget_status or 'unknown',
                'note': rec.budget_note or '',
                'page_note': note, 'page_tone': tone,
            },
            'budget_agreement': rec.budget_agreement or 'not_yet',
            'budget_agreements': [{'key': k, 'label': v}
                                  for k, v in BUDGET_AGREEMENT],
            'budget_people': people.mapped('name'),
            'budget_people_sentence': _(
                "Nobody is named yet. Until somebody is, an over-budget "
                "request gives the Head of hiring a to-do.") if not people
            else '',
            'is_confidential': bool(rec.is_confidential),
            'can_recruit': can_recruit,
            'can_ask': can_recruit and rec.state != 'closed' and (
                rec.request_state not in SENT_STATES
                or rec.request_state == 'not_approved'),
            'can_remind': can_recruit and rec.request_state in REQUEST_WAITING
            and bool(asked),
            'can_send_in': rec.request_state not in SENT_STATES[:3]
            and rec.state != 'closed' and bool(rec._may_send_in(self.env.user)),
            'missing': rec._missing_for_send_in()
            if rec.request_state not in SENT_STATES[:3] else [],
            'can_agree': bool(can_agree),
            'can_budget': can_recruit or self._can_write(),
            'can_setup': self._can_write(),
            'can_open_role': rec.state == 'setup' and can_recruit,
            'offer_block_reason': rec._offer_block_reason(),
        }

    @api.model
    def _request_trail(self, rec):
        """asked → sent in → Head of HR agreed → agreed, with who and when."""
        out = []

        def add(key, label, who='', when=None, done=True, tone=''):
            out.append({'key': key, 'label': label, 'who': who or '',
                        'when': str(when or ''), 'done': done, 'tone': tone})

        if rec.asked_on:
            add('asked', _('Asked'), rec.asked_by_id.name, rec.asked_on)
        if rec.manager_agreed_on:
            add('sent_in', _('Sent in'),
                rec.manager_agreed_by_id.name or rec.sent_in_by_id.name,
                rec.manager_agreed_on)
        request = rec.approval_request_id
        decided = False
        if request:
            for d in request.sudo().decision_ids.sorted('stamp'):
                if d.action == 'approve':
                    step = request.step_ids.filtered(
                        lambda s: s.key == d.step_key)[:1]
                    add('step', _('%s agreed', step.title or _('Head of HR')),
                        d.user_id.name, d.stamp)
                    decided = True
                elif d.action == 'reject':
                    add('stopped', _('Not approved'), d.user_id.name, d.stamp,
                        tone='rose')
                elif d.action == 'return':
                    add('returned', _('Sent back'), d.user_id.name, d.stamp,
                        tone='amber')
        if rec.request_state in REQUEST_WITH_HR:
            add('waiting', _('Waiting on %s', rec._agree_holders_names()),
                done=False, tone='amber')
        elif rec.request_state == 'agreed':
            if not decided and rec.agreed_on:
                add('agreed', _('Agreed'), '', rec.agreed_on)
            add('done', _('Request agreed'), '', rec.agreed_on, tone='green')
        elif rec.request_state == 'not_approved' and not request:
            add('stopped', _('Not approved'), '', rec.write_date, tone='rose')
        return out

    @api.model
    def _advert_block(self, req):
        rec = req.sudo()
        templates = self.env['pb.hiring.jd.template'].sudo().search(
            [('company_id', '=', rec.company_id.id)])
        suggested = self.env['pb.hiring.jd.template']._for_role(rec)
        jds = []
        for jd in rec.jd_ids.sorted('version', reverse=True):
            jds.append({
                'id': jd.id, 'version': jd.version or 1,
                'title': jd.title or '', 'state': jd.state,
                'is_current': bool(jd.is_current),
                'shared_with': jd.shared_with_id.name or '',
                'shared_on': str(jd.shared_on or ''),
                'final_on': str(jd.approved_on or ''),
                'template': jd.template_id.name or '',
                'comments': [{'id': c.id, 'who': c.author_name or '',
                              'body': c.body or '',
                              'on': str(c.create_date or '')}
                             for c in jd.comment_ids[:20]],
            })
        manager = rec.asked_employee_id or rec.requested_by_id \
            or rec.reporting_manager_id
        return {
            'templates': [{'id': t.id, 'name': t.name or '',
                           'family': t.family or ''} for t in templates],
            'suggested_id': suggested.id,
            'versions': jds,
            'stale': bool(rec.advert_stale),
            'share_to': manager.name or '',
            'can_edit': bool(self._can_recruit(req)),
        }

    # =====================================================================
    #  The verbs — the role
    # =====================================================================
    def _act_new_role(self, payload):
        """"Open a role": five things, and the role exists (G-14)."""
        if not self._can_recruit():
            raise AccessError(_(
                "Opening a role is for the hiring team. A manager asks for "
                "one with a hiring request."))
        title = (payload.get('title') or '').strip()
        dept = self.env['hr.department'].sudo().browse(
            as_id(payload.get('department_id'))).exists()
        if not title or not dept:
            raise UserError(_("A role needs a name and a department."))
        vals = {
            'title': title[:120], 'department_id': dept.id,
            'company_id': (dept.company_id or self.env.company).id,
            'headcount': max(1, min(500, int(payload.get('headcount') or 1))),
        }
        if payload.get('country_id'):
            vals['country_id'] = as_id(payload['country_id'])
        if payload.get('recruiter_id'):
            vals['recruiter_id'] = as_id(payload['recruiter_id'])
        me = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if me:
            vals['requested_by_id'] = me.id
        req = self.env['pb.hiring.requisition'].create(vals)
        return {'id': req.id, 'name': req.name,
                'note': _("%s is set up. Publish it, add candidates, or ask a "
                          "manager for the hiring request.", req.title)}

    def _act_ask_manager(self, payload):
        """"Ask a manager for a request" — on a role, or on a new one."""
        self._require_recruit()
        if payload.get('requisition_id'):
            req = self._get(payload)
            self._require_recruit(req)
        else:
            res = self._act_new_role(payload)
            req = self.env['pb.hiring.requisition'].browse(res['id'])
        employee = self.env['hr.employee'].sudo().browse(
            as_id(payload.get('employee_id'))).exists()
        out = req._ask(employee, payload.get('message') or '',
                       payload.get('remind_every_days') or 2)
        if out['mailed']:
            note = _("%s has the request by email. The card will say when "
                     "they open it and send it in.", out['who'])
        else:
            note = _("%s has no email address, so nothing was sent. Copy "
                     "their link and send it however you like.", out['who'])
        res = {'id': req.id, 'note': note}
        if not out['mailed']:
            res['link'] = out['link']
        return res

    def _act_remind_now(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        mailed = req._remind(manual=True)
        who = req.asked_employee_id.name or ''
        return {'id': req.id,
                'note': _("%s has been reminded.", who) if mailed else
                _("%s has no email address; the reminder is on the role's "
                  "timeline. Copy their link to send it yourself.", who)}

    def _act_copy_request_link(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        req._ensure_request_token()
        return {'id': req.id, 'link': req._request_url(),
                'note': _("The request page's link is on screen.")}

    def _act_send_in(self, payload):
        """"Send in myself" — the hiring team or the manager, from the app."""
        return self._act_submit(payload)

    def _act_request_agree(self, payload):
        req = self._get(payload)
        req._request_agree(note=payload.get('note'))
        req.invalidate_recordset()
        return {'id': req.id, 'request_state': req.request_state,
                'note': _("Agreed. An offer can be sent now.")
                if req.request_state == 'agreed'
                else _("Agreed. It now waits on the next person.")}

    def _act_request_decline(self, payload):
        req = self._get(payload)
        req._request_decline(note=payload.get('note'))
        return {'id': req.id, 'request_state': req.request_state,
                'note': _("Not approved. The role carries on; the recruiter "
                          "has a to-do.")}

    def _act_set_budget(self, payload):
        """The confirmed figure and the tracking tag (R2). Blocks nothing."""
        req = self._get(payload)
        if not (self._can_recruit(req) or self._can_write()):
            raise AccessError(_("The budget figures are the hiring team's."))
        vals = {}
        if 'budget_confirmed' in payload:
            try:
                vals['budget_confirmed'] = max(0.0, float(
                    str(payload.get('budget_confirmed') or 0).replace(',',
                                                                      '')))
            except (TypeError, ValueError):
                raise UserError(_("Type the confirmed budget as a number."))
        if payload.get('budget_agreement') in dict(BUDGET_AGREEMENT):
            vals['budget_agreement'] = payload['budget_agreement']
        if not vals:
            return {'id': req.id}
        req.sudo().write(vals)
        req._refresh_budget(silent=True)
        return {'id': req.id, 'note': req.budget_note or _("Saved.")}

    def _act_set_confidential(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        on = bool(payload.get('on'))
        req.sudo().write({'is_confidential': on})
        if not on:
            req._log_role(_("No longer confidential. Open referrals and "
                            "publish it again when you are ready."))
        return {'id': req.id, 'is_confidential': on,
                'note': _("Confidential: off referrals and the careers page, "
                          "and seen only by the hiring team, the person it is "
                          "for and who they would report to.") if on
                else _("No longer confidential.")}

    # ------------------------------------------------------------ the advert
    def _jd(self, payload):
        jd = self.env['pb.hiring.jd'].browse(as_id(payload.get('jd_id')))
        jd.ensure_one()
        self._require_recruit(jd.sudo().requisition_id)
        return jd

    def _act_make_final(self, payload):
        jd = self._jd(payload)
        jd.sudo().action_make_final()
        req = jd.sudo().requisition_id
        return {'id': jd.id, 'state': jd.state,
                'note': _("Version %s is the advert now. It is on the job "
                          "already; press Republish to refresh the job-board "
                          "packs.", jd.version) if req.published
                else _("Version %s is the advert now.", jd.version)}

    def _act_jd_from_template(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        tpl = self.env['pb.hiring.jd.template'].sudo().browse(
            as_id(payload.get('template_id'))).exists()
        if not tpl:
            raise UserError(_("Pick a template."))
        jd = self.env['pb.hiring.jd'].sudo().create({
            'requisition_id': req.id, 'title': req.title,
            'body': tpl.body or '', 'template_id': tpl.id})
        req.sudo().write({'jd_template_id': tpl.id})
        return {'id': jd.id, 'jd_id': jd.id,
                'note': _("Version %(n)s started from %(t)s. Edit it, share "
                          "it with the manager, then make it final.",
                          n=jd.version, t=tpl.name)}

    def _act_share_jd(self, payload):
        jd = self._jd(payload)
        employee = self.env['hr.employee'].sudo().browse(
            as_id(payload.get('employee_id'))).exists() or None
        out = jd.sudo().action_share(employee)
        res = {'id': jd.id,
               'note': _("Shared with %s for input. Their comments land on "
                         "the role.", out['who']) if out['mailed']
               else _("%s has no email address. Copy the link and send it "
                      "yourself.", out['who'])}
        if not out['mailed']:
            res['link'] = out['link']
        return res

    def _act_copy_jd_link(self, payload):
        jd = self._jd(payload)
        jd.sudo()._ensure_share_token()
        return {'id': jd.id, 'link': jd.sudo()._share_url(),
                'note': _("The comment page's link is on screen.")}

    def _act_republish(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        return self.env['pb.hiring.posting'].publish_for(req.id)

    # =====================================================================
    #  The ask sheet's lists, and set-up's "Who does what"
    # =====================================================================
    @api.model
    def journey_options(self):
        res = super().journey_options()
        group = self.env.ref(GROUP_USER, raise_if_not_found=False)
        co = self.env.companies.ids or [self.env.company.id]
        users = group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share
            and set(u.company_ids.ids) & set(co)) if group else []
        res['recruiters'] = sorted([{'id': u.id, 'name': u.name or ''}
                                    for u in users],
                                   key=lambda r: fold(r['name']))
        res['departments'] = self._safe(lambda: self._departments(co),
                                        default=[])
        res['me'] = self.env.uid
        return res

    @api.model
    def ask_people(self, query='', department_id=None, limit=40):
        """Employees for the Ask sheet's search (accent-blind, R78). The
        department's own people first."""
        if not self._can_recruit():
            return []
        co = self.env.companies.ids or [self.env.company.id]
        rows = self.env['hr.employee'].sudo().search_read(
            [('company_id', 'in', co)],
            ['id', 'name', 'job_title', 'department_id', 'work_email',
             'user_id'], limit=5000)
        q = fold(query or '')
        dep = as_id(department_id)
        out = []
        for r in rows:
            if q and q not in fold(r['name'] or ''):
                continue
            out.append({'id': r['id'], 'name': r['name'] or '',
                        'role': r.get('job_title') or '',
                        'department': r['department_id'][1]
                        if r.get('department_id') else '',
                        'has_email': bool(r.get('work_email')
                                          or r.get('user_id')),
                        'mine': bool(dep and r.get('department_id')
                                     and r['department_id'][0] == dep)})
        out.sort(key=lambda r: (not r['mine'], fold(r['name'])))
        return out[:max(1, min(int(limit or 40), 200))]

    @api.model
    def get_setup(self):
        res = super().get_setup()
        company = self.env.company
        people = company.sudo().pb_budget_flag_user_ids
        users = self.env['res.users'].sudo().search(
            [('share', '=', False), ('company_ids', 'in', company.ids)],
            limit=500)
        who = {
            'budget_flag': [{'id': u.id, 'name': u.name or ''}
                            for u in people],
            'budget_flag_sentence': _(
                "Nobody is named yet. Until somebody is, an over-budget "
                "request gives the Head of hiring a to-do.") if not people
            else '',
            'mr_approver': {'id': company.pb_mr_approver_id.id,
                            'name': company.pb_mr_approver_id.name}
            if company.pb_mr_approver_id else None,
            'docreq_trigger': text(self.env, P_DOCREQ_TRIGGER,
                                   'on_check_clear'),
            'docreq_triggers': [{'key': k, 'label': v}
                                for k, v in DOCREQ_TRIGGERS],
            'users': sorted([{'id': u.id, 'name': u.name or ''}
                             for u in users], key=lambda r: fold(r['name'])),
            'company': company.name,
            'sender': self._sender(company),
        }
        res['who'] = who
        res['switches']['referral_announce'] = flag(self.env,
                                                    P_REFERRAL_ANNOUNCE)
        for card in res.get('cards', []):
            if card['key'] == 'people':
                n = len(people)
                card.update({
                    'status': _("Over budget tells %s. Recruiter, Talent lead "
                                "and Head of hiring are given on the Access "
                                "screen.", ', '.join(people.mapped('name')))
                    if n else _("Nobody is told about over-budget requests "
                                "yet. Name them here."),
                    'inline': True, 'live': False})
        return res

    def _act_set_budget_people(self, payload):
        self._require_write()
        ids = [as_id(i) for i in payload.get('user_ids') or []]
        users = self.env['res.users'].sudo().browse(ids).exists().filtered(
            lambda u: not u.share)
        company = self.env.company.sudo()
        before = company.pb_budget_flag_user_ids
        company.write({'pb_budget_flag_user_ids': [(6, 0, users.ids)]})
        return {'before': before.ids,
                'note': _("Over-budget requests now tell %s.",
                          ', '.join(users.mapped('name')))
                if users else _("Nobody is told about over-budget requests "
                                "now; the Head of hiring gets a to-do "
                                "instead.")}

    def _act_set_mr_approver(self, payload):
        self._require_write()
        user = self.env['res.users'].sudo().browse(
            as_id(payload.get('user_id'))).exists()
        if user and user.share:
            raise UserError(_("The approver has to be somebody with a full "
                              "login."))
        self.env.company.sudo().write({'pb_mr_approver_id': user.id or False})
        return {'note': _("%s now agrees every hiring request after the Head "
                          "of HR.", user.name) if user
                else _("No extra approver: the Head of HR's agreement is "
                       "enough.")}

    def _act_set_docreq_trigger(self, payload):
        self._require_write()
        key = payload.get('key')
        if key not in dict(DOCREQ_TRIGGERS):
            raise UserError(_("That is not one of the moments."))
        self.env['ir.config_parameter'].sudo().set_param(P_DOCREQ_TRIGGER,
                                                         key)
        return {'note': _("Papers are now asked for %s.",
                          dict(DOCREQ_TRIGGERS)[key].lower())}

    def _act_set_switch(self, payload):
        if payload.get('key') == 'referral_announce':
            self._require_write()
            on = bool(payload.get('on'))
            self.env['ir.config_parameter'].sudo().set_param(
                P_REFERRAL_ANNOUNCE, '1' if on else '0')
            return {'on': on, 'note': _("Switched on.") if on
                    else _("Switched off.")}
        return super()._act_set_switch(payload)
