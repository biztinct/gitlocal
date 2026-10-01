# -*- coding: utf-8 -*-
"""RECRUIT P6 — the screens' payloads and verbs for joining.

  * **The candidate drawer** (`get_candidate` → `joining`): the countdown,
    the "Before they join" list with one button per item, the signed
    documents with the market's expected set, the joining-date history, and
    the two doors: "Confirm they joined" and "Did not join".
  * **The Next box** on a Post-offer candidate: "Joining Mon 3 Nov · 9 days ·
    2 of 4 things done", the next open item as the button; from three days
    before the date the button is "Confirm they joined".
  * **The card**: "Joining in 9 days" (amber when an item is late, rose when
    the date has passed and nobody has confirmed).
  * **Hiring set-up → Before they join**: the company's list.

Nothing here decides who may do what beyond the usual gates
(`_require_recruit` on every verb; set-up verbs `_require_write`).
"""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    DROP_REASONS, JOIN_STATUS, OFFER_DOC_KINDS, PREJOIN_KINDS, PREJOIN_OWNERS,
    PREJOIN_STATES, UPLOAD_MAX_BYTES, UPLOAD_MIME_OK, as_id, slug_filename,
)
from .joining_p6 import _laptop_lines, _words

_logger = logging.getLogger(__name__)

#: From this many days before the joining date, "Confirm they joined" is the
#: primary button (both doors are always available).
CONFIRM_FROM_DAYS = 3

KIND_ICON = {'buddy': 'users', 'laptop': 'laptop', 'chat': 'coffee', 'todo': 'checkCircle'}


class PbHiringP6(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  Reading
    # =====================================================================
    @api.model
    def _join_offer(self, app):
        """The offer that tells this candidate's joining story."""
        return self.env['pb.hiring.offer'].sudo().search([
            ('applicant_id', '=', app.id),
            ('state', 'in', ('signed', 'joined', 'dropped'))],
            order='id desc', limit=1)

    @api.model
    def _days_words(self, days):
        if days is None:
            return ''
        if days == 0:
            return _('today')
        if days == 1:
            return _('tomorrow')
        if days > 1:
            return _('in %s days', days)
        if days == -1:
            return _('yesterday')
        return _('%s days ago', -days)

    @api.model
    def _item_row(self, item, offer, can_recruit):
        kinds, owners, states = dict(PREJOIN_KINDS), dict(PREJOIN_OWNERS), dict(PREJOIN_STATES)
        manager = offer._manager()
        owner_name = {
            'manager': manager.name if manager else _('the hiring manager'),
            'candidate': offer.candidate_name or _('the new joiner'),
            'recruiter': offer.requisition_id.sudo().recruiter_id.name or _('the recruiter'),
            'hr': _('HR'),
        }.get(item.owner, '')
        row = {
            'id': item.id, 'kind': item.kind, 'kind_label': kinds.get(item.kind, ''),
            'icon': KIND_ICON.get(item.kind, 'circle'),
            'title': item.title or '', 'owner': item.owner,
            'owner_label': owners.get(item.owner, ''), 'owner_name': owner_name,
            'due': str(item.due_date or ''),
            'due_words': _words(self.env, item.due_date, 'EEE d MMM'),
            'state': item.state, 'state_label': states.get(item.state, ''),
            'late': item.is_late(),
            'sent': bool(item.sent_at), 'sent_at': str(item.sent_at or ''),
            'reminded': bool(item.reminded_at),
            'done_at': str(item.done_on or ''), 'answered_by': item.answered_by or '',
            'answer': item._answer_text() if item.state == 'done' else '',
            'note': item.note or '',
            'removable': item.kind == 'todo',
        }
        if item.kind == 'chat' and item.chat_start:
            row['chat'] = {
                'when': str(item.chat_start), 'when_words': item._chat_when_words(),
                'minutes': item.chat_minutes or 30, 'mode': item.chat_mode or 'video',
                'where': item.chat_where or '', 'link': item.videocall_url or '',
                'people': item.chat_people_ids.sudo().mapped('name'),
                'people_ids': item.chat_people_ids.ids,
                'waiting_meet': bool(item.invites_pending),
            }
        verb = None
        if can_recruit and offer.state == 'signed':
            if item.state == 'open':
                if item.kind == 'buddy':
                    who = (manager.name or '').split(' ')[-1] if manager else ''
                    verb = {'verb': 'prejoin_send', 'label': (_('Remind %s', who) if item.sent_at
                                                              else _('Ask %s', who)) if who
                            else (_('Remind them') if item.sent_at else _('Send the question'))}
                elif item.kind == 'laptop':
                    verb = {'verb': 'prejoin_send', 'label': _('Remind them') if item.sent_at
                            else _('Send the question')}
                elif item.kind == 'chat':
                    verb = {'verb': 'chat_open', 'label': _('Change it') if item.chat_start
                            else _('Set it up')}
                else:
                    verb = {'verb': 'prejoin_done', 'label': _('Done')}
            elif item.state in ('done', 'skipped'):
                verb = {'verb': 'prejoin_reopen', 'label': _('Undo')}
        row['action'] = verb
        return row

    @api.model
    def _joining_payload(self, offer, can_recruit):
        offer = offer.sudo()
        today = fields.Date.context_today(self)
        expected = offer.expected_join_date or offer.start_date
        days = (expected - today).days if expected else None
        items = offer.prejoin_ids.filtered(lambda i: i.state != 'cancelled').sorted(
            lambda i: (i.sequence, i.id))
        rows = [self._item_row(i, offer, can_recruit) for i in items]
        done = len([r for r in rows if r['state'] in ('done', 'skipped')])
        late = len([r for r in rows if r['late']])
        nxt = next((r for r in rows if r['state'] == 'open'), None)
        kinds = dict(OFFER_DOC_KINDS)
        docs = []
        for doc in offer.document_ids.sorted(lambda d: (d.sequence, d.id)):
            att = doc.attachment_id
            docs.append({
                'id': doc.id, 'kind': doc.kind, 'kind_label': kinds.get(doc.kind, ''),
                'label': doc.label or kinds.get(doc.kind, ''),
                'name': att.name or '', 'url': '/web/content/%s?download=true' % att.id
                if att else '', 'signed_on': str(doc.signed_on or ''),
                'by': doc.recorded_by_id.name or '', 'filed': bool(doc.vault_doc_id),
            })
        changes = [{'at': str(c.create_date or ''), 'old': str(c.old_date or ''),
                    'new': str(c.new_date or ''),
                    'old_words': _words(self.env, c.old_date, 'EEE d MMM'),
                    'new_words': _words(self.env, c.new_date, 'EEE d MMM'),
                    'reason': c.reason or '', 'by': c.by_name or '',
                    'source': c.source or 'drawer'} for c in offer.join_change_ids]
        laptop = [{'label': k, 'value': v} for k, v in _laptop_lines(offer._laptop_prefs())]
        return {
            'offer_id': offer.id,
            'offer_name': offer.name or '',
            'state': offer.state,
            'join_status': offer.join_status or '',
            'join_status_label': dict(JOIN_STATUS).get(offer.join_status, ''),
            'expected': str(expected or ''),
            'expected_words': _words(self.env, expected, 'EEE d MMM'),
            'expected_long': _words(self.env, expected, 'EEEE d MMMM y'),
            'start_date': str(offer.start_date or ''),
            'days': days, 'days_words': self._days_words(days),
            'joined_on': str(offer.joined_on or ''),
            'joined_words': _words(self.env, offer.joined_on, 'EEE d MMM y'),
            'dropped_words': ' — '.join(x for x in (
                dict(DROP_REASONS).get(offer.drop_reason, ''), offer.drop_note or '') if x),
            'dropped_on': str(offer.dropped_on or ''),
            'items': rows, 'done': done, 'total': len(rows), 'late': late,
            'next_item': nxt,
            'documents': docs if can_recruit else [],
            'doc_count': len(docs),
            'doc_set': offer._doc_set() if can_recruit else {},
            'changes': changes,
            'week': {'sent_at': str(offer.week_before_sent_at or ''),
                     'answer': offer.week_answer or '',
                     'answer_label': dict(offer._fields['week_answer'].selection).get(
                         offer.week_answer, ''),
                     'by': offer.week_answered_by or '',
                     'at': str(offer.week_answered_at or '')},
            'buddies': offer.buddy_employee_ids.mapped('name'),
            'laptop': laptop,
            'employee_id': offer.employee_id.id or False,
            'case_id': offer.case_id.id or False,
            'contract_id': offer.contract_id.id or False,
            'can_act': bool(can_recruit and offer.state == 'signed'),
            'can_docs': bool(can_recruit and offer.state in ('signed', 'joined')),
            'confirm_primary': days is not None and days <= CONFIRM_FROM_DAYS,
            'drop_reasons': [{'key': k, 'label': v} for k, v in DROP_REASONS],
            'doc_kinds': [{'key': k, 'label': v} for k, v in OFFER_DOC_KINDS],
            'requisition_id': offer.requisition_id.id,
            'manager': offer._manager().name or '',
            'candidate': offer.candidate_name or '',
        }

    @api.model
    def get_candidate(self, applicant_id):
        res = super().get_candidate(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(res['id'])
        offer = self._safe(lambda: self._join_offer(app), default=None)
        if offer:
            res['joining'] = self._safe(
                lambda: self._joining_payload(offer, res.get('can_recruit')), default=None)
        return res

    @api.model
    def _next_box(self, app, ivs, can_recruit):
        key = app.stage_id.pb_key or ''
        if key == 'post_offer' and app.active:
            offer = self._join_offer(app)
            if offer and offer.state == 'signed':
                return self._post_offer_box(offer, can_recruit)
        return super()._next_box(app, ivs, can_recruit)

    @api.model
    def _post_offer_box(self, offer, can_recruit):
        pay = self._joining_payload(offer, can_recruit)
        days = pay['days']
        things = _('%(done)s of %(total)s things done', done=pay['done'], total=pay['total']) \
            if pay['total'] else _('nothing on the list')
        if days is None:
            text = _("Signed. Set the joining date.")
        elif days > 0:
            text = _("Joining %(when)s · %(n)s · %(things)s.", when=pay['expected_words'],
                     n=self._days_words(days), things=things)
        elif days == 0:
            text = _("Joining today, %(when)s · %(things)s. Confirm they joined once they "
                     "are in.", when=pay['expected_words'], things=things)
        else:
            text = _("They were expected on %(when)s (%(n)s). Confirm they joined, or "
                     "record that they did not.", when=pay['expected_words'],
                     n=self._days_words(days))
        box = {'text': text, 'countdown': {
            'days': days, 'words': pay['days_words'], 'when': pay['expected_words'],
            'done': pay['done'], 'total': pay['total'], 'late': pay['late']}}
        if not can_recruit:
            return box
        payload = {'offer_id': offer.id}
        if pay['confirm_primary'] or not pay['next_item']:
            box.update({'verb': 'confirm_open', 'label': _('Confirm they joined'),
                        'payload': payload,
                        'secondary': {'verb': 'drop_open', 'label': _('Did not join'),
                                      'payload': payload}})
        else:
            item = pay['next_item']
            act = item.get('action') or {}
            box.update({'verb': act.get('verb') or 'prejoin_done',
                        'label': act.get('label') or _('Done'),
                        'payload': {'item_id': item['id'], 'offer_id': offer.id},
                        'item_title': item['title'],
                        'secondary': {'verb': 'date_open', 'label': _('Change the date'),
                                      'payload': payload}})
        return box

    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        card = super()._card(app, ivs, doc_count, req, now, today, can_recruit)
        if (app.stage_id.pb_key or '') != 'post_offer':
            return card
        offer = self._join_offer(app)
        if not offer or offer.state != 'signed':
            return card
        expected = offer.expected_join_date or offer.start_date
        if not expected:
            return card
        days = (expected - today).days
        items = offer.prejoin_ids.filtered(lambda i: i.state != 'cancelled')
        done = len(items.filtered(lambda i: i.state in ('done', 'skipped')))
        late = len(items.filtered(lambda i: i.is_late()))
        if days > 1:
            label, tone = _('Joining in %s days', days), ('amber' if late else 'info')
        elif days == 1:
            label, tone = _('Joining tomorrow'), ('amber' if late else 'green')
        elif days == 0:
            label, tone = _('Joining today'), 'green'
        else:
            label, tone = _('Confirm they joined'), 'rose'
        chips = [{'label': label, 'tone': tone}]
        if late:
            chips.append({'label': _('%s late', late) if late > 1 else _('1 thing late'),
                          'tone': 'amber'})
        card['chips'] = chips
        card['sub'] = _('Joining %(when)s · %(done)s of %(total)s ready',
                        when=_words(self.env, expected, 'EEE d MMM'), done=done,
                        total=len(items)) if items else \
            _('Joining %s', _words(self.env, expected, 'EEE d MMM'))
        card['waiting'] = ''
        card['edge'] = 'rose' if days < 0 else ('amber' if late else card.get('edge') or '')
        card['joining'] = {'days': days, 'done': done, 'total': len(items), 'late': late}
        return card

    @api.model
    def get_timeline(self, applicant_id):
        items = super().get_timeline(applicant_id)
        app = self._applicant(applicant_id)
        extra = []
        for offer in self.env['pb.hiring.offer'].sudo().search(
                [('applicant_id', '=', app.id), ('state', 'in', ('joined', 'dropped'))],
                limit=5):
            if offer.state == 'joined' and offer.joined_on:
                extra.append({'at': str(offer.closed_on or offer.joined_on), 'kind': 'offer',
                              'text': _('Started on %s', _words(self.env, offer.joined_on,
                                                                 'EEE d MMM y')), 'by': ''})
            if offer.state == 'dropped':
                extra.append({'at': str(offer.write_date or ''), 'kind': 'offer',
                              'text': _('Did not join: %s', dict(DROP_REASONS).get(
                                  offer.drop_reason, '')), 'by': ''})
        if extra:
            items = sorted(items + extra, key=lambda r: r['at'], reverse=True)[:200]
        return items

    # =====================================================================
    #  The role drawer's offer panel
    # =====================================================================
    @api.model
    def _offer_row(self, offer, full=False):
        row = super()._offer_row(offer, full=full)
        offer = offer.sudo()            # a line manager reads this row (RC55)
        row.update({
            'expected_join_date': str(offer.expected_join_date or ''),
            'expected_words': _words(self.env, offer.expected_join_date or offer.start_date,
                                     'EEE d MMM y'),
            'joined_on': str(offer.joined_on or ''),
            'join_status': offer.join_status or '',
            'join_status_label': dict(JOIN_STATUS).get(offer.join_status, ''),
            'drop_words': dict(DROP_REASONS).get(offer.drop_reason, ''),
            'doc_count': len(offer.document_ids),
        })
        return row

    # =====================================================================
    #  The verbs
    # =====================================================================
    def _item(self, payload):
        item = self.env['pb.hiring.prejoin'].sudo().browse(
            as_id(payload.get('item_id'))).exists()
        if not item:
            raise UserError(_("That item is no longer on the list."))
        self._require_recruit(item.offer_id.requisition_id)
        return item

    def _signed_offer(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        return offer

    def _joining_reply(self, offer, note, **extra):
        res = {'id': offer.id, 'note': note,
               'joining': self._joining_payload(offer, True)}
        res.update(extra)
        return res

    def _act_prejoin_send(self, payload):
        item = self._item(payload)
        note = item.action_send()
        return self._joining_reply(item.offer_id, note)

    def _act_prejoin_done(self, payload):
        item = self._item(payload)
        item.action_done(note=(payload.get('note') or '').strip() or None)
        return self._joining_reply(item.offer_id, _("%s — done.", item.title),
                                   undo={'verb': 'prejoin_reopen', 'item_id': item.id})

    def _act_prejoin_skip(self, payload):
        item = self._item(payload)
        item.action_skip()
        return self._joining_reply(item.offer_id, _("%s — not needed.", item.title),
                                   undo={'verb': 'prejoin_reopen', 'item_id': item.id})

    def _act_prejoin_reopen(self, payload):
        item = self._item(payload)
        item.action_reopen()
        return self._joining_reply(item.offer_id, _("%s is back on the list.", item.title))

    def _act_prejoin_link(self, payload):
        item = self._item(payload)
        if item.kind not in ('buddy', 'laptop'):
            raise UserError(_("This item has no link."))
        return {'id': item.id, 'link': item.pb_link_url,
                'note': _("Their own link is on screen — send it however you like.")}

    def _act_prejoin_add(self, payload):
        offer = self._signed_offer(payload)
        title = (payload.get('title') or '').strip()[:200]
        if not title:
            raise UserError(_("Say what needs doing."))
        owner = payload.get('owner') if payload.get('owner') in dict(PREJOIN_OWNERS) \
            else 'recruiter'
        kind = 'chat' if payload.get('kind') == 'chat' else 'todo'
        last = max(offer.prejoin_ids.mapped('sequence') or [0])
        expected = offer.expected_join_date or offer.start_date
        due = fields.Date.to_date(payload.get('due')) if payload.get('due') else None
        offset = (due - expected).days if (due and expected) else int(payload.get('days') or -2)
        item = self.env['pb.hiring.prejoin'].sudo().create({
            'offer_id': offer.id, 'sequence': last + 10, 'kind': kind, 'title': title,
            'owner': owner, 'due_offset_days': offset})
        return self._joining_reply(offer, _("Added to the list."), item_id=item.id,
                                   undo={'verb': 'prejoin_remove', 'item_id': item.id})

    def _act_prejoin_remove(self, payload):
        item = self._item(payload)
        if item.kind not in ('todo', 'chat') or (item.kind == 'chat' and item.event_id):
            raise UserError(_("This one stays on the list. Mark it “not needed” instead."))
        offer = item.offer_id
        item.unlink()
        return self._joining_reply(offer, _("Taken off the list."))

    def _act_chat_people(self, payload):
        """Who a new joiner can meet: their manager's team first, then the
        company."""
        offer = self._signed_offer(payload)
        req = offer.requisition_id.sudo()
        manager = offer._manager()
        Emp = self.env['hr.employee'].sudo()
        rows = Emp.search([('company_id', '=', offer.company_id.id), ('active', '=', True)],
                          order='name', limit=600)
        team = set()
        if manager:
            team.add(manager.id)
            team |= set(Emp.search([('parent_id', '=', manager.id)]).ids)
        if req.department_id:
            team |= set(Emp.search([('department_id', '=', req.department_id.id)]).ids)
        out = [{'id': e.id, 'name': e.name or '', 'job': e.job_title or '',
                'team': e.id in team, 'manager': bool(manager and e.id == manager.id)}
               for e in rows]
        out.sort(key=lambda r: (not r['manager'], not r['team'], r['name'].lower()))
        return {'people': out}

    def _act_chat_save(self, payload):
        offer = self._signed_offer(payload)
        item = None
        if payload.get('item_id'):
            item = self._item(payload)
        if not item:
            last = max(offer.prejoin_ids.mapped('sequence') or [0])
            item = self.env['pb.hiring.prejoin'].sudo().create({
                'offer_id': offer.id, 'sequence': last + 10, 'kind': 'chat',
                'title': _('Set up a meet-the-team chat'), 'owner': 'recruiter',
                'due_offset_days': -5})
        out = item.schedule_chat(payload)
        note = _("In the diary. Invitations with a calendar file went to %(n)s people.",
                 n=out['sent']) if not out['waits'] else _(
            "In the diary. The invitations go the moment Google sends the Meet link.")
        return self._joining_reply(offer, note, item_id=item.id)

    def _act_change_join_date(self, payload):
        offer = self._signed_offer(payload)
        offer.action_change_join_date(payload.get('date'), reason=payload.get('reason'))
        return self._joining_reply(offer, _(
            "Joining date moved to %s. The hiring manager and HR have been told, and "
            "the list's dates moved with it.",
            _words(self.env, offer.expected_join_date, 'EEE d MMM y')))

    def _act_confirm_joined(self, payload):
        offer = self._signed_offer(payload)
        offer.action_confirm_joined(joined_on=payload.get('joined_on') or None)
        made = []
        if offer.employee_id:
            made.append(_('their employee record'))
        if offer.contract_id:
            made.append(_('a contract from %s', _words(self.env, offer.joined_on, 'd MMM')))
        if offer.login_user_id:
            made.append(_('a sign-in'))
        if offer.case_id:
            made.append(_('the welcome checklist'))
        return self._joining_reply(
            offer, _("%(who)s has joined. Made: %(what)s.", who=offer.candidate_name or '',
                     what=', '.join(made) or _('nothing new — it was all there')),
            employee_id=offer.employee_id.id or False, case_id=offer.case_id.id or False,
            filled=offer.requisition_id.state == 'filled')

    def _act_did_not_join(self, payload):
        offer = self._signed_offer(payload)
        offer.action_did_not_join(reason=payload.get('reason'), note=payload.get('note'))
        return self._joining_reply(offer, _(
            "Recorded as an offer drop. The hiring manager, the talent lead and HR "
            "have been told; the role stays open."))

    def _act_week_send(self, payload):
        """Send the week-before email now (the daily job does it at seven
        days; this is the same thing on a press)."""
        offer = self._signed_offer(payload)
        if offer.state != 'signed':
            raise UserError(_("This is for somebody who has not started yet."))
        offer.sudo().write({'week_before_sent_at': False})
        n = offer._week_before_send()
        return self._joining_reply(offer, _("The “still on?” email went to %s people.", n)
                                   if n != 1 else _("The “still on?” email went to 1 person."))

    def _act_doc_add(self, payload):
        offer = self._signed_offer(payload)
        if offer.state not in ('signed', 'joined'):
            raise UserError(_("Signed documents are added once the offer is signed."))
        try:
            content = base64.b64decode(payload.get('data') or '')
        except Exception:               # noqa: BLE001 — never a traceback
            raise UserError(_("That file did not arrive in one piece. Try it again."))
        if not content:
            raise UserError(_("Choose the signed file first."))
        if len(content) > UPLOAD_MAX_BYTES:
            raise UserError(_("That file is bigger than 5 MB. A scan is usually well under that."))
        if (payload.get('mimetype') or '') not in UPLOAD_MIME_OK:
            raise UserError(_("Attach a PDF, a Word document or a photograph."))
        kind = payload.get('kind') if payload.get('kind') in dict(OFFER_DOC_KINDS) else 'other'
        att = self.env['ir.attachment'].sudo().create({
            'name': slug_filename(payload.get('filename') or 'signed.pdf',
                                  fallback='signed-document'),
            'datas': base64.b64encode(content), 'mimetype': payload.get('mimetype'),
            'res_model': 'pb.hiring.offer', 'res_id': offer.id})
        last = max(offer.document_ids.mapped('sequence') or [0])
        self.env['pb.hiring.offer.document'].sudo().create({
            'offer_id': offer.id, 'attachment_id': att.id, 'kind': kind,
            'label': (payload.get('label') or '').strip()[:120] or False,
            'signed_on': payload.get('signed_on') or fields.Date.context_today(self),
            'recorded_by_id': self.env.uid, 'sequence': last + 10})
        note = _("Added.")
        if offer.state == 'joined':
            offer._file_signed_copy()
            note = _("Added and filed on their employee record.")
        return self._joining_reply(offer, note)

    def _act_doc_remove(self, payload):
        offer = self._signed_offer(payload)
        doc = offer.document_ids.filtered(lambda d: d.id == as_id(payload.get('doc_id')))
        if not doc:
            raise UserError(_("That document is no longer on the offer."))
        if doc.vault_doc_id:
            raise UserError(_("This one is already filed on their employee record. "
                              "Remove it there."))
        att = doc.attachment_id
        doc.unlink()
        if att and att != offer.signed_attachment_id:
            att.sudo().unlink()
        return self._joining_reply(offer, _("Removed."))

    def _act_close_offer(self, payload):
        """The wave-2 verb: now "Confirm they joined" on the expected date."""
        return self._act_confirm_joined(payload)

    def _act_record_signed(self, payload):
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        content = None
        if payload.get('data'):
            try:
                content = base64.b64decode(payload['data'])
            except Exception:           # noqa: BLE001 — never a traceback
                raise UserError(_("That file did not arrive in one piece. Try it again."))
        offer.action_record_signed(filename=payload.get('filename'), content=content,
                                   mimetype=payload.get('mimetype'),
                                   signed_on=payload.get('signed_on'),
                                   kind=payload.get('kind'), label=payload.get('label'))
        return {'id': offer.id, 'state': offer.state, 'applicant_id': offer.applicant_id.id,
                'note': _("Signed. %(who)s is in Post-offer, joining %(when)s — the "
                          "Before they join list is ready.",
                          who=offer.candidate_name or '',
                          when=_words(self.env, offer.expected_join_date, 'EEE d MMM'))}

    # =====================================================================
    #  Hiring set-up → Before they join
    # =====================================================================
    @api.model
    def get_setup(self):
        res = super().get_setup()
        co_ids = self.env.companies.ids or [self.env.company.id]
        Tpl = self.env['pb.hiring.prejoin.template'].sudo()
        rows = Tpl.search([('company_id', 'in', co_ids)])
        res['prejoin'] = {
            'items': [r._payload() for r in rows],
            'kinds': [{'key': k, 'label': v} for k, v in PREJOIN_KINDS],
            'owners': [{'key': k, 'label': v} for k, v in PREJOIN_OWNERS],
        }
        status = _("%(n)s things on every signed offer · %(names)s", n=len(rows),
                   names=', '.join(rows[:3].mapped('title'))) if rows else \
            _("Nothing yet. Add the first thing below.")
        cards = res.get('cards') or []
        cards.append({'key': 'prejoin', 'title': _('Before they join'),
                      'icon': 'listChecks', 'status': status, 'action': False,
                      'live': True})
        res['cards'] = cards
        return res

    def _tpl(self, payload):
        self._require_write()
        row = self.env['pb.hiring.prejoin.template'].sudo().with_context(
            active_test=False).browse(as_id(payload.get('id'))).exists()
        if not row:
            raise UserError(_("That line is no longer on the list."))
        return row

    def _act_prejoin_tpl_save(self, payload):
        row = self._tpl(payload)
        vals, before = {}, {}
        if 'title' in payload:
            title = (payload.get('title') or '').strip()[:200]
            if not title:
                raise UserError(_("Say what needs doing."))
            before['title'], vals['title'] = row.title, title
        if 'owner' in payload and payload['owner'] in dict(PREJOIN_OWNERS):
            before['owner'], vals['owner'] = row.owner, payload['owner']
        if 'days' in payload:
            try:
                days = int(payload.get('days'))
            except (TypeError, ValueError):
                raise UserError(_("Say how many days before they join, as a number."))
            before['days'], vals['due_offset_days'] = row.due_offset_days, max(-120, min(30, days))
        row.write(vals)
        return {'id': row.id, 'before': before, 'note': _("Saved. New signed offers use it.")}

    def _act_prejoin_tpl_add(self, payload):
        self._require_write()
        kind = payload.get('kind') if payload.get('kind') in dict(PREJOIN_KINDS) else 'todo'
        defaults = {'buddy': (_('Ask {manager} to name a buddy'), 'manager', -10),
                    'laptop': (_('Ask {name} for their laptop preferences'), 'candidate', -10),
                    'chat': (_('Set up a meet-the-team chat'), 'recruiter', -5),
                    'todo': (_('A new thing to do'), 'recruiter', -3)}[kind]
        Tpl = self.env['pb.hiring.prejoin.template'].sudo()
        last = max(Tpl.search([('company_id', '=', self.env.company.id)]).mapped('sequence') or [0])
        row = Tpl.create({'company_id': self.env.company.id, 'kind': kind,
                          'title': (payload.get('title') or '').strip() or defaults[0],
                          'owner': defaults[1], 'due_offset_days': defaults[2],
                          'sequence': last + 10})
        return {'id': row.id, 'note': _("Added. Click the words to change them.")}

    def _act_prejoin_tpl_remove(self, payload):
        row = self._tpl(payload)
        row.write({'active': False})
        return {'id': row.id, 'note': _("Taken off the list. Offers already signed keep theirs.")}

    def _act_prejoin_tpl_restore(self, payload):
        row = self._tpl(payload)
        row.write({'active': True})
        return {'id': row.id, 'note': _("It is back on the list.")}

    def _act_prejoin_tpl_reorder(self, payload):
        self._require_write()
        Tpl = self.env['pb.hiring.prejoin.template'].sudo()
        ids = [as_id(i) for i in payload.get('ids') or []]
        rows = Tpl.browse(ids).exists()
        before = Tpl.search([('company_id', '=', self.env.company.id)]).ids
        for n, row in enumerate(rows.sorted(lambda r: ids.index(r.id))):
            row.write({'sequence': (n + 1) * 10})
        return {'before': before, 'note': _("New order saved.")}
