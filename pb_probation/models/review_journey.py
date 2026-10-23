"""SOP review gates. Peer agreement and manager expectations are distinct scales."""
import json
from datetime import datetime, time, timedelta
import pytz
from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .probation_common import NON_STAFF_TYPES
from .verdict_approval import VERDICT_WRITE

AGREEMENT = ['1 · Strongly disagree', '2 · Disagree', '3 · Agree', '4 · Strongly agree']
EXPECTATION = [('1', 'Below expectations'), ('2', 'Slightly below expectations'),
               ('3', 'Slightly above expectations'), ('4', 'Above expectations')]
PEER_CRITERIA = [
    ('enjoy', 'I enjoy working with this colleague.'),
    ('communication', 'This colleague communicates effectively.'),
    ('execution', 'This colleague gets things done.'),
    ('initiative', 'This colleague contributes beyond their assigned duties.'),
    ('quality', 'This colleague delivers quality work on time.'),
    ('recommend', 'I recommend confirming this colleague as a permanent employee.'),
]
SOP_QUESTIONS = [{'key': 'sop_frequency', 'type': 'choice', 'label': 'How often do you work together?',
                 'options': ['Daily', 'Several times a week', 'Weekly', 'Occasionally']}] + [
    {'key': 'sop_' + key, 'type': 'choice', 'label': label, 'options': AGREEMENT}
    for key, label in PEER_CRITERIA] + [
    {'key': 'sop_' + kind + str(n), 'type': 'text', 'label': '%s %s' % (label, n)}
    for kind, label in [('strength', 'Strength'), ('improve', 'Area for improvement')] for n in range(1, 4)] + [
    {'key': 'sop_comments', 'type': 'text', 'label': 'Additional comments (optional)'}]


class ReviewPolicy(models.Model):
    _inherit = 'pb.probation.policy'
    peer_min = fields.Integer('Minimum peers', default=3)
    peer_max = fields.Integer('Maximum peers', default=4)
    hr_reviewer_id = fields.Many2one('res.users', string='HR lead reviewer', domain=[('share', '=', False)])
    ceo_reviewer_id = fields.Many2one('res.users', string='CEO / executive reviewer', domain=[('share', '=', False)])

    @api.constrains('peer_min', 'peer_max')
    def _check_peer_limits(self):
        for policy in self:
            if not 1 <= policy.peer_min <= policy.peer_max <= 10:
                raise ValidationError(_('Peer limits must be between 1 and 10, with minimum no greater than maximum.'))

    def settings_for(self, employee):
        result = super().settings_for(employee)
        policy = self.policy_for(employee)
        result.update(peer_min=policy.peer_min if policy else 3, peer_max=policy.peer_max if policy else 4)
        return result


class ReviewJourney(models.Model):
    _inherit = 'pb.probation.review'
    pb_leadership = fields.Boolean('Leadership / regional role', tracking=True)
    pb_gate = fields.Selection([('manager', 'Manager evaluation'), ('hr', 'HR lead review'),
                               ('ceo', 'CEO review'), ('rework', 'Changes requested'), ('approved', 'Approved')],
                              default='manager', readonly=True, copy=False, tracking=True)
    pb_proposed = fields.Json('Proposed outcome', readonly=True, copy=False)
    pb_review_note = fields.Text('Review notes / objections', readonly=True, copy=False)
    pb_hr_by = fields.Many2one('res.users', string='HR reviewed by', readonly=True, copy=False)
    pb_ceo_by = fields.Many2one('res.users', string='CEO reviewed by', readonly=True, copy=False)
    pb_manager_quality = fields.Selection(EXPECTATION, 'Quality and productivity')
    pb_manager_culture = fields.Selection(EXPECTATION, 'Culture and teamwork')
    pb_manager_adaptability = fields.Selection(EXPECTATION, 'Adaptability')
    pb_manager_initiative = fields.Selection(EXPECTATION, 'Initiative and resourcefulness')
    pb_manager_leadership = fields.Selection(EXPECTATION, 'Leadership')
    pb_improvement_plan = fields.Text('One-month improvement plan')
    pb_improvement_due = fields.Date('Improvement plan review date')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if vals.get('pb_gate', 'manager') != 'manager' or any(vals.get(k) for k in ('pb_proposed', 'pb_hr_by', 'pb_ceo_by')):
                    raise AccessError(_('New evaluations must start with the manager assessment.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and set(vals) & {'pb_gate', 'pb_proposed', 'pb_hr_by', 'pb_ceo_by', 'pb_review_note'}:
            raise AccessError(_('Use the review actions to change approval status.'))
        if not self.env.su and set(vals) & {'pb_leadership', 'pb_manager_quality', 'pb_manager_culture',
                'pb_manager_adaptability', 'pb_manager_initiative', 'pb_manager_leadership', 'pb_improvement_plan'}:
            for rec in self:
                rec._require_manager()
                if rec.pb_gate in ('hr', 'ceo', 'approved'):
                    raise UserError(_('Request changes before editing a submitted evaluation.'))
        return super().write(vals)

    def _working_deadline(self, start, days):
        self.ensure_one()
        calendar = self.employee_id.resource_calendar_id or self.company_id.resource_calendar_id
        zone = pytz.timezone(calendar.tz or 'UTC')
        current = fields.Date.to_date(start)
        weekdays = {int(a.dayofweek) for a in calendar.attendance_ids if not a.display_type} or {0,1,2,3,4}
        remaining = int(days)
        for unused in range(370):
            if remaining <= 0:
                break
            current += timedelta(days=1)
            lower = zone.localize(datetime.combine(current, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
            upper = lower + timedelta(days=1)
            holiday = self.env['resource.calendar.leaves'].sudo().search_count([
                ('resource_id', '=', False), ('company_id', '=', self.company_id.id),
                '|', ('calendar_id', '=', False), ('calendar_id', '=', calendar.id),
                ('date_from', '<', upper), ('date_to', '>', lower)])
            if current.weekday() in weekdays and not holiday:
                remaining -= 1
        if remaining:
            raise UserError(_('The working calendar has no available days. Ask HR to check it.'))
        return current

    def action_confirm_nominees(self, employee_ids=None):
        self.ensure_one()
        if self.kind != 'probation':
            return super().action_confirm_nominees(employee_ids)
        self._require_manager()
        if self.employee_id.employee_type in NON_STAFF_TYPES:
            raise UserError(_('This probation evaluation applies to full-time employees only.'))
        if self.state not in ('scheduled', 'nomination'):
            raise UserError(_('The peer feedback window has already started.'))
        people = self.env['hr.employee'].sudo().browse([int(i) for i in employee_ids]).exists() if employee_ids is not None else self.nominee_ids
        settings = self._settings()
        if not settings['peer_min'] <= len(people) <= settings['peer_max']:
            raise UserError(_('Choose between %(low)s and %(high)s colleagues.', low=settings['peer_min'], high=settings['peer_max']))
        if self.employee_id in people or any(p.company_id != self.company_id or not p.active for p in people):
            raise UserError(_('Choose active colleagues in the employee’s company, excluding the employee.'))
        if any(not (p.work_email or p.user_id.email) for p in people):
            raise UserError(_('Every peer needs an email address to receive their private feedback link.'))
        deadline = self._working_deadline(fields.Date.context_today(self), settings['feedback_window_days'])
        self.sudo().write({'nominee_ids': [(6, 0, people.ids)]})
        sent = self._make_feedback_requests(people, deadline)
        if sent != len(people):
            raise UserError(_('Some feedback requests could not be prepared. Check peer contact details and retry.'))
        self.sudo().write({'state': 'feedback', 'feedback_deadline': deadline})
        self.message_post(body=_('%(count)s peers invited. Feedback due %(date)s (working-day calendar).', count=sent, date=deadline))
        return {'sent': sent, 'deadline': str(deadline)}

    def _make_feedback_requests(self, people, deadline):
        result = super()._make_feedback_requests(people, deadline)
        if self.kind == 'probation':
            self.feedback_request_ids.filtered(lambda r: r.state != 'submitted').sudo().write({'questions_json': json.dumps(SOP_QUESTIONS)})
        return result

    def _build_report(self):
        if not any('sop_' in (r.questions_json or '') for r in self.feedback_request_ids):
            return super()._build_report()
        submitted = self.feedback_request_ids.filtered(lambda r: r.state == 'submitted')
        rows = [json.loads(r.answers_json or '{}') for r in submitted]
        parts = [Markup('<h3>Peer perspective</h3><p>%s of %s peers responded. Agreement scale: 1 strongly disagree · 4 strongly agree.</p>') % (len(submitted), len(self.feedback_request_ids))]
        averages = []
        for key, label in PEER_CRITERIA:
            values = [float(str(row.get('sop_' + key, {}).get('value', '0')).split(' · ')[0]) for row in rows]
            values = [v for v in values if 1 <= v <= 4]
            if values:
                avg = sum(values) / len(values)
                averages.append(avg)
                parts.append(Markup('<p>%s <strong>%.2f / 4</strong></p>') % (label, avg))
        parts.append(Markup('<h4>Unattributed feedback</h4>'))
        for row in rows:
            for question in SOP_QUESTIONS:
                if question['type'] == 'text' and row.get(question['key'], {}).get('value'):
                    parts.append(Markup('<p><b>%s</b><br/>%s</p>') % (question['label'], row[question['key']]['value']))
        parts.extend(self._checkin_section(self.employee_id))
        return Markup('').join(parts), round(sum(averages) / len(averages), 2) if averages else 0

    def _write_performance_rating(self):
        if any('sop_' in (r.questions_json or '') for r in self.feedback_request_ids):
            # Peer agreement must not overwrite a different five-point performance scale.
            return False
        return super()._write_performance_rating()

    def verdict_preview(self, verdict, extension_months=None):
        result = super().verdict_preview(verdict, extension_months)
        if self.kind == 'probation':
            result['label'] = _('Submit recommendation')
            result['lines'] = [
                _('Your assessment and proposed outcome go to the HR lead for review.'),
                _('Leadership and regional roles also require the configured CEO reviewer.'),
                _('Employment status and the outcome letter change only after all required reviews.'),
            ]
        return result

    def action_verdict(self, verdict, strengths=None, improvements=None, extension_months=None):
        self.ensure_one()
        if self.kind != 'probation':
            return super().action_verdict(verdict, strengths, improvements, extension_months)
        self._require_manager()
        if self.state == 'closed' or self.pb_gate in ('hr', 'ceo', 'approved'):
            raise UserError(_('This evaluation is already submitted or completed.'))
        if verdict not in ('pass', 'extend', 'fail'):
            raise UserError(_('Choose Confirm, Extend or Not passed.'))
        if not self.one_on_one_checkin_id or self.one_on_one_checkin_id.state != 'done':
            raise UserError(_('Record the manager 1:1 before submitting the recommendation.'))
        if not all(self[name] for name in ('pb_manager_quality', 'pb_manager_culture', 'pb_manager_adaptability', 'pb_manager_initiative')):
            raise UserError(_('Complete the four manager ratings using the expectations scale.'))
        if self.pb_leadership and not self.pb_manager_leadership:
            raise UserError(_('Add the leadership rating for this role.'))
        if not strengths or not improvements:
            raise UserError(_('Record strengths and areas for improvement.'))
        if verdict == 'extend' and not self.pb_improvement_plan:
            raise UserError(_('Add a one-month improvement plan before proposing an extension.'))
        if verdict == 'pass':
            self._check_training_gate()
        proposal = dict(verdict=verdict, strengths=strengths, improvements=improvements,
                        extension_months=extension_months)
        self.sudo().write({'pb_gate': 'hr', 'pb_proposed': proposal, 'strengths': strengths,
                           'improvements': improvements, 'pb_review_note': False, 'policy_id': (self.policy_id or self.env['pb.probation.policy'].policy_for(self.employee_id)).id})
        self._notify_journey_reviewer()
        self.message_post(body=_('Manager recommendation submitted for HR lead review. No outcome has been communicated.'))
        return {'pending': True, 'note': _('Submitted to HR. The outcome will be recorded after the required reviews.')}

    def action_pb_approve(self):
        self.action_pb_review('approve')
        return True

    def _notify_journey_reviewer(self):
        self.ensure_one()
        policy = self.policy_id or self.env['pb.probation.policy'].policy_for(self.employee_id)
        reviewer = policy.hr_reviewer_id if self.pb_gate == 'hr' else policy.ceo_reviewer_id
        if reviewer:
            self.sudo().activity_schedule('mail.mail_activity_data_todo', user_id=reviewer.id,
                summary=_('Review probation recommendation'), date_deadline=fields.Date.context_today(self))

    def action_pb_review(self, decision, note=None):
        self.ensure_one()
        self.check_access('read')
        if self.kind != 'probation' or self.pb_gate not in ('hr', 'ceo'):
            raise UserError(_('There is no recommendation awaiting review.'))
        policy = self.policy_id or self.env['pb.probation.policy'].policy_for(self.employee_id)
        reviewer = policy.hr_reviewer_id if self.pb_gate == 'hr' else policy.ceo_reviewer_id
        if reviewer:
            if reviewer != self.env.user and not self.env.is_superuser():
                raise AccessError(_('This step is assigned to %s.', reviewer.name))
        elif self.pb_gate == 'ceo':
            raise UserError(_('Configure the CEO reviewer on the country probation policy.'))
        elif not self.env.user.has_group('hr.group_hr_manager') and not self.env.is_superuser():
            raise AccessError(_('The HR lead must review this recommendation.'))
        if decision == 'changes':
            if not (note or '').strip():
                raise UserError(_('Explain what needs to change.'))
            self.sudo().write({'pb_gate': 'rework', 'pb_review_note': note, 'pb_hr_by': False, 'pb_ceo_by': False})
            self.message_post(body=_('Changes requested: %s', note))
            return {'note': _('Returned to the manager. Resolve the feedback and submit again.')}
        if decision != 'approve':
            raise UserError(_('Choose Approve or Request changes.'))
        if self.pb_gate == 'hr':
            self.sudo().write({'pb_hr_by': self.env.uid, 'pb_review_note': note or False})
            if self.pb_leadership:
                self.sudo().write({'pb_gate': 'ceo'})
                self._notify_journey_reviewer()
                self.message_post(body=_('HR review complete. Awaiting CEO review.'))
                return {'note': _('Sent for CEO review.')}
        else:
            self.sudo().write({'pb_ceo_by': self.env.uid})
        proposal = dict(self.pb_proposed or {})
        if proposal.get('verdict') == 'extend':
            self.sudo().write({'pb_improvement_due': fields.Date.add(fields.Date.context_today(self), months=1)})
        # Only this private continuation bypasses the earlier proposal engine;
        # an RPC context flag cannot bypass the HR/CEO gates above.
        result = super(ReviewJourney, self.sudo().with_context(**{VERDICT_WRITE: True})).action_verdict(**proposal)
        self.sudo().write({'pb_gate': 'approved'})
        self.message_post(body=_('Required reviews completed. The approved outcome has been recorded.'))
        return {'note': _('Outcome approved and recorded.'), 'outcome': result}


class SopFeedback(models.Model):
    _inherit = 'pb.feedback.request'

    def submit_answers(self, answers):
        self.ensure_one()
        if self.probation_review_id and 'sop_' in (self.questions_json or ''):
            for question in SOP_QUESTIONS:
                value = str(answers.get(question['key'], {}).get('value') or '').strip()
                if question['key'] != 'sop_comments' and not value:
                    raise UserError(_('Please answer: %s', question['label']))
                if question['type'] == 'choice' and value not in question['options']:
                    raise UserError(_('Choose one of the listed answers for: %s', question['label']))
        return super().submit_answers(answers)


class ProbationJourney(models.AbstractModel):
    _inherit = 'pb.probation'

    def _row(self, emp, today=None):
        row = super()._row(emp, today)
        review = self.env['pb.probation.review'].for_employee(emp)
        row['review_gate'] = review.pb_gate if review else 'manager'
        return row

    @api.model
    def get_person(self, employee_id):
        result = super().get_person(employee_id)
        review = self.env['pb.probation.review'].for_employee(self.env['hr.employee'].browse(int(employee_id)))
        if review:
            result['sop'] = {'gate': review.pb_gate, 'note': review.pb_review_note or '',
                'leadership': review.pb_leadership, 'proposal': review.pb_proposed or {},
                'ratings': {key: review['pb_manager_' + key] or '' for key in ('quality','culture','adaptability','initiative','leadership')},
                'improvement_plan': review.pb_improvement_plan or '',
                'peer_min': review._settings()['peer_min'], 'peer_max': review._settings()['peer_max'],
                'scale': 4 if any('sop_' in (r.questions_json or '') for r in review.feedback_request_ids) else 5}
        return result

    @api.model
    def save_manager_evaluation(self, review_id, ratings, leadership=False, improvement_plan=''):
        self._require_write()
        review = self.env['pb.probation.review'].browse(int(review_id)).exists()
        review._require_manager()
        review.write({'pb_manager_' + key: ratings.get(key) or False for key in ('quality','culture','adaptability','initiative','leadership')})
        review.write({'pb_leadership': bool(leadership), 'pb_improvement_plan': str(improvement_plan or '')})
        return True

    @api.model
    def review_recommendation(self, review_id, decision, note=None):
        review = self.env['pb.probation.review'].browse(int(review_id)).exists()
        return review.action_pb_review(decision, note)
