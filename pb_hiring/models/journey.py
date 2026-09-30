"""Guided hiring: one pipeline, tenant-owned content and explicit next actions."""
import base64
import json
import logging
import re
from pathlib import Path
from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .hiring_common import as_id, flag, P_CANDIDATE_MAIL

_logger = logging.getLogger(__name__)

# RECRUIT P1 (RC-D2, RC-D8): Rize's vocabulary is the product default. The
# KEYS are the contract every other file and every stored row speaks; the
# NAMES and the ORDER are the client's (a talent lead renames a stage in
# Hiring set-up, and an upgrade must never put the old word back).
#
#   key, English name, sequence, family (open / done / closed)
STAGE_ROWS = [
    ('screening', 'Applications received', 10, 'open'),
    ('shortlist', 'Shortlist', 20, 'open'),
    ('panel_review', 'Hiring manager review', 30, 'open'),
    ('phone', 'Recruiter review', 40, 'open'),
    ('assignment', 'Assignment', 50, 'open'),
    ('discussion_1', 'Discussion 1', 60, 'open'),
    ('discussion_2', 'Discussion 2', 70, 'open'),
    ('discussion_3', 'Discussion 3', 80, 'open'),
    ('reference', 'Reference check', 90, 'open'),
    ('offer', 'Offer', 100, 'open'),
    ('post_offer', 'Post-offer', 110, 'open'),
    ('joined', 'Joined', 120, 'done'),
    ('cv_reject', 'CV reject', 130, 'closed'),
    ('interview_reject', 'Interview reject', 140, 'closed'),
    ('drop_out', 'Drop-out', 150, 'closed'),
    ('on_hold', 'On hold', 160, 'closed'),
    ('offer_drop_out', 'Offer drop', 170, 'closed'),
]
STAGES = [(key, name) for key, name, _seq, _fam in STAGE_ROWS]
FAMILY = {key: fam for key, _n, _s, fam in STAGE_ROWS}
OUTCOMES = {key for key, fam in FAMILY.items() if fam == 'closed'}
#: Shown on every role whatever its own set says: the first two and the last
#: two open stages carry the story, and the outcome stages are the words the
#: numbers are counted in (blueprint, "Outcome stages are always on").
ALWAYS_ON = {'screening', 'shortlist', 'offer', 'post_offer', 'joined'} | OUTCOMES
#: Hidden on a new role unless its preset says otherwise.
HIDDEN_BY_DEFAULT = {'reference', 'discussion_3'}
#: The words wave 2 shipped. The seed renames a row ONLY while it still
#: carries one of these (or was never named): a client's own rename survives
#: every upgrade. "Recruiter phone screen" is here because RC-D8 says any
#: surface still carrying it is wrong.
OLD_NAMES = {
    'screening': {'Screening'}, 'panel_review': {'Panel Review'},
    'phone': {'Recruiter Phone Call', 'Recruiter phone screen',
              'Recruiter Phone Screen'},
    'reference': {'Reference Check'}, 'offer': {'Offer Stage'},
    'cv_reject': {'CV Reject'}, 'interview_reject': {'Interview Reject'},
    'drop_out': {'Drop Out'}, 'on_hold': {'On Hold'},
    'offer_drop_out': {'Offer Drop out'},
}
#: The talent lead's one-line meaning of each stage, shown on hover over the
#: column name. Seeded only where a row has none. Deliberately silent about
#: anything a later phase automates (the Calendly link, the assignment brief):
#: a sentence promising an email that does not go is a lie on the board.
MEANINGS = {
    'screening': 'Everyone who applied and has not had a first look yet.',
    'shortlist': 'Worth a conversation. From here they go to a recruiter '
                 'review or straight to a hiring manager review.',
    'panel_review': 'The hiring manager looks at the CV before interviews '
                    'are set up. Used for senior or new roles.',
    'phone': 'A 30-minute conversation with the recruiter.',
    'assignment': 'A take-home task, for roles that need one.',
    'discussion_1': 'The first interview round, with the panel\'s opinions.',
    'discussion_2': 'The second interview round, with the panel\'s opinions.',
    'discussion_3': 'A third interview round, for roles that need one.',
    'reference': 'Checking references before an offer. Hidden unless a role '
                 'needs it.',
    'offer': 'The person we want. Sending the offer needs the request agreed.',
    'post_offer': 'Offer accepted and a joining date known. Still a candidate '
                  'until they start.',
    'joined': 'Started on the confirmed date. Now an employee.',
    'cv_reject': 'Not taken forward after the first look.',
    'interview_reject': 'Not taken forward after a conversation or interview.',
    'drop_out': 'The candidate withdrew before an offer.',
    'on_hold': 'Paused with a date to look again.',
    'offer_drop_out': 'Declined the offer, or accepted and did not join.',
}
#: Vietnamese for the seeded names and meanings, written with the rows.
VI_NAMES = {
    'screening': 'Hồ sơ đã nhận', 'shortlist': 'Danh sách chọn',
    'panel_review': 'Quản lý tuyển dụng xem xét',
    'phone': 'Chuyên viên tuyển dụng xem xét', 'assignment': 'Bài tập',
    'discussion_1': 'Trao đổi 1', 'discussion_2': 'Trao đổi 2',
    'discussion_3': 'Trao đổi 3', 'reference': 'Kiểm tra tham chiếu',
    'offer': 'Mời nhận việc', 'post_offer': 'Chờ nhận việc',
    'joined': 'Đã nhận việc', 'cv_reject': 'Loại hồ sơ',
    'interview_reject': 'Loại sau phỏng vấn', 'drop_out': 'Ứng viên rút lui',
    'on_hold': 'Tạm hoãn', 'offer_drop_out': 'Từ chối lời mời',
}
VI_MEANINGS = {
    'screening': 'Mọi người đã nộp hồ sơ nhưng chưa được xem lần đầu.',
    'shortlist': 'Đáng để trao đổi. Từ đây họ chuyển sang chuyên viên tuyển '
                 'dụng xem xét hoặc thẳng tới quản lý tuyển dụng xem xét.',
    'panel_review': 'Quản lý tuyển dụng xem CV trước khi sắp xếp phỏng vấn. '
                    'Dùng cho vị trí cấp cao hoặc vị trí mới.',
    'phone': 'Một cuộc trao đổi 30 phút với chuyên viên tuyển dụng.',
    'assignment': 'Một bài tập làm ở nhà, cho vị trí cần đến.',
    'discussion_1': 'Vòng phỏng vấn thứ nhất, kèm ý kiến của hội đồng.',
    'discussion_2': 'Vòng phỏng vấn thứ hai, kèm ý kiến của hội đồng.',
    'discussion_3': 'Vòng phỏng vấn thứ ba, cho vị trí cần đến.',
    'reference': 'Kiểm tra tham chiếu trước khi mời nhận việc. Ẩn trừ khi '
                 'vị trí cần đến.',
    'offer': 'Người chúng ta muốn tuyển. Gửi lời mời cần yêu cầu tuyển dụng '
             'đã được đồng ý.',
    'post_offer': 'Đã nhận lời và biết ngày vào làm. Vẫn là ứng viên cho đến '
                  'khi bắt đầu làm việc.',
    'joined': 'Đã bắt đầu làm việc vào ngày đã xác nhận. Giờ là nhân viên.',
    'cv_reject': 'Không tiếp tục sau lần xem hồ sơ đầu tiên.',
    'interview_reject': 'Không tiếp tục sau một cuộc trao đổi hoặc phỏng vấn.',
    'drop_out': 'Ứng viên rút lui trước khi được mời nhận việc.',
    'on_hold': 'Tạm dừng, có ngày để xem lại.',
    'offer_drop_out': 'Từ chối lời mời, hoặc đã nhận lời nhưng không đến làm.',
}
#: The six stock stages and where their candidates go (RC5).
STOCK_STAGE_MAP = [
    ('hr_recruitment.stage_job0', 'screening'),
    ('hr_recruitment.stage_job1', 'shortlist'),
    ('hr_recruitment.stage_job2', 'discussion_1'),
    ('hr_recruitment.stage_job3', 'discussion_2'),
    ('hr_recruitment.stage_job4', 'offer'),
    ('hr_recruitment.stage_job5', 'joined'),
]
#: Bumped when the stage ORDER the product ships changes. Sequences are set
#: once per bump and then belong to the client (a talent lead's reorder must
#: survive an upgrade just as their rename does).
STAGE_SET_VERSION = '2'
P_STAGE_SET = 'pb_hiring.stage_set_version'
AUTHORIZATION = [('permit', 'Yes, I have a valid work permit/visa'),
                 ('citizen', 'Yes, I am a citizen/permanent resident'),
                 ('sponsor', 'No, I would require visa sponsorship'),
                 ('unsure', "I'm unsure")]
RELOCATION = [('yes', 'Yes'), ('no', 'No'), ('depends', 'Depends on the role/terms')]


def text_html(value):
    return Markup('<p>') + escape(value or '').replace('\n', Markup('<br/>')) + Markup('</p>')


class HiringBrand(models.Model):
    _inherit = 'res.company'

    pb_mr_approver_id = fields.Many2one('res.users', string='Manpower request approver', domain=[('share', '=', False)])
    pb_hiring_brand = fields.Char('Recruitment brand name')
    pb_hiring_intro = fields.Text('Application acknowledgement introduction')
    pb_hiring_linkedin = fields.Char('Company LinkedIn URL')
    pb_hiring_about = fields.Text('About the company')
    pb_hiring_building = fields.Text('What we are building')
    pb_hiring_mission = fields.Text('Our mission')
    pb_hiring_operate = fields.Text('Where we operate')
    pb_hiring_why = fields.Text('Why join us')

    def _hiring_brand(self):
        self.ensure_one()
        return self.pb_hiring_brand or self.name


class HiringStage(models.Model):
    _inherit = 'hr.recruitment.stage'
    pb_key = fields.Selection(STAGES, index=True, copy=False)
    pb_family = fields.Selection(
        [('open', 'Still in play'), ('done', 'Joined'), ('closed', 'Closed')],
        string='Kind of stage', compute='_compute_pb_family', store=True,
        help='Open stages are the working board; closed ones sit in the quiet '
             'rail on the right.')
    pb_always_on = fields.Boolean(
        string='Shown on every role', compute='_compute_pb_family', store=True)
    pb_meaning = fields.Char(
        string='What this stage means', translate=True,
        help='One sentence, shown when somebody points at the column name.')

    @api.depends('pb_key')
    def _compute_pb_family(self):
        for rec in self:
            rec.pb_family = FAMILY.get(rec.pb_key) or False
            rec.pb_always_on = rec.pb_key in ALWAYS_ON

    @api.model
    def _pb_stage(self, key):
        """THE one lookup for a stage by its key (RC4)."""
        if not key:
            return self.browse()
        return self.sudo().search([('pb_key', '=', key)], order='id', limit=1)

    @api.model
    def _pb_vi(self):
        return bool(self.env['res.lang'].sudo().search_count(
            [('code', '=', 'vi_VN'), ('active', '=', True)]))

    @api.model
    def _ensure_journey_stages(self):
        """Idempotent on names, order and meanings — and polite about them.

        * A row is CREATED with Rize's name, order and meaning.
        * An existing row is renamed only while it still carries a wave-2
          name (`OLD_NAMES`): a talent lead's own rename survives.
        * The order is set once per `STAGE_SET_VERSION`, then it is theirs.
        * A meaning is written only where there is none.
        * fold / hired are facts about the key and are always put right.
        """
        Stage = self.sudo().with_context(active_test=False, lang='en_US')
        ICP = self.env['ir.config_parameter'].sudo()
        reorder = ICP.get_param(P_STAGE_SET) != STAGE_SET_VERSION
        vi = self._pb_vi()
        for key, name, seq, _family in STAGE_ROWS:
            fixed = {'fold': key in OUTCOMES, 'hired_stage': key == 'joined'}
            row = Stage.search([('pb_key', '=', key)], order='id', limit=1)
            if not row:
                row = Stage.create(dict(fixed, name=name, pb_key=key,
                                        sequence=seq,
                                        pb_meaning=MEANINGS[key]))
                if vi:
                    row.update_field_translations('name', {'vi_VN': VI_NAMES[key]})
                    row.update_field_translations('pb_meaning', {'vi_VN': VI_MEANINGS[key]})
                continue
            vals = {k: v for k, v in fixed.items() if row[k] != v}
            renamed = (row.name or '') in OLD_NAMES.get(key, set())
            if renamed:
                vals['name'] = name
            if reorder and row.sequence != seq:
                vals['sequence'] = seq
            meaning = not row.pb_meaning
            if meaning:
                vals['pb_meaning'] = MEANINGS[key]
            if vals:
                row.write(vals)
            if vi:
                # Vietnamese only where the row still carries the PRODUCT's
                # English and no Vietnamese of its own (a client's words, in
                # either language, are theirs).
                vi_row = row.with_context(lang='vi_VN')
                if row.name == name and vi_row.name == name:
                    row.update_field_translations('name', {'vi_VN': VI_NAMES[key]})
                if row.pb_meaning == MEANINGS[key] and vi_row.pb_meaning == MEANINGS[key]:
                    row.update_field_translations('pb_meaning', {'vi_VN': VI_MEANINGS[key]})
        self._retire_stock_stages()
        if reorder:
            ICP.set_param(P_STAGE_SET, STAGE_SET_VERSION)

    @api.model
    def _retire_stock_stages(self):
        """RC5. The stock stages have no `active`, so retiring one is: move its
        candidates to the mapped stage (silently — `just_moved` stops the
        stock acknowledgement, and the ledger does not count a housekeeping
        move as somebody's decision), clear its email, then delete it.

        Idempotent and run on every load of this module, because an upgrade
        of the standard recruitment module re-creates a noupdate record whose
        xmlid has gone.
        """
        Applicant = self.env['hr.applicant'].sudo().with_context(
            active_test=False, just_moved=True, tracking_disable=True,
            mail_notrack=True, pb_no_stage_log=True)
        retired = 0
        for xmlid, key in STOCK_STAGE_MAP:
            stock = self.env.ref(xmlid, raise_if_not_found=False)
            if not stock or stock._name != 'hr.recruitment.stage' \
                    or stock.pb_key:
                continue
            target = self._pb_stage(key)
            if not target:
                continue
            try:
                with self.env.cr.savepoint():
                    moving = Applicant.search([('stage_id', '=', stock.id)])
                    for app in moving:
                        app.write({'stage_id': target.id})
                    Applicant.search([('last_stage_id', '=', stock.id)]).write(
                        {'last_stage_id': target.id})
                    self.env['pb.hiring.step'].sudo().search(
                        [('stage_id', '=', stock.id)]).write(
                            {'stage_id': target.id})
                    Log = self.env['pb.hiring.stage.log'].sudo()
                    Log.search([('from_stage_id', '=', stock.id)]).write(
                        {'from_stage_id': target.id})
                    Log.search([('to_stage_id', '=', stock.id)]).write(
                        {'to_stage_id': target.id})
                    stock.sudo().write({'template_id': False})
                    stock.sudo().unlink()
                    retired += 1
            except Exception:           # noqa: BLE001 — never fail an upgrade
                _logger.warning('pb_hiring: could not retire the stock stage '
                                '%s', xmlid, exc_info=True)
        if retired:
            _logger.info('pb_hiring: retired %s stock recruitment stages',
                         retired)
        return retired


class HiringApplicant(models.Model):
    _inherit = 'hr.applicant'
    pb_location = fields.Char('Current location')
    pb_nationality = fields.Char('Nationality')
    pb_linkedin = fields.Char('LinkedIn profile')
    pb_portfolio = fields.Char('Website / portfolio')
    pb_work_authorization = fields.Selection(AUTHORIZATION, string='Work authorization')
    pb_relocation = fields.Selection(RELOCATION, string='Willing to relocate')
    pb_motivation = fields.Text('Why join us?')
    pb_first_touch = fields.Json('First touch', readonly=True, copy=False)
    pb_application_touch = fields.Json('Application touch', readonly=True, copy=False)
    pb_hold_until = fields.Date('Next candidate update')
    pb_stage_reason = fields.Text('Stage decision reason')

    def write(self, vals):
        # RC-D5: the offer and joined gates are gone from the stage write —
        # the one hard rule (no offer SENT without an agreed request) lives on
        # the offer itself. Only the touch-field protection stays.
        if not self.env.su and set(vals) & {'pb_first_touch', 'pb_application_touch'}:
            raise AccessError(_('Source attribution is captured automatically and cannot be edited.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        first = self.env['hr.recruitment.stage']._pb_stage('screening')
        for vals in vals_list:
            if vals.get('job_id') and not vals.get('stage_id') and first:
                vals['stage_id'] = first.id
        return super().create(vals_list)

    def _pb_next_stage(self, step=None):
        """The next stage THIS ROLE shows, in order — what "Advance" means.

        A step from the hiring request that names a stage still wins. Joined
        is never "next": it is set from the offer when somebody starts.
        """
        self.ensure_one()
        if step and step.stage_id:
            return step.stage_id
        Stage = self.env['hr.recruitment.stage']
        current = self.stage_id
        if current.pb_key and current.pb_family != 'open':
            return Stage.browse()
        req = self.sudo().pb_requisition_id
        shown = req._pb_board_stages() if req else Stage.sudo().search(
            [('pb_key', '!=', False)], order='sequence,id').filtered(
                lambda s: s.pb_key not in HIDDEN_BY_DEFAULT)
        ahead = shown.filtered(lambda s: s.pb_family == 'open'
                               and s.sequence > (current.sequence or 0))
        if not current.pb_key:
            # A legacy record enters the pipeline at its first working column.
            ahead = shown.filtered(lambda s: s.pb_family == 'open')[:2][-1:]
        return ahead[:1]

    def _pb_shortlist(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage']._pb_stage('shortlist')
        if stage:
            self.sudo().write({'stage_id': stage.id, 'kanban_state': 'done'})
            self.sudo().message_post(body=_("Shortlisted."))
            return True
        return super()._pb_shortlist()

    def _pb_reject(self, reason_id=None):
        for rec in self:
            key = 'cv_reject' if rec.stage_id.pb_key in ('screening', 'shortlist', 'panel_review', False) else 'interview_reject'
            stage = self.env['hr.recruitment.stage']._pb_stage(key)
            if stage:
                rec.sudo().write({'stage_id': stage.id})
        return super()._pb_reject(reason_id)

    def _pb_keep_in_touch(self):
        """Future-fit: into the pool AND onto CV reject, so the count stays
        honest (blueprint, first-look outcomes)."""
        res = super()._pb_keep_in_touch()
        stage = self.env['hr.recruitment.stage']._pb_stage('cv_reject')
        if stage and self.stage_id != stage:
            self.sudo().write({'stage_id': stage.id})
        return res

    def _pb_move_role(self, job_id):
        """Fit for other role: a COPY lands in the other role's Applications
        received, and this card moves to CV reject here — both roles keep an
        honest story (blueprint, first-look outcomes)."""
        self.ensure_one()
        job = self.env['hr.job'].sudo().browse(as_id(job_id)).exists()
        if not job:
            raise UserError(_("Say which role they fit before copying them there."))
        if job.id == self.job_id.id:
            raise UserError(_("They are already on that role."))
        if job.company_id and self.company_id and job.company_id != self.company_id:
            raise UserError(_("That role belongs to another company, so a candidate cannot be copied onto it."))
        Stage = self.env['hr.recruitment.stage']
        requisition = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', job.id)], order='id desc', limit=1)
        # `no_copy_in_partner_name`: the stock copy appends "(copy)" to the
        # person's name, which is wrong for the same person on another role.
        copy = self.sudo().with_context(pb_no_stage_log=True,
                                        no_copy_in_partner_name=True).copy({
            'job_id': job.id,
            'department_id': job.department_id.id or False,
            'stage_id': Stage._pb_stage('screening').id or False,
            'pb_requisition_id': requisition.id or False,
            'pb_screen': False, 'pb_other_job_id': False,
        })
        here = Stage._pb_stage('cv_reject')
        vals = {'pb_other_job_id': job.id}
        if here:
            vals['stage_id'] = here.id
        self.sudo().write(vals)
        old = self.job_id
        self.sudo().message_post(body=_(
            "A copy went to %(new)s, where they start at the first stage.",
            new=job.name or ''))
        for target, text in ((old, _("%(who)s fits %(job)s better; a copy went there.",
                                     who=self.partner_name or '', job=job.name or '')),
                             (job, _("%(who)s came across from %(job)s.",
                                     who=self.partner_name or '', job=old.name or ''))):
            if target:
                try:
                    with self.env.cr.savepoint():
                        target.sudo().message_post(body=text)
                except Exception:           # noqa: BLE001 — a note is a courtesy
                    _logger.warning('pb_hiring: could not note the copy on job %s', target.id, exc_info=True)
        return copy


class HiringOfferJourney(models.Model):
    _inherit = 'pb.hiring.offer'

    @api.model
    def draft_for(self, requisition_id, values=None):
        offer = super().draft_for(requisition_id, values)
        stage = self.env['hr.recruitment.stage']._pb_stage('offer')
        if stage and offer.state != 'closed' and offer.applicant_id.stage_id.pb_key not in ('offer', 'post_offer', 'joined'):
            offer.applicant_id.sudo().write({'stage_id': stage.id})
        return offer

    def _mark_applicant_hired(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage']._pb_stage('joined')
        if stage:
            self.applicant_id.sudo().write({'stage_id': stage.id})
            return True
        return super()._mark_applicant_hired()



class HiringRequest(models.Model):
    _inherit = 'pb.hiring.requisition'
    pb_target_close_date = fields.Date('Target position closing date')
    pb_role_level = fields.Char('Role level / seniority')
    pb_assignment = fields.Boolean('Include an assignment')
    pb_jd_file = fields.Binary('Job description attachment', attachment=True)
    pb_jd_filename = fields.Char('JD filename')
    pb_assignment_file = fields.Binary('Assignment attachment', attachment=True)
    pb_assignment_filename = fields.Char('Assignment filename')

    def _approval_manager_uids(self):
        self.ensure_one()
        approver = self.company_id.pb_mr_approver_id
        return approver.ids if approver else super()._approval_manager_uids()

    def _chain_revision_values(self):
        vals = super()._chain_revision_values()
        # These are part of the proposal that approvers agree to.
        vals.update({'pb_role_level': self.pb_role_level, 'pb_assignment': self.pb_assignment,
                     'reporting_manager_id': self.reporting_manager_id.id,
                     'pb_target_close_date': self.pb_target_close_date})
        return vals


class HiringReferral(models.Model):
    _inherit = 'pb.hiring.referral'
    pb_consent = fields.Boolean('Candidate consent')
    pb_declaration = fields.Boolean('Relationship and panel declaration')
    pb_relationship = fields.Char('Relationship with candidate')
    pb_nationality = fields.Char('Candidate nationality')
    pb_location = fields.Char('Candidate current location')
    pb_linkedin = fields.Char('Candidate LinkedIn profile')
    pb_employment_type = fields.Char('Referrer employment type')
    pb_referrer_email = fields.Char('Referrer email')
    pb_department = fields.Char('Referrer department')
    pb_designation = fields.Char('Referrer designation')
    pb_entity = fields.Char('Referrer employment entity')

    @api.model
    def _state_of(self, applicant):
        applicant = applicant.sudo()
        if applicant and applicant.active and applicant.stage_id.pb_key == 'screening':
            return 'received'
        return super()._state_of(applicant)

    @api.model
    def refer(self, requisition_id, employee_id, values):
        employee = self.env['hr.employee'].sudo().browse(as_id(employee_id)).exists()
        if not self.env.su and (not employee or employee.user_id != self.env.user):
            raise AccessError(_('You can submit a referral only as yourself.'))
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if not req or req.state != 'open' or not req.referral_open or req.role_type == 'sensitive_replacement':
            raise ValueError('This role is not open to referrals.')
        if not values.get('consent') or not values.get('declaration'):
            raise UserError(_('Candidate consent and the relationship declaration are required.'))
        for key in ('name', 'email', 'phone', 'nationality', 'location', 'relationship', 'linkedin'):
            if not str(values.get(key) or '').strip():
                raise UserError(_('Complete the candidate contact, profile and relationship fields.'))
        if not values.get('attachment'):
            raise UserError(_('Attach the candidate’s updated resume.'))
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if req and req.role_type == 'sensitive_replacement':
            raise UserError(_('This role is not open to referrals.'))
        referral = super().refer(requisition_id, employee_id, values)
        referral.sudo().write({
            'pb_consent': True, 'pb_declaration': True,
            'pb_relationship': values['relationship'], 'pb_nationality': values['nationality'],
            'pb_location': values['location'], 'pb_linkedin': values['linkedin'],
            'pb_referrer_email': employee.work_email or employee.user_id.email,
            'pb_department': employee.department_id.name, 'pb_designation': employee.job_title,
            'pb_employment_type': employee.employee_type, 'pb_entity': employee.company_id.name,
        })
        referral.applicant_id.sudo().write({
            'pb_nationality': values['nationality'], 'pb_location': values['location'],
            'pb_linkedin': values['linkedin'],
            'pb_application_touch': {'source': 'Referral', 'referrer_employee_id': employee.id},
        })
        return referral


class HiringInterview(models.Model):
    _inherit = 'pb.hiring.interview'

    @api.constrains('panel_employee_ids', 'applicant_id')
    def _check_referrer_panel(self):
        for rec in self:
            referrers = rec.applicant_id.sudo().pb_referral_ids.employee_id
            if rec.panel_employee_ids & referrers:
                raise ValidationError(_('A referrer cannot sit on the candidate’s interview panel.'))


class HiringMessageTemplate(models.Model):
    _name = 'pb.hiring.message.template'
    _description = 'Hiring communication template'
    _order = 'sequence, id'
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    key = fields.Selection([('received', 'Application received'), ('phone', 'Recruiter review'),
                            ('assignment', 'Assignment'), ('on_hold', 'On hold'), ('cv_reject', 'CV rejection')], required=True)
    # RECRUIT P2 (G-02): the candidate-facing words exist per language; the
    # "Application received" email goes out in the language they applied in.
    subject = fields.Char(required=True, translate=True)
    body = fields.Text(required=True, translate=True)
    active = fields.Boolean(default=True)

    def _render(self, applicant, values=None):
        self.ensure_one()
        company = self.company_id
        tokens = {'first_name': (applicant.partner_name or '').split(' ')[0],
                  'role': applicant.job_id.name or '', 'brand': company._hiring_brand(),
                  'website': company.website or '', 'linkedin': company.pb_hiring_linkedin or '',
                  'company_intro': company.pb_hiring_intro or '',
                  'sender_name': self.env.user.name, 'hr_name': applicant.user_id.name or self.env.user.name}
        tokens.update(values or {})
        required = set(re.findall(r'{{\s*(\w+)\s*}}', self.subject + self.body))
        missing = sorted(k for k in required if not str(tokens.get(k) or '').strip()
                         and k not in ('website', 'linkedin', 'company_intro'))
        if missing:
            raise UserError(_('Complete these message details first: %s', ', '.join(missing)))
        render = lambda text: re.sub(r'{{\s*(\w+)\s*}}', lambda m: str(tokens.get(m[1]) or ''), text)
        return {'subject': render(self.subject), 'body': render(self.body)}


class HiringJourney(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _seed_journey(self):
        seed_journey(self.env)

    @api.model
    def journey_options(self):
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        company = self.env.company
        return {'brand': company._hiring_brand(),
                'requestor': self.env.user.name,
                'currencies': self.env['res.currency'].search_read([('active', '=', True)], ['name']),
                'currency_id': company.currency_id.id,
                'countries': self.env['res.country'].search_read([], ['name']),
                'message_fields': {t.key: sorted(set(re.findall(r'{{\s*(\w+)\s*}}', t.subject + t.body)) -
                    {'first_name', 'role', 'brand', 'website', 'linkedin', 'company_intro', 'sender_name', 'hr_name'})
                    # sudo (RECRUIT P1, RC16): a line manager reads the board
                    # and holds no read on the templates; only the field names
                    # leave this method, never a template.
                    for t in self.env['pb.hiring.message.template'].sudo().search([('company_id', '=', company.id)])},
                'managers': self.env['hr.employee'].sudo().search_read(
                    [('company_id', 'in', self.env.companies.ids)], ['name'], limit=1000),
                'users': self.env['res.users'].sudo().search_read(
                    [('share', '=', False), ('company_ids', 'in', self.env.companies.ids)], ['name'], limit=1000),
                'stages': [{'id': s.id, 'key': s.pb_key, 'name': s.name, 'outcome': s.pb_key in OUTCOMES,
                            'family': s.pb_family or 'open', 'meaning': s.pb_meaning or ''}
                           for s in self.env['hr.recruitment.stage'].sudo().search([('pb_key', '!=', False)], order='sequence,id')],
                'company_sections': [{'key': k, 'title': title, 'body': company['pb_hiring_' + k] or ''}
                    for k, title in [('about', 'About ' + company._hiring_brand()), ('building', 'What we are building'),
                                     ('mission', 'Our mission'), ('operate', 'Where we operate'), ('why', 'Why join us')]]}

    def _row(self, req):
        row = super()._row(req)
        row['target_close_date'] = str(req.pb_target_close_date or '')
        return row

    def _act_create(self, payload):
        result = super()._act_create(payload)
        req = self.env['pb.hiring.requisition'].browse(result['id'])
        extra = {'pb_role_level': str(payload.get('role_level') or '')[:200],
                 'pb_assignment': bool(payload.get('assignment')),
                 'pb_target_close_date': payload.get('target_close_date') or False}
        manager = self.env['hr.employee'].sudo().browse(as_id(payload.get('reporting_manager_id'))).exists()
        if manager:
            if manager.company_id != req.company_id:
                raise UserError(_('Choose a reporting manager in this company.'))
            extra['reporting_manager_id'] = manager.id
        if payload.get('currency_id'):
            extra['currency_id'] = as_id(payload['currency_id'])
        for kind in ('jd', 'assignment'):
            upload = payload.get(kind + '_file')
            if upload:
                if len(upload) > 14000000:
                    raise UserError(_('Attachments must be smaller than 10 MB.'))
                extra['pb_' + kind + '_file'] = upload
                extra['pb_' + kind + '_filename'] = str(payload.get(kind + '_filename') or kind)[:200]
        req.write(extra)
        for index, step in enumerate(payload.get('interviews') or []):
            if not step.get('owner_id') or not step.get('focus'):
                continue
            owner = self.env['res.users'].sudo().browse(as_id(step['owner_id'])).exists()
            if not owner or req.company_id not in owner.company_ids:
                raise UserError(_('Choose interviewers in this company.'))
            stage = self.env['hr.recruitment.stage']._pb_stage('discussion_%s' % (index + 1))
            self.env['pb.hiring.step'].create({'requisition_id': req.id, 'name': 'Discussion %s' % (index + 1),
                'sequence': (index + 1) * 10, 'owner_id': owner.id, 'notes': step['focus'],
                'kind': 'interview', 'stage_id': stage.id})
        return result

    def _act_new_jd(self, payload):
        if payload.get('sections'):
            req = self._get(payload)
            self._require_recruit(req)
            company = req.company_id
            html = Markup('')
            for key, title in [('about', 'About ' + company._hiring_brand()), ('building', 'What we are building'),
                               ('mission', 'Our mission'), ('operate', 'Where we operate')]:
                if company['pb_hiring_' + key]:
                    html += Markup('<h2>%s</h2>') % title + text_html(company['pb_hiring_' + key])
            for key, title in [('role', 'What the role is about'), ('duties', 'What you will be doing'),
                               ('must', 'Must-have skills and characteristics'), ('nice', 'Nice-to-have skills and characteristics'),
                               ('process', 'Interview process')]:
                value = payload['sections'].get(key, '').strip()
                if key in ('role', 'duties', 'must') and not value:
                    raise UserError(_('Complete the role summary, responsibilities and must-have criteria.'))
                if value:
                    html += Markup('<h2>%s</h2>') % title + text_html(value)
            if company.pb_hiring_why:
                html += Markup('<h2>Why join %s</h2>') % company._hiring_brand() + text_html(company.pb_hiring_why)
            payload = dict(payload, body=str(html))
        return super()._act_new_jd(payload)

    def _act_open_brand(self, payload):
        # RECRUIT P1 (G-10): the talent lead self-serves the company story.
        if not self._can_write():
            raise AccessError(_('Only the talent lead and the head of hiring change the company story.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'res.company', 'res_id': self.env.company.id,
                'views': [(self.env.ref('pb_hiring.view_hiring_brand').id, 'form')], 'target': 'new', 'name': _('Recruitment identity')}

    def _act_open_templates(self, payload):
        self._require_recruit()
        return {'type': 'ir.actions.act_window', 'res_model': 'pb.hiring.message.template',
                'view_mode': 'list,form', 'views': [(False, 'list'), (False, 'form')], 'name': _('Candidate emails')}

    def _act_message_preview(self, payload):
        applicant = self.env['hr.applicant'].with_context(active_test=False).browse(as_id(payload.get('applicant_id'))).exists()
        applicant.check_access('read')
        self._require_recruit(applicant.pb_requisition_id)
        template = self.env['pb.hiring.message.template'].search([
            ('company_id', '=', applicant.company_id.id), ('key', '=', payload.get('key'))], limit=1)
        if not template:
            raise UserError(_('Configure this candidate email for the company first.'))
        return template._render(applicant, payload.get('values'))

    def _act_message_send(self, payload):
        rendered = self._act_message_preview(payload)
        applicant = self.env['hr.applicant'].browse(as_id(payload['applicant_id']))
        if not flag(self.env, P_CANDIDATE_MAIL):
            raise UserError(_('Candidate emails are switched off in Hiring settings.'))
        if not applicant.email_from:
            raise UserError(_('Add a candidate email address first.'))
        applicant.message_post(subject=rendered['subject'], body=text_html(rendered['body']),
                               message_type='comment', subtype_xmlid='mail.mt_note')
        self.env['mail.mail'].sudo().create({'subject': rendered['subject'],
            'body_html': text_html(rendered['body']), 'email_to': applicant.email_from,
            'email_from': self.env.company.email or self.env.user.email_formatted,
            'model': 'hr.applicant', 'res_id': applicant.id, 'auto_delete': False})
        return {'note': _('Candidate email queued. Delivery is tracked in the mail queue.')}


def seed_journey(env):
    env['hr.recruitment.stage']._ensure_journey_stages()
    # RECRUIT P1: a Standard preset per company, then every role that has no
    # columns of its own gets them (idempotent: a role's own set is never
    # touched once it has one).
    env['pb.hiring.stage.preset']._ensure_standard()
    env['pb.hiring.requisition']._pb_fill_visible_stages()
    source = json.loads((Path(__file__).parent.parent / 'data/journey_content.json').read_text())
    for company in env['res.company'].sudo().search([]):
        if env.cr.dbname == 'rize' and not company.pb_mr_approver_id:
            matches = env['res.users'].sudo().search([('name', '=ilike', 'Dhruv%'), ('share', '=', False), ('company_ids', 'in', company.id)])
            if len(matches) == 1:
                company.pb_mr_approver_id = matches
        if env.cr.dbname == 'rize' and not company.pb_hiring_brand:
            company.write(dict(pb_hiring_brand='Rize', pb_hiring_intro=source['intro'],
                               **{'pb_hiring_' + k: v for k, v in source['sections'].items()}))
        for index, template in enumerate(source['emails']):
            if not env['pb.hiring.message.template'].sudo().search_count([('company_id', '=', company.id), ('key', '=', template['key'])]):
                env['pb.hiring.message.template'].sudo().with_context(lang='en_US').create(
                    dict(template, company_id=company.id, sequence=index * 10))
    # RECRUIT P2: application forms (templates per company, every role its
    # own copy, the Vietnamese / Indonesian words). Imported here: the forms
    # file reads this one's constants.
    from .forms_p2 import seed_forms
    seed_forms(env)
