# -*- coding: utf-8 -*-
"""F114 — Ready-made HR/API connector mapping templates.

A template is a set of standard field-path → canonical-code rows for one vendor
(Zoho / Workday / SAP SuccessFactors / Oracle HCM), shipped as data. Applying a
template to a connector auto-creates field mappings matched by canonical code;
anything unmatched (or flagged verify/derive) lands in the `suggested` state so
a template guess NEVER silently feeds a wrong number — it is promoted to active
only through the onboarding wizard's batch test against the tenant's real
payload (D114.2/D114.4).
"""
from odoo import _, api, fields, models

_VENDORS = [
    ('zoho', 'Zoho People'),
    ('workday', 'Workday'),
    ('sap', 'SAP SuccessFactors'),
    ('oracle', 'Oracle HCM'),
]


class HrIntegrationMappingTemplate(models.Model):
    _name = 'hr.integration.mapping.template'
    _description = 'HR Integration Mapping Template Row'
    _order = 'connector_type, sequence, id'

    connector_type = fields.Selection(_VENDORS, required=True, index=True)
    source_path = fields.Char(required=True, help="Vendor payload field path.")
    target_code = fields.Char(required=True, help="Canonical input code (BASIC, DEPS, WDAYS…).")
    target_label = fields.Char()
    transformation_type = fields.Selection([
        ('direct', 'Direct'), ('divide', 'Divide'), ('multiply', 'Multiply'),
        ('round', 'Round'), ('python', 'Python'),
    ], default='direct')
    transformation_value = fields.Float(default=0.0)
    transformation_code = fields.Text()
    is_required = fields.Boolean(default=False)
    default_value = fields.Float(default=0.0)
    # verify/derive rows ship in 'suggested' state — never load-bearing until
    # confirmed against the real payload in the wizard (A3 hard rule).
    verify = fields.Boolean(default=False)
    note = fields.Char(help="Vendor doc citation and any traps.")
    sequence = fields.Integer(default=10)


class HrIntegrationOnboardingWizard(models.TransientModel):
    _name = 'hr.integration.onboarding.wizard'
    _description = 'Connect an HR / Timesheet System'

    step = fields.Selection([
        ('vendor', 'Vendor'), ('auth', 'Connect'),
        ('mappings', 'Fields'), ('activate', 'Activate'),
    ], default='vendor', required=True)

    connector_type = fields.Selection(
        _VENDORS + [('demo', 'Demo / Stub (live-tested)')], string='HR system')
    config_id = fields.Many2one(
        'hr.formula.config', string='Payroll configuration',
        domain="[('active','=',True)]",
        help="The configuration whose input components these fields will feed.")
    connector_id = fields.Many2one('hr.integration.connector', string='Connector', readonly=True)

    # step 2 — reuse the connector's existing auth fields
    name = fields.Char(string='Connection name')
    api_endpoint = fields.Char(string='API endpoint')
    auth_type = fields.Selection([
        ('oauth2', 'OAuth 2.0'), ('api_key', 'API Key'),
        ('basic', 'Basic Authentication'), ('bearer', 'Bearer Token')], default='oauth2')
    api_key = fields.Char()
    client_id = fields.Char()
    client_secret = fields.Char()
    connection_status = fields.Selection(related='connector_id.connection_status', readonly=True)

    # step 3 — mapping outcome
    applied_count = fields.Integer(readonly=True)
    suggested_count = fields.Integer(readonly=True)
    summary_html = fields.Html(readonly=True, sanitize=False)

    guide_display = fields.Html(compute='_compute_guide', sanitize=False)
    badge_display = fields.Char(compute='_compute_guide')

    # ------------------------------------------------------------------
    _GUIDE = {
        'zoho': _("In Zoho, open <b>Developer Space → API</b>, create a Self-Client, and grant the "
                  "<code>ZOHOPEOPLE.forms.READ</code> and attendance scopes. Paste the Client ID / Secret."),
        'workday': _("In Workday, build a <b>RaaS custom report</b> exposing the worker fields, enable "
                     "<b>JSON output</b>, and use an ISU account with report access. Paste the report URL + credentials."),
        'sap': _("In SAP SuccessFactors, register an <b>OAuth client (API Center)</b> with access to "
                 "<code>PerPerson</code>, <code>EmpEmployment</code> and <code>EmpPayCompRecurring</code>. Note your API server."),
        'oracle': _("In Oracle HCM, use a user with the <b>REST worker + salaries</b> resources. Paste the pod REST base URL "
                    "(<code>.../hcmRestApi/resources/11.13.18.05/</code>) and credentials."),
        'demo': _("The demo connector serves a built-in sample payload — nothing to configure. Great for a dry run."),
    }
    _TESTED = {'demo'}   # D114.4: only the demo is live-tested end to end

    @api.depends('connector_type')
    def _compute_guide(self):
        for w in self:
            w.guide_display = self._GUIDE.get(w.connector_type or '', '')
            w.badge_display = (_("✓ Live-tested") if w.connector_type in self._TESTED
                               else _("Field template — verify against your tenant"))

    # ------------------------------------------------------------------
    # step transitions
    # ------------------------------------------------------------------
    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def action_to_auth(self):
        self.ensure_one()
        if not self.connector_type:
            raise models.ValidationError(_("Please choose an HR system to connect."))
        if not self.name:
            self.name = dict(self._fields['connector_type'].selection).get(self.connector_type, 'Connector')
        self.step = 'auth'
        return self._reopen()

    def action_back(self):
        order = ['vendor', 'auth', 'mappings', 'activate']
        i = order.index(self.step)
        self.step = order[max(0, i - 1)]
        return self._reopen()

    def action_test_connection(self):
        self.ensure_one()
        self._ensure_connector()
        self.connector_id.action_test_connection()
        return self._reopen()

    def _ensure_connector(self):
        """Create-or-update the real connector record from the wizard fields."""
        self.ensure_one()
        vals = {
            'name': self.name or 'Connector',
            'connector_type': self.connector_type,
            'api_endpoint': self.api_endpoint or False,
            'auth_type': self.auth_type,
            'api_key': self.api_key or False,
            'client_id': self.client_id or False,
            'client_secret': self.client_secret or False,
        }
        if self.connector_id:
            self.connector_id.write(vals)
        else:
            self.connector_id = self.env['hr.integration.connector'].create(vals)
        # link the chosen config to this connector so mapping targets resolve
        # (sudo throughout — configs are company-scoped/record-rule-gated)
        if self.config_id:
            cfg = self.config_id.sudo()
            if cfg.connector_id != self.connector_id:
                cfg.connector_id = self.connector_id

    def action_apply_template(self):
        self.ensure_one()
        self._ensure_connector()
        res = self.connector_id.action_apply_mapping_template(
            config_id=self.config_id.id if self.config_id else None)
        self.applied_count = res['applied']
        self.suggested_count = res['suggested']
        self.summary_html = self._build_summary()
        self.step = 'mappings'
        return self._reopen()

    def _build_summary(self):
        self.ensure_one()
        maps = self.connector_id.field_mapping_ids
        act = maps.filtered(lambda m: m.active_state == 'active')
        sug = maps.filtered(lambda m: m.active_state == 'suggested')
        rows = []
        for m in maps.sorted(key=lambda m: (m.active_state, m.source_field or '')):
            tag = ('<span style="color:#166534;font-weight:600">● active</span>'
                   if m.active_state == 'active'
                   else '<span style="color:#B45309;font-weight:600">● suggested</span>')
            tgt = m.target_rule_id.sudo().code or _('— pick a target —')
            rows.append('<tr><td style="padding:3px 10px"><code>%s</code></td>'
                        '<td style="padding:3px 10px">%s</td>'
                        '<td style="padding:3px 10px">%s</td></tr>'
                        % (m.source_field or '', tgt, tag))
        return (
            '<p><b>%s</b> field(s) mapped automatically, <b>%s</b> need review.</p>'
            '<p style="color:#6B7280;font-size:12px">Suggested rows are excluded from sync until you '
            'confirm them against your real payload (Test mappings).</p>'
            '<table style="border-collapse:collapse;font-size:12.5px">'
            '<tr><th style="text-align:left;padding:3px 10px">Source field</th>'
            '<th style="text-align:left;padding:3px 10px">Target</th>'
            '<th style="text-align:left;padding:3px 10px">Status</th></tr>%s</table>'
        ) % (len(act), len(sug), ''.join(rows))

    def action_test_mappings(self):
        """Test suggested mappings against a real sample payload and promote the
        ones that resolve (the only path from 'suggested' → 'active')."""
        self.ensure_one()
        if not self.connector_id:
            self._ensure_connector()
        res = self.connector_id.action_test_field_mappings(
            config_id=self.config_id.id if self.config_id else None)
        if not res.get('ok'):
            note = ('<p style="color:#B45309;font-size:12px">%s</p>'
                    % (res.get('msg') or _('Could not test mappings.')))
        else:
            note = ('<p style="color:#166534;font-size:12px">Promoted <b>%s</b> of %s '
                    'testable suggested field(s) to active; <b>%s</b> still need review.</p>'
                    % (res.get('promoted', 0), res.get('tested', 0), res.get('remaining', 0)))
        self.summary_html = note + self._build_summary()
        self.step = 'mappings'
        return self._reopen()

    def action_to_activate(self):
        self.step = 'activate'
        return self._reopen()

    def action_finish(self):
        self.ensure_one()
        self._ensure_connector()
        self.connector_id.active = True
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connector'),
            'res_model': 'hr.integration.connector',
            'res_id': self.connector_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
