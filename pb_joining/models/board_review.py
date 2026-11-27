from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_datetime

from odoo.addons.pb_new_hire.models.studio_docs import SECRET_FIELDS
from odoo.addons.pb_hiring.models.hiring_common import ALL_GROUPS, flag

from .items import masked

STEPS = ('invited', 'filling', 'to_check', 'added')


class JoiningReview(models.Model):
    _inherit = 'pb.joining'

    review_revision = fields.Integer(copy=False)

    def _step_names(self):
        return dict(self._fields['state']._description_selection(self.env))

    def _can_add(self):
        rows = self.item_ids.filtered('available')
        return (self.state == 'to_check' and not self.proposal_id
                and not any(r.state in ('saved', 'returned') or (r.state == 'empty' and r.need != 'optional') for r in rows)
                and self._paper_signing_done())

    def _remaining_labels(self):
        states = self._section_states()
        return [title for key, title, icon, hint in self._section_info()
                if states.get(key) in ('empty', 'returned')]

    def _reminder(self):
        names = ', '.join(self._remaining_labels()) or _('Your first day')
        sent = self._mail('joining_reminder', {'sections': names})
        message = _('Hello %(name)s, please finish %(sections)s before %(date)s. %(url)s',
                    name=self._first(), sections=names, date=self._day_label(), url=self._url())
        self.write({'reminded_at': fields.Datetime.now(), 'remind_count': self.remind_count + 1})
        return {'sent': bool(sent), 'message': '' if sent else message}


class JoiningReviewBoard(models.AbstractModel):
    _inherit = 'pb.joining.board'

    def _broad_reader(self):
        return (self._can_manage() or any(self.env.user.has_group(g) for g in ALL_GROUPS)
                or self.env['pb.onboarding']._can_read()
                or self.env.user.has_group('pb_new_hire.group_joiners_board'))

    @api.model
    def can_open(self):
        return bool(self.env.user._is_internal() and (self._broad_reader() or
                    self.env['pb.joining'].sudo().search_count(self._base(), limit=1)))

    def _base(self):
        domain = super()._base() + [('state', '!=', 'cancelled')]
        if not self._broad_reader():
            covered = self.env['pb.hiring']._covered_uids()
            domain.extend(['|', ('offer_id.requisition_id.recruiter_id', 'in', list(covered)),
                           ('manager_id.user_id', '=', self.env.uid)])
        return domain

    @api.model
    def pbf_layout(self):
        if not self.can_open():
            return {'refused': _('Joining is looked after by the hiring team')}
        return super().pbf_layout()

    def _can_link(self, j):
        if self._can_manage():
            return True
        req = j.offer_id.requisition_id
        return bool(req and self.env['pb.hiring']._can_recruit(req) and (
            req.recruiter_id.id == self.env.uid or req.recruiter_id.id in self.env['pb.hiring']._covered_uids()))

    def _pbf_model(self):
        return 'pb.joining'

    def _pbf_screen(self):
        return 'joining'

    def _pbf_records(self):
        if not self.can_open():
            raise AccessError(_('You cannot open this joining.'))
        return self.env['pb.joining'].sudo()

    def _pbf_base_domain(self):
        return self._base()

    def _pbf_search_fields(self):
        return ['name', 'job_title', 'department_id.name']

    def _pbf_sorts(self):
        return [{'key': k, 'label': label, 'order': order} for k, label, order in [
            ('first', _('First day soonest'), 'first_day, id'),
            ('most', _('Most complete'), 'progress desc, id'),
            ('least', _('Least complete'), 'progress, id'), ('new', _('Newest'), 'id desc')]]

    def _pbf_spec(self):
        today = fields.Date.context_today(self)
        week = today - timedelta(days=today.weekday())
        def choice(key, label, icon, options):
            return {'key': key, 'label': label, 'icon': icon, 'type': 'choice', 'group': 'people', 'pinned': True,
                    'options': [{'value': v, 'label': l, 'domain': d} for v, l, d in options]}
        j = self.env['pb.joining']
        countries = self.env['res.country'].sudo().search([('code', 'in', self._pbf_records().search(
            self._base()).mapped('payroll_country'))]) if self.can_open() else self.env['res.country']
        return [
            choice('step', _('Step'), 'layers', [(k, j._step_names()[k], [('state', '=', k)]) for k in STEPS]),
            choice('country', _('Country of work'), 'globe', [(c.code, c.name, [('payroll_country', '=', c.code)]) for c in countries]),
            {'key': 'team', 'label': _('Team'), 'icon': 'users', 'type': 'many2one', 'group': 'people', 'path': 'department_id'},
            choice('day', _('First day'), 'calendar', [
                ('week', _('This week'), [('first_day', '>=', week), ('first_day', '<', week+timedelta(days=7))]),
                ('two', _('Next 2 weeks'), [('first_day', '>=', today), ('first_day', '<', today+timedelta(days=14))]),
                ('month', _('This month'), [('first_day', '>=', fields.Date.start_of(today,'month')), ('first_day', '<=', fields.Date.end_of(today,'month'))])]),
            choice('flags', _('Flags'), 'flag', [
                ('risk', _('At risk'), [('at_risk', '=', True)]),
                ('pass', _('To pass on'), [('link_mode', '=', 'pass_on'), ('link_copied_at', '=', False)]),
                ('back', _('Sent back'), [('sent_back_count','>',0)]),
                ('bank', _('Bank still to come'), [('bank_later','=',True)])]),
            choice('origin', _('Where from'), 'briefcase', [('hiring', _('Hiring'), [('origin','=','hiring')]),
                                                          ('invited', _('Invited'), [('origin','=','invited')])])]

    @api.model
    def get_board(self):
        if not self.can_open():
            return {'allowed': False}
        records = self._pbf_records()
        base = self._base()
        today = fields.Date.context_today(self)
        def count(*criteria):
            return records.search_count(base + list(criteria))
        steps = {k: count(('state', '=', k)) for k in STEPS}
        return {'allowed': True, 'can_manage': self._can_manage(), 'steps': steps, 'mail_on': self.env['pb.new.hire.invite']._mail_on(),
                'kpis': {'joining': count(('state','in',STEPS[:3]), ('first_day','<=',today+timedelta(days=30))),
                         'to_check': steps['to_check'], 'at_risk': count(('at_risk','=',True)),
                         'pass_on': count(('link_mode','=','pass_on'), ('link_copied_at','=',False)),
                         'started_week': count(('opened_at','>=',today-timedelta(days=today.weekday())))}}

    def _card(self, j):
        days = (j.first_day-j._today()).days
        chips = []
        def chip(tone, icon, text):
            chips.append({'tone': tone, 'icon': icon, 'text': text})
        if j.at_risk:
            chip('rose','alertTriangle',_('At risk: %(missing)s, %(days)s days left', missing=j.risk_reason, days=days))
        if j.link_mode == 'pass_on' and not j.link_copied_at:
            chip('amber','send',_('Link to pass on'))
        if not j.opened_at:
            chip('amber','clock',_('Not opened yet'))
        if j.proposal_id and j.state != 'added':
            chip('amber','clock',_('Waiting for approval of the hire'))
        elif j.state == 'to_check':
            chip('indigo','eye',_('Waiting for your check'))
        if j.sent_back_count:
            chip('amber','arrowLeft',_('Sent back · %s', j.sent_back_count))
        if j.bank_later:
            chip('amber','landmark',_('Bank account still to come'))
        if j.state == 'added':
            chip('green','check',_('Employee record made'))
        prejoin = j.offer_id.prejoin_ids.filtered(lambda r: r.state != 'cancelled')
        country = self.env['res.country'].sudo().search([('code','=',j.payroll_country)],limit=1)
        return {'id': j.id, 'name': j.name, 'initials': ''.join(s[0] for s in j.name.split()[:2]),
                'job': j.job_title, 'country': country.name or j.payroll_country, 'country_code': j.payroll_country,
                'first_day': str(j.first_day), 'first_day_label': j._day_label('EEE d MMM'), 'days': days,
                'step': STEPS.index(j.state)+1, 'state': j.state, 'step_label': j._step_names()[j.state],
                'progress': j.progress, 'chips': chips[:3], 'origin': j.origin,
                'prejoin': {'done': len(prejoin.filtered(lambda r: r.state in ('done','skipped'))), 'total': len(prejoin)}}

    @api.model
    def get_page(self, filters=None, search='', sort=None, offset=0, limit=30):
        if not self.can_open():
            return {'rows': [], 'total': 0, 'offset': 0}
        offset, limit = max(0,int(offset or 0)), min(100,max(1,int(limit or 30)))
        domain = self.pbf_domain(filters or {}, search)
        records = self._pbf_records()
        return {'rows': [self._card(j) for j in records.search(domain, order=self.pbf_order(sort) or 'first_day,id', offset=offset, limit=limit)],
                'offset': offset, 'total': records.search_count(domain)}

    def _item_row(self, j, r, spec, manage):
        row = {'key': r.key, 'label': spec['label'], 'state': r.state}
        if not manage:
            return row
        vals = r.values or {}
        inputs = spec['fields']
        if r.key == 'bank' and vals:
            inputs = spec['bank']['fields'].get(vals.get('bank_format'), inputs)
        shown = []
        for box in inputs:
            key = box['name']
            value = vals.get(key)
            if not value:
                continue
            hidden = key in SECRET_FIELDS
            options = {o['value']:o['label'] for o in box['options']}
            shown.append({'key':key, 'label':box['label'], 'value': masked(value) if hidden else options.get(value,value), 'masked':hidden})
        row.update(icon=spec['icon'], fields=shown, files=[self._file_row(j,a) for a in r.attachment_ids],
                   source=_("Read from Hiring's paper") if r.from_hiring else (_('From Hiring') if r.key=='personal' and j.offer_id else ''),
                   note=r.return_note or '', none=bool(r.none_fields), decided_by=r.decided_by_id.name,
                   decided_on=str(r.decided_on or ''))
        return row

    def _file_row(self, j, a):
        return {'id':a.id, 'name':a.name, 'mime':a.mimetype, 'url':f'/pb_joining/file/{j.id}/{a.id}'}

    def _sign_rows(self, j, manage):
        return []

    @api.model
    def get_one(self, joining_id):
        j = self._one(joining_id)
        manage = self._can_manage()
        specs = {s['key']: s for s in j._catalogue()}
        rows = [self._item_row(j,r,specs[r.key],manage) for r in j.item_ids if r.available and r.key in specs]
        def dt(value):
            return format_datetime(self.env, value) if value else ''
        return dict(self._card(j), revision=j.review_revision, can_manage=manage, can_link=self._can_link(j),
                    link={'mode':j.link_mode,'masked':j._masked_email(),'sent_at':dt(j.link_sent_at),'copied_at':dt(j.link_copied_at),
                          'opened_at':dt(j.opened_at),'last_seen_at':dt(j.last_seen_at),'remind_count':j.remind_count,
                          'locked':bool(j.code_locked_until and j.code_locked_until > fields.Datetime.now())},
                    day={k:j[k] or '' for k in ('day_time','day_place','day_ask_for','day_bring','manager_note')} if manage else {},
                    items=rows, signs=self._sign_rows(j, manage),
                    foot={'can_add':manage and j._can_add(), 'waiting_for_person':j.sent_back_count,
                          'approval_waiting':bool(j.proposal_id and j.state!='added')})

    def _item(self, j, key):
        rows = j.item_ids.filtered(lambda r: r.key == key and r.available)
        if len(rows)!=1:
            raise UserError(_('This item is no longer available.'))
        return rows

    @api.model
    def reveal(self, joining_id, key, field):
        self._check_manage()
        j = self._one(joining_id)
        row = self._item(j, key)
        if field not in SECRET_FIELDS or field not in (row.values or {}):
            raise UserError(_('This number is not available.'))
        j.message_post(body=_('%(who)s viewed a number in %(item)s.', who=self.env.user.name, item=key))
        return {'value': row.values[field]}

    def _files(self,j):
        return j.item_ids.filtered('available').attachment_ids

    def _file(self, joining_id, attachment_id):
        self._check_manage()
        j = self._one(joining_id)
        a = self._files(j).filtered(lambda a: a.id == attachment_id)
        if not a:
            raise AccessError(_('You cannot open this file.'))
        return a

    def _link_action(self, joining_id, action):
        j = self._one(joining_id)
        if not self._can_link(j):
            raise AccessError(_('Ask the recruiter handling this offer or HR to pass on the link.'))
        j._lock()
        if j._for_token(j.token)[1] != 'ok':
            raise UserError(_('This link is not active'))
        now = fields.Datetime.now()
        actions = dict(j.actions_at or {})
        if actions.get(action) and fields.Datetime.to_datetime(actions[action]) > now-timedelta(minutes=1):
            raise UserError(_('Wait a minute before trying again.'))
        actions[action] = fields.Datetime.to_string(now)
        j.actions_at = actions
        return j

    @api.model
    def copy_link(self, joining_id):
        j = self._link_action(joining_id, 'copy')
        j.link_copied_at = fields.Datetime.now()
        return {'url':j._url()}

    @api.model
    def show_code(self, joining_id):
        j = self._link_action(joining_id, 'code')
        out = j._issue(by_hr=True)
        if out['status'] == 'locked':
            raise UserError(_('Too many tries. Wait 15 minutes, then ask for a new code.'))
        return out

    @api.model
    def send_again(self, joining_id):
        j = self._link_action(joining_id, 'send')
        j._send_link()
        return {'sent':j.link_mode=='email'}

    @api.model
    def remind_now(self, joining_id):
        j = self._link_action(joining_id, 'remind')
        if j.state not in STEPS[:2]:
            raise UserError(_('This person has already sent their details.'))
        return j._reminder()

    def _review(self, joining_id, action, key=None, note=None, revision=None):
        self._check_manage()
        j = self._one(joining_id)
        j._lock()
        if revision is not None and revision != j.review_revision:
            return dict(self.get_one(j.id), message=_('Updated by %(name)s just now.', name=j.write_uid.name))
        if j.proposal_id or j.state != 'to_check' and not (action=='back' and j.state=='filling' and j.submitted_at):
            raise UserError(_('This person is not waiting for your check.'))
        rows = j.item_ids.filtered(lambda r:r.available and r.state=='saved') if action=='all' else self._item(j,key)
        if action == 'back':
            note = str(note or '').strip()
            if not note or len(note)>200:
                raise UserError(_('Write what needs fixing in 200 characters or fewer.'))
            if rows.state not in ('accepted','saved'):
                raise UserError(_('Choose an item the person sent.'))
            rows.write({'state':'returned','return_note':note,'reopened':True})
            j.state = 'filling'
            label = next(s['label'] for s in j._catalogue() if s['key'] == key)
            if not j._mail('joining_back', {'notes': f'{label} — {note}'}):
                j.activity_schedule('mail.mail_activity_data_todo', user_id=j._contact().id,
                                    summary=_('Pass on the request to fix details to %(name)s', name=j.name))
        elif action == 'undo' and rows.state=='accepted':
            rows.write({'state':'saved','decided_on':False,'decided_by_id':False})
        elif action in ('all','accept'):
            for row in rows:
                if row.state not in ('saved','accepted'):
                    raise UserError(_('Choose an item the person sent.'))
                row.write({'state':'accepted','decided_on':fields.Datetime.now(),'decided_by_id':self.env.uid})
        j.review_revision += 1
        return self.get_one(j.id)

    @api.model
    def accept(self, joining_id, key, revision=None):
        return self._review(joining_id,'accept',key,revision=revision)

    @api.model
    def undo(self, joining_id, key, revision=None):
        return self._review(joining_id,'undo',key,revision=revision)

    @api.model
    def send_back(self, joining_id, key, note, revision=None):
        return self._review(joining_id,'back',key,note,revision)

    @api.model
    def accept_all(self, joining_id, revision=None):
        return self._review(joining_id,'all',revision=revision)

    def _mutable(self, joining_id):
        self._check_manage()
        j = self._one(joining_id)
        j._lock()
        if j.state=='added' or j.proposal_id:
            raise UserError(_('This hire has already gone to Add employee.'))
        return j

    @api.model
    def set_day(self, joining_id, vals):
        j = self._mutable(joining_id)
        j.write({k:str(vals[k] or '').strip()[:500] for k in ('day_time','day_place','day_ask_for','day_bring','manager_note') if k in vals})
        return self.get_one(j.id)

    @api.model
    def change_first_day(self, joining_id, date, reason):
        j = self._mutable(joining_id)
        if j.offer_id:
            j.offer_id.action_change_join_date(date, reason, by_name=self.env.user.name)
        else:
            j.first_day = fields.Date.to_date(date)
        return self.get_one(j.id)

    @api.model
    def not_joining(self, joining_id, reason):
        j = self._mutable(joining_id)
        if not str(reason or '').strip():
            raise UserError(_('Give a reason for closing the joining link.'))
        if j.offer_id:
            j.offer_id.action_did_not_join('other', note=reason, by_name=self.env.user.name)
        else:
            j._cancel(reason)
        return {'closed':True}

    @api.model
    def settings(self, vals=None):
        self._check_manage()
        company = self.env.company.sudo()
        params = self.env['ir.config_parameter'].sudo()
        if vals is not None:
            company.write({key:str(vals[key] or '')[:500] for key in ('pb_joining_day_place','pb_joining_day_bring') if key in vals})
            if 'auto_invite' in vals:
                params.set_param('pb_joining.auto_invite','1' if vals['auto_invite'] else '0')
        return {'pb_joining_day_place':company.pb_joining_day_place or '', 'pb_joining_day_bring':company.pb_joining_day_bring or '',
                'auto_invite':flag(self.env,'pb_joining.auto_invite','1')}

    @api.model
    def invite_options(self):
        self._check_manage()
        base = [('company_id','=',self.env.company.id)]
        return {'countries':self.env['pb.new.hire']._countries(), 'teams':self.env['hr.department'].sudo().search_read(base,['name'],order='name'),
                'managers':self.env['hr.employee'].sudo().search_read(base,['name'],order='name'),
                'langs':[(k,l) for k,l in self.env['res.lang'].get_installed() if k in ('en_US','vi_VN','id_ID')]}
