"""Meta template reminders, adapted from Health19's WhatsApp adapter (LGPL-3).

Original adapter: I Am Dream Catcher Ltd. No healthcare models or credentials
are copied. Delivery evidence comes from signed, account-scoped webhooks.
"""
import re

import requests

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.exceptions import UserError


class WhatsAppConnection(models.Model):
    _inherit = 'pb.hiring.connection'

    def _meta(self, method, path, **kwargs):
        cfg = self._config()
        version = cfg.get('version', '')
        if not re.fullmatch(r'v\d+\.\d+', version):
            raise UserError(_('Enter the Graph API version shown in your Meta application.'))
        try:
            response = requests.request(method, 'https://graph.facebook.com/' + version + '/' + path,
                headers={'Authorization': 'Bearer ' + self._secret('api_key')}, timeout=(5,15), allow_redirects=False, **kwargs)
            if response.status_code >= 300:
                raise UserError(_('Meta refused the request (HTTP %s). Check account approval, token permissions and template status.', response.status_code))
            return response.json()
        except (requests.RequestException, ValueError):
            raise UserError(_('Meta could not be reached. Delivery is not confirmed.')) from None

    def _check_whatsapp(self):
        cfg = self._config()
        if not cfg.get('phone_id', '').isdigit() or not cfg.get('waba_id', '').isdigit():
            raise UserError(_('Phone number and business account IDs must be numeric.'))
        account = self._meta('GET', cfg['waba_id'] + '/phone_numbers', params={'fields':'id,display_phone_number,code_verification_status', 'limit':100})
        phones = [p for p in account.get('data', []) if p.get('id') == cfg['phone_id']]
        if not phones or phones[0].get('code_verification_status') != 'VERIFIED':
            raise UserError(_('This number is not verified under the selected WhatsApp business account.'))
        result = self._meta('GET', cfg['waba_id'] + '/message_templates', params={'name': cfg['template'], 'limit':100})
        template = next((t for t in result.get('data', []) if t.get('name') == cfg['template'] and t.get('language') == cfg['language'] and t.get('status') == 'APPROVED'), None)
        if not template:
            raise UserError(_('The selected template/language is not approved by Meta yet.'))
        body = next((c.get('text', '') for c in template.get('components', []) if c.get('type') == 'BODY'), '')
        if set(re.findall(r'\{\{(\d+)\}\}', body)) != {'1','2','3','4'}:
            raise UserError(_('Use a reminder template with four body parameters: candidate, role, interview time and joining details.'))
        if any(c.get('type') in ('HEADER','BUTTONS') and ('{{' in str(c) or c.get('format') not in (None,'TEXT')) for c in template.get('components', [])):
            raise UserError(_('This connector supports four body parameters without dynamic header or button parameters.'))
        return _('Verified number and approved reminder template. Register the webhook and complete an opted-in test before candidate use.')

    def _receive_whatsapp_status(self, data):
        for entry in data.get('entry', []):
            if str(entry.get('id', '')) != self._config().get('waba_id'):
                continue
            for change in entry.get('changes', []):
                value = change.get('value', {})
                if str(value.get('metadata', {}).get('phone_number_id', '')) != self._config().get('phone_id'):
                    continue
                for status in value.get('statuses', []):
                    row = self.env['pb.hiring.message.delivery'].sudo().search([
                        ('connection_id', '=', self.id), ('external_id', '=', status.get('id'))], limit=1)
                    state = status.get('status')
                    if row and state in ('sent','delivered','read','failed'):
                        order = {'queued':0,'unknown':0,'failed':1,'sent':2,'delivered':3,'read':4}
                        if state == 'failed' and row.state in ('delivered','read'):
                            continue
                        if state == 'failed' or order[state] >= order.get(row.state,0):
                            row.write({'state': state, 'updated_at': fields.Datetime.now()})


class CandidateWhatsApp(models.Model):
    _inherit = 'hr.applicant'
    pb_whatsapp_opt_in = fields.Boolean(string='Candidate agreed to WhatsApp interview reminders', tracking=True)
    pb_whatsapp_consent_note = fields.Char(string='WhatsApp consent evidence', help='When and how the candidate agreed. Keep their preference separate from general application consent.')


class MessageDelivery(models.Model):
    _name = 'pb.hiring.message.delivery'
    _description = 'Interview reminder delivery'
    _order = 'id desc'
    interview_id = fields.Many2one('pb.hiring.interview', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='interview_id.company_id', store=True)
    connection_id = fields.Many2one('pb.hiring.connection', required=True)
    reminder = fields.Selection([('24h','Day before'), ('30m','Half hour before')], required=True)
    external_id = fields.Char(readonly=True, index=True)
    state = fields.Selection([('queued','Queued'), ('sent','Accepted by provider'), ('delivered','Delivered'), ('read','Read'), ('failed','Failed'), ('unknown','Delivery unknown')], default='queued', readonly=True)
    note = fields.Char(readonly=True)
    updated_at = fields.Datetime(readonly=True)
    _once = models.Constraint('unique(interview_id, reminder)', 'This interview reminder has already been attempted.')


class InterviewWhatsApp(models.Model):
    _inherit = 'pb.hiring.interview'
    pb_delivery_ids = fields.One2many('pb.hiring.message.delivery', 'interview_id', readonly=True)

    def _remind(self, which):
        result = super()._remind(which)
        app = self.applicant_id.sudo()
        conn = self.env['pb.hiring.connection']._for_company('whatsapp', self.company_id)
        if conn and conn.enabled and conn.check_ok and app.pb_whatsapp_opt_in and app.pb_whatsapp_consent_note:
            Delivery = self.env['pb.hiring.message.delivery'].sudo()
            if not Delivery.search_count([('interview_id','=',self.id),('reminder','=',which)]):
                Delivery.create({'interview_id': self.id, 'connection_id': conn.id, 'reminder': which})
        return result


class ConnectionJobs(models.AbstractModel):
    _name = 'pb.hiring.connection.jobs'
    _description = 'Hiring connection jobs'

    @api.model
    def _run(self):
        applicants = self.env['hr.applicant'].sudo().search([('pb_cv_state', '=', 'queued')], limit=2)
        for applicant in applicants:
            try:
                with self.env.cr.savepoint():
                    applicant._extract_cv()
            except Exception:
                applicant.write({'pb_cv_state': 'failed', 'pb_cv_note': _('Extraction failed. Check the connection and CV, then use Extract CV to retry.')})
        # Separate cursor transactions make provider outcomes durable. There
        # is no automatic repeat of an ambiguous outbound message attempt.
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('pb_envelope_id','!=',False), ('pb_sign_status','in', ['draft','pending']),
            ('pb_sign_connection_id.enabled','=',True)], order='pb_sign_checked_at asc, id', limit=10)
        for offer in offers:
            try:
                with self.env.cr.savepoint():
                    offer._sync_esign(offer._envelope())
            except Exception:
                offer.write({'pb_sign_checked_at': fields.Datetime.now(), 'pb_sign_note': _('Status check failed. Use Check signing status to retry.')})
        deliveries = self.env['pb.hiring.message.delivery'].sudo().search([('state','=','queued')], limit=20)
        for delivery in deliveries:
            with Registry(self.env.cr.dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['pb.hiring.message.delivery'].browse(delivery.id)._process()
                cr.commit()


class DeliveryWorker(models.Model):
    _inherit = 'pb.hiring.message.delivery'

    def _process(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_hiring_message_delivery WHERE id=%s FOR UPDATE SKIP LOCKED', [self.id])
        if not self.env.cr.fetchone():
            return
        self.invalidate_recordset()
        if self.state != 'queued':
            return
        conn = self.connection_id
        interview = self.interview_id
        app = interview.applicant_id
        if not conn.enabled or not conn.check_ok or interview.state != 'scheduled' or interview.start <= fields.Datetime.now() or not app.pb_whatsapp_opt_in or not app.pb_whatsapp_consent_note:
            self.write({'state':'failed','note':_('Reminder skipped: connection, interview or candidate consent is no longer active.')})
            return
        phone = re.sub(r'[\s().-]', '', app.partner_phone or '')
        if not re.fullmatch(r'\+[1-9]\d{7,14}', phone):
            self.write({'state':'failed','note':_('Candidate phone needs an international country code.')})
            return
        cfg = conn._config()
        values = [app.partner_name, interview.requisition_id.title, interview.pb_when_local,
                  interview.videocall_url or interview.location or _('Contact your recruiter for joining details')]
        # Mark the attempt BEFORE network I/O in a separate committed cursor
        # from the cron caller (see _cron_process_deliveries below).
        self.write({'state':'unknown', 'note':_('Send attempted; awaiting provider evidence.'), 'updated_at':fields.Datetime.now()})
        self.env.cr.commit()
        try:
            result = conn._meta('POST', cfg['phone_id'] + '/messages', json={
                'messaging_product':'whatsapp', 'recipient_type':'individual', 'to':phone[1:], 'type':'template',
                'template':{'name':cfg['template'],'language':{'code':cfg['language']},'components':[
                    {'type':'body','parameters':[{'type':'text','text':str(v or '')} for v in values]}]}})
            external = (result.get('messages') or [{}])[0].get('id')
            self.write({'state':'sent' if external else 'unknown', 'external_id':external,
                'note':_('Accepted by Meta; delivery confirmation is pending.') if external else _('Provider response did not contain a message ID.')})
        except UserError:
            self.write({'state':'unknown','note':_('The send could not be confirmed. Check Meta before attempting another reminder.')})
