# -*- coding: utf-8 -*-
"""The company's privacy notice: its own words, a version, published once.

A company has at most ONE published notice at a time. Publishing a new
version replaces the old one (kept, read-only, as history) and makes every
employee of that company answer again on their next visit to My Payobook.
The words are the customer's legal text: the module ships a neutral starting
point that names no law and no vendor, and HR is told to review it.

Every publish bumps one database setting (`STAMP_PARAM`). The sign-in gate
(`ir_http.py`) caches "nothing to ask" per session against that stamp, so a
person is asked again the moment a new version is published, and the gate
costs one cached read per page otherwise.
"""

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

#: Bumped whenever a notice is published or replaced (see module docstring).
STAMP_PARAM = 'pb_me_privacy.stamp'

#: Who manages notices and reads answers: HR, and nobody else (managers are
#: left out on purpose, as for the PayAI consent precedent).
HR_GROUP = 'hr.group_hr_user'


def default_body(env):
    """The neutral starting wording, in the reader's language."""
    _t = env._
    parts = [
        _t("We keep the personal details you give us, and the details of your "
           "work with us, so that we can employ you, pay you correctly and "
           "meet our duties to the tax office and social insurance."),
        _t("Only the people whose job needs your details can see them. We share "
           "them only where we have to, for example with the tax office, social "
           "insurance, and the bank that pays your salary."),
        _t("We keep your details while you work with us, and afterwards for as "
           "long as the rules we follow require."),
        _t("You can ask HR at any time to see the details we keep about you, to "
           "correct them, or to explain how they are used."),
    ]
    return Markup('').join(Markup('<p>%s</p>') % p for p in parts)


class PbPrivacyNotice(models.Model):
    _name = 'pb.privacy.notice'
    _description = 'Privacy notice'
    _inherit = ['mail.thread']
    _order = 'company_id, version desc, id desc'

    name = fields.Char(
        string='Title', required=True, translate=True, tracking=True,
        default=lambda self: self.env._("How we use your personal details"))
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    version = fields.Integer(string='Version', readonly=True, copy=False,
                             help='Given when the notice is published.')
    body = fields.Html(
        string='Notice', translate=True, sanitize=True, required=True,
        default=lambda self: default_body(self.env),
        help="Your company's own wording. Employees read exactly this, in "
             "their language, before they answer.")
    state = fields.Selection([
        ('draft', 'Not published yet'),
        ('published', 'Published'),
        ('replaced', 'Replaced by a newer version'),
    ], string='Status', default='draft', required=True, readonly=True,
        copy=False, index=True, tracking=True)
    published_on = fields.Datetime(string='Published on', readonly=True,
                                   copy=False)
    published_by = fields.Many2one('res.users', string='Published by',
                                   readonly=True, copy=False)
    replaced_on = fields.Datetime(string='Replaced on', readonly=True,
                                  copy=False)
    consent_ids = fields.One2many('pb.privacy.consent', 'notice_id',
                                  string='Answers', readonly=True)

    # ---------------------------------------------------------------- rules
    def _pb_check_hr(self):
        if self.env.su:
            return
        if not self.env.user.has_group(HR_GROUP):
            raise AccessError(_("Only HR can change the privacy notice."))

    def write(self, vals):
        # A published or replaced version is what people agreed to: its words
        # can never change underneath their answers.
        locked = {'name', 'body', 'company_id'}.intersection(vals)
        if locked and not self.env.context.get('pb_privacy_sys'):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_(
                        "A published notice cannot be changed, because people "
                        "have answered it. Write a new version instead."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "A notice people have seen is kept as a record and cannot "
                    "be deleted."))
        return super().unlink()

    # -------------------------------------------------------------- actions
    def action_publish(self):
        """Publish this draft: it becomes the company's notice, the previous
        one is kept as replaced, and everybody is asked again."""
        self._pb_check_hr()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This version is already published."))
            if not (rec.body or '').strip():
                raise UserError(_("Write the notice before publishing it."))
            Notice = self.sudo()
            current = Notice.search([('company_id', '=', rec.company_id.id),
                                     ('state', '=', 'published')])
            last = Notice.search([('company_id', '=', rec.company_id.id)],
                                 order='version desc', limit=1)
            now = fields.Datetime.now()
            current.with_context(pb_privacy_sys=True).write({
                'state': 'replaced', 'replaced_on': now})
            rec.sudo().with_context(pb_privacy_sys=True).write({
                'state': 'published',
                'version': (last.version or 0) + 1,
                'published_on': now,
                'published_by': self.env.uid,
            })
            rec.message_post(body=_("Version %s published. Everybody in %s is "
                                    "asked to read it on their next visit to "
                                    "My Payobook.", rec.version,
                                    rec.company_id.name))
        self._pb_bump_stamp()
        return True

    def action_new_version(self):
        """A draft copy of this notice to edit and publish."""
        self.ensure_one()
        self._pb_check_hr()
        draft = self.search([('company_id', '=', self.company_id.id),
                             ('state', '=', 'draft')], limit=1)
        if not draft:
            draft = self.copy({'state': 'draft'})
        return draft._pb_form_action()

    def _pb_form_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('pb_me_privacy.view_pb_privacy_notice_form').id,
                       'form')],
            'target': 'current',
            'name': self.name,
        }

    @api.model
    def _pb_bump_stamp(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            stamp = int(icp.get_param(STAMP_PARAM) or 0)
        except (TypeError, ValueError):
            stamp = 0
        icp.set_param(STAMP_PARAM, str(stamp + 1))

    @api.model
    def _pb_current(self, company):
        """The company's published notice (sudo), or an empty recordset."""
        return self.sudo().search([('company_id', '=', company.id),
                                   ('state', '=', 'published')],
                                  order='version desc', limit=1)
