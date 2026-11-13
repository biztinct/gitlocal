# -*- coding: utf-8 -*-
"""`pb.hiring.bgv` — the background check, and the door it holds shut.

THE ONLY REASON THIS MODEL EXISTS IS THE DOOR. A checklist that does not stop
anything is a note, and a note is what a background check is today in most
companies: somebody rings two referees, remembers the answer, and nobody can
say six months later whether it was ever done. So the checklist is a record,
every line has to be ANSWERED before an offer can be drafted, and the answer
"does not apply" is a different answer from "clear".

A FLAG DOES NOT REFUSE AN OFFER FOR EVER, and it must not: a candidate whose
previous employer will not confirm a date is a perfectly ordinary case, and a
system that made that unhireable would simply be worked around. It refuses the
offer until the HR lead says, in writing, that we are going ahead anyway — and
that sentence is kept.

WHAT IT DELIBERATELY DOES NOT DO. It does not talk to a screening agency, it
does not score anybody, and it does not decide. It says what was asked, what
came back and who pressed on.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    BGV_RESULTS, BGV_STATES, GROUP_MANAGER, as_id, counted,
)

_logger = logging.getLogger(__name__)


class PbHiringBgvTemplate(models.Model):
    """The lines a company checks, as a template somebody can edit.

    Company-less seeds (R8): a `company_id` on a seeded row installs onto
    whichever company happened to run the install, and the company rule then
    hides it from every other one. Each seeded line is its own `<record>` with
    its own xmlid (R58) — a `(0, 0, {...})` inside a one2many is a CREATE with
    nothing to match on, so three upgrades would leave three copies of every
    line and the screen would show each one three times.
    """
    _name = 'pb.hiring.bgv.template'
    _description = 'Background check line'
    _order = 'sequence, id'

    name = fields.Char(string='What is checked', required=True, translate=True)
    sequence = fields.Integer(string='Order', default=10)
    required = fields.Boolean(
        string='Must be answered', default=True,
        help='On, an offer cannot be drafted until somebody has said what '
             'came back. Off, it is a line worth having and not a blocker.')
    help_text = fields.Char(
        string='What good looks like', translate=True,
        help='One sentence under the line, so two people checking the same '
             'thing mean the same by "clear".')
    active = fields.Boolean(string='In use', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty and every company uses it.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Background check line')

    @api.model
    def lines_for(self, company=None):
        company_id = as_id(company) or self.env.company.id
        return self.sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', company_id)])


class PbHiringBgv(models.Model):
    _name = 'pb.hiring.bgv'
    _description = 'Background check'
    _inherit = ['mail.thread']
    _order = 'id desc'

    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    applicant_id = fields.Many2one(
        'hr.applicant', string='Candidate', required=True, index=True,
        ondelete='cascade')
    # R56 — one field of an applicant reads the lot, some of it group-gated,
    # so the name is read as the system once and stored.
    candidate_name = fields.Char(string='Their name', compute='_compute_who',
                                 compute_sudo=True, store=True, readonly=True)
    item_ids = fields.One2many('pb.hiring.bgv.item', 'bgv_id',
                               string='What is being checked')
    state = fields.Selection(BGV_STATES, string='How it stands',
                             compute='_compute_state', store=True,
                             readonly=True, index=True, tracking=True)

    #: The HR lead's written "we are going ahead anyway". A boolean on its own
    #: would say a decision was taken and not who took it or why, which is the
    #: half that matters when somebody asks a year later.
    override_user_id = fields.Many2one('res.users', string='Pressed on by',
                                       readonly=True, copy=False)
    override_on = fields.Datetime(string='Pressed on', readonly=True,
                                  copy=False)
    override_note = fields.Text(string='Why we went ahead', copy=False)

    pending_count = fields.Integer(compute='_compute_state', store=True,
                                   string='Still to answer')
    flag_count = fields.Integer(compute='_compute_state', store=True,
                                string='Came back with something')
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)

    _one_per_candidate = models.Constraint(
        'unique(requisition_id, applicant_id)',
        'There is already a background check for this candidate on this role.')

    # =====================================================================
    #  Names and computes
    # =====================================================================
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Background check · %s',
                                 rec.candidate_name or _('a candidate'))

    @api.depends('applicant_id', 'applicant_id.partner_name')
    def _compute_who(self):
        for rec in self:
            app = rec.applicant_id
            rec.candidate_name = (app.partner_name or app.email_from
                                  or '') if app else ''

    @api.depends('item_ids', 'item_ids.result', 'item_ids.required')
    def _compute_state(self):
        for rec in self:
            items = rec.item_ids
            pending = items.filtered(
                lambda i: i.required and i.result == 'pending')
            flags = items.filtered(lambda i: i.result == 'flag')
            rec.pending_count = len(pending)
            rec.flag_count = len(flags)
            if flags:
                rec.state = 'flagged'
            elif pending:
                rec.state = 'open'
            else:
                rec.state = 'complete'

    # =====================================================================
    #  Opening one
    # =====================================================================
    @api.model
    def open_for(self, requisition_id, applicant_id=None):
        """The check for the candidate a panel picked, made once.

        IDEMPOTENT BY THE PAIR, not by a stamp: a recruiter who presses the
        button twice, a second visit to the drawer and a re-run after a
        failure all reach the same row. R30's rule, reached from the hiring
        side.
        """
        req = self.env['pb.hiring.requisition'].browse(
            as_id(requisition_id)).exists()
        if not req:
            raise UserError(_("That hiring request is no longer there."))
        app_id = as_id(applicant_id) or req.selected_applicant_id.id
        if not app_id:
            raise UserError(_(
                "Nobody has been picked for this role yet. The background "
                "check starts from the panel's decision on the last round — "
                "record the debrief first."))
        existing = self.sudo().search([('requisition_id', '=', req.id),
                                       ('applicant_id', '=', app_id)], limit=1)
        if existing:
            return existing
        bgv = self.sudo().create({'requisition_id': req.id,
                                  'applicant_id': app_id})
        bgv._seed_items()
        bgv.message_post(body=_(
            "Background check opened for %s.", bgv.candidate_name or ''))
        return bgv

    def _seed_items(self):
        """One row per template line, copied so the template can change
        afterwards without rewriting history."""
        self.ensure_one()
        Template = self.env['pb.hiring.bgv.template']
        Item = self.env['pb.hiring.bgv.item'].sudo()
        made = 0
        for line in Template.lines_for(self.company_id):
            existing = Item.search_count([('bgv_id', '=', self.id),
                                          ('name', '=', line.name)])
            if existing:
                continue
            Item.create({
                'bgv_id': self.id,
                'name': line.name,
                'sequence': line.sequence,
                'required': line.required,
                'help_text': line.help_text or '',
            })
            made += 1
        return made

    # =====================================================================
    #  The door
    # =====================================================================
    def check_ready(self):
        """`(ok, sentence)` — may an offer be drafted from this check?

        The sentence NAMES the lines, because "the background check is not
        complete" is a wall and "nobody has answered Two references or the
        criminal record check" is an instruction.
        """
        self.ensure_one()
        if self.override_user_id:
            return True, ''
        pending = self.item_ids.filtered(
            lambda i: i.required and i.result == 'pending')
        if pending:
            return False, _(
                "The background check is not finished — %(n)s %(word)s still "
                "waiting for an answer: %(names)s. Say what came back on each "
                "one and the offer opens by itself.",
                n=len(pending),
                word=counted(len(pending), _('line is'), _('lines are')),
                names=', '.join(i.name or '' for i in pending))
        flags = self.item_ids.filtered(lambda i: i.result == 'flag')
        if flags:
            return False, _(
                "Something came back on %(names)s. An offer can still be "
                "made — the HR lead has to say so on this screen first, and "
                "what they say is kept with the check.",
                names=', '.join(i.name or '' for i in flags))
        return True, ''

    def action_override(self, note=None):
        """"Go ahead anyway", said by the HR lead and written down.

        The gate is the MANAGER tier and not the recruiter's: deciding to
        hire somebody a check flagged is a decision about risk, and a
        recruiter clearing their own blocker is not a control at all.
        """
        self.ensure_one()
        if not (self.env.su or self.env.user.has_group(GROUP_MANAGER)):
            raise UserError(_(
                "Going ahead when a background check has come back with "
                "something is the HR lead's decision. Ask them — it is one "
                "press and a sentence."))
        note = (note or '').strip()
        if not note:
            raise UserError(_(
                "Say why we are going ahead. In a year this sentence is the "
                "only thing that will explain the decision."))
        self.sudo().write({'override_user_id': self.env.uid,
                           'override_on': fields.Datetime.now(),
                           'override_note': note})
        self.sudo().message_post(body=_(
            "Going ahead despite the background check. %s", note))
        return True

    # ------------------------------------------------------------- the door
    def action_open_requisition(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.requisition',
                'res_id': self.requisition_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.requisition_id.display_name}


class PbHiringBgvItem(models.Model):
    _name = 'pb.hiring.bgv.item'
    _description = 'Background check line'
    _order = 'sequence, id'

    bgv_id = fields.Many2one('pb.hiring.bgv', string='Background check',
                             required=True, index=True, ondelete='cascade')
    name = fields.Char(string='What is checked', required=True)
    sequence = fields.Integer(string='Order', default=10)
    required = fields.Boolean(string='Must be answered', default=True)
    help_text = fields.Char(string='What good looks like')
    result = fields.Selection(BGV_RESULTS, string='What came back',
                              default='pending', required=True, index=True)
    note = fields.Text(string='What was found')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'pb_hiring_bgv_item_att_rel', 'item_id',
        'attachment_id', string='Anything on paper')
    checked_by_id = fields.Many2one('res.users', string='Answered by',
                                    readonly=True)
    checked_on = fields.Datetime(string='Answered on', readonly=True)
    applicant_id = fields.Many2one(
        'hr.applicant', related='bgv_id.applicant_id', store=True,
        index=True, readonly=True, string='Candidate')
    company_id = fields.Many2one(
        'res.company', related='bgv_id.company_id', store=True, index=True,
        readonly=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Background check line')

    def write(self, vals):
        """WHO SAID IT IS PART OF THE ANSWER, so it is stamped here rather
        than left to whoever remembers to fill a field in."""
        if 'result' in vals and vals.get('result') != 'pending':
            vals = dict(vals, checked_by_id=self.env.uid,
                        checked_on=fields.Datetime.now())
        return super().write(vals)

    def action_set(self, result, note=None):
        """The board's press. Coerced at the door (R43)."""
        self.ensure_one()
        if result not in dict(BGV_RESULTS):
            raise UserError(_("That is not one of the answers this line "
                              "takes."))
        vals = {'result': result}
        if note is not None:
            vals['note'] = (note or '').strip()
        self.sudo().write(vals)
        if result == 'flag':
            self.bgv_id.sudo().message_post(body=_(
                "%(what)s came back with something. %(note)s",
                what=self.name or '', note=(note or '').strip()))
        return True
