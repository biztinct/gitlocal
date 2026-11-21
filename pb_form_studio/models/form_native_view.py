# -*- coding: utf-8 -*-
"""The native-view sync helper: one Studio-owned page per host view.

A host (FS-2/FS-3) calls `pb.form.studio._pbfs_sync_native_view(model,
parent_view_xmlid, page_title, host_key)` once; the engine then regenerates
the page on every publish and BEFORE every field delete (core refuses to drop
a field a view still names). The engine itself never names a host's view.

The view has no XML id on purpose: a module upgrade removes XML-id records a
module no longer ships, and this view belongs to the customer's layout, not
to any module's data. It survives `-u` of the host's module and of this one.
"""
import logging

from lxml import etree

from odoo import api, fields, models

from .ir_model_fields import PREFIX

_logger = logging.getLogger(__name__)


class PbFormNativeView(models.Model):
    _name = 'pb.form.native.view'
    _description = 'Form builder page on a standard screen'

    model = fields.Char(required=True, index=True)
    parent_xmlid = fields.Char(required=True)
    host_key = fields.Char()
    titles = fields.Json(help='Page title per language.')
    view_id = fields.Many2one('ir.ui.view', ondelete='set null')

    _parent_uniq = models.Constraint('UNIQUE (model, parent_xmlid)',
                                     'One Form builder page per screen design.')

    @api.model
    def _pbfs_sync(self, model, parent_xmlid, page_title, host_key=None):
        rec = self.search([('model', '=', model), ('parent_xmlid', '=', parent_xmlid)], limit=1)
        titles = page_title if isinstance(page_title, dict) else {'en_US': page_title or ''}
        vals = {'titles': titles, 'host_key': host_key or (rec.host_key if rec else False)}
        if rec:
            rec.write(vals)
        else:
            rec = self.create(dict(vals, model=model, parent_xmlid=parent_xmlid))
        return rec._pbfs_regenerate()

    # ----------------------------------------------------------- content
    def _pbfs_host(self):
        Studio = self.env['pb.form.studio']
        hosts = Studio._pbfs_hosts()
        if self.host_key and self.host_key in hosts:
            return self.host_key, hosts[self.host_key]
        for key, host in hosts.items():
            if host['model'] == self.model and not host.get('dev'):
                return key, host
        for key, host in hosts.items():
            if host['model'] == self.model:
                return key, host
        return None, None

    def _pbfs_sections(self, exclude=()):
        """[(section id, title, [custom field names])] in published order."""
        Studio = self.env['pb.form.studio']
        key, host = self._pbfs_host()
        if not host:
            return []
        Model = self.env[self.model]
        out = []
        for sec in Studio._pbfs_effective(key):
            names = [n for n in sec['fields'] if n.startswith(PREFIX) and n not in exclude
                     and n in Model._fields]
            if sec['kind'] == 'open' and names:
                out.append((sec['id'], sec['title'], names))
        return out

    def _pbfs_arch(self, sections, xpath, wrap):
        Studio = self.env['pb.form.studio']
        key, host = self._pbfs_host()
        Model = self.env[self.model]
        metas = Studio._pbfs_meta(self.model)
        cvf = host.get('country_view_field') if host else None
        if cvf and (cvf not in Model._fields or Model._fields[cvf].type != 'many2one'):
            cvf = None
        root = etree.Element('data')
        xp = etree.SubElement(root, 'xpath', expr=xpath, position='inside')
        parent = xp
        if wrap:
            parent = etree.SubElement(xp, 'notebook', name='pbfs_notebook')
        page = etree.SubElement(parent, 'page', string=(self.titles or {}).get('en_US') or 'Company details',
                                name='pbfs_company_details')
        need_cvf = False
        for sid, title, names in sections:
            group = etree.SubElement(page, 'group', string=title, name='pbfs_sec_%s' % sid)
            for name in names:
                node = etree.SubElement(group, 'field', name=name)
                field = Model._fields[name]
                if field.groups:
                    node.set('groups', field.groups)
                meta = metas.get(name)
                if meta and meta.country_ids and cvf:
                    node.set('invisible', '%s not in %s' % (cvf, meta.country_ids.ids))
                    need_cvf = True
                elif meta and meta.country_ids:
                    # No country field to test on this screen: hide rather
                    # than show it to every country.
                    node.set('invisible', 'True')
        if need_cvf:
            etree.SubElement(page, 'field', name=cvf, invisible='1')
        return etree.tostring(root, encoding='unicode')

    def _pbfs_translate(self, view, sections):
        """Page and section titles in every installed language."""
        Studio = self.env['pb.form.studio']
        key, _host = self._pbfs_host()
        en_page = (self.titles or {}).get('en_US') or 'Company details'
        per_lang = {}
        for lang in Studio._pbfs_langs():
            if lang == 'en_US':
                continue
            terms = {}
            page_tr = (self.titles or {}).get(lang)
            if page_tr:
                terms[en_page] = page_tr
            try:
                host_l = Studio.with_context(lang=lang)._pbfs_hosts().get(key) or {}
                titles_l = {s['id']: s['title'] for s in host_l.get('sections', [])}
            except Exception:                           # noqa: BLE001
                titles_l = {}
            for sid, title, _n in sections:
                if titles_l.get(sid) and titles_l[sid] != title:
                    terms[title] = titles_l[sid]
            if terms:
                per_lang[lang] = terms
        if per_lang:
            try:
                view.update_field_translations('arch_db', per_lang)
            except Exception:                           # noqa: BLE001
                _logger.info('pb_form_studio: page titles not translated', exc_info=True)

    def _pbfs_regenerate(self, exclude=()):
        self.ensure_one()
        parent = self.env.ref(self.parent_xmlid, raise_if_not_found=False)
        sections = self._pbfs_sections(exclude=exclude)
        View = self.env['ir.ui.view'].sudo()
        if not parent or parent._name != 'ir.ui.view' or not sections:
            if self.view_id:
                self.view_id.unlink()
            return False
        candidates = [('//notebook', False), ('//sheet', True), ('/form', True)]
        for xpath, wrap in candidates:
            arch = self._pbfs_arch(sections, xpath, wrap)
            try:
                with self.env.cr.savepoint():
                    if self.view_id:
                        self.view_id.write({'arch_db': arch, 'active': True})
                        view = self.view_id
                    else:
                        view = View.create({
                            'name': 'Form builder page (%s)' % self.model,
                            'model': self.model, 'type': parent.type,
                            'inherit_id': parent.id, 'mode': 'extension',
                            'priority': 99, 'arch_db': arch,
                        })
                    # Validate the WHOLE result, not just the extension.
                    parent.with_context(check_view_ids=view.ids).get_combined_arch()
                    self.env[self.model].get_view(parent.id, parent.type)
            except Exception:                           # noqa: BLE001
                _logger.info('pb_form_studio: page for %s did not fit at %s; trying the next place',
                             self.parent_xmlid, xpath)
                self.invalidate_recordset(['view_id'])
                continue
            if not self.view_id:
                self.view_id = view
            self._pbfs_translate(view, sections)
            return view
        _logger.warning('pb_form_studio: could not place the page on %s; the previous one is kept',
                        self.parent_xmlid)
        return self.view_id or False
