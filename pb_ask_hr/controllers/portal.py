# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/ask-hr` — the employee asks HR, and reads the answer (TIERS T3a).

THE ROUTE IS THE GATE (ledger T-R11, D3). The employee is re-resolved from the
SESSION on every request (`_ess_employee`, pb_me_portal); no route accepts an
employee id. A ticket reached by id is browsed under sudo and shown only when
its employee is the session's own (or, read-only, when the request carries the
ticket's own access token — the e-mail link). Every write runs on that sudo
record AFTER the guard; `sudo()` keeps `env.uid`, so `create_uid` and the
message author stay the employee. No `base.group_portal` ACL exists.

Errors never 500 and never show a stock error page: a refused upload or an
empty reply comes back to the same page with the reason (`?error=`), a ticket
that is not the person's own is a styled 404.
"""

import base64
import logging

from odoo import fields, http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import (
    PbMePortal, _UPLOAD_MAX_BYTES, _UPLOAD_MIME_OK,
)

from ..models.ticket import CATEGORIES, CATEGORY_ICONS, OPEN_STATES, REOPEN_DAYS

_logger = logging.getLogger(__name__)

#: At most this many files per question or reply.
MAX_FILES = 3

#: `?done=` → nothing else; the template owns the words (one toast each).
_DONE = ('sent', 'reply', 'closed', 'reopened', 'already_closed', 'already_open')
#: `?error=` keys the pages explain.
_ERRORS = ('subject', 'empty', 'type', 'size', 'count', 'late', 'failed')


class PbAskHrPortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _ask_hr_own(self, ticket_id):
        """The ticket as a SUDO record when the session's own employee asked
        it, else an empty recordset (the ownership guard, T-R11)."""
        Ticket = request.env['pb.ask.hr.ticket'].sudo()
        emp = self._ess_employee()
        if not emp:
            return Ticket.browse()
        try:
            ticket = Ticket.browse(int(ticket_id)).exists()
        except (TypeError, ValueError):
            return Ticket.browse()
        if ticket and ticket.employee_id in self._ess_own_employees():
            return ticket
        return Ticket.browse()

    def _ask_hr_files(self):
        """The uploaded files of this request, checked BEFORE anything is
        created: at most MAX_FILES, each a PDF/JPG/PNG up to 10 MB (the same
        checks as `/my/documents/upload`). ``(files, error_key)``."""
        files = [f for f in request.httprequest.files.getlist('attachments')
                 if f and f.filename]
        if len(files) > MAX_FILES:
            return [], 'count'
        out = []
        for upload in files:
            data = upload.read(_UPLOAD_MAX_BYTES + 1)
            if len(data) > _UPLOAD_MAX_BYTES:
                return [], 'size'
            if (upload.mimetype or '') not in _UPLOAD_MIME_OK:
                return [], 'type'
            out.append((upload.filename, upload.mimetype, data))
        return out, None

    def _ask_hr_attach(self, ticket, files):
        """Create the checked files as attachments bound to ``ticket`` (sudo,
        after the guard and the checks)."""
        Att = request.env['ir.attachment'].sudo()
        atts = Att.browse()
        for name, mimetype, data in files:
            atts |= Att.create({
                'name': name,
                'datas': base64.b64encode(data),
                'mimetype': mimetype,
                'res_model': ticket._name,
                'res_id': ticket.id,
            })
        return atts

    def _ask_hr_ago(self, when):
        """``{'unit': 'now'|'min'|'h'|'d'|'date', 'n': int, 'date': dt}`` —
        the template says it in words."""
        if not when:
            return None
        delta = fields.Datetime.now() - when
        seconds = max(0, int(delta.total_seconds()))
        if seconds < 60:
            return {'unit': 'now', 'n': 0, 'date': when}
        if seconds < 3600:
            return {'unit': 'min', 'n': seconds // 60, 'date': when}
        if seconds < 86400:
            return {'unit': 'h', 'n': seconds // 3600, 'date': when}
        if seconds < 7 * 86400:
            return {'unit': 'd', 'n': seconds // 86400, 'date': when}
        return {'unit': 'date', 'n': 0, 'date': when}

    def _ask_hr_row(self, ticket):
        return {
            'id': ticket.id,
            'number': ticket.number,
            'name': ticket.name,
            'category': ticket.category,
            'category_label': dict(ticket._fields['category']._description_selection(
                request.env)).get(ticket.category, ''),
            'icon': CATEGORY_ICONS.get(ticket.category, 'message-circle-question'),
            'state': ticket.state,
            'ago': self._ask_hr_ago(ticket.last_activity_on),
            'unread': ticket.state == 'answered' and ticket.last_public_by == 'hr',
            'url': '/my/ask-hr/%s' % ticket.id,
        }

    def _ask_hr_categories(self):
        labels = dict(request.env['pb.ask.hr.ticket']._fields['category']
                      ._description_selection(request.env))
        return [{'value': value, 'icon': CATEGORY_ICONS[value],
                 'label': labels.get(value, value)}
                for value, _label in CATEGORIES]

    def _ask_hr_not_found(self):
        return request.render('pb_ask_hr.portal_ask_hr_missing',
                              {'page_name': 'ask_hr'}, status=404)

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'askhr_count' in counters:
            emp = self._ess_employee()
            values['askhr_count'] = request.env['pb.ask.hr.ticket'].sudo().search_count(
                [('employee_id', '=', emp.id), ('state', 'in', OPEN_STATES)]) if emp else 0
        return values

    # =============================================================== list
    @http.route(['/my/ask-hr'], type='http', auth='user', website=True)
    def portal_ask_hr(self, tab=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Ticket = request.env['pb.ask.hr.ticket'].sudo()
        tickets = Ticket.search([('employee_id', '=', emp.id)])
        open_t = tickets.filtered(lambda t: t.state in OPEN_STATES)
        closed_t = tickets - open_t
        tab = tab if tab in ('open', 'closed') else 'open'
        shown = open_t if tab == 'open' else closed_t
        values = {
            'page_name': 'ask_hr',
            'tab': tab,
            'rows': [self._ask_hr_row(t) for t in shown],
            'total': len(tickets),
            'n_open': len(open_t),
            'n_closed': len(closed_t),
            'n_answered': len(open_t.filtered(lambda t: t.state == 'answered')),
            'n_with_hr': len(open_t.filtered(lambda t: t.state in ('new', 'with_hr'))),
            'done': kw.get('done') if kw.get('done') in _DONE else None,
        }
        return request.render('pb_ask_hr.portal_ask_hr_list', values)

    # ================================================================ new
    def _ask_hr_render_new(self, values=None, error=None):
        # NAV P3d: named `_ask_hr_*` like every other helper here. As
        # `_render_new` it shared its name with pb_me_expense's portal helper
        # `_render_new(emp, …)` on the same controller class, and whichever
        # loaded last won: /my/ask-hr/new answered 403 "That is not your
        # employee record" on every database with Expenses installed.
        values = dict(values or {})
        values.update({
            'page_name': 'ask_hr_new',
            'categories': self._ask_hr_categories(),
            'error': error,
            'max_files': MAX_FILES,
        })
        values.setdefault('category', 'other')
        return request.render('pb_ask_hr.portal_ask_hr_new', values)

    @http.route(['/my/ask-hr/new'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_ask_hr_new(self, category=None, **kw):
        if not self._ess_employee():
            return request.redirect('/my')
        return self._ask_hr_render_new({'category': category if category in dict(CATEGORIES) else 'other'})

    @http.route(['/my/ask-hr/new'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_ask_hr_create(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        kept = {
            'category': post.get('category') if post.get('category') in dict(CATEGORIES) else 'other',
            'subject': (post.get('subject') or '').strip(),
            'text': (post.get('text') or '').strip(),
        }
        if not kept['subject']:
            return self._ask_hr_render_new(kept, 'subject')
        files, error = self._ask_hr_files()
        if error:
            return self._ask_hr_render_new(kept, error)
        Ticket = request.env['pb.ask.hr.ticket'].sudo()
        try:
            # T-R11: sudo AFTER the guard — the employee is the session's own
            # (forced, never a form value), the files are checked above.
            with request.env.cr.savepoint():
                ticket = Ticket._portal_create(emp, kept['category'],
                                               kept['subject'], kept['text'])
                atts = self._ask_hr_attach(ticket, files)
                if atts:
                    ticket.write({'attachment_ids': [(6, 0, atts.ids)]})
        except (AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_ask_hr: a new question was refused: %s', exc)
            return self._ask_hr_render_new(kept, 'failed')
        return request.redirect('/my/ask-hr/%s?done=sent' % ticket.id)

    # ============================================================= ticket
    @http.route(['/my/ask-hr/<int:ticket_id>'], type='http', auth='user',
                website=True, methods=['GET'])
    def portal_ask_hr_ticket(self, ticket_id, access_token=None, **kw):
        ticket = self._ask_hr_own(ticket_id)
        owner = bool(ticket)
        if not ticket and access_token:
            # the e-mail link: the ticket's own token lets a signed-in person
            # READ it; only its owner can write (the actions are not drawn)
            try:
                found = self._document_check_access('pb.ask.hr.ticket', ticket_id,
                                                    access_token=access_token)
                ticket = request.env['pb.ask.hr.ticket'].sudo().browse(found.id)
            except (AccessError, MissingError):
                ticket = None
        if not ticket:
            return self._ask_hr_not_found()
        row = self._ask_hr_row(ticket)
        values = {
            'page_name': 'ask_hr_ticket',
            'ticket': ticket,
            'row': row,
            'owner': owner,
            'question': {
                'author': ticket.employee_id.name,
                'initials': ticket._pb_initials(ticket.employee_id.name),
                'body': ticket.description,
                'date': ticket.create_date,
                'attachments': ticket._pb_attachment_payload(ticket.attachment_ids),
            },
            'thread': ticket._portal_messages(),
            'can_reopen': ticket._portal_can_reopen(),
            'reopen_days': REOPEN_DAYS,
            'done': kw.get('done') if kw.get('done') in _DONE else None,
            'error': kw.get('error') if kw.get('error') in _ERRORS else None,
            'max_files': MAX_FILES,
        }
        return request.render('pb_ask_hr.portal_ask_hr_ticket', values)

    @http.route(['/my/ask-hr/<int:ticket_id>/reply'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_ask_hr_reply(self, ticket_id, **post):
        ticket = self._ask_hr_own(ticket_id)
        if not ticket:
            return self._ask_hr_not_found()
        url = '/my/ask-hr/%s' % ticket.id
        body = (post.get('body') or '').strip()
        files, error = self._ask_hr_files()
        if error:
            return request.redirect('%s?error=%s#pbah-reply' % (url, error))
        if not body and not files:
            return request.redirect('%s?error=empty#pbah-reply' % url)
        if ticket.state == 'closed' and not ticket._portal_can_reopen():
            return request.redirect('%s?error=late' % url)
        try:
            with request.env.cr.savepoint():
                atts = self._ask_hr_attach(ticket, files)
                ticket._portal_reply(body, atts)
        except (AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_ask_hr: a reply was refused: %s', exc)
            return request.redirect('%s?error=failed#pbah-reply' % url)
        return request.redirect('%s?done=reply#pbah-end' % url)

    @http.route(['/my/ask-hr/<int:ticket_id>/close'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_ask_hr_close(self, ticket_id, **post):
        ticket = self._ask_hr_own(ticket_id)
        if not ticket:
            return self._ask_hr_not_found()
        done = 'closed' if ticket._portal_close() else 'already_closed'
        return request.redirect('/my/ask-hr/%s?done=%s' % (ticket.id, done))

    @http.route(['/my/ask-hr/<int:ticket_id>/reopen'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_ask_hr_reopen(self, ticket_id, **post):
        ticket = self._ask_hr_own(ticket_id)
        if not ticket:
            return self._ask_hr_not_found()
        try:
            done = 'reopened' if ticket._portal_reopen() else 'already_open'
        except UserError:
            return request.redirect('/my/ask-hr/%s?error=late' % ticket.id)
        return request.redirect('/my/ask-hr/%s?done=%s' % (ticket.id, done))
