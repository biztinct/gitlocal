# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A named route and its revisions.

A workflow is a stable identity; a VERSION is one immutable revision of its
definition document. Editing a published workflow never changes it: it copies
the published definition into a new draft revision. A request in flight keeps
the version it was given (design §8).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import definition as D


class BizApprovalWorkflow(models.Model):
    _name = 'biz.approval.workflow'
    _description = 'Approval Workflow'
    _order = 'name'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    process_id = fields.Many2one('biz.approval.process', required=True,
                                 index=True, ondelete='restrict')
    owner_user_id = fields.Many2one(
        'res.users', string='Looked after by',
        default=lambda self: self.env.user,
        help='Who hears about late and unusual requests on this route.')
    active = fields.Boolean(default=True)
    parent_workflow_id = fields.Many2one(
        'biz.approval.workflow', string='Started from',
        help='Set when this route began as a copy of another one.')
    version_ids = fields.One2many('biz.approval.workflow.version',
                                  'workflow_id')
    published_version_id = fields.Many2one(
        'biz.approval.workflow.version', compute='_compute_versions',
        store=False)
    draft_version_id = fields.Many2one(
        'biz.approval.workflow.version', compute='_compute_versions',
        store=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'In use'),
        ('archived', 'Put away'),
    ], compute='_compute_versions')
    summary = fields.Char(compute='_compute_versions')

    @api.depends('version_ids.status', 'version_ids.revision',
                 'version_ids.definition', 'active')
    def _compute_versions(self):
        for rec in self:
            published = rec.version_ids.filtered(
                lambda v: v.status == 'published').sorted('revision')[-1:]
            draft = rec.version_ids.filtered(
                lambda v: v.status == 'draft').sorted('revision')[-1:]
            rec.published_version_id = published
            rec.draft_version_id = draft
            if not rec.active:
                rec.state = 'archived'
            elif published:
                rec.state = 'published'
            else:
                rec.state = 'draft'
            rec.summary = (published or draft).summary if (published or draft) \
                else _('Nothing is checked yet.')

    def action_new_draft(self):
        """Copy the published definition into a fresh draft revision."""
        self.ensure_one()
        if self.draft_version_id:
            return self.draft_version_id
        source = self.published_version_id
        last = max(self.version_ids.mapped('revision') or [0])
        return self.env['biz.approval.workflow.version'].create({
            'workflow_id': self.id,
            'revision': last + 1,
            'status': 'draft',
            'definition': source.definition if source else D.empty_definition(),
        })


class BizApprovalWorkflowVersion(models.Model):
    _name = 'biz.approval.workflow.version'
    _description = 'Approval Workflow Revision'
    _order = 'workflow_id, revision desc'

    workflow_id = fields.Many2one('biz.approval.workflow', required=True,
                                  index=True, ondelete='cascade')
    company_id = fields.Many2one(related='workflow_id.company_id', store=True,
                                 index=True)
    process_id = fields.Many2one(related='workflow_id.process_id', store=True,
                                 index=True)
    revision = fields.Integer(required=True, default=1)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'In use'),
        ('superseded', 'Replaced'),
        ('archived', 'Put away'),
    ], default='draft', required=True, index=True)
    definition = fields.Json(default=D.empty_definition)
    schema_version = fields.Integer(default=D.SCHEMA_VERSION)
    summary = fields.Char(compute='_compute_readable', store=True)
    route_labels = fields.Json(compute='_compute_readable', store=True)
    published_by_uid = fields.Many2one('res.users', readonly=True)
    published_at = fields.Datetime(readonly=True)
    effective_from = fields.Datetime()
    publish_reason = fields.Char()
    confirmations = fields.Json(default=list, readonly=True)
    fingerprint = fields.Char(readonly=True, index=True)
    draft_revision = fields.Integer(
        default=1, readonly=True,
        help='Counts every change to this draft, so two people editing at '
             'once cannot overwrite each other.')

    _revision_uniq = models.Constraint(
        'unique(workflow_id, revision)',
        'That revision number is already used by this workflow.')

    @api.depends('definition', 'workflow_id.name', 'revision')
    def _compute_readable(self):
        roles = {r.key: r.name
                 for r in self.env['biz.approval.role'].sudo().search([])}
        for rec in self:
            names = {}
            user_ids = []
            for step in D.normalise(rec.definition)['steps']:
                user_ids += (step.get('who') or {}).get('user_ids') or []
            if user_ids:
                for user in self.env['res.users'].sudo().browse(
                        list(set(user_ids))).exists():
                    names[user.id] = user.name
            rec.summary = D.sentence(rec.definition, roles, names)
            rec.route_labels = D.route_labels(rec.definition, roles, names)

    @api.depends('workflow_id.name', 'revision', 'status')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s · v%s' % (rec.workflow_id.name or '',
                                             rec.revision)

    # ------------------------------------------------------- immutability
    def write(self, vals):
        """A published revision is frozen. Only its status may move on."""
        # Only the lifecycle status may move on a frozen version; the two
        # related columns are the ORM keeping its own bookkeeping in step.
        allowed_on_published = {'status', 'display_name', 'company_id',
                                'process_id', 'summary', 'route_labels'}
        for rec in self:
            if rec.status == 'published' and set(vals) - allowed_on_published:
                raise UserError(_(
                    "This version is in use and cannot be changed. Start a "
                    "new draft instead — requests already under way keep the "
                    "version they were given."))
            if rec.status in ('superseded', 'archived') \
                    and set(vals) - allowed_on_published:
                raise UserError(_(
                    "This version has been replaced and is kept as a record. "
                    "It cannot be changed."))
        if 'definition' in vals:
            for rec in self:
                if rec.status == 'draft':
                    vals = dict(vals)
                    vals['draft_revision'] = rec.draft_revision + 1
                    super(BizApprovalWorkflowVersion, rec).write(vals)
            return True
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.status != 'draft':
                raise UserError(_(
                    "A version that has been in use is part of the record and "
                    "cannot be deleted."))
        return super().unlink()
