# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.me.notices` — the facts behind the notice board (TIERS T3b D4).

THE AUDIENCE IS pb_hr_comm's OWN: a notice is shown to a person when there is a
`pb.hr.comm.delivery` row for them of an announcement that has gone out
(`state == 'sent'`, still active). Nothing here decides who an announcement
was for; a scheduled announcement never shows before it goes out.

OWN DATA ONLY (M-R4 / T-R11). Every method takes the employee the controller
resolved from the session and refuses one that is not the caller's own, then
reads under sudo keyed on that employee. Read receipts are written under sudo
after the same guard.
"""

import logging
import re

from psycopg2 import IntegrityError

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mail import html_to_inner_content

_logger = logging.getLogger(__name__)

#: The excerpt under a subject on the board and the home card.
EXCERPT_CHARS = 160
#: A ceiling on one person's board (they are sent far fewer).
NOTICES_CAP = 500
#: Picture types a poster may be drawn as (anything else is a file to open).
IMAGE_TYPES = ('image/png', 'image/jpeg', 'image/gif', 'image/webp')


class PbMeNotices(models.AbstractModel):
    _name = 'pb.me.notices'
    _description = 'Employee notice board facts'

    # ------------------------------------------------------------- guards
    @api.model
    def _own(self, emp):
        """``emp`` as a sudo record when it is the CALLER's own employee,
        else an empty recordset (M-R4: a crafted call never reads another
        person's notices)."""
        Emp = self.env['hr.employee'].sudo()
        if not isinstance(emp, models.BaseModel) or emp._name != 'hr.employee':
            return Emp.browse()
        emp = emp.sudo()[:1]
        if not emp or emp.user_id.id != self.env.uid:
            return Emp.browse()
        return emp

    @api.model
    def _deliveries(self, emp, post_id=None):
        domain = [('employee_id', '=', emp.id),
                  ('post_id.state', '=', 'sent'),
                  ('post_id.active', '=', True)]
        if post_id:
            domain.append(('post_id', '=', post_id))
        return self.env['pb.hr.comm.delivery'].sudo().search(
            domain, order='sent_on desc, id desc', limit=NOTICES_CAP)

    @api.model
    def _read_post_ids(self, emp, post_ids):
        if not post_ids:
            return set()
        reads = self.env['pb.me.notice.read'].sudo().search(
            [('employee_id', '=', emp.id), ('post_id', 'in', list(post_ids))])
        return set(reads.post_id.ids)

    # -------------------------------------------------------------- words
    @api.model
    def _excerpt(self, html, size=EXCERPT_CHARS):
        text = re.sub(r'\s+', ' ', html_to_inner_content(html or '') or '').strip()
        if len(text) <= size:
            return text
        cut = text[:size].rsplit(' ', 1)[0] or text[:size]
        return cut.rstrip(' ,.;:') + '…'

    @api.model
    def _attachment_url(self, att, download=False):
        """A link an employee login can open (ledger T14/T20): the attachment's
        own access token, for every kind of login (one code path)."""
        token = att.sudo().generate_access_token()[0]
        return '/web/content/%s?access_token=%s%s' % (
            att.id, token, '&download=true' if download else '')

    @api.model
    def _posters(self, post):
        out = []
        for att in post.sudo().poster_ids:
            is_image = (att.mimetype or '') in IMAGE_TYPES
            out.append({
                'id': att.id,
                'name': att.name or '',
                'is_image': is_image,
                'url': self._attachment_url(att),
                'download_url': self._attachment_url(att, download=True),
            })
        return out

    @api.model
    def _ago(self, when):
        """``{'unit': 'now'|'min'|'h'|'d'|'date', 'n', 'date'}`` — the template
        says it in words (same shape as Ask HR's)."""
        if not when:
            return None
        seconds = max(0, int((fields.Datetime.now() - when).total_seconds()))
        if seconds < 60:
            return {'unit': 'now', 'n': 0, 'date': when}
        if seconds < 3600:
            return {'unit': 'min', 'n': seconds // 60, 'date': when}
        if seconds < 86400:
            return {'unit': 'h', 'n': seconds // 3600, 'date': when}
        if seconds < 7 * 86400:
            return {'unit': 'd', 'n': seconds // 86400, 'date': when}
        return {'unit': 'date', 'n': 0, 'date': when}

    @api.model
    def _row(self, delivery, read_ids):
        post = delivery.post_id.sudo()
        posters = self._posters(post)
        image = next((p for p in posters if p['is_image']), None)
        sent_on = delivery.sent_on or post.sent_at or post.send_at
        return {
            'post_id': post.id,
            'subject': post.subject or '',
            'sent_on': sent_on,
            'ago': self._ago(sent_on),
            'excerpt': self._excerpt(post.body_html),
            'has_poster': bool(posters),
            'poster_url': image['url'] if image else '',
            'poster_count': len(posters),
            'read': post.id in read_ids,
            'url': '/my/notices/%s' % post.id,
        }

    # ============================================================ public
    @api.model
    def get_my_notices(self, emp, limit=None, unread_only=False):
        """``emp``'s notices, newest first: ``[{post_id, subject, sent_on,
        excerpt, has_poster, poster_url, read, url}]``. Empty for anybody
        but the caller's own employee."""
        emp = self._own(emp)
        if not emp:
            return []
        deliveries = self._deliveries(emp)
        read_ids = self._read_post_ids(emp, deliveries.post_id.ids)
        if unread_only:
            deliveries = deliveries.filtered(lambda d: d.post_id.id not in read_ids)
        if limit:
            deliveries = deliveries[:int(limit)]
        return [self._row(d, read_ids) for d in deliveries]

    @api.model
    def get_my_notice(self, emp, post_id):
        """One notice for ``emp`` — the row plus the body and every poster —
        or ``None`` when there is no delivery row for them (the ownership
        guard: a notice the person was never sent does not exist for them)."""
        emp = self._own(emp)
        try:
            post_id = int(post_id)
        except (TypeError, ValueError):
            return None
        if not emp or post_id <= 0:
            return None
        delivery = self._deliveries(emp, post_id)[:1]
        if not delivery:
            return None
        read_ids = self._read_post_ids(emp, [post_id])
        row = self._row(delivery, read_ids)
        post = delivery.post_id.sudo()
        row.update({
            # the Html field's own value: sanitized when HR saved it
            'body_html': post.body_html or '',
            'posters': self._posters(post),
        })
        # older and newer neighbours on the person's own board
        ids = self._deliveries(emp).post_id.ids
        at = ids.index(post_id) if post_id in ids else -1
        row['newer_url'] = '/my/notices/%s' % ids[at - 1] if at > 0 else None
        row['older_url'] = ('/my/notices/%s' % ids[at + 1]
                            if 0 <= at < len(ids) - 1 else None)
        return row

    @api.model
    def notice_counts(self, emp):
        """``{'total', 'unread'}`` for ``emp`` — two small reads, no rows built
        (the home asks this on every visit)."""
        emp = self._own(emp)
        if not emp:
            return {'total': 0, 'unread': 0}
        deliveries = self._deliveries(emp)
        read_ids = self._read_post_ids(emp, deliveries.post_id.ids)
        unread = sum(1 for d in deliveries if d.post_id.id not in read_ids)
        return {'total': len(deliveries), 'unread': unread}

    @api.model
    def unread_count(self, emp):
        return self.notice_counts(emp)['unread']

    @api.model
    def mark_read(self, emp, post_id):
        """Record that ``emp`` opened ``post_id`` (once). True when the notice
        is theirs (already read or now read), False when it is not."""
        emp = self._own(emp)
        try:
            post_id = int(post_id)
        except (TypeError, ValueError):
            return False
        if not emp or not self._deliveries(emp, post_id):
            return False
        if self._read_post_ids(emp, [post_id]):
            return True
        self._notice_read_create(post_id, emp)
        return True

    @api.model
    def _notice_read_create(self, post_id, emp):
        """The one writer (sudo, after the guards above). A second writer that
        raced this one hits the unique constraint: that is a read already
        recorded, not an error — the savepoint keeps the page's transaction
        alive."""
        try:
            with self.env.cr.savepoint():
                self.env['pb.me.notice.read'].sudo().create({
                    'post_id': post_id, 'employee_id': emp.id,
                    'read_on': fields.Datetime.now()})
        except (IntegrityError, ValidationError):
            _logger.debug('pb_me_portal_comm: notice %s already read by %s',
                          post_id, emp.id)
            return False
        return True
