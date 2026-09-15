# -*- coding: utf-8 -*-
"""`pb.hiring.posting` — the advert, made ready for each place it goes.

PUBLISH BUILDS; SENDING IS A SEPARATE, SWITCHED ACT. Ruling D12 keeps every
outside service off, so there is no LinkedIn API call here and there never was
going to be one. What Publish does is honest and useful without one: it puts
the role on the company's own careers page and it writes, per job board, the
exact email somebody would send — subject, body, where to apply — and stores
it. With the switch off the row says "Ready to send" and a person pushes it.
With the switch on it goes out.

A ROW PER PLATFORM AND NEVER A SECOND ONE. Pressing Publish twice must not
produce six adverts; the row is found by (request, platform) and refreshed.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

from .hiring_common import P_PLATFORM_MAIL, POSTING_STATES, as_id, counted, flag

_logger = logging.getLogger(__name__)


class PbHiringPosting(models.Model):
    _name = 'pb.hiring.posting'
    _description = 'Advert'
    _order = 'requisition_id, platform_id, id'

    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    job_id = fields.Many2one('hr.job', related='requisition_id.job_id',
                             store=True, readonly=True, string='The job')
    platform_id = fields.Many2one('hr.job.platform', string='Where it goes',
                                  required=True, ondelete='cascade')
    platform_email = fields.Char(related='platform_id.email', readonly=True,
                                 string='Their address')
    subject = fields.Char(string='Subject', readonly=True)
    body_html = fields.Html(string='The advert', readonly=True,
                            sanitize_attributes=False)
    state = fields.Selection(POSTING_STATES, string='How far it has got',
                             default='ready', required=True, copy=False)
    sent_on = fields.Datetime(string='Sent on', readonly=True, copy=False)
    sent_by = fields.Many2one('res.users', string='Sent by', readonly=True,
                              copy=False)
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)

    _requisition_platform_uniq = models.Constraint(
        'unique(requisition_id, platform_id)',
        'That advert has already been prepared for that job board.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s · %s' % (
                rec.platform_id.name or '', rec.job_id.name or '')

    # =====================================================================
    #  Publishing
    # =====================================================================
    @api.model
    def publish_for(self, requisition_id):
        """Put the role on the careers page and build one pack per job board.

        Returns a small dictionary the board turns into one sentence. It
        never raises for "there are no job boards set up" — that is a true
        and recoverable state of the world, and the careers page is published
        either way.
        """
        req = self.env['pb.hiring.requisition'].browse(as_id(requisition_id))
        req.ensure_one()
        if req.state != 'open':
            raise UserError(_(
                "A role is advertised once it has been agreed. This one is "
                "still %s.", dict(req._fields['state'].selection).get(
                    req.state, req.state)))
        if not req.jd_current_id:
            raise UserError(_(
                "There is no agreed advert for this role yet. Write one and "
                "have it agreed, then publish."))
        job = req.job_id or req._ensure_job()
        try:
            job.sudo().write({'website_published': True,
                              'website_description': req.jd_current_id.body
                              or job.website_description})
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: %s could not be put on the careers '
                            'page', job.name, exc_info=True)
        req.sudo().write({'published': True})

        platforms = self.env['hr.job.platform'].sudo().search([])
        made, refreshed = 0, 0
        for platform in platforms:
            row = self.sudo().search([('requisition_id', '=', req.id),
                                      ('platform_id', '=', platform.id)],
                                     limit=1)
            subject, body = self._render_pack(req, job, platform)
            if row:
                if row.state == 'ready':
                    row.write({'subject': subject, 'body_html': body})
                    refreshed += 1
                continue
            self.sudo().create({
                'requisition_id': req.id, 'platform_id': platform.id,
                'subject': subject, 'body_html': body, 'state': 'ready',
            })
            made += 1

        mail_on = flag(self.env, P_PLATFORM_MAIL)
        if not platforms:
            note = _("The role is on the careers page. No job boards have "
                     "been set up yet, so there is nothing else to send.")
        elif mail_on:
            note = _("The role is on the careers page and %(n)s job-board "
                     "%(word)s ready. Press Send on each one.",
                     n=len(platforms),
                     word=counted(len(platforms), _('advert is'),
                                  _('adverts are')))
        else:
            note = _("The role is on the careers page and %(n)s job-board "
                     "%(word)s ready. Sending them by email is switched off, "
                     "so copy the text out or ask an administrator to switch "
                     "it on.", n=len(platforms),
                     word=counted(len(platforms), _('advert is'),
                                  _('adverts are')))
        return {'made': made, 'refreshed': refreshed,
                'platforms': len(platforms), 'mail_on': mail_on,
                'note': note, 'job_id': job.id}

    @api.model
    def _render_pack(self, req, job, platform):
        """Subject and body, built here rather than in a mail template.

        A job board wants a plain advert: title, where, what, how to apply.
        The agreed advert IS the body, and the only thing added is the line
        that tells a reader where to go.
        """
        where = req.location or (req.country_id.name or '')
        subject = _("%(title)s — %(where)s", title=req.title or job.name,
                    where=where) if where else (req.title or job.name)
        url = ''
        try:
            url = job.sudo().full_url or ''
        except Exception:               # noqa: BLE001
            url = ''
        if not url:
            base = self.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') or ''
            url = '%s/jobs' % base.rstrip('/')
        advert = (req.jd_current_id.body or job.website_description or '')
        summary = req.jd_current_id.summary or ''
        head = _(
            "<p>Hello,</p><p>We are hiring for <strong>%(title)s</strong>"
            "%(where)s. %(count)s to find.</p>",
            title=req.title or job.name,
            where=(' in %s' % where) if where else '',
            count=_("%(n)s %(word)s", n=req.headcount or 1,
                    word=counted(req.headcount or 1, _('person'),
                                 _('people'))))
        if summary:
            head += '<p>%s</p>' % summary
        tail = _(
            "<p>The full advert is below. Candidates apply here: "
            "<a href=\"%(url)s\">%(url)s</a></p>", url=url)
        return subject, '%s%s<hr/>%s' % (head, tail, advert)

    # =====================================================================
    #  Sending one
    # =====================================================================
    def action_send(self):
        for rec in self:
            rec._send_one()
        return True

    def _send_one(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_("This one has already been sent."))
        if not flag(self.env, P_PLATFORM_MAIL):
            raise UserError(_(
                "Sending adverts to job boards by email is switched off. An "
                "administrator switches it on in Settings; until then, copy "
                "the text out of this advert and send it yourself."))
        if not self.platform_email:
            raise UserError(_(
                "%s has no email address on it, so there is nowhere to send "
                "this. Add one to the job board first.",
                self.platform_id.name or ''))
        template = self.env.ref('pb_hiring.mail_template_posting',
                                raise_if_not_found=False)
        if not template:
            raise UserError(_("The advert email is missing from this build."))
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': self.platform_email,
                          'subject': self.subject or '',
                          'body_html': self.body_html or ''})
        self.sudo().write({'state': 'sent',
                           'sent_on': fields.Datetime.now(),
                           'sent_by': self.env.uid})
        return True

    def plain_text(self):
        """The advert as text, for somebody copying it into a web form."""
        self.ensure_one()
        return html2plaintext(self.body_html or '')
