# -*- coding: utf-8 -*-
"""FS-12 (owner ruling R30) — the My Payobook page builder: "My Profile".

A guided builder, not a free-form web editor: the administrator arranges the
employee's own-details page as SECTIONS (title per language, one or two
columns) holding FIELDS (half or full width), plus a header (heading and
sub-line per language, an optional banner image, a tint from the locked
palette). Everything else stays the product's:

* WHICH fields may be offered is the engine's R14 rule (`_pbfs_portal_rules`):
  own fields, the openable standard boxes (R19) minus the spouse boxes
  (R25), the fields today's page shows. Pay figures are never offered.
* PLACING a field on the page IS its "Show on My Payobook" tick — one stored
  fact (`pb.form.field.meta.portal_show`). Ticking a field in the employee
  Form builder puts it on the page (at the end of the first section until
  the administrator moves it); unticking it there takes it off.
* "Employee can change it", "HR approves" / "Saves at once" are the engine's
  own ticks with the engine's refusals (locked list, R26 sensitive boxes).
* Values are read ONLY through `fields_for(…, 'portal')` / `portal_values`,
  changes go through `portal_check` / `portal_apply` and the existing change
  requests — the page cannot show or write anything the engine would refuse.

Storage: the engine's own `pb.form.layout` row of the host `my_profile_page`
(`sections` = the page's sections; `page` = header, side order, per-company
pages, the ticks as they were before the first publish), the engine's drafts
(one per administrator) and its history (`pb.form.audit`, the whole page in
each publish's detail — "Restore" and "Undo" read it back). Nothing is
cached in a worker: every request reads the published row.

Silent install: no layout, no tick, no job, no mail.
"""
import base64
import logging
import re

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX
from odoo.addons.pb_form_studio_people.models.form_studio import (
    HOST as EMP_HOST, PORTAL_SPOUSE, STANDARD_FIELDS)

_logger = logging.getLogger(__name__)

PAGE_HOST = 'my_profile_page'
EMP = 'hr.employee'
#: The fields today's "My Profile" page shows (pb_me_portal portal_my_profile),
#: in its own order — the starting point and the "standard page".
TODAY_FIELDS = ('work_email', 'work_phone', 'private_phone', 'private_email', 'private_street',
                'emergency_contact', 'emergency_phone')
#: Changed through today's profile change request (pb_me_portal
#: `_MASTER_FIELDS`), always approved by HR: field → the request's box.
PROFILE_REQUEST = {'private_phone': 'x_phone', 'private_email': 'x_private_email',
                   'private_street': 'x_address', 'emergency_contact': 'x_emergency_contact',
                   'emergency_phone': 'x_emergency_phone'}
#: FS-14 — which of those boxes the employee may change: pb_me_portal's own
#: whitelist (`pb_profile_change_request.py:36-37,110-116`), enforced by that
#: model at create/write/diff/apply. The page builder's "Employee can change
#: it" switch of these five fields writes THIS parameter (one stored fact; no
#: second store). Unset = all five (pb_me_portal's default).
PROFILE_PARAM = 'pb_me_portal.editable_fields'
PROFILE_BOXES = tuple(PROFILE_REQUEST.values())
#: The locked palette's light tints (design system: light-tint hero, no gradients).
TINTS = ('plain', 'brand', 'teal', 'sky', 'green', 'amber', 'rose', 'slate')
#: Fixed blocks of the side column; their order may change, they stay.
SIDE_BLOCKS = ('requests', 'door')
MAX_SECTIONS = 12
MAX_FIELDS = 30
MAX_TITLE = 60
MAX_HEADING = 80
MAX_SUB = 200
MAX_ALT = 120
MAX_BANNER_BYTES = 2 * 1024 * 1024
#: Allowed banner kinds, told apart by their first bytes (never by the name).
BANNER_MAGIC = (
    (b'\xff\xd8\xff', 'image/jpeg', 'jpg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png', 'png'),
)
SECTION_ID = re.compile(r'^[a-z][a-z0-9_]{0,23}$')
HISTORY = 15

#: NEWHIRE P8 H — who may build the My Payobook page besides the
#: administrator: the HR manager role (implied, `security/page_builder.xml`).
#: Such a builder changes the page of the company they are working in and
#: nothing else the administrator gate guards (no other screen of the Form
#: builder, no field settings that apply to every company, no reset, no
#: history restore).
BUILDER_GROUP = 'pb_form_studio_portal.group_page_builder'
#: "This call comes from the page builder's own draft / preview path." An
#: object, never a value JSON can carry: a client cannot set it.
_BUILDER = object()
_BUILDER_CTX = 'pbfp_builder_call'



def _sniff(raw):
    for magic, mime, ext in BANNER_MAGIC:
        if raw.startswith(magic):
            return mime, ext
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp', 'webp'
    return None, None


class PbFormStudioPage(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ================================================================ host
    @api.model
    def _pbfs_hosts(self):
        hosts = super()._pbfs_hosts()
        if EMP not in self.env or EMP_HOST not in hosts:
            return hosts
        _ = self.env._
        emp_host = hosts[EMP_HOST]
        # Never `_pbfp_default_spec` here: it asks `fields_for`, which asks
        # the hosts — the standard page is one section until a page exists.
        # Cached: the hosts are asked on every screen; no query per call.
        stored = self._pbfp_host_sections() or (('details', (('en_US', 'Your details'),)),)
        sections = []
        for sid, titles in stored:
            sections.append({'id': sid, 'kind': 'open', 'icon': 'layers', 'tone': 'brand',
                             'title': self._pbfp_text(dict(titles)) or _('Section')})
        hosts[PAGE_HOST] = {
            'model': EMP,
            'title': _('My Payobook page'),
            'icon': 'smartphone',
            'purpose': 'portal_page',
            'sections': sections,
            'default_layout': {},
            'standard_fields': [n for n in emp_host.get('standard_fields') or []
                                if n not in PORTAL_SPOUSE],
            'custom_section': sections[0]['id'] if sections else None,
            'country_field': emp_host.get('country_field'),
            'country_view_field': emp_host.get('country_view_field'),
            'copy_custom': False,
            'native_views': [],
            # The employee host is THE My Payobook host of the record type
            # (`_pbfs_portal_host`); this page only arranges its fields.
            'portal': False,
        }
        return hosts

    @api.model
    @tools.ormcache()
    def _pbfp_host_sections(self):
        """`((section id, ((lang, title), …)), …)` of the published page —
        cached per database; every publish and reset clears it (the registry
        tells every worker)."""
        layout = self._pbfs_layout(PAGE_HOST)
        out = []
        for sec in (layout.sections or []) if layout else []:
            if isinstance(sec, dict) and sec.get('id'):
                titles = sec.get('title') if isinstance(sec.get('title'), dict) else {}
                out.append((sec['id'], tuple(sorted((k, str(v)) for k, v in titles.items()))))
        return tuple(out)

    # ================================================================ words
    @api.model
    def _pbfp_text(self, texts, lang=None):
        """One text of a `{lang: text}` dict in the reader's language, else
        English, else the first one written."""
        if not isinstance(texts, dict):
            return str(texts or '')
        lang = lang or self.env.lang or 'en_US'
        for key in (lang, 'en_US'):
            if (texts.get(key) or '').strip():
                return texts[key].strip()
        return next((v.strip() for v in texts.values() if isinstance(v, str) and v.strip()), '')

    @api.model
    def _pbfp_words(self, source):
        """`{lang: text}` of one of this module's sentences in every installed
        language (a new section's title starts translated)."""
        out = {}
        for lang in self._pbfs_langs():
            out[lang] = self.with_context(lang=lang).env._(source)
        return out

    @api.model
    def _pbfp_section_words(self, key):
        # one literal per sentence, so each is a msgid
        words = {
            'details': lambda env: env._('Your details'),
            'company': lambda env: env._('Company details'),
            'new': lambda env: env._('New section'),
        }
        return {lang: words[key](self.with_context(lang=lang).env) for lang in self._pbfs_langs()}

    # ============================================================ eligible
    @api.model
    def _pbfp_eligible(self):
        """`{name: row}` of every field the page may show, A to Z by label.
        Row: what the left list and the settings column draw."""
        Model = self.env[EMP]
        metas = self._pbfs_meta(EMP)
        locked = self._pbfs_locked_fields(EMP)
        names = [n for n in STANDARD_FIELDS if n in Model._fields and n not in PORTAL_SPOUSE]
        names += [n for n in self._pbfs_custom_names(EMP) if n not in names]
        hidden = self._pbfs_portal_hidden(EMP)
        profile_edit = self._pbfp_profile_editable()
        out = {}
        for name in names:
            if name in hidden:
                continue
            rules = self._pbfs_portal_rules(EMP, name)
            if not rules['can_show']:
                continue
            desc = self._pbfs_describe(Model, name, meta=metas.get(name), locked=locked)
            meta = metas.get(name)
            std_country = []
            if not desc['custom'] and meta and meta.std_country_ids:
                std_country = [{'id': c.id, 'name': c.name} for c in meta.std_country_ids]
            out[name] = {
                'name': name, 'label': desc['label'], 'field_label': desc['field_label'],
                'kind': desc['kind'], 'type_label': desc['type_label'], 'custom': desc['custom'],
                'countries': desc['countries'], 'std_countries': std_country,
                'portal': desc['portal'], 'labels': desc.get('labels') or {},
                'std_labels': dict(meta.std_labels or {}) if (meta and not desc['custom']
                                                             and isinstance(meta.std_labels, dict))
                else {},
                'today': name in TODAY_FIELDS,
                'request': name in PROFILE_REQUEST,
                # FS-14: the "Employee can change it" switch of a personal box
                'request_edit': name in profile_edit,
                'options': desc['options'],
            }
        return dict(sorted(out.items(), key=lambda kv: (kv[1]['label'] or '').lower()))

    # ================================================ FS-14 personal boxes
    @api.model
    def _pbfp_profile_editable(self, updates=None):
        """The employee fields among today's five personal boxes (private
        phone, private e-mail, address, emergency contact and phone) the
        employee may change through "Request a change" — read from
        pb_me_portal's own whitelist. `updates` (a draft's field settings)
        lays its `profile_edit` switches over it, for the preview."""
        boxes = self.env['pb.profile.change.request'].sudo()._editable_fields()
        out = {name for name, box in PROFILE_REQUEST.items() if box in boxes}
        for name, upd in (updates or {}).items() if isinstance(updates, dict) else []:
            if name in PROFILE_REQUEST and isinstance(upd, dict) and 'profile_edit' in upd:
                if upd['profile_edit']:
                    out.add(name)
                else:
                    out.discard(name)
        return out

    @api.model
    def _pbfp_set_profile_editable(self, wanted, eligible):
        """Write the personal-box switches (`{field: bool}`) into the
        whitelist; one history line per box that changes. → the parameter's
        raw value BEFORE the change (False when it was unset), or None when
        nothing changed."""
        _ = self.env._
        current = self._pbfp_profile_editable()
        new = set(current)
        for name, on in wanted.items():
            if on:
                new.add(name)
            else:
                new.discard(name)
        if new == current:
            return None
        Param = self.env['ir.config_parameter'].sudo()
        before = Param.get_param(PROFILE_PARAM)
        Param.set_param(PROFILE_PARAM, ','.join(
            box for name, box in PROFILE_REQUEST.items() if name in new))
        for name in PROFILE_REQUEST:
            if (name in new) == (name in current):
                continue
            label = (eligible.get(name) or {}).get('label') or name
            self._pbfs_audit('update_field', PAGE_HOST, EMP, name,
                             (_('%s: the employee can change it (HR approves)', label)
                              if name in new else
                              _('%s: look only for the employee; only HR changes it', label)))
        return before

    # ============================================================ the spec
    @api.model
    def _pbfp_default_spec(self):
        """Today's page as a spec: one section with the seven fields today's
        page shows, then the fields already ticked for My Payobook in the
        employee Form builder (their sections' order)."""
        Model = self.env[EMP]
        details = [{'name': n, 'width': 'half'} for n in TODAY_FIELDS if n in Model._fields]
        sections = [{'id': 'details', 'title': self._pbfp_section_words('details'), 'cols': 2,
                     'fields': details}]
        ticked = [s['name'] for s in self.sudo().fields_for(EMP, 'portal')
                  if s['name'] not in TODAY_FIELDS]
        if ticked:
            sections.append({'id': 'company', 'title': self._pbfp_section_words('company'),
                             'cols': 2, 'fields': [{'name': n, 'width': 'half'} for n in ticked]})
        return {'header': {'title': {}, 'sub': {}, 'tint': 'plain', 'banner': False,
                           'banner_alt': {}},
                'sections': sections, 'side': list(SIDE_BLOCKS)}

    @api.model
    def _pbfp_published(self, layout=None):
        """`{'default': spec, 'companies': {company id (str): spec}}` of the
        published page, or None when the standard page is in use."""
        layout = layout if layout is not None else self._pbfs_layout(PAGE_HOST)
        if not layout:
            return None
        page = layout.page or {}
        default = {'header': page.get('header') or {}, 'sections': layout.sections or [],
                   'side': page.get('side') or list(SIDE_BLOCKS)}
        return {'default': default, 'companies': dict(page.get('companies') or {})}

    @api.model
    def _pbfp_clean_texts(self, texts, limit, what):
        langs = self._pbfs_langs()
        out = {}
        for lang, text in (texts or {}).items() if isinstance(texts, dict) else []:
            text = (text or '').strip() if isinstance(text, str) else ''
            if not text or lang not in langs:
                continue
            if len(text) > limit:
                raise UserError(self.env._('%(what)s can be at most %(n)s characters.',
                                           what=what, n=limit))
            out[lang] = text
        return out

    @api.model
    def _pbfp_clean_spec(self, spec, eligible, layout=None):
        """Validate one page in plain words; → the clean spec to store."""
        _ = self.env._
        spec = spec if isinstance(spec, dict) else {}
        head = spec.get('header') if isinstance(spec.get('header'), dict) else {}
        tint = head.get('tint') or 'plain'
        if tint not in TINTS:
            raise UserError(_('Pick a header colour from the list.'))
        banner = head.get('banner') or False
        if banner:
            att = self.env['ir.attachment'].sudo().browse(int(banner)).exists()
            if not att or att.res_model != 'pb.form.layout' or att.mimetype not in (
                    'image/jpeg', 'image/png', 'image/webp'):
                raise UserError(_('The banner image could not be found. Upload it again.'))
            banner = att.id
        header = {
            'title': self._pbfp_clean_texts(head.get('title'), MAX_HEADING, _('The heading')),
            'sub': self._pbfp_clean_texts(head.get('sub'), MAX_SUB, _('The line under the heading')),
            'tint': tint, 'banner': banner,
            'banner_alt': self._pbfp_clean_texts(head.get('banner_alt'), MAX_ALT,
                                                 _('The picture description')),
        }
        raw = spec.get('sections') if isinstance(spec.get('sections'), list) else []
        if len(raw) > MAX_SECTIONS:
            raise UserError(_('A page can have at most %s sections.', MAX_SECTIONS))
        sections, ids, placed = [], set(), set()
        for sec in raw:
            if not isinstance(sec, dict):
                continue
            sid = str(sec.get('id') or '')
            if not SECTION_ID.match(sid) or sid in ids:
                raise UserError(_('Each section needs its own name tag. Start again from the '
                                  'published page.'))
            ids.add(sid)
            cols = sec.get('cols') if sec.get('cols') in (1, 2) else 2
            items = []
            for item in sec.get('fields') or []:
                name = item.get('name') if isinstance(item, dict) else item
                if not isinstance(name, str) or name in placed:
                    continue
                if name not in self.env[EMP]._fields:
                    continue        # a field deleted since: it simply leaves the page
                if name not in eligible:
                    raise UserError(_('"%s" cannot be shown on My Payobook.',
                                      self.env[EMP]._fields[name].get_description(
                                          self.env, ['string'])['string']
                                      if name in self.env[EMP]._fields else name))
                width = item.get('width') if isinstance(item, dict) else 'half'
                items.append({'name': name, 'width': width if width in ('half', 'full') else 'half'})
                placed.add(name)
            if len(items) > MAX_FIELDS:
                raise UserError(_('A section can hold at most %s fields.', MAX_FIELDS))
            sections.append({'id': sid, 'cols': cols, 'fields': items,
                             'title': self._pbfp_clean_texts(sec.get('title'), MAX_TITLE,
                                                             _('A section name'))})
        if not sections:
            raise UserError(_('The page needs at least one section.'))
        side = [b for b in (spec.get('side') or []) if b in SIDE_BLOCKS]
        side += [b for b in SIDE_BLOCKS if b not in side]
        return {'header': header, 'sections': sections, 'side': side[:len(SIDE_BLOCKS)]}, placed

    # ============================================================ P8 gates
    @api.model
    def _pbfp_can_build(self):
        """The administrator, or a page builder (the HR manager role)."""
        if self._pbfs_is_admin():
            return True
        user = self.env.user
        return bool(user and not user._is_public() and user.has_group(BUILDER_GROUP))

    @api.model
    def _pbfp_check_build(self):
        if not self._pbfp_can_build():
            raise AccessError(self.env._('Only the administrator can change forms.'))
        return True

    @api.model
    def _pbfp_limited(self):
        """True for a page builder who is not the administrator: they change
        their own company's page only."""
        return not self._pbfs_is_admin()

    @api.model
    def _pbfs_check_admin(self):
        """The page builder's own draft calls (`save_draft` / `discard_draft`
        for this page) pass for a page builder; everything else the
        administrator gate guards stays the administrator's."""
        if self.env.context.get(_BUILDER_CTX) is _BUILDER and self._pbfp_can_build():
            return True
        return super()._pbfs_check_admin()

    @api.model
    def save_draft(self, host_key, payload):
        if host_key == PAGE_HOST:
            self._pbfp_check_build()
            return super(PbFormStudioPage, self.with_context(**{_BUILDER_CTX: _BUILDER})).save_draft(
                host_key, payload)
        return super().save_draft(host_key, payload)

    @api.model
    def discard_draft(self, host_key):
        if host_key == PAGE_HOST:
            self._pbfp_check_build()
            return super(PbFormStudioPage, self.with_context(**{_BUILDER_CTX: _BUILDER})).discard_draft(
                host_key)
        return super().discard_draft(host_key)

    @api.model
    def _pbfp_own_company(self):
        """The company a limited page builder's page is for: the one they are
        working in (it is always one of their own)."""
        company = self.env.company
        return company if company in self.env.user.company_ids else self.env.user.company_id

    @api.model
    def _pbfp_companies(self):
        """The companies a page may be made for (FS-13): active ones the
        administrator works in — the companies switched on in their company
        switcher, which are always among the ones their login may open. An
        archived company (or one they cannot open) is not offered; a page made
        for it earlier is kept as it is (`page_publish` carries it over)."""
        allowed = self.env.companies & self.env.user.company_ids
        return self.env['res.company'].sudo().search(
            [('id', 'in', allowed.ids), ('active', '=', True)], order='sequence, name')

    # ============================================================ studio
    @api.model
    def page_studio(self):
        """Everything the page builder draws. Administrator only (R2); P8: a
        page builder too, for their own company's page."""
        self._pbfp_check_build()
        self._pbfp_sweep_locked()
        layout = self._pbfs_layout(PAGE_HOST)
        eligible = self._pbfp_eligible()
        published = self._pbfp_published(layout)
        draft = self._pbfs_drafts(PAGE_HOST)[:1]
        version = layout.version if layout else 0
        companies = self._pbfp_companies()
        ticked = [n for n, row in eligible.items() if (row['portal'] or {}).get('show')]
        out = {
            'version': version,
            'published': published,
            'standard': self._pbfp_default_spec(),
            'draft': ({'payload': draft.payload or {}, 'base_version': draft.base_version,
                       'stale': draft.base_version != version} if draft else None),
            'fields': eligible,
            'ticked': ticked,
            'today': list(TODAY_FIELDS),
            'tints': list(TINTS),
            # the name My Payobook carries on this site ("My Rize" on a tenant)
            'brand': self.env['ir.config_parameter'].sudo().get_param('biz_debrand.brand_name')
            or self.env.company.name or '',
            'langs': self._pbfs_langs(),
            'lang': self.env.lang or 'en_US',
            'companies': ([{'id': c.id, 'name': c.name} for c in companies]
                          if len(companies) > 1 else []),
            'countries': [{'id': c.id, 'name': c.name, 'code': c.code}
                          for c in self.env['res.country'].search([])],
            'history': self._pbfp_history(),
            'published_by': layout.published_by.name if layout and layout.published_by else '',
            'published_at': fields.Datetime.to_string(layout.published_at)
            if layout and layout.published_at else '',
            'banners': self._pbfp_banner_urls(published, draft),
            'caps': {'sections': MAX_SECTIONS, 'fields': MAX_FIELDS, 'title': MAX_TITLE,
                     'heading': MAX_HEADING, 'sub': MAX_SUB, 'alt': MAX_ALT,
                     'banner_mb': MAX_BANNER_BYTES // (1024 * 1024)},
            'limited': False,
        }
        if self._pbfp_limited():
            out = self._pbfp_limit_studio(out)
        return out

    @api.model
    def _pbfp_limit_studio(self, out):
        """A page builder who is not the administrator sees ONE page: their
        company's own (or, until it has one, the page every company sees, to
        start from). No company switch, no history to restore, no reset, and
        the field settings that apply to every company are read-only."""
        own = self._pbfp_own_company()
        published = out.get('published')
        if published:
            mine = (published.get('companies') or {}).get(str(own.id))
            out['published'] = {'default': mine or published['default'], 'companies': {}}
        out['companies'] = []
        out['history'] = []
        out['limited'] = True
        out['limited_company'] = own.name or ''
        return out

    @api.model
    def _pbfp_banner_urls(self, published, draft):
        ids = set()
        for spec in self._pbfp_all_specs(published):
            if (spec.get('header') or {}).get('banner'):
                ids.add(spec['header']['banner'])
        payload = (draft.payload or {}) if draft else {}
        for spec in [payload.get('spec') or {}] + list((payload.get('companies') or {}).values()):
            if isinstance(spec, dict) and (spec.get('header') or {}).get('banner'):
                ids.add(spec['header']['banner'])
        return {str(i): '/my/profile/banner/%s' % i for i in ids if isinstance(i, int)}

    @api.model
    def _pbfp_all_specs(self, published):
        if not published:
            return []
        return [published['default']] + [s for s in (published.get('companies') or {}).values()
                                         if isinstance(s, dict)]

    @api.model
    def _pbfp_history(self):
        rows = self.env['pb.form.audit'].sudo().search(
            [('host_key', '=', PAGE_HOST), ('action', '=', 'publish')], limit=HISTORY)
        return [{'id': r.id, 'when': fields.Datetime.to_string(r.stamp), 'who': r.user_id.name or '',
                 'summary': r.summary or '', 'version': (r.detail or {}).get('version'),
                 'restorable': bool((r.detail or {}).get('page'))} for r in rows]

    @api.model
    def page_version(self, audit_id):
        """A published version from the history, to load into the draft
        ("Restore" / "Undo"). Nothing is published by this."""
        self._pbfs_check_admin()
        row = self.env['pb.form.audit'].sudo().browse(int(audit_id)).exists()
        if not row or row.host_key != PAGE_HOST or not (row.detail or {}).get('page'):
            raise UserError(self.env._('This version cannot be restored.'))
        return row.detail['page']

    @api.model
    def page_employees(self, term=''):
        """People to preview the page as (administrator only): any employee
        the administrator may see, the ones with a My Payobook login first
        (FS-13: a site where nobody has a login yet can still be previewed).
        P8: a page builder too (their own read access decides who)."""
        self._pbfp_check_build()
        limit = 20
        dom = [('name', 'ilike', term)] if term else []
        emps = self.env[EMP].search(dom + [('user_id', '!=', False)], limit=limit, order='name')
        if len(emps) < limit:
            emps |= self.env[EMP].search(dom + [('user_id', '=', False)],
                                         limit=limit - len(emps), order='name')
        countries = self._pbfs_record_countries(emps)
        Country = self.env['res.country']
        return [{'id': e.id, 'name': e.name, 'company': e.company_id.name or '',
                 'login': bool(e.user_id),
                 'country': Country.browse(countries.get(e.id) or []).name or ''} for e in emps]

    # ----------------------------------------------------------- banner
    @api.model
    def page_upload_banner(self, filename, data):
        """Store a banner picture (administrator only). JPEG, PNG or WebP
        told apart by their first bytes, at most 2 MB; never SVG. P8: a page
        builder too."""
        self._pbfp_check_build()
        _ = self.env._
        try:
            raw = base64.b64decode((data or '').split(',', 1)[-1], validate=True)
        except Exception:                               # noqa: BLE001
            raise UserError(_('That file could not be read.'))
        if not raw:
            raise UserError(_('That file is empty.'))
        if len(raw) > MAX_BANNER_BYTES:
            raise UserError(_('The picture is too big: at most 2 MB.'))
        mime, ext = _sniff(raw)
        if not mime:
            raise UserError(_('Use a JPG, PNG or WebP picture.'))
        name = 'my-profile-banner.%s' % ext
        att = self.env['ir.attachment'].sudo().create({
            'name': name, 'datas': base64.b64encode(raw), 'mimetype': mime,
            'res_model': 'pb.form.layout', 'res_id': 0, 'public': False,
        })
        self._pbfs_audit('update_field', PAGE_HOST, EMP, None,
                         _('Uploaded a banner picture for My Payobook (%s KB)', len(raw) // 1024))
        return {'id': att.id, 'url': '/my/profile/banner/%s' % att.id}

    @api.model
    def _pbfp_banner_allowed(self, att_id, user=None):
        """May this signed-in user see banner `att_id`? Yes when it is the
        banner of the published page their company sees (or of any page, for
        the administrator, who also sees drafts)."""
        user = user or self.env.user
        if not user or user._is_public():
            return False
        if user.has_group('base.group_system') or user.has_group(BUILDER_GROUP):
            return True
        published = self._pbfp_published()
        if not published:
            return False
        if ((published['default'].get('header') or {}).get('banner')) == att_id:
            return True
        companies = {str(c) for c in user.company_ids.ids}
        for cid, spec in (published.get('companies') or {}).items():
            if cid in companies and ((spec or {}).get('header') or {}).get('banner') == att_id:
                return True
        return False

    # ----------------------------------------------------------- publish
    @api.model
    def publish(self, host_key, payload):
        if host_key == PAGE_HOST:
            return self.page_publish(payload)
        return super().publish(host_key, payload)

    @api.model
    def page_publish(self, payload):
        """Make the page live for every employee, in one transaction.

        `payload`: `{spec, companies: {company id: spec | None}, updates:
        {field: vals}, base_version, overwrite, changes: [text]}`. `updates`
        carry each field's own settings, applied through the engine exactly
        as the employee Form builder does (labels, "Employee can change it",
        "HR approves" / "Saves at once"). Then every offered field's "Show on
        My Payobook" tick is set from the page: placed = shown.

        P8: a page builder who is not the administrator publishes their own
        company's page only — the `spec` they send becomes that company's
        page; the page every company sees, the other companies' pages and the
        field settings that apply to every company (`updates`) are kept as
        they are."""
        self._pbfp_check_build()
        _ = self.env._
        payload = dict(payload or {})
        limited = self._pbfp_limited()
        if limited:
            payload['updates'] = {}
        layout = self._pbfs_layout(PAGE_HOST)
        current = layout.version if layout else 0
        base = payload.get('base_version', current)
        if base != current and not payload.get('overwrite'):
            who = layout.published_by.name or _('another administrator')
            return {'ok': False, 'stale': True,
                    'message': _('%(who)s published this page after you started your changes. '
                                 'Publishing now would replace their page with yours.', who=who)}
        eligible = self._pbfp_eligible()
        if limited:
            own = self._pbfp_own_company()
            old = self._pbfp_published(layout) if layout else None
            mine, placed = self._pbfp_clean_spec(payload.get('spec'), eligible, layout)
            payload['spec'] = old['default'] if old else self._pbfp_default_spec()
            payload['companies'] = {str(own.id): mine}
        spec, more_default = self._pbfp_clean_spec(payload.get('spec'), eligible, layout)
        placed = (placed | more_default) if limited else more_default
        companies = {}
        valid = {str(own.id)} if limited else {str(c.id) for c in self._pbfp_companies()}
        for cid, cspec in (payload.get('companies') or {}).items():
            if cspec is None or str(cid) not in valid:
                continue
            clean, more = self._pbfp_clean_spec(cspec, eligible, layout)
            companies[str(cid)] = clean
            placed |= more
        # FS-13: a company's own page for a company not offered here (archived
        # since, or outside this administrator's companies) stays exactly as
        # it is, and its fields stay shown.
        for cid, kept in ((layout.page or {}).get('companies') or {}).items() if layout else []:
            if str(cid) in valid or not isinstance(kept, dict):
                continue
            companies[str(cid)] = kept
            for sec in kept.get('sections') or []:
                for item in (sec or {}).get('fields') or []:
                    name = item.get('name') if isinstance(item, dict) else item
                    if name in eligible:
                        placed.add(name)
        # 1. each field's own settings (the engine refuses what R14 forbids)
        profile_wanted = {}
        for name, vals in (payload.get('updates') or {}).items():
            if name not in eligible or not isinstance(vals, dict):
                continue
            if name in PROFILE_REQUEST and 'profile_edit' in vals:
                # FS-14: today's personal boxes — pb_me_portal's whitelist
                profile_wanted[name] = bool(vals['profile_edit'])
            vals = {k: v for k, v in vals.items()
                    if k in ('portal_edit', 'portal_mode', 'labels', 'std_labels')}
            portal = {k: vals[k] for k in ('portal_edit', 'portal_mode') if k in vals}
            if portal.get('portal_edit') and name not in placed:
                portal['portal_edit'] = False
            if name.startswith(PREFIX):
                if 'labels' in vals:
                    self.update_field(EMP, name, {'labels': vals['labels']})
                if portal:
                    self.update_portal(EMP, name, dict(portal, portal_show=name in placed))
            else:
                std = {k: vals[k] for k in ('std_labels',) if k in vals}
                std.update(portal)
                if portal:
                    std['portal_show'] = name in placed
                if std:
                    self.with_context(pbfs_publishing=True).update_standard(EMP, name, std)
        # 2. placed = "Show on My Payobook" (one truth with the employee builder)
        first = not layout
        before = self._pbfp_ticks(eligible) if first else None
        self._pbfp_set_ticks(eligible, placed)
        # 3. the page itself
        stored_page = {'header': spec['header'], 'side': spec['side'], 'companies': companies}
        if first:
            stored_page['ticks_before'] = before
        else:
            stored_page['ticks_before'] = (layout.page or {}).get('ticks_before') or {}
        # FS-14: the personal boxes' switches; the whitelist as it was before
        # the builder first changed it is kept for "Reset to the standard page"
        old_page = (layout.page or {}) if layout else {}
        if 'profile_before' in old_page:
            stored_page['profile_before'] = old_page['profile_before']
        if profile_wanted:
            raw_before = self._pbfp_set_profile_editable(profile_wanted, eligible)
            if raw_before is not None and 'profile_before' not in stored_page:
                stored_page['profile_before'] = raw_before or False
        vals = {'sections': spec['sections'], 'page': stored_page, 'version': current + 1,
                'published_by': self.env.uid, 'published_at': fields.Datetime.now()}
        if layout:
            layout.write(vals)
        else:
            layout = self.env['pb.form.layout'].sudo().create(dict(
                vals, host_key=PAGE_HOST, model=EMP, company_id=self.env.company.id))
        self._pbfs_drafts(PAGE_HOST).unlink()
        changes = [str(c)[:200] for c in (payload.get('changes') or [])][:100]
        self._pbfs_audit('publish', PAGE_HOST, EMP, None,
                         _('Published the My Payobook page, version %s', layout.version),
                         detail={'changes': changes, 'version': layout.version,
                                 'page': {'spec': spec, 'companies': companies}})
        self.env.registry.clear_cache('templates')       # R27 labels on every screen
        self.env.registry.clear_cache()                  # the page's sections (every worker)
        self._pbfs_notify(PAGE_HOST, layout.version)
        return {'ok': True, 'version': layout.version}

    @api.model
    def _pbfp_ticks(self, eligible):
        metas = self._pbfs_meta(EMP, list(eligible))
        return {n: [bool(m.portal_show), bool(m.portal_edit), m.portal_mode or 'approve']
                for n, m in metas.items() if m.portal_show or m.portal_edit}

    @api.model
    def _pbfp_set_ticks(self, eligible, placed):
        """Placed → shown; offered but not placed → not shown (and so not
        changeable). One history line per field that changes."""
        _ = self.env._
        metas = self._pbfs_meta(EMP, list(eligible))
        for name in eligible:
            meta = metas.get(name)
            show = name in placed
            if bool(meta and meta.portal_show) == show:
                continue
            self._pbfs_set_portal(EMP, name, {'portal_show': show} if show
                                  else {'portal_show': False, 'portal_edit': False})
            self._pbfs_audit('update_field', PAGE_HOST, EMP, name,
                             (_('%s: placed on the My Payobook page', eligible[name]['label'])
                              if show else
                              _('%s: taken off the My Payobook page', eligible[name]['label'])))

    @api.model
    def _pbfp_sweep_locked(self):
        """A field on the page that became locked (FS-10 rule or the hard
        list) stays shown, look-only: its "Employee can change it" tick is
        switched off with a history line."""
        _ = self.env._
        Meta = self.env['pb.form.field.meta'].sudo()
        for meta in Meta.search([('model', '=', EMP), ('portal_edit', '=', True)]):
            if meta.name not in self.env[EMP]._fields:
                continue
            rules = self._pbfs_portal_rules(EMP, meta.name)
            if rules['can_edit']:
                continue
            meta.write({'portal_edit': False})
            label = self.env[EMP]._fields[meta.name].get_description(self.env, ['string'])['string']
            self._pbfs_audit('update_field', PAGE_HOST, EMP, meta.name,
                             _('%(label)s: "Employee can change it" switched off: %(why)s',
                               label=label, why=rules['edit_reason']))

    @api.model
    def page_reset(self):
        """"Reset to the standard page": today's page again, exactly. The
        page is removed (its history stays) and every field's My Payobook
        tick goes back to what it was before the page was first published."""
        self._pbfs_check_admin()
        _ = self.env._
        layout = self._pbfs_layout(PAGE_HOST)
        if not layout:
            self._pbfs_drafts(PAGE_HOST).unlink()
            return {'ok': True}
        before = (layout.page or {}).get('ticks_before') or {}
        eligible = self._pbfp_eligible()
        Meta = self.env['pb.form.field.meta'].sudo()
        for meta in Meta.search([('model', '=', EMP), '|', ('portal_show', '=', True),
                                 ('name', 'in', list(before))]):
            show, edit, mode = (before.get(meta.name) or [False, False, 'approve'])[:3]
            vals = {'portal_show': bool(show), 'portal_edit': bool(edit) and bool(show),
                    'portal_mode': mode or 'approve'}
            if any(meta[k] != v for k, v in vals.items()):
                meta.write(vals)
                label = (eligible.get(meta.name) or {}).get('label') or meta.name
                self._pbfs_audit('update_field', PAGE_HOST, EMP, meta.name,
                                 _('%s: My Payobook tick put back as before the page', label))
        # FS-14: the personal boxes' switches as before the builder changed them
        if 'profile_before' in (layout.page or {}):
            raw = layout.page['profile_before']
            Param = self.env['ir.config_parameter'].sudo()
            if (Param.get_param(PROFILE_PARAM) or False) != (raw or False):
                Param.set_param(PROFILE_PARAM, raw or False)
                self._pbfs_audit('update_field', PAGE_HOST, EMP, None,
                                 _('Personal details: "Employee can change it" put back as '
                                   'before the page'))
        version = layout.version
        layout.unlink()
        self.env.registry.clear_cache()
        self._pbfs_drafts(PAGE_HOST).unlink()
        self._pbfs_audit('publish', PAGE_HOST, EMP, None,
                         _('Reset the My Payobook page to the standard page'),
                         detail={'version': version, 'reset': True})
        self._pbfs_notify(PAGE_HOST, 0)
        return {'ok': True}

    # ============================================================ render
    @api.model
    def portal_page_render(self, employee, spec=None, company=None, preview=None):
        """The published page for ONE employee, or None when the standard
        page is in use. Built only from `fields_for(…, 'portal')` and
        `portal_values` (safe around the sudo record the portal hands over;
        an id over the wire needs the caller's own read access — engine rule).

        `spec`: a page to draw instead of the published one (the
        administrator's preview of a draft). → `{header, sections, side}`;
        a section with nothing to show for this person is left out.

        `preview` (FS-13, administrator only): a dict of the draft's field
        settings (`updates`, may be empty) — the page is drawn EXACTLY as
        Publish would make it: every eligible field the spec places (ticked
        or not yet), with the draft's labels and change settings, and nothing
        the spec does not place. Nothing is written: the "Show on My
        Payobook" tick changes only at Publish."""
        rec = self._pbfs_portal_record(EMP, employee)
        if preview is not None:
            self._pbfp_check_build()
            if spec is None:
                raise UserError(self.env._('There is no page to preview.'))
        if spec is None:
            published = self._pbfp_published()
            if not published:
                return None
            cid = str((company or rec.company_id).id or '')
            spec = (published.get('companies') or {}).get(cid) or published['default']
        if preview is not None:
            specs, values = self._pbfp_preview_fields(rec, spec, preview)
        else:
            specs = {s['name']: s for s in self.fields_for(EMP, 'portal', record=rec)}
            values = self.portal_values(EMP, rec)
        sections, placed = [], set()
        for sec in spec.get('sections') or []:
            items = []
            for item in sec.get('fields') or []:
                name = item.get('name') if isinstance(item, dict) else item
                s = specs.get(name)
                if not s or name in placed:
                    continue
                placed.add(name)
                items.append(self._pbfp_item(s, values.get(name) or {},
                                             (item.get('width') if isinstance(item, dict) else '')
                                             or 'half'))
            sections.append({'id': sec.get('id'), 'title': self._pbfp_text(sec.get('title')),
                             'cols': 1 if sec.get('cols') == 1 else 2, 'fields': items})
        # ticked in the employee Form builder but not placed yet: the end of
        # the first section (one truth: shown = on the page)
        extra = [n for n in specs if n not in placed] if preview is None else []
        if extra and sections:
            for name in extra:
                sections[0]['fields'].append(self._pbfp_item(specs[name], values.get(name) or {},
                                                             'half'))
        # FS-14: may the employee change this personal box? (the draft's
        # switches in a preview, the stored whitelist otherwise)
        profile_edit = self._pbfp_profile_editable(preview)
        for sec in sections:
            for item in sec['fields']:
                item['request_edit'] = bool(item['request']) and item['name'] in profile_edit
        head = spec.get('header') or {}
        banner = head.get('banner') or False
        return {
            'header': {'title': self._pbfp_text(head.get('title')),
                       'sub': self._pbfp_text(head.get('sub')),
                       'tint': head.get('tint') if head.get('tint') in TINTS else 'plain',
                       'banner_url': ('/my/profile/banner/%s' % banner) if banner else '',
                       'banner_alt': self._pbfp_text(head.get('banner_alt'))},
            'sections': [s for s in sections if s['fields']],
            'side': [b for b in (spec.get('side') or SIDE_BLOCKS) if b in SIDE_BLOCKS],
        }

    @api.model
    def _pbfp_preview_fields(self, rec, spec, updates):
        """FS-13 — the field specs and values of a page as Publish would
        make it, for the administrator's preview: the fields `spec` places
        that the page may show (`_pbfp_eligible`, the engine's R14 rules),
        Country of Work honoured as on the real page, the draft's own labels
        and change settings (`updates`) over the stored ones. Same item shape
        as `fields_for(…, 'portal')`. Reads only; writes nothing."""
        Model = self.env[EMP]
        updates = updates if isinstance(updates, dict) else {}
        eligible = self._pbfp_eligible()
        metas = self._pbfs_meta(EMP)
        sensitive = self._pbfs_portal_sensitive(EMP)
        country = self._pbfs_record_countries(rec)[rec.id]
        lang = self.env.lang or 'en_US'
        specs, values = {}, {}
        for sec in spec.get('sections') or []:
            for item in (sec or {}).get('fields') or []:
                name = item.get('name') if isinstance(item, dict) else item
                if not isinstance(name, str) or name in specs or name not in eligible:
                    continue
                field = Model._fields.get(name)
                if not field:
                    continue
                meta = metas.get(name)
                custom = name.startswith(PREFIX) and bool(meta and meta.custom)
                if name.startswith(PREFIX) and not self._pbfs_applies(meta, country):
                    continue
                rules = self._pbfs_portal_rules(EMP, name)
                if not rules['can_show']:
                    continue
                upd = updates.get(name) if isinstance(updates.get(name), dict) else {}
                desc = field.get_description(self.env, ['string', 'help'])
                if custom:
                    own = ((upd.get('labels') or {}) if isinstance(upd.get('labels'), dict)
                           else {}).get(lang)
                elif 'std_labels' in upd:
                    labels = upd['std_labels'] if isinstance(upd['std_labels'], dict) else {}
                    own = labels.get(lang)
                else:
                    own = self._pbfs_std_label_of(meta)
                own = own.strip() if isinstance(own, str) else ''
                edit = upd['portal_edit'] if 'portal_edit' in upd else bool(meta and meta.portal_edit)
                mode = upd.get('portal_mode') or (meta.portal_mode if meta else '') or 'approve'
                specs[name] = {
                    'name': name, 'label': own or desc.get('string') or name,
                    'help': desc.get('help') or '', 'type': field.type,
                    'options': self._pbfs_options(field),
                    'comodel': field.comodel_name if field.type == 'many2one' else False,
                    'edit': bool(edit and rules['can_edit']),
                    'mode': 'approve' if name in sensitive else (
                        mode if mode in ('instant', 'approve') else 'approve'),
                    'required': bool(custom and meta.is_required),
                }
                values[name] = {'value': self._pbfs_raw(rec, field),
                                'display': self._pbfs_display(rec, field)}
        return specs, values

    @api.model
    def _pbfp_item(self, spec, cell, width):
        return {'name': spec['name'], 'label': spec.get('label') or spec['name'],
                'value': cell.get('display') or '', 'raw': cell.get('value'),
                'width': width if width in ('half', 'full') else 'half',
                'edit': bool(spec.get('edit')), 'mode': spec.get('mode') or 'approve',
                'type': spec.get('type'), 'options': spec.get('options') or [],
                'comodel': spec.get('comodel') or False, 'help': spec.get('help') or '',
                'required': bool(spec.get('required')),
                'request': PROFILE_REQUEST.get(spec['name']) or ''}
