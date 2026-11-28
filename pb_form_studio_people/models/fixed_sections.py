# -*- coding: utf-8 -*-
"""FS-11 (owner ruling R29) — what each FIXED section of the employee side
panel really shows, field by field, for the Form builder's canvas.

THE MAP is kept beside the code that draws the panel, through this bridge:

* Personal · Job · Pay & tax — the panel's own table, read at run time
  (`pb_employee_vault/models/employee_details.py` `_SPEC`: tab, group, rows,
  country gate), so a row added there is listed here at once;
* the Vietnam payroll group the panel builds for people paid in Vietnam
  (`employee_vietnam.py` `_e360_vietnam`) — declared below (`VN_PAY_ROWS`),
  because that group is worked out from the pay scheme, not from a table;
* the Bank block of FS-9 (`pb_employee_bank_panel`, where installed) —
  its four lines replace the table's Bank group, exactly as on screen;
* Profile — the summary cells of the panel's template (`employee_360.xml`
  Profile tab), all worked out by the screen (`PROFILE_ROWS`).

`test_fs11_fixed.py` proves map = screen both ways: every line the panel
draws for a filled-in person is in the map, and every field in the map is
drawn for that person. A field line opens the same settings as the Standard
fields tab (hide / rename per Country of Work, My Payobook ticks); a line the
screen works out itself (the summary, the pay scheme's settings, the bank
block) is listed for truth and opens nothing.
"""
from lxml import etree
from odoo import api, models
from .premium_section import SECTIONS
from odoo.tools.translate import LazyTranslate

from .form_studio import HOST, MODEL

_lt = LazyTranslate(__name__)

#: The Profile tab's cells (employee_360.xml, PROFILE section): summary
#: lines the panel works out itself; none of them follows a screen rule.
PROFILE_ROWS = (
    ('wage', _lt("Monthly wage")), ('department', _lt("Department")),
    ('manager', _lt("Manager")), ('costcenter', _lt("Cost centre")),
    ('joined', _lt("Joined")), ('email', _lt("Email")), ('phone', _lt("Phone")),
    ('structure', _lt("Structure")), ('contract_dates', _lt("Contract dates")),
    ('on_record', _lt("On record")), ('ready_bank', _lt("Bank on file")),
    ('ready_tax', _lt("Tax")), ('ready_insurance', _lt("Insurance")),
)
#: The Vietnam payroll group (`_e360_vietnam`), in its own order. Row keys;
#: the first two are employee fields, the rest come from the pay scheme and
#: the running contract.
VN_PAY_ROWS = (
    ('vietnam_tax_code', _lt("PIT number")),
    ('vietnam_social_insurance_number', _lt("SI number")),
    ('vn_payroll_scheme', _lt("Payroll scheme")),
    ('vn_settings_date', _lt("Settings as of")),
    ('VNSIJOIN', _lt("Social insurance (SI)")),
    ('VNHIJOIN', _lt("Health insurance (HI)")),
    ('VNUIJOIN', _lt("Unemployment insurance (UI)")),
    ('VNINSMODE', _lt("Insurance salary basis")),
    ('vn_insurance_salary', _lt("Salary before insurance caps")),
    ('VNTAXMODE', _lt("PIT calculation method")),
    ('VNPTYPE', _lt("Saved payroll treatment")),
    ('VNPERSONAL', _lt("Personal deduction — scheme rate")),
    ('VNREGISTER', _lt("Registered dependents — payroll count")),
    ('VNDEPAMT', _lt("Deduction per registered dependent")),
    ('vn_dependent_total', _lt("Dependent deduction from saved payroll count")),
    ('vn_saved_dependents', _lt("Dependent records saved")),
    ('vn_pending_dependents', _lt("Dependent records needing verification")),
    ('vn_deduction_note', _lt("How relief is applied")),
)
#: One line per dependent record (group "Dependent records").
VN_DEPENDENT_KEY = 'dependent_*'
#: The FS-9 Bank block (`pb_employee_bank_panel` `_pb_bank_group`).
BANK_ROWS = (
    ('pb_bank_status', _lt("Status")), ('pb_bank_name', _lt("Bank")),
    ('pb_bank_holder', _lt("Account holder")), ('pb_bank_number', _lt("Account number")),
)
#: The panel's "Home address" line joins these boxes into one.
HOME_ADDRESS_KEY = '_home_address'


class PbFormStudioPeopleFixed(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_people_panel_map(self):
        """`{tab: [item]}` — THE map of the side panel's fixed tabs. Items as
        `_pbfs_fixed_items` describes them; `name` is False for a line the
        panel works out itself."""
        _ = self.env._
        Model = self.env[MODEL]
        out = {'profile': [], 'personal': [], 'job': [], 'pay': [], 'documents': [],
               'timeline': [], 'resume': [], 'settings': []}
        summary = _('Summary')
        for key, label in PROFILE_ROWS:
            out['profile'].append({'key': 'profile.%s' % key, 'name': False,
                                   'label': str(label), 'group': summary, 'country': ''})
        try:
            from odoo.addons.pb_employee_vault.models.employee_details import _SPEC
        except ImportError:
            _SPEC = []
        bank_block = 'pb.people' in self.env and hasattr(self.env['pb.people'], '_pb_bank_group')
        for tab, gkey, title, _icon, gate, rows in _SPEC:
            if tab not in out:
                continue
            if gkey == 'bank' and bank_block:
                for key, label in BANK_ROWS:
                    out[tab].append({'key': key, 'name': False, 'label': str(label),
                                     'group': str(title), 'country': ''})
                continue
            if gkey == 'vn':
                # People paid in Vietnam: the group the pay scheme fills in.
                group = str(title)
                for key, label in VN_PAY_ROWS:
                    name = key if key in Model._fields else False
                    out[tab].append({'key': 'vnpay.%s' % key, 'name': name, 'label': str(label),
                                     'group': group, 'country': 'VN'})
                out[tab].append({'key': VN_DEPENDENT_KEY, 'name': False,
                                 'label': _('One line per dependent record'),
                                 'group': _('Dependent records'), 'country': 'VN'})
                # Anybody else with Vietnamese details typed in: the table's group.
                group = _('%s (recorded boxes)', str(title))
            else:
                group = str(title)
            for name, label, _opt in rows:
                if name == HOME_ADDRESS_KEY:
                    out[tab].append({'key': name, 'name': False, 'label': str(label),
                                     'group': group, 'country': gate or ''})
                    continue
                if name not in Model._fields:
                    continue            # the module that carries it is not installed
                out[tab].append({'key': name, 'name': name, 'label': str(label),
                                 'group': group, 'country': gate or ''})
        # The premium editors also expose native boxes absent from the old
        # summary. Read their actual processed section so the builder does not
        # promise a box removed by permissions or an installed view.
        labels = Model.fields_get(attributes=['string'])
        for tab, groups in SECTIONS.items():
            root = etree.fromstring(Model.get_view(view_type='form', pb_workspace_section=tab)['arch'])
            fields = {n.get('name'): n for n in root.xpath('.//section//field[not(ancestor::field)]')
                      if not any(a.get('invisible') in ('1', 'True', 'true') for a in [n, *n.iterancestors()])}
            existing = {item['name'] for item in out[tab] if item['name']}
            for title, names in groups:
                for name in names:
                    if name in fields and name not in existing:
                        out[tab].append({'key': name, 'name': name,
                                         'label': fields[name].get('string') or labels.get(name, {}).get('string') or name,
                                         'group': _(title), 'country': ''})
                        existing.add(name)
            for name, node in fields.items():
                if name not in existing:
                    card = next(node.iterancestors('section'))
                    out[tab].append({'key': name, 'name': name,
                                     'label': node.get('string') or labels.get(name, {}).get('string') or name,
                                     'group': card.findtext('h3') or '', 'country': ''})
                    existing.add(name)
        return out

    @api.model
    def _pbfs_fixed_items(self, host_key, surface='panel'):
        out = dict(super()._pbfs_fixed_items(host_key, surface) or {})
        if host_key == HOST and surface != 'full' and MODEL in self.env:
            out.update(self._pbfs_people_panel_map())
        return out
