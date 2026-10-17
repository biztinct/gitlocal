# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``/work/ack/<token>`` — confirming a shift with no login at all.

Most people on a shop floor, a delivery round or a factory line do not have an
Odoo login and never will. The portal is the channel for the ones who do; this
is the channel for everyone else, and it is modelled on the ONE login-less
precedent this codebase already trusts: ``pb_formula_studio``'s client review
portal (``controllers/review.py``), where the link IS the credential.

WHAT THE PRECEDENT ACTUALLY ASKS FOR, POINT BY POINT

  * *an unguessable token* — 24 bytes of ``secrets.token_urlsafe``, minted per
    SHIFT (not per week, not per person), so a leaked link confirms one shift on
    one day and expires by itself when that shift starts;
  * *a single-purpose route* — two routes, GET to look and POST to confirm, and
    nothing else lives under this prefix;
  * *no data exposure beyond the target record* — the page renders the shift's
    day, hours and template name plus the employee's own first name. Not their
    id, not their department's roster, not a neighbouring shift, not a link into
    the backend. A stranger who finds the URL learns that somebody works a
    morning shift on Thursday;
  * *used-token invalidation* — the model answers with a STATUS
    (``ok``/``used``/``expired``/``stale``/``invalid``) and only ``ok`` may
    write. See ``models/shift_planning_ack.py`` for why the token is kept rather
    than deleted on use.

The whole controller is sudo because the visitor is the public user with no ACL
on anything — and that is exactly why the write behind it is sentinel-guarded
down to two named fields.
"""

from odoo import _, http
from odoo.http import request


class PbEssAckPortal(http.Controller):

    def _shifts(self):
        return request.env['hr.shift.planning'].sudo()

    def _page(self, token, shift, status):
        """One template for every outcome. A separate "sorry" page per status
        would drift; the page IS the status, and the copy lives beside it."""
        emp = shift.employee_id if shift else None
        tz = request.env['pb.ess.workforce'].sudo()._tzinfo(emp)
        Ess = request.env['pb.ess.workforce'].sudo()
        return request.render('pb_ess_workforce.ack_token_page', {
            'status': status,
            # echoed back so the confirm form can post to the same token —
            # never re-derived from the record (the record's token is a
            # system-restricted field and must not travel to a template)
            'token': token,
            'has_shift': bool(shift),
            # Deliberately narrow: what a person needs to recognise their own
            # shift, and not one field more.
            'shift': {
                'day': shift.date.strftime('%A %d %B %Y') if shift and shift.date else '',
                'start': Ess._hhmm(shift.start_datetime, tz) if shift else '',
                'end': Ess._hhmm(shift.end_datetime, tz) if shift else '',
                'name': (shift.shift_template_id.name or '') if shift else '',
                'hours_label': _('%(hours)s h',
                                 hours=round(shift.planned_hours or 0.0, 2))
                if shift else '',
                'who': (emp.name or '').split(' ')[-1] if emp else '',
                'acked_on': (shift.acked_at.date().isoformat()
                             if shift and shift.acked_at else ''),
            } if shift else {},
            # W80.2 — one sentence, one msgid. Neither of these may be
            # assembled from template fragments around a `<t t-esc/>`: a
            # translator cannot reorder fragments, and both of these sentences
            # put the variable somewhere else in Vietnamese.
            'greeting': _('Hi %(name)s — please confirm you have seen this shift.',
                          name=(emp.name or '').split(' ')[-1]) if emp else '',
            'already': _('You confirmed this shift on %(date)s. There is '
                         'nothing left to do.',
                         date=(shift.acked_at.date().isoformat()
                               if shift and shift.acked_at else '')),
        })

    @http.route('/work/ack/<string:token>', type='http', auth='public',
                website=True, sitemap=False)
    def ack_view(self, token, **kw):
        shift, status = self._shifts()._ess_shift_for_token(token)
        if kw.get('done') == '1' and status == 'used':
            status = 'acked'
        return self._page(token, shift, status)

    @http.route('/work/ack/<string:token>/confirm', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def ack_confirm(self, token, **post):
        """csrf=False for the same reason the review portal's sign-off is: the
        visitor has no Odoo session to carry a CSRF token in. The request is
        idempotent by construction — a replay finds the shift already
        acknowledged and writes nothing."""
        self._shifts()._ess_ack_by_token(token)
        return request.redirect('/work/ack/%s?done=1' % token)
