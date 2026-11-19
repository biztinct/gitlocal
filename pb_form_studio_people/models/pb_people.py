# -*- coding: utf-8 -*-
"""The People screens' half of the employee host (FS-2), all from outside.

* `get_employee_detail` (`pb_people/models/pb_people.py:487`) gains ONE new
  key, `form_sections`. That payload is ALSO the side panel's `profile`
  (`pb_employee_vault/models/pb_people_360.py:102`), so the full page and the
  panel read the same answer; no existing key is touched.
* `pbfs_employee_sections` / `pbfs_save_employee` — the panel tab's reload
  and its one Save. The save goes through the engine's `write_values`, the
  only write path for custom fields (THE HOST CONTRACT item 3).
* `_pbf_spec` / `_pbf_groups` — custom choice, yes/no, link and date fields as
  People list filters, in their own "Company details" group.

Visibility is the ENGINE's (FS1-1): values come from `render` only, never
from a plain read. STANDARD amounts (the wage, hourly cost — when an
administrator places one on the tab) are masked exactly as the panel masks the
wage (`_vault_unmask_wage`, `pb_people_360.py:38`); a CUSTOM money field follows
its own "who can see it" only (owner ruling R15). A reader who is not a payroll
manager gets neither the number nor a way to change it.
"""
import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from .form_studio import HOST, MODEL

_logger = logging.getLogger(__name__)

#: Field types the People list can filter on, and the filter kind for each.
FILTER_KIND = {'selection': 'selection', 'boolean': 'choice', 'many2one': 'many2one',
               'date': 'date'}
#: Date filter choices: custom dates can lie behind or ahead (a visa's end).
DATE_PRESETS = ['passed', 'next_30', 'next_90', 'this_month', 'last_month', 'this_year',
                'last_year', 'none']


class PbPeople(models.AbstractModel):
    _inherit = 'pb.people'

    # ================================================================ payload
    @api.model
    def _pbfs_people_payload(self, emp):
        """The open sections of the published layout for one person, as the
        panel tab and the full page draw them, or None when this reader may
        not see them. Never raises: a broken layout must not blank a page."""
        Studio = self.env['pb.form.studio']
        try:
            data = Studio.render(HOST, emp.id)
        except (AccessError, UserError):
            return None
        except Exception:                               # noqa: BLE001
            _logger.warning('pb_form_studio_people: Company details could not be drawn for '
                            'employee %s', emp.id, exc_info=True)
            return None
        unmask = self._vault_unmask_wage()
        masked = self.env._('Visible to payroll managers only')
        sections, total, filled, writable = [], 0, 0, 0
        for sec in data.get('sections') or []:
            if sec.get('kind') != 'open':
                continue            # the panel draws its own tabs
            for f in sec.get('fields') or []:
                # R15: only standard amounts get the wage's mask
                if f.get('kind') == 'money' and not f.get('custom') and not unmask:
                    # drawn as a locked line (lock icon, quiet ink), not as money
                    f.update(value=False, display=masked, writable=False, masked=True,
                             kind='readonly')
                total += 1
                # "Filled in" = somebody answered: a ticked yes/no, a number
                # other than 0, any text, date, choice, link or file.
                if not f.get('masked') and f.get('value') not in (None, '', False, 0, 0.0):
                    filled += 1
                writable += 1 if f.get('writable') else 0
            sections.append(sec)
        out = {
            'sections': sections,
            'version': data.get('version', 0),
            'can_write': bool(data.get('can_write')),
            'editable': bool(writable),
            'currency': data.get('currency') or '',
            'total': total,
            'filled': filled,
            'country': emp.sudo().pbfs_country_of_work_id.name or '',
        }
        if Studio.can_edit(HOST):
            # Only the administrator hears how many fields exist in all,
            # to tell "none made yet" from "none for this country".
            out['custom_count'] = len(Studio._pbfs_custom_names(MODEL))
        return out

    @api.model
    def get_employee_detail(self, emp_id):
        res = super().get_employee_detail(emp_id)
        if isinstance(res, dict) and not res.get('error') and self._vault_is_hr():
            emp = self.env[MODEL].browse(int(emp_id)).exists()
            res['form_sections'] = self._pbfs_people_payload(emp) if emp else None
        return res

    @api.model
    def pbfs_employee_sections(self, employee_id):
        """The panel tab, again (after a save or a publish)."""
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            raise UserError(self.env._('This employee no longer exists.'))
        return self._pbfs_people_payload(emp)

    @api.model
    def pbfs_save_employee(self, employee_id, vals):
        """The panel tab's one Save (R8). → `{ok: True, data}` or the
        engine's `{ok: False, error?, errors}` with every field's reason."""
        self._require_hr()
        _ = self.env._
        emp = self._emp(employee_id)
        if not emp:
            return {'ok': False, 'error': _('This employee no longer exists.'), 'errors': {}}
        vals = dict(vals or {})
        res = self.env['pb.form.studio'].write_values(MODEL, emp.id, vals)
        if not res.get('ok'):
            return res
        return {'ok': True, 'data': self._pbfs_people_payload(emp)}

    # ================================================================ filters
    @api.model
    def _pbf_groups(self):
        groups = list(super()._pbf_groups())
        mine = {'key': 'pbfs', 'label': self.env._('Company details')}
        at = next((i for i, g in enumerate(groups) if g.get('key') == 'other'), len(groups))
        groups.insert(at, mine)
        return groups

    @api.model
    def _pbfs_people_filters(self):
        """One filter section per custom field of a filterable type that this
        person may see (`fields_for` asks the engine, never a plain read).
        The section key IS the field name, so a saved view that uses it is
        found by the engine's delete check (`_pbfs_refs_saved_views`)."""
        _ = self.env._
        out = []
        try:
            specs = self.env['pb.form.studio'].fields_for(MODEL, 'all')
        except Exception:                               # noqa: BLE001
            _logger.info('pb_form_studio_people: custom filters skipped', exc_info=True)
            return out
        for spec in specs:
            kind = FILTER_KIND.get(spec['type'])
            if not kind:
                continue
            name = spec['name']
            section = {'key': name, 'label': spec['label'], 'group': 'pbfs', 'type': kind,
                       'path': name, 'none_label': _('Not filled in')}
            if spec.get('help'):
                section['help'] = spec['help']
            if kind == 'selection':
                section['icon'] = 'list'
            elif kind == 'many2one':
                section['icon'] = 'link'
            elif kind == 'date':
                section['icon'] = 'calendar'
                section['presets'] = list(DATE_PRESETS)
            else:
                section.update(icon='checkCircle', options=[
                    {'value': 'yes', 'label': _('Yes'), 'tone': 'green', 'domain': [(name, '=', True)]},
                    {'value': 'no', 'label': _('No'), 'tone': 'slate', 'domain': [(name, '!=', True)]},
                ])
                section.pop('none_label', None)
                section.pop('path', None)
                section['requires'] = [name]
            out.append(section)
        return out

    def _pbf_spec(self):
        spec = super()._pbf_spec()
        if self._pbf_model() != MODEL:
            return spec
        return list(spec) + self._pbfs_people_filters()
