# -*- coding: utf-8 -*-
"""What the offer phase adds to the board's one server surface.

THE SHAPE IS THE SAME AND THE RULES ARE THE SAME: `@api.model` reads, `_safe`
around every independent probe, the company boundary written into every
domain, no sudo in a read except where a field's own `groups=` forces it, and
one `act` verb per press. This file exists so that A3 is reviewable on its own
rather than as a diff through eight hundred lines somebody else wrote.

ONE REAL CHANGE TO AN EXISTING RULE, and it is the cover. `_can_recruit` used
to ask only "does this person hold a hiring group". It now also asks "is this
person standing in for the recruiter whose role this is" — and, crucially, the
second question is asked ABOUT A ROLE. A cover is not a promotion: somebody
covering for one recruiter for a fortnight may work on that recruiter's roles
and on nobody else's, and a gate that could not see which role it was being
asked about could not say that.
"""

import base64
import logging
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .hiring_common import (
    BGV_RESULTS, BGV_STATES, CANDIDATE_DECISIONS, DOCREQ_STATES, OFFER_KINDS,
    OFFER_LETTER_TYPE, OFFER_PERIODS, OFFER_STATES, as_id,
)

_logger = logging.getLogger(__name__)


class PbHiringA3(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  The gate, with the cover in it
    # =====================================================================
    @api.model
    def _covered_uids(self):
        return self.env['pb.hiring.cover'].covered_recruiter_uids()

    @api.model
    def _can_read(self):
        """A cover has to be able to OPEN the board, or it is a permission
        with no screen behind it.

        Found live on 2026-09-15: a colleague standing in for a recruiter was
        allowed every action on that recruiter's roles and was shown "Hiring
        is looked after by the hiring team" when they went to do any of them.
        The gate that decides what somebody may DO and the gate that decides
        whether they may LOOK have to agree, or the more generous of the two
        is unreachable.
        """
        return super()._can_read() or bool(self._covered_uids())

    @api.model
    def _can_recruit(self, requisition=None):
        """May this person do a recruiter's work — and on WHICH role.

        A cover answers for exactly the roles of the recruiter it is standing
        in for. Asked without a role (the board deciding whether to draw the
        buttons at all) an active cover answers yes, and every press is then
        checked against the role it is about — an offer the server would
        refuse is worse than no offer, but a button that is missing for
        somebody who does have cover is worse still.
        """
        if super()._can_recruit():
            return True
        covered = self._covered_uids()
        if not covered:
            return False
        if requisition is None:
            return True
        return requisition.sudo().recruiter_id.id in covered

    @api.model
    def _require_recruit(self, requisition=None):
        """STRICTER THAN THE DISPLAY GATE, and deliberately so.

        `_can_recruit(None)` answers yes for somebody with any live cover, so
        the board draws their buttons. This is the door itself, and a door
        that could not see which role it was being asked about would turn a
        fortnight's cover for one colleague into the run of the place. A
        cover-only caller therefore has to NAME the role, and it has to be one
        of the roles they are covering.
        """
        if super()._can_recruit():                  # a real hiring group
            return True
        covered = self._covered_uids()
        if covered:
            if requisition is not None and requisition \
                    and requisition.sudo().recruiter_id.id in covered:
                return True
            raise AccessError(_(
                "You are standing in for somebody, and this is not one of "
                "their roles. Ask the recruiter on it, or ask the HR team to "
                "add you to the hiring team."))
        return super()._require_recruit()

    @api.model
    def _cover_scope(self):
        """The recruiters this reader is STANDING IN FOR and nothing else.

        Empty for anybody who holds a hiring group of their own — they can
        already see everything their tier allows, and reading around the
        record rules for them would be a hole rather than a courtesy.
        """
        if super()._can_recruit():
            return []
        return self._covered_uids()

    # =====================================================================
    #  The board
    # =====================================================================
    @api.model
    def get_board(self, limit=None):
        # A COVER IS READ AS THE SYSTEM, WITH THE BOUNDARY IN THE DOMAIN.
        # The record rules let a plain user see the roles they raised, manage
        # or recruit — and a stand-in is none of those, so the board opened
        # empty for somebody the server would happily let publish an advert
        # (found live 2026-09-15, one press after the cover started). Widening
        # the rule was the other option and it is the worse one: an `ir.rule`
        # domain is memoised in the `default` ormcache group, which nothing
        # about creating a cover invalidates, so a cover would start working
        # some time later (R59 from the other side). Reading as the system
        # with the recruiter clause WRITTEN OUT is the doctrine this module
        # already uses everywhere else (R89).
        covered = self._safe(lambda: self._cover_scope(), default=[])
        board = super(PbHiringA3, self.sudo() if covered else self).get_board(
            limit=limit)
        if covered:
            board['rows'] = [r for r in board['rows']
                             if r['recruiter_id'] in covered]
            board['total'] = len(board['rows'])
            board['capped'] = False
            board['kpis'] = self._kpis(board['rows'], board.get('interviews'))
        if not board.get('allowed'):
            board.update({'offer_rows': [], 'agencies': [],
                          'my_cover': {}, 'covering': []})
            return board
        board['offer_rows'] = self._safe(lambda: self._offer_rows(), default=[])
        board['agencies'] = self._safe(lambda: self._agencies(), default=[])
        board['covering'] = self._safe(lambda: self._covering(), default=[])
        board['kpis'].update(self._safe(
            lambda: self._offer_kpis(board['offer_rows']), default={}))
        board['offer_states'] = [{'key': k, 'label': v}
                                 for k, v in OFFER_STATES]
        board['bgv_results'] = [{'key': k, 'label': v} for k, v in BGV_RESULTS]
        board['offer_kinds'] = [{'key': k, 'label': v} for k, v in OFFER_KINDS]
        board['offer_periods'] = [{'key': k, 'label': v}
                                  for k, v in OFFER_PERIODS]
        return board

    @api.model
    def _offer_rows(self):
        co_ids = self.env.companies.ids or [self.env.company.id]
        rows = self.env['pb.hiring.offer'].search(
            [('company_id', 'in', co_ids)], order='id desc', limit=200)
        return [self._offer_row(offer) for offer in rows]

    @api.model
    def _offer_kpis(self, offer_rows):
        month_start = date.today().replace(day=1)
        return {
            'offers_out': sum(1 for r in offer_rows
                              if r['state'] in ('sent', 'accepted', 'signed')),
            'filled_month': sum(1 for r in offer_rows
                                if r['state'] == 'closed' and r['closed_on']
                                and r['closed_on'][:10] >= str(month_start)),
        }

    @api.model
    def _covering(self):
        """Who this reader is standing in for right now, in names."""
        Cover = self.env['pb.hiring.cover']
        rows = Cover.sudo().browse()
        uids = Cover.covered_recruiter_uids()
        if uids:
            today = fields.Date.context_today(self)
            rows = Cover.sudo().search([
                ('cover_user_id', '=', self.env.uid),
                ('state', 'in', ('approved', 'active')),
                ('date_from', '<=', today), ('date_to', '>=', today)])
        return [{'id': r.id, 'who': r.recruiter_id.name or '',
                 'until': str(r.date_to or '')} for r in rows]

    @api.model
    def _agencies(self):
        rows = self.env['pb.vendor'].sudo().search_read(
            [('vendor_type', '=', 'recruitment'),
             ('company_id', 'in', self.env.companies.ids
              or [self.env.company.id])], ['id', 'name'], limit=100)
        return [{'id': r['id'], 'name': r['name'] or ''} for r in rows]

    # =====================================================================
    #  One request, in full
    # =====================================================================
    @api.model
    def get_requisition(self, requisition_id):
        # The same rule as the board: a stand-in reads the roles they are
        # covering as the system, and nothing else at all.
        covered = self._safe(lambda: self._cover_scope(), default=[])
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(requisition_id))
        if covered and req.recruiter_id.id not in covered:
            raise AccessError(_(
                "You are standing in for somebody, and this is not one of "
                "their roles."))
        me = self.sudo() if covered else self
        row = super(PbHiringA3, me).get_requisition(requisition_id)
        req = me.env['pb.hiring.requisition'].browse(as_id(requisition_id))
        row.update({
            'agency_id': req.agency_vendor_id.id,
            'agency': req.agency_vendor_id.sudo().name or '',
            'agencies': self._safe(lambda: self._agencies(), default=[]),
            'filled_count': req.filled_count,
            'offer_out_count': req.offer_out_count,
            'filled_on': str(req.filled_on or ''),
            'letter_templates': self._safe(
                lambda: self._letter_templates(req), default=[]),
            'cover': self._safe(lambda: self._cover_banner(req), default={}),
            'journey': self._safe(lambda: self._journey(req), default={}),
            'offers': self._safe(
                lambda: [self._offer_row(o, full=True)
                         for o in req.offer_ids.sorted(lambda o: -o.id)],
                default=[]),
        })
        return row

    @api.model
    def _letter_templates(self, req):
        rows = self.env['pb.letter.template'].sudo().search_read(
            ['|', ('company_id', '=', False),
             ('company_id', '=', req.company_id.id),
             ('letter_type', '=', OFFER_LETTER_TYPE)],
            ['id', 'name'], limit=50)
        return [{'id': r['id'], 'name': r['name'] or ''} for r in rows]

    @api.model
    def _cover_banner(self, req):
        cover = self.env['pb.hiring.cover'].active_for_recruiter(
            req.recruiter_id)
        if not cover:
            return {}
        return {'id': cover.id, 'who': cover.cover_user_id.name or '',
                'recruiter': cover.recruiter_id.name or '',
                'until': str(cover.date_to or '')}

    @api.model
    def _journey(self, req):
        """THE PATH STRIP: six chips, each one a state and a door.

        This is the hero of the drawer and it is computed on the SERVER for
        the same reason every other decision in this module is: a second
        opinion written in JavaScript about where a candidate has got to would
        only ever disagree with the one that counts.
        """
        applicant = req.sudo().selected_applicant_id
        if not applicant:
            return {'ready': False,
                    'why': _("Nobody has been picked for this role yet. "
                             "Record the debrief on the last conversation and "
                             "this fills in.")}
        offer = req.offer_ids.filtered(
            lambda o: o.applicant_id.id == applicant.id
            and o.state not in ('refused', 'declined')).sorted(
                lambda o: -o.id)[:1]
        if not offer:
            offer = req.offer_ids.filtered(
                lambda o: o.applicant_id.id == applicant.id).sorted(
                    lambda o: -o.id)[:1]
        bgv = req.bgv_ids.filtered(
            lambda b: b.applicant_id.id == applicant.id)[:1]
        docreq = offer.docreq_id if offer else False

        def chip(key, label, tone, note, done=False):
            return {'key': key, 'label': label, 'tone': tone, 'note': note,
                    'done': done}

        chips = [
            # ONE WORD, because the strip is six chips wide and the box
            # clips rather than wraps: "Background check" came back as
            # "Background c…" on a 1500px screen (R63's rule — prefer a
            # label whose longest word fits, and let the line under it carry
            # the meaning).
            chip('bgv', _('Background'),
                 'done' if bgv and bgv.state == 'complete'
                 else 'warn' if bgv and bgv.state == 'flagged'
                 else 'live' if bgv else 'todo',
                 (dict(BGV_STATES).get(bgv.state, '') if bgv
                  else _('Not started')),
                 done=bool(bgv and bgv.state == 'complete')),
            chip('documents', _('Documents'),
                 'done' if docreq and docreq.state == 'complete'
                 else 'warn' if docreq and docreq.state == 'expired'
                 else 'live' if docreq else 'todo',
                 (_('%(in)s of %(total)s in', **{'in': docreq.in_count,
                                                 'total': len(docreq.item_ids)})
                  if docreq else _('Not asked for yet')),
                 done=bool(docreq and docreq.state == 'complete')),
            chip('offer', _('Offer'),
                 'done' if offer and offer.state in (
                     'hr_ok', 'sent', 'accepted', 'signed', 'closed')
                 else 'live' if offer else 'todo',
                 (dict(OFFER_STATES).get(offer.state, '') if offer
                  else _('Not drafted')),
                 done=bool(offer and offer.state in (
                     'hr_ok', 'sent', 'accepted', 'signed', 'closed'))),
            chip('candidate', _('Their answer'),
                 'done' if offer and offer.candidate_decision == 'accepted'
                 else 'warn' if offer and offer.candidate_decision == 'declined'
                 else 'live' if offer and offer.state == 'sent' else 'todo',
                 (dict(CANDIDATE_DECISIONS).get(offer.candidate_decision, '')
                  if offer else _('Waiting on the offer')),
                 done=bool(offer and offer.candidate_decision == 'accepted')),
            chip('signed', _('Signed'),
                 'done' if offer and offer.signed_on else 'todo',
                 (str(offer.signed_on) if offer and offer.signed_on
                  else _('Not yet')),
                 done=bool(offer and offer.signed_on)),
            chip('day_one', _('Day one'),
                 'done' if offer and offer.state == 'closed' else 'todo',
                 (str(offer.start_date) if offer and offer.start_date
                  else _('Not yet')),
                 done=bool(offer and offer.state == 'closed')),
        ]
        return {
            'ready': True,
            'applicant_id': applicant.id,
            'candidate': applicant.sudo().partner_name or '',
            'chips': chips,
            'bgv': self._bgv_payload(bgv) if bgv else {},
            'docreq': self._docreq_payload(docreq) if docreq else {},
            'offer': self._offer_row(offer, full=True) if offer else {},
        }

    # =====================================================================
    #  The payloads
    # =====================================================================
    @api.model
    def _bgv_payload(self, bgv):
        ready, why = bgv.check_ready()
        return {
            'id': bgv.id,
            'state': bgv.state,
            'state_label': dict(BGV_STATES).get(bgv.state, ''),
            'pending': bgv.pending_count,
            'flags': bgv.flag_count,
            'ready': ready,
            'why': why,
            'override_by': bgv.override_user_id.name or '',
            'override_note': bgv.override_note or '',
            'items': [{
                'id': i.id,
                'name': i.name or '',
                'help': i.help_text or '',
                'required': bool(i.required),
                'result': i.result,
                'result_label': dict(BGV_RESULTS).get(i.result, ''),
                'note': i.note or '',
                'by': i.checked_by_id.name or '',
                'files': len(i.attachment_ids),
            } for i in bgv.item_ids.sorted(lambda r: (r.sequence, r.id))],
        }

    @api.model
    def _docreq_payload(self, docreq):
        return {
            'id': docreq.id,
            'state': docreq.state,
            'state_label': dict(DOCREQ_STATES).get(docreq.state, ''),
            'deadline': str(docreq.deadline or ''),
            'sent_on': str(docreq.sent_on or ''),
            'reminded_on': str(docreq.last_reminder_on or ''),
            'in': docreq.in_count,
            'total': len(docreq.item_ids),
            'items': [{
                'id': i.id,
                'name': i.name or '',
                'required': bool(i.required),
                'received': str(i.received_at or ''),
                'attachment_id': i.attachment_id.id,
            } for i in docreq.item_ids.sorted(lambda r: (r.sequence, r.id))],
        }

    @api.model
    def _offer_row(self, offer, full=False):
        # NEVER THE TOKEN, on any payload, ever (R13). The board's "copy the
        # link" verb asks for it by id and returns it on its own, so it
        # travels only when somebody has pressed something.
        row = {
            'id': offer.id,
            'name': offer.name or '',
            'requisition_id': offer.requisition_id.id,
            'role': offer.job_title or '',
            'applicant_id': offer.applicant_id.id,
            'candidate': offer.candidate_name or '',
            'state': offer.state,
            'state_label': dict(OFFER_STATES).get(offer.state, ''),
            'start_date': str(offer.start_date or ''),
            'monthly_total': offer.monthly_total or 0.0,
            'annual_total': offer.annual_total or 0.0,
            'currency': offer.currency_id.name or '',
            'decision': offer.candidate_decision or 'pending',
            'decision_label': dict(CANDIDATE_DECISIONS).get(
                offer.candidate_decision or 'pending', ''),
            'comment': offer.candidate_comment or '',
            'signed_on': str(offer.signed_on or ''),
            'closed_on': str(offer.closed_on or ''),
            'has_letter': bool(offer.attachment_id),
            'has_signed': bool(offer.signed_attachment_id),
        }
        if not full:
            return row
        ok, why = offer._documents_ready()
        row.update({
            'location': offer.location or '',
            'template_id': offer.letter_template_id.id,
            'template': offer.letter_template_id.sudo().name or '',
            'attachment_id': offer.attachment_id.id,
            'documents_ready': ok,
            'documents_why': why,
            'employee_id': offer.employee_id.id,
            'contract_id': offer.contract_id.id,
            'comp_id': offer.comp_id.id,
            'case_id': offer.case_id.id,
            'login': offer.login_user_id.sudo().login or '',
            'lines': [{
                'id': ln.id,
                'name': ln.name or '',
                'kind': ln.kind or '',
                'kind_label': dict(OFFER_KINDS).get(ln.kind, ''),
                'amount': ln.amount or 0.0,
                'period': ln.period or '',
                'period_label': dict(OFFER_PERIODS).get(ln.period, ''),
                'note': ln.note or '',
            } for ln in offer.line_ids.sorted(lambda r: (r.sequence, r.id))],
        })
        return row

    # =====================================================================
    #  The verbs
    # =====================================================================
    def _offer(self, payload, key='offer_id'):
        offer = self.env['pb.hiring.offer'].browse(
            as_id(payload.get(key) or payload.get('id')))
        offer.ensure_one()
        return offer

    # ------------------------------------------------- the background check
    def _act_open_bgv(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        bgv = self.env['pb.hiring.bgv'].open_for(req.id)
        return {'id': bgv.id, 'bgv': self._bgv_payload(bgv)}

    def _act_set_bgv_item(self, payload):
        item = self.env['pb.hiring.bgv.item'].browse(
            as_id(payload.get('item_id')))
        item.ensure_one()
        self._require_recruit(item.bgv_id.requisition_id)
        item.action_set(payload.get('result'), note=payload.get('note'))
        return {'id': item.id,
                'bgv': self._bgv_payload(item.bgv_id),
                'note': _("%(what)s: %(answer)s.", what=item.name or '',
                          answer=dict(BGV_RESULTS).get(item.result, ''))}

    def _act_bgv_override(self, payload):
        bgv = self.env['pb.hiring.bgv'].browse(as_id(payload.get('bgv_id')))
        bgv.ensure_one()
        bgv.action_override(note=payload.get('note'))
        return {'id': bgv.id, 'bgv': self._bgv_payload(bgv),
                'note': _("Written down. The offer can be drafted now.")}

    # ------------------------------------------------------- the documents
    def _act_request_documents(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        docreq = offer.action_request_documents()
        return {'id': docreq.id,
                'note': _("Asked %(who)s for their papers by %(when)s.",
                          who=offer.candidate_name or '',
                          when=docreq.deadline or '')}

    def _act_remind_documents(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        docreq = offer.docreq_id
        if not docreq:
            raise UserError(_("Nobody has been asked for anything yet."))
        # THREE DIFFERENT ANSWERS AND NOT TWO. "Already reminded today" over a
        # candidate who has sent everything is a sentence that makes a
        # recruiter go looking for a problem that is not there — found live
        # on 2026-09-15, one press after the last document landed.
        if docreq.state == 'complete':
            return {'id': docreq.id,
                    'note': _("They have sent everything — there is nothing "
                              "left to chase.")}
        sent = docreq.action_remind()
        return {'id': docreq.id,
                'note': _("Reminder sent.") if sent else
                _("They were already reminded today — one a day is enough.")}

    def _act_copy_doc_link(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        docreq = offer.docreq_id
        if not docreq:
            raise UserError(_("Nobody has been asked for anything yet."))
        return {'id': docreq.id, 'link': docreq.sudo()._token_url(),
                'note': _("Their own link is on screen.")}

    # ------------------------------------------------------------ the offer
    def _act_draft_offer(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        offer = self.env['pb.hiring.offer'].draft_for(req.id, payload)
        return {'id': offer.id, 'offer': self._offer_row(offer, full=True),
                'note': _("%s is open. Put the numbers on it, then send it "
                          "for sign-off.", offer.name)}

    def _act_offer_set(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        vals = {}
        for key in ('job_title', 'location'):
            if payload.get(key) is not None:
                vals[key] = (payload.get(key) or '').strip()
        if payload.get('start_date'):
            vals['start_date'] = payload['start_date']
        if payload.get('template_id'):
            vals['letter_template_id'] = as_id(payload['template_id'])
        if vals:
            offer.sudo().write(vals)
        return {'id': offer.id, 'offer': self._offer_row(offer, full=True)}

    def _act_offer_line(self, payload):
        """Add, change or remove one line. ONE VERB, because the board's
        editor is one grid and three verbs would be three round trips for
        what a person thinks of as one edit."""
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        # DRAFT ONLY, and the reason is the engine rather than tidiness.
        # A route stamps the numbers when it is sent in and re-reads them when
        # the LAST rung is given, so a figure changed mid-route does not
        # "reopen" anything — it makes the final approval refuse to carry out,
        # and the offer then sits agreed-but-blocked with a sentence nobody
        # asked for. Found live on 2026-09-15 by changing an allowance after
        # the hiring manager had agreed it. Refusing the edit at the door is
        # the same rule said at the moment a person can still act on it.
        if offer.state != 'draft':
            raise UserError(_(
                "This offer has been sent for sign-off, and the numbers are "
                "what somebody is agreeing to. Ask whoever it is waiting on "
                "to send it back, then change it and send it again."))
        Line = self.env['pb.hiring.offer.line'].sudo()
        line_id = as_id(payload.get('line_id'))
        if payload.get('remove') and line_id:
            Line.browse(line_id).unlink()
            return {'id': offer.id, 'offer': self._offer_row(offer, full=True)}
        vals = {
            'name': (payload.get('name') or '').strip(),
            'kind': payload.get('kind') or 'earning',
            'amount': float(payload.get('amount') or 0.0),
            'period': payload.get('period') or 'monthly',
            'note': (payload.get('note') or '').strip(),
        }
        if not vals['name']:
            raise UserError(_(
                "Say what the line is. “25,000,000” on its own is a number "
                "nobody can check."))
        if line_id:
            Line.browse(line_id).write(vals)
        else:
            vals['offer_id'] = offer.id
            vals['sequence'] = (max(offer.line_ids.mapped('sequence') or [0])
                                + 10)
            Line.create(vals)
        offer.invalidate_recordset(['monthly_total', 'annual_total'])
        return {'id': offer.id, 'offer': self._offer_row(offer, full=True)}

    def _act_prepare_letter(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        offer.action_prepare_letter()
        return {'id': offer.id, 'offer': self._offer_row(offer, full=True),
                'note': _("The letter is written. Open it and read it before "
                          "it goes anywhere.")}

    def _act_offer_letter(self, payload):
        """The letter as it will read, for a look before it is sent."""
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        if not offer.rendered_html:
            offer.action_prepare_letter()
        return {'id': offer.id, 'html': offer.rendered_html or '',
                'attachment_id': offer.attachment_id.id}

    def _act_submit_offer(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        offer.action_submit()
        return {'id': offer.id, 'state': offer.state,
                'note': _("Sent for sign-off. You will see it move as each "
                          "person agrees it.")}

    def _act_send_offer(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        offer.action_send_to_candidate(force=bool(payload.get('force')))
        return {'id': offer.id, 'state': offer.state,
                'note': _("Sent to %s, with the letter attached and a page to "
                          "answer on.", offer.candidate_name or '')}

    def _act_record_signed(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        content = None
        if payload.get('data'):
            try:
                content = base64.b64decode(payload['data'])
            except Exception:           # noqa: BLE001 — never a traceback
                raise UserError(_(
                    "That file did not arrive in one piece. Try it again."))
        offer.action_record_signed(filename=payload.get('filename'),
                                   content=content,
                                   mimetype=payload.get('mimetype'),
                                   signed_on=payload.get('signed_on'))
        return {'id': offer.id, 'state': offer.state,
                'note': _("Recorded. %s is a joiner — close the offer and "
                          "everything else follows.",
                          offer.candidate_name or '')}

    def _act_close_offer(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        offer.action_close()
        return {'id': offer.id, 'state': offer.state,
                'offer': self._offer_row(offer, full=True),
                'note': _("%(who)s joins on %(when)s. Their record, their "
                          "contract, their pay package and their joining "
                          "checklist are all ready.",
                          who=offer.candidate_name or '',
                          when=offer.start_date or '')}

    def _act_copy_offer_link(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        return {'id': offer.id, 'link': offer.sudo()._token_url(),
                'note': _("Their own link is on screen.")}

    def _act_open_offer(self, payload):
        offer = self._offer(payload)
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.offer', 'res_id': offer.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': offer.display_name}

    def _act_open_employee(self, payload):
        return self._offer(payload).action_open_employee()

    def _act_open_package(self, payload):
        return self._offer(payload).action_open_package()

    def _act_open_case(self, payload):
        return self._offer(payload).action_open_case()

    def _act_open_letter(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        return offer.action_open_pdf()

    # ----------------------------------------------------------- the agency
    def _act_set_agency(self, payload):
        req = self._get(payload)
        self._require_recruit(req)
        vendor_id = as_id(payload.get('vendor_id'))
        req.sudo().write({'agency_vendor_id': vendor_id or False})
        return {'id': req.id, 'agency_id': vendor_id,
                'note': _("%s is working on this role.",
                          req.agency_vendor_id.sudo().name or '')
                if vendor_id else _("No agency is on this role now.")}

    # ------------------------------------------------------------ the cover
    def _act_request_cover(self, payload):
        """Anybody who recruits may ask; the route decides."""
        self._require_recruit()
        cover = self.env['pb.hiring.cover'].sudo().create({
            'recruiter_id': as_id(payload.get('recruiter_id')) or self.env.uid,
            'cover_user_id': as_id(payload.get('cover_user_id')),
            'date_from': payload.get('date_from'),
            'date_to': payload.get('date_to'),
            'reason': (payload.get('reason') or '').strip(),
            'company_id': self.env.company.id,
        })
        cover.with_user(self.env.uid).action_submit()
        return {'id': cover.id,
                'note': _("Sent to %s to agree.",
                          cover.approver_user_id.name or _('your manager'))}

    def _act_end_cover(self, payload):
        cover = self.env['pb.hiring.cover'].browse(
            as_id(payload.get('cover_id')))
        cover.ensure_one()
        if not (cover.recruiter_id.id == self.env.uid
                or self._can_write()):
            raise AccessError(_(
                "Ending somebody's cover early is for the recruiter it is "
                "covering, or for the hiring managers."))
        cover.action_end(note=payload.get('note'))
        return {'id': cover.id, 'note': _("Cover finished.")}

    def _act_open_covers(self, payload):
        action = self.env.ref('pb_hiring.action_pb_hiring_cover',
                              raise_if_not_found=False)
        if not action:
            raise UserError(_("The cover screen is not in this build."))
        return action.read()[0]

    # --------------------------------------------------------- the numbers
    def _act_hiring_numbers(self, payload):
        return self.env['pb.hiring.analytics'].get_board(
            payload.get('from'), payload.get('to'))

    def _act_run_cover_window(self, payload):
        """"Run it now" does exactly what the night does (R53)."""
        self._require_recruit()
        Cover = self.env['pb.hiring.cover']
        counts = Cover.run_window()
        return {'note': Cover.describe_window(counts), 'counts': counts}
