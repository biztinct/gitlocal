"""What Hiring tells Workflow Studio about a candidate (WF2 P2).

Read-only declarations plus two doors that already exist: the stages a
candidate can be in (rows the talent lead names and orders, scoped to the
candidate's role), what Hiring already does at each stage (its automation
rules and switched-on built-ins), who a candidate's work belongs to, and two
operations Studio may ask for — moving a candidate (through the board's own
`journey_stage` verb, so every safeguard and every "enters a stage" rule
runs exactly as when a recruiter drags the card) and renaming a shared stage
(through `stage_rename`). Nothing here changes how Hiring behaves. Studio
reads this through a duck-typed hook.
"""
from odoo import _, api, models
from odoo.exceptions import UserError

from .automation_p8 import BUILTINS, _days_words
from .hiring_common import P_LEAD_LATE_DAYS, P_WEEK_BEFORE_DAYS, flag, number
from .stage_add import OWN, retired_keys

#: Stages a workflow may not move a candidate into. Joined comes from
#: confirming the person started, on their offer.
NOT_BY_WORKFLOW = ('joined', 'offer_accepted', 'offer_rejected')
SETTINGS = {'action': 'pb_hiring.action_pb_hiring_hub', 'lens': 'setup'}
RULE_KIND = {'send_email': 'message', 'todo': 'todo', 'move_stage': 'change', 'tag': 'change'}
RULE_AUDIENCE = {'candidate': 'candidate', 'recruiter': 'team', 'hiring_manager': 'manager',
                 'talent_lead': 'team', 'custom': 'other'}
#: (kind, audience) of each built-in, as its own sentence describes it.
BUILTIN_SHAPE = {
    'received': ('message', 'candidate'), 'invite': ('message', 'candidate'),
    'reminders': ('reminder', 'candidate'), 'opinions': ('reminder', 'team'),
    'papers_in': ('todo', 'team'), 'papers_remind': ('reminder', 'candidate'),
    'check': ('todo', 'team'), 'offer': ('message', 'candidate'),
    'finalists': ('change', 'candidate'), 'week_before': ('message', 'team'),
    'joined': ('message', 'manager'), 'assigned': ('message', 'team'),
    'referral': ('message', 'team'), 'announce': ('message', 'other'),
    'shared': ('message', 'other'), 'agency': ('todo', 'team'),
}


class HiringApplicantWorkflowContract(models.Model):
    _inherit = 'hr.applicant'

    @api.model
    def _workflow_capabilities(self):
        area = _('Hiring')
        options = [{'key': s['key'], 'name': s['name']} for s in self._workflow_stage_options()
                   if s['key'] not in NOT_BY_WORKFLOW]
        return {
            'label': _('Candidate'),
            'area': area,
            'stage_field': 'stage_id',
            'actions': {'hiring.stage': {
                'label': _('Move to a Hiring stage'), 'owner': area,
                'params': [{'key': 'stage_key', 'label': _('Existing stage'), 'type': 'choice',
                            'options': options, 'code': 'bad_hiring_stage',
                            'error': _('Choose a permitted Hiring stage. Joined stays with its own action.')}],
            }},
            'owners': [{'key': 'hiring', 'label': _('Stages, candidate messages and automations'),
                        'owner': _('Hiring settings'), 'action': 'pb_hiring.action_pb_hiring_hub',
                        'lens': 'setup'}],
            'effects': [
                {'stage': 'joined', 'kind': 'record', 'audience': 'team', 'owner': area,
                 'settings': SETTINGS,
                 'text': _('Confirming the person started creates their employee record, '
                           'contract and login, and opens their joining checklist.')},
                {'stage': 'cv_reject', 'kind': 'message', 'audience': 'candidate', 'owner': area,
                 'settings': SETTINGS,
                 'text': _('Whoever moves a candidate here can choose to send the '
                           '“not this time” email.')},
                {'stage': 'interview_reject', 'kind': 'message', 'audience': 'candidate',
                 'owner': area, 'settings': SETTINGS,
                 'text': _('Whoever moves a candidate here can choose to send the '
                           '“not this time” email.')},
            ],
            'screen': 'pb_hiring_hub',
            # Hiring keeps its own stage rows (D10): Workflow Studio offers
            # headings on candidates and sends people to Hiring set-up for
            # a new stage; it never keeps a stage layer of its own here.
            'own_stage_rows': True,
            # WF2 P3b (D10): a new candidate stage is a real Hiring stage,
            # added through Hiring's own `stage_add` door.
            'adds_stages': True,
            # WF2 P4a (D14): the one thing a workflow's "Update the record"
            # step may do to a candidate is add one of Hiring's tags, through
            # the same door Hiring's own "tag the candidate" automation uses.
            # The evaluation stars are no longer offered (Hiring's screens do
            # not show them).
            'safe_fields': [
                {'key': 'tag', 'label': _('Add a tag'), 'type': 'choice',
                 'done_words': _('Added the tag “%s”.'), 'would_words': _('Would add the tag “%s”'),
                 'card_words': _('Adds the tag “%s”'),
                 'options': [{'key': t.id, 'label': t.name}
                             for t in self.env['hr.applicant.category'].sudo().search([], order='name', limit=300)]},
            ],
            'retired_fields': ['priority'],
            # WF2 P4a (D17): a company-added stage can be removed, by Hiring;
            # a workflow section that waited for one becomes a heading.
            'removes_stages': True,
            'removed_keys': sorted(retired_keys(self.env)),
            # WF2 P4b (D18): the candidate takes part in a workflow by the
            # private email link — never a login, never a user.
            'participants': [{'key': 'candidate', 'label': _('The candidate'), 'audience': 'candidate'}],
        }

    def _workflow_participant(self, key):
        """Name and email of someone this candidate record names (D18).
        Only "the candidate" today; nobody else is ever returned."""
        self.ensure_one()
        if key != 'candidate':
            return {}
        app = self.sudo()
        return {'name': app.partner_name or app.display_name or '', 'email': (app.email_from or '').strip()}

    def _workflow_update(self, key, value):
        """Studio's "Update the record" step: one declared value only. A tag
        is added through Hiring's own door (`_pb_tag_add`), as its "tag the
        candidate" automation does; nothing else is written."""
        self.ensure_one()
        allowed = {f['key'] for f in self._workflow_capabilities().get('safe_fields', [])}
        if key not in allowed:
            raise UserError(_('Hiring has not opened this value to workflows.'))
        if key == 'tag':
            tag = self.env['hr.applicant.category'].sudo().browse(int(value or 0)).exists()
            if not tag:
                raise UserError(_('That tag is no longer in Hiring. Edit the step.'))
            self._pb_tag_add(tag)
            return True
        raise UserError(_('Hiring has not opened this value to workflows.'))

    def _pb_tag_add(self, tag):
        """Hiring's one door for adding a tag (its automations use it too).
        Returns False when the candidate already had it."""
        self.ensure_one()
        if tag in self.sudo().categ_ids:
            return False
        self.sudo().write({'categ_ids': [(4, tag.id)]})
        return True

    @api.model
    def _workflow_remove_stage(self, stage_id):
        """Remove a company-added candidate stage (D17), by Hiring itself:
        its own door and its own set-up permission."""
        return self.env['pb.hiring'].act('stage_remove', {'stage_id': stage_id})

    @api.model
    def _workflow_add_stage(self, name, after_stage_id):
        """A new candidate stage, made by Hiring itself (D10): the talent
        lead's own door, with Hiring's own write permission."""
        return self.env['pb.hiring'].act('stage_add', {'name': name, 'after_stage_id': after_stage_id})

    @api.model
    def _workflow_stage_options(self, record=None):
        """The Hiring stages that apply, in board order: shared rows,
        narrowed to the candidate's role when there is one."""
        Stage = self.env['hr.recruitment.stage'].sudo()
        domain = [('pb_key', '!=', False)]
        if 'company_id' in Stage._fields:
            domain += [('company_id', 'in', [False, self.env.company.id])]
        if record:
            domain += ['|', ('job_ids', '=', False), ('job_ids', 'in', record.sudo().job_id.ids)]
        stages = Stage.search(domain, order='sequence, id')
        current = record.sudo().stage_id if record else Stage
        if current and current.pb_key and current not in stages:
            stages |= current
        can_rename = self.env['pb.hiring']._can_write()
        rows = []
        for s in stages:
            if s.pb_key == 'joined':
                enters = _('Someone confirms the person started, from their offer')
            elif s.pb_key == 'screening':
                enters = _('Somebody applies, or a recruiter moves them here')
            else:
                enters = _('A recruiter moves the candidate here')
            rows.append({'key': s.pb_key, 'id': s.id, 'name': s.name or '', 'family': s.pb_family or 'open',
                         'exit': s.pb_family == 'closed', 'renamable': can_rename,
                         'removable': can_rename and s.pb_key in OWN,
                         'revision': str(s.write_date) if can_rename else None,
                         'meaning': s.pb_meaning or '', 'enters': enters})
        return rows

    @api.model
    def _workflow_effects(self, company):
        """Hiring's own automation that is switched on for this company."""
        effects = []
        rules = self.env['pb.hiring.automation.rule'].sudo().search([('company_id', '=', company.id)])
        for rule in rules:
            effects.append({
                'stage': rule.stage_id.pb_key if rule.event in ('stage_entered', 'stage_waiting') else None,
                'kind': RULE_KIND.get(rule.action, 'change'),
                'audience': RULE_AUDIENCE.get(rule.recipient or '', 'other'),
                'owner': _('Hiring automations'), 'settings': SETTINGS,
                'text': rule._sentence(), 'ref': 'hiring_rule:%s' % rule.id,
                # WF2 P4a: what the rule sets, so a workflow adding the same
                # tag is caught as a double-up (R2e).
                **({'sets': 'tag:%s' % rule.tag_id.id} if rule.action == 'tag' and rule.tag_id else {})})
        lead_days = number(self.env, P_LEAD_LATE_DAYS, 0)
        week = number(self.env, P_WEEK_BEFORE_DAYS, 7)
        for key, sentence, param, default, _email, _why in BUILTINS:
            if param and not flag(self.env, param, default):
                continue
            sentence = _(sentence)
            if '%(' in sentence:
                sentence = sentence % {
                    'lead': (_days_words(lead_days) + ' ' + _('late')) if lead_days else _('the feedback deadline'),
                    'days': _days_words(week).capitalize()}
            kind, audience = BUILTIN_SHAPE.get(key, ('message', 'other'))
            effects.append({'stage': None, 'kind': kind, 'audience': audience,
                            'owner': _('Hiring automations'), 'settings': SETTINGS,
                            'text': sentence, 'ref': 'hiring_builtin:%s' % key})
        return effects

    def _workflow_subject(self):
        """A candidate is nobody's employee yet: their work belongs to the
        recruiter (the role's, else the candidate's), and the hiring manager
        is the role's own (as Hiring's rules address them)."""
        self.ensure_one()
        app = self.sudo()
        req = app.pb_requisition_id
        manager = self.env['res.users']
        if req:
            targets = req._pb_manager_targets()
            manager = targets[0][0] if targets else manager
        return {'employee': self.env['hr.employee'],
                'user': (req.recruiter_id if req else self.env['res.users']) or app.user_id,
                'manager_user': manager}

    def _workflow_execute(self, key, params):
        """Studio's "Move to a Hiring stage" step: the board's own door."""
        self.ensure_one()
        if key != 'hiring.stage':
            raise UserError(_('This business action is no longer available.'))
        target = (params or {}).get('stage_key')
        if target in NOT_BY_WORKFLOW:
            raise UserError(_('Choose a permitted Hiring stage. Joined stays with its own action.'))
        if self.stage_id.pb_key == target:
            return {'already_done': True}
        result = self.env['pb.hiring'].act('journey_stage', {'applicant_ids': self.ids, 'key': target})
        if not result.get('moved'):
            raise UserError(result.get('warning') or result.get('note') or _('Hiring did not move this candidate.'))
        return result

    @api.model
    def _workflow_rename_stage(self, stage_id, name, revision):
        """Rename a shared stage, as the talent lead would in Hiring set-up.

        The same checks the Studio dialog made before WF2 P2: Hiring's own
        write permission, a row lock, and a stale-copy refusal."""
        Hiring = self.env['pb.hiring']
        Hiring._require_write()
        stage = self.env['hr.recruitment.stage'].browse(int(stage_id or 0)).exists()
        if not stage:
            raise UserError(_('This stage no longer exists.'))
        stage.check_access('read')
        self.env.cr.execute('SELECT id FROM hr_recruitment_stage WHERE id=%s FOR UPDATE', [stage.id])
        stage.invalidate_recordset()
        if str(stage.write_date) != revision:
            raise UserError(_('This stage changed. Reopen Stages before editing it.'))
        return Hiring.act('stage_rename', {'stage_id': stage.id, 'name': str(name or '')})
