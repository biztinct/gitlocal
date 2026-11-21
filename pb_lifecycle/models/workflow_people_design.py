"""WF2 P4a — what a designer sees about teams, links and reminders.

Design-time checks by code (ledger G2), the team list for the owner picker,
plain words for a team owner, and the Review lines that say who gets a link
and what cannot be done by link. Nothing here runs a workflow.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import workflow_definition as D
from .workflow_people import LINK_UNSUPPORTED, late_numbers, mask_email


class WorkflowPeopleDesign(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _teams(self, company):
        """Teams (Approvals' "a group of people" responsibilities) with how
        many staff are on each here."""
        roles = self.env['biz.approval.role'].sudo().search([('is_pool', '=', True)])
        return [{'id': r.id, 'name': r.name, 'members': len(self._team_members(r, company))} for r in roles]

    def _new_step_issues(self, w, d, n):
        out = list(super()._new_step_issues(w, d, n))
        owner = n.get('owner') or {}
        if owner.get('kind') != 'team':
            return out
        if n['type'] == 'notify':
            return out + [('team_notice', _('A notice goes to one person. Choose someone, not a team.'))]
        role = self.env['biz.approval.role'].sudo().browse(int(owner.get('id') or 0)).exists()
        if not role or not role.is_pool:
            return out + [('bad_team', _('Choose one of the teams from Approvals › Who approves.'))]
        if not self._team_members(role, w.company_id):
            out.append(('team_empty', _('Nobody is on the team “%s” here yet. Add people to it in Approvals › Who approves.',
                                        role.name)))
        return out

    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        result['teams'] = self._teams(self._company())
        remind, escalate = late_numbers()
        result['late_words'] = (
            _('Reminded a day after it is due, then their manager is told a day later — the same way approvals work.')
            if (remind, escalate) == (1, 2) else
            _('Reminded %(r)s days after it is due, then their manager is told %(e)s days after it is due — '
              'the same way approvals work.', r=remind, e=escalate))
        return result

    def _owner_words(self, model, owner):
        owner = owner or {}
        if owner.get('kind') == 'team':
            role = self.env['biz.approval.role'].sudo().browse(int(owner.get('id') or 0)).exists()
            return _('The team %s', role.name) if role else _('A team')
        return super()._owner_words(model, owner)

    def _check_owner(self, model, company, owner):
        if isinstance(owner, dict) and owner.get('kind') == 'team':
            raise UserError(_('Choose one person to move records into this stage, not a team.'))
        return super()._check_owner(model, company, owner)

    def _people_notes(self, w, d):
        """Review lines (never blocking): who gets a link, and what a link
        page cannot do."""
        notes = []
        for n in d.get('nodes', []):
            if n.get('type') not in D.PEOPLE:
                continue
            kind = (n.get('owner') or {}).get('kind')
            if kind in ('subject', 'manager'):
                who = self._owner_words(w.source_model or '', n.get('owner'))
                notes.append({'id': n['id'], 'tone': 'info', 'code': 'by_link',
                              'text': _('If %(who)s has no login, “%(step)s” goes to them by email link '
                                        '(people with an employee-home login do it there).',
                                        who=self._lower_words(who), step=n.get('title', ''))})
                bad = [f.get('label', '') for f in (n.get('form') or {}).get('fields', [])
                       if f.get('type') in LINK_UNSUPPORTED]
                if bad:
                    notes.append({'id': n['id'], 'tone': 'warn', 'code': 'link_cannot',
                                  'text': _('By link, “%(step)s” cannot take %(fields)s: files and record choices '
                                            'need the app. The page asks them to send these another way.',
                                            step=n.get('title', ''), fields=', '.join('“%s”' % b for b in bad))})
            if kind == 'team':
                notes.append({'id': n['id'], 'tone': 'info', 'code': 'team',
                              'text': _('“%(step)s” goes to %(who)s: anyone on it can take it in Approvals.',
                                        step=n.get('title', ''),
                                        who=self._lower_words(self._owner_words(w.source_model or '', n.get('owner'))))})
        return notes

    @staticmethod
    def _lower_words(text):
        text = str(text or '')
        first = text.split(' ', 1)[0]
        return first.lower() + text[len(first):] if first in ('The', 'Their', 'A', 'An') else text

    @api.model
    def stage_remove_area(self, model, stage_key):
        """Remove a stage the area added (D17, Hiring), through the area's
        own door and permission. Studio never deletes such a stage itself."""
        self._design()
        if model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This record type is not available.'))
        contract = self._contract(model)
        obj = self.env[model]
        if not contract.get('removes_stages') or not hasattr(obj, '_workflow_remove_stage'):
            raise UserError(_('%s stages are removed in its own set-up.', contract['area'] or contract['label']))
        stage = next((s for s in contract['stages'] if str(s['key']) == str(stage_key)), None)
        if not stage or not stage.get('id') or not stage.get('removable'):
            raise UserError(_('Only a stage your company added can be removed.'))
        made = obj._workflow_remove_stage(stage['id'])
        catalogue = self.stage_catalogue(model)
        catalogue['removed'] = {'note': made.get('note', '')}
        return catalogue

    @api.model
    def progress(self, run_id):
        """Progress also says who covers, which team has it, and where a
        link went (masked). Never the link key."""
        result = super().progress(run_id)
        steps = {s.id: s for s in self.env['pb.workflow.step'].sudo().browse([r['id'] for r in result['steps']])}
        can_resend = self._can_view_progress()
        for row in result['steps']:
            s = steps.get(row['id'])
            if not s or s.kind not in D.PEOPLE:
                continue
            if s.covered_user_id:
                row['covering'] = _('Covering for %s while they are away', s.covered_user_id.name)
            role = self._team_role(s)
            if role and s.state == 'waiting':
                row['team'] = (_('Team %(team)s · taken by %(who)s', team=role.name, who=s.assignee_id.name)
                               if s.assignee_id else _('Team %s · nobody has taken it yet', role.name))
                if not s.assignee_id:
                    row['owner'] = _('The team %s', role.name)
            if s.sudo().link_email:
                masked = s._link_words()
                if s.state == 'waiting':
                    row['owner'] = s.link_name or row.get('owner') or ''
                    row['reason'] = _('Waiting for %(who)s to answer %(link)s.',
                                      who=s.link_name or _('them'), link=masked)
                    row['link'] = {'text': _('Link sent to %s', mask_email(s.sudo().link_email)), 'until': fields.Datetime.to_string(s.link_expires_at)[:10]
                                   if s.link_expires_at else '',
                                   'opened': bool(s.link_opened_at), 'can_resend': can_resend}
                elif s.state == 'done' and s.sudo().link_done_ip:
                    row['owner'] = s.link_name or ''
                    row['done_by'] = _('Done by %s', masked)
            if s.due_at and not row.get('due'):
                row['due'] = fields.Datetime.to_string(s.due_at)[:10]
            if s.state == 'waiting' and s.assignee_id.share:
                row['reason'] = _('Waiting for %s on their employee home', s.assignee_id.name)
        return result

    @api.model
    def review(self, workflow_id):
        result = super().review(workflow_id)
        w = self._workflow(workflow_id)
        result['people_notes'] = self._people_notes(w, w.draft or {})
        return result
