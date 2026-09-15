# -*- coding: utf-8 -*-
"""`/hiring/f/<token>` — the one page in this module with no login behind it.

THE LINK IS THE CREDENTIAL, exactly as `pb_lifecycle`'s two token pages
established and `pb_ess_workforce`'s acknowledgment page before them:

  * an unguessable key — 24 bytes of `secrets.token_urlsafe`, minted per
    OPINION, so a leaked link answers one question about one hour for one
    person;
  * single-purpose routes — a GET to look and a POST to answer, and nothing
    else lives under the prefix;
  * no data beyond the target — the candidate's name, the role, the round and
    the questions. Not an id, not a salary expectation, not what anybody else
    on the panel said, not a link into the backend;
  * ONE page for every outcome, so a stranger probing the URL space learns
    nothing: an unknown key, a finished one and a called-off interview all get
    the same courteous "this link has closed".

The controller is sudo because the visitor is the public user with no access
to anything. Every write behind it goes through the model's own `submit`,
touches one record, and can only move that record forward.
"""

import logging

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

#: A public form must never be usable to post a book.
_MAX_NOTES = 4000

#: Never buffer more than the limit (+1 to notice the excess), so a large
#: upload cannot be used to exhaust memory on a page with no login in front
#: of it.
_UPLOAD_MAX_BYTES = 5 * 1024 * 1024


class PbHiringTokenPages(http.Controller):

    def _page(self, token, row, status):
        return request.render('pb_hiring.hiring_feedback_page', {
            'status': status,
            # Echoed back so the form posts to the same key — never
            # re-derived from the record, whose token is a restricted field.
            'token': token,
            # NOT `request`: QWeb already has one, and ours would shadow the
            # HTTP request the layout itself reads — the page then dies with
            # "'Request' object is not subscriptable" and the visitor gets a
            # 500 instead of a form (R4).
            'facts': row.page_facts() if (row and status == 'ok') else {},
            'questions': row.questions() if (row and status == 'ok') else [],
        })

    @http.route('/hiring/f/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_feedback_view(self, token, **kw):
        row, status = request.env[
            'pb.hiring.feedback'].sudo()._request_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return self._page(token, row, status)

    @http.route('/hiring/f/<string:token>/submit', type='http',
                auth='public', website=True, methods=['POST'], csrf=False,
                sitemap=False)
    def hiring_feedback_submit(self, token, **post):
        """`csrf=False` for the reason every token page in this product has
        it: the visitor has no session to carry a token in. The write is
        idempotent — a replay finds the opinion already given and writes
        nothing."""
        row, status = request.env[
            'pb.hiring.feedback'].sudo()._request_for_token(token)
        if status == 'ok':
            try:
                ratings = []
                for question in row.questions():
                    raw = post.get('c_%s' % question['id'])
                    if raw:
                        ratings.append({'id': question['id'], 'score': raw})
                row.sudo().submit(
                    ratings,
                    recommendation=post.get('recommendation'),
                    notes=(post.get('notes') or '').strip()[:_MAX_NOTES])
            except Exception:           # noqa: BLE001 — never a traceback
                _logger.exception('pb_hiring: a feedback submit failed')
        return request.redirect('/hiring/f/%s?done=1' % token)

    # =====================================================================
    #  A3 — `/hiring/d/<token>`: the papers a candidate sends us
    # =====================================================================
    def _documents_page(self, token, row, status, problem=''):
        return request.render('pb_hiring.hiring_documents_page', {
            'status': status,
            'token': token,
            # NOT `request` (R4): QWeb already has one, and ours would shadow
            # the HTTP request the layout itself reads.
            'facts': row.page_facts() if (row and status == 'ok') else {},
            'problem': problem,
        })

    @http.route('/hiring/d/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_documents_view(self, token, **kw):
        row, status = request.env[
            'pb.hiring.docreq'].sudo()._request_for_token(token)
        problems = {
            'size': _("That file is bigger than 5 MB. A photograph taken on "
                      "a phone is usually well under that."),
            'type': _("Send a PDF, a Word document or a photograph (JPG or "
                      "PNG). Anything else we cannot open."),
            'empty': _("The file did not arrive. Try it again."),
            'unknown': _("That is not one of the things you were asked for."),
            # A PICTURE THIS SYSTEM CANNOT OPEN is a real and ordinary case —
            # a truncated upload on a train, a file that is not the picture
            # its name says it is. It is not "did not arrive", and telling
            # somebody the wrong thing sends them looking in the wrong place.
            'unreadable': _("We could not open that file. If it is a "
                            "photograph, take it again; if it is a document, "
                            "send it as a PDF."),
        }
        return self._documents_page(token, row, status,
                                    problem=problems.get(kw.get('problem'),
                                                         ''))

    @http.route('/hiring/d/<string:token>/upload', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_documents_upload(self, token, **post):
        """One file against one line.

        `csrf=False` for the reason every token page in this product has it:
        the visitor has no session to carry a token in. The write is bounded,
        typed and idempotent — sending the same file twice replaces it rather
        than adding a second copy, and nothing here can reach a line that
        belongs to somebody else's request.
        """
        row, status = request.env[
            'pb.hiring.docreq'].sudo()._request_for_token(token)
        if status != 'ok':
            return request.redirect('/hiring/d/%s' % token)
        upload = post.get('upload')
        if not upload or not getattr(upload, 'filename', ''):
            return request.redirect('/hiring/d/%s?problem=empty' % token)
        data = upload.read(_UPLOAD_MAX_BYTES + 1)
        if len(data) > _UPLOAD_MAX_BYTES:
            return request.redirect('/hiring/d/%s?problem=size' % token)
        try:
            row.sudo().receive(post.get('item_id'), upload.filename, data,
                               mimetype=upload.mimetype or '')
        except UserError:
            # Said plainly, never as a traceback: a candidate must never see
            # a stack trace on a page with our name at the top of it.
            kind = 'type' if (upload.mimetype or '') not in (
                'application/pdf', 'application/msword', 'image/jpeg',
                'image/png',
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document') else 'unknown'
            return request.redirect('/hiring/d/%s?problem=%s' % (token, kind))
        except Exception:               # noqa: BLE001 — never a traceback
            # The attachment layer runs its own image processing and refuses a
            # picture it cannot parse. That reaches here as an ordinary
            # exception and the candidate must be told what is actually wrong
            # with their file, not "it did not arrive".
            _logger.exception('pb_hiring: a document upload failed')
            return request.redirect(
                '/hiring/d/%s?problem=unreadable' % token)
        return request.redirect('/hiring/d/%s' % token)

    # =====================================================================
    #  A3 — `/hiring/o/<token>`: the offer, and the answer
    # =====================================================================
    @http.route('/hiring/o/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def hiring_offer_view(self, token, **kw):
        row, status = request.env[
            'pb.hiring.offer'].sudo()._request_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        return request.render('pb_hiring.hiring_offer_page', {
            'status': status,
            'token': token,
            'facts': row.page_facts() if row else {},
        })

    @http.route('/hiring/o/<string:token>/answer', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_offer_answer(self, token, **post):
        row, status = request.env[
            'pb.hiring.offer'].sudo()._request_for_token(token)
        if status == 'ok':
            try:
                row.sudo().record_decision(
                    post.get('decision'),
                    comment=(post.get('comment') or '').strip()[:_MAX_NOTES])
            except Exception:           # noqa: BLE001 — never a traceback
                _logger.exception('pb_hiring: an offer answer failed')
        return request.redirect('/hiring/o/%s?done=1' % token)

    @http.route('/hiring/o/<string:token>/letter', type='http', auth='public',
                website=False, sitemap=False)
    def hiring_offer_letter(self, token, **kw):
        """The letter itself, as the PDF that was attached to the email.

        THE TOKEN IS THE GATE and nothing else is: the attachment is fetched
        from the offer the token resolved to, never from an id in the URL, so
        there is no attachment id a visitor could change. A spent or unknown
        token gets the page rather than a file.
        """
        row, status = request.env[
            'pb.hiring.offer'].sudo()._request_for_token(token)
        if status not in ('ok', 'used') or not row.sudo().attachment_id:
            return request.redirect('/hiring/o/%s' % token)
        attachment = row.sudo().attachment_id
        return request.make_response(
            attachment.raw,
            headers=[('Content-Type', attachment.mimetype
                      or 'application/pdf'),
                     ('Content-Disposition',
                      'inline; filename="%s"' % (attachment.name or
                                                 'offer.pdf'))])
