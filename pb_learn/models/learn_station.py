# -*- coding: utf-8 -*-
"""Stations — the nodes on the Guided Journey map — and the bundle endpoint.

The bundle carries BOTH languages for every translatable value. That is a
deliberate cost: the alternative (serve the session language only) breaks the
brief's "switchable live" requirement, because a learner who flips to Vietnamese
mid-lesson would have to reload and lose their place.

It is built by reading the same records twice under two language contexts and
zipping the trees. Anything not in ``_RAW_KEYS`` is treated as prose.
"""
import hashlib

from odoo import api, fields, models, tools

# Keys whose values are structure, not prose: they must survive the bilingual
# zip untouched. Getting this list wrong is visible immediately (a screen key
# would arrive as {"en": ..., "vi": ...} and the engine would fail to match an
# anchor), which is why an explicit list beats a clever heuristic here.
_RAW_KEYS = frozenset({
    'key', 'id', 'icon', 'line', 'section', 'kind', 'anchor', 'screen', 'visual',
    'role', 'value', 'sidebar_key', 'sequence', 'duration_min', 'required',
    'star', 'after', 'visible', 'lesson_key', 'station_key', 'correct',
    'moment_kind', 'moment_chain', 'moment_which', 'moment_from', 'moment_to',
    # Phase 2. `capability` and `action_tags` are structure inside a structural
    # tree; the flat map of UI labels is zipped by _zip_prose instead, so these
    # cannot repeat the collision that hid three chrome strings (ledger §5.146).
    'capability', 'action_tags', 'action_xmlids', 'models',
    'own_tag', 'own_xmlid',
    'show_me', 'practice_key', 'matched',
    # Phase 3 mission structure.
    # NOT 'did' / 'check': those are LISTS OF PROSE (the debrief), and marking
    # them raw would ship the whole debrief in English — the same class of bug
    # as §5.146, one level deeper.
    'nav', 'target', 'is_decision', 'is_consequence', 'is_undo',
    'confidence_key', 'confidence_gain',
})


def _zip_bilingual(en, vi, key=None):
    """Merge two identically-shaped trees into one with {en, vi} leaves."""
    if isinstance(en, dict) and isinstance(vi, dict):
        return {k: _zip_bilingual(v, vi.get(k), k) for k, v in en.items()}
    if isinstance(en, list) and isinstance(vi, list):
        # Same query, same order, same length — but never index blindly into a
        # list that turned out shorter, or a missing translation becomes a
        # traceback instead of an English fallback.
        return [_zip_bilingual(a, vi[i] if i < len(vi) else a, key)
                for i, a in enumerate(en)]
    if isinstance(en, str) and key not in _RAW_KEYS:
        # An EMPTY translatable stays an empty string. Wrapping it as
        # {"en": "", "vi": ""} would make it truthy, and every `field ? render
        # : ""` in the frontend would draw an empty card — which is exactly how
        # a step with no consequence ended up showing a blank "Before you do
        # this" panel.
        if not en:
            return ''
        return {'en': en, 'vi': vi if isinstance(vi, str) and vi else en}
    return en


def _zip_prose(en, vi):
    """Merge a flat {key: text} map where EVERY value is prose.

    No key exceptions, because the keys here are content names, not structure.
    """
    return {k: ({'en': v, 'vi': vi.get(k) or v} if v else '') for k, v in en.items()}


class LearnStationMistake(models.Model):
    _name = 'learn.station.mistake'
    _description = 'Learn station — common mistake'
    _order = 'sequence, id'

    station_id = fields.Many2one('learn.station', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Text(required=True, translate=True)


class LearnStation(models.Model):
    _name = 'learn.station'
    _description = 'Learn station'
    _order = 'line, sequence, id'

    key = fields.Char(required=True, index=True, help="Stable id used by content and progress.")
    name = fields.Char(required=True, translate=True)
    line = fields.Selection(
        selection=lambda self: self._selection_line(),
        required=True, default='payrun')
    section = fields.Selection(
        selection=lambda self: self._selection_section(),
        required=True, default='payroll',
        help="Which application area this station teaches. Later phases add rows here, not columns.")
    sequence = fields.Integer(default=10)
    summary = fields.Text(translate=True)
    icon = fields.Char(default='circle')
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(),
        required=True, default='outline')
    sidebar_key = fields.Char(
        help="xml-id of the pb.sidebar.item this station teaches. "
             "The join back to the product; a dangling one is a test failure.")
    duration_min = fields.Integer(default=5)
    required = fields.Boolean(default=False)
    star = fields.Boolean(default=False, help="Flagship — rendered larger on the map.")
    after_key = fields.Char(help="Key of the station this one should follow.")
    active = fields.Boolean(default=True)

    outline_what = fields.Text(translate=True)
    outline_why = fields.Text(translate=True)
    outline_when = fields.Text(translate=True)
    outline_prereq = fields.Text(translate=True)
    mistake_ids = fields.One2many('learn.station.mistake', 'station_id')
    lesson_ids = fields.One2many('learn.lesson', 'station_id')

    _sql_constraints = [
        ('key_uniq', 'unique(key)', 'A station key must be unique.'),
    ]

    # -- selections -------------------------------------------------------
    # Callable form throughout. A static list does not translate in this
    # codebase — measured, and the reason is in the memory ledger.
    @api.model
    def _selection_line(self):
        # One list across every section. Later phases add ROWS to the map, not
        # a second map — a learner who moves from the Pay Run desk to People
        # meets the same journey, further along. Phase A ships one line; the
        # selection stays extensible on purpose.
        return [('payrun', self.env._('Pay run line'))]

    @api.model
    def _selection_section(self):
        return [('payroll', self.env._('Payroll'))]

    @api.model
    def _selection_kind(self):
        return [('lesson', self.env._('Full lesson')),
                ('outline', self.env._('Outline')),
                ('mission', self.env._('Mission'))]

    # -- cache ------------------------------------------------------------
    def _invalidate_learn_bundle(self):
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        rec = super().create(vals_list)
        self._invalidate_learn_bundle()
        return rec

    def write(self, vals):
        res = super().write(vals)
        self._invalidate_learn_bundle()
        return res

    def unlink(self):
        res = super().unlink()
        self._invalidate_learn_bundle()
        return res

    # -- serialisation ----------------------------------------------------
    def _station_dict(self):
        self.ensure_one()
        return {
            'key': self.key,
            'name': self.name,
            'line': self.line,
            'section': self.section,
            'sequence': self.sequence,
            'summary': self.summary or '',
            'icon': self.icon or 'circle',
            'kind': self.kind,
            'sidebar_key': self.sidebar_key or '',
            'duration_min': self.duration_min,
            'required': self.required,
            'star': self.star,
            'after': self.after_key or '',
            'outline': {
                'what': self.outline_what or '',
                'why': self.outline_why or '',
                'when': self.outline_when or '',
                'prereq': self.outline_prereq or '',
                'mistakes': [m.name for m in self.mistake_ids],
            },
            'lessons': [lesson._lesson_dict() for lesson in self.lesson_ids],
        }

    @api.model
    def _content_tree(self):
        """The language-dependent part of the bundle, in the context language."""
        Station = self.env['learn.station'].sudo()
        return {
            'stations': [s._station_dict() for s in Station.search([])],
            'chrome': self.env['learn.string'].sudo()._as_map(),
            'missions': [m._mission_dict()
                         for m in self.env['learn.mission'].sudo().search([])],
            'glossary': [
                {'key': g.key, 'term': g.term, 'definition': g.definition}
                for g in self.env['learn.glossary.term'].sudo().search([])
            ],
        }

    @api.model
    @tools.ormcache()
    def _content_bundle(self):
        """Both languages, zipped. Content is company-independent, so one cache
        entry per registry is correct — tokens and progress are merged in after.

        `chrome` is zipped SEPARATELY. It is a flat map whose keys are content
        names chosen by the author, and three of them — required, correct,
        after — happen to collide with structural keys in _RAW_KEYS. Running it
        through the structural zipper left those three as bare English, so a
        Vietnamese learner saw "Required" beside "Tùy chọn". Every chrome value
        is prose by definition, so it needs no key-based exceptions at all.
        """
        en = self.with_context(lang='en_US')._content_tree()
        vi = self.with_context(lang='vi_VN')._content_tree()
        return {
            'stations': _zip_bilingual(en['stations'], vi['stations']),
            'glossary': _zip_bilingual(en['glossary'], vi['glossary']),
            'missions': _zip_bilingual(en['missions'], vi['missions']),
            'chrome': _zip_prose(en['chrome'], vi['chrome']),
        }

    @api.model
    def _bundle_version(self):
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'pb_learn')], limit=1)
        stamps = [module.latest_version or '0']
        for model in ('learn.station', 'learn.lesson', 'learn.step',
                      'learn.step.line', 'learn.quiz', 'learn.quiz.option',
                      'learn.string', 'learn.glossary.term',
                      'learn.tenant.override'):
            rec = self.env[model].sudo().search([], order='write_date desc', limit=1)
            stamps.append(str(rec.write_date) if rec else '-')
        stamps.append(str(self.env.company.id))
        return hashlib.sha1('|'.join(stamps).encode()).hexdigest()[:12]

    @api.model
    def _visible_sidebar_item_ids(self):
        """Exactly what the real sidebar shows this user.

        Computed by CALLING get_sidebar_data rather than re-implementing its
        role rule. Re-implementing it would work today and drift the first time
        the gate changes — and the gate lives in the database, where a reader of
        this file cannot see it.
        """
        ids = set()

        def walk(items):
            for item in items:
                ids.add(item['id'])
                walk(item.get('children') or [])

        for section in self.env['pb.sidebar.item'].get_sidebar_data():
            walk(section.get('items') or [])
        return ids

    @api.model
    def get_bundle(self):
        """The one call the frontend makes. Returns both languages."""
        bundle = dict(self._content_bundle())

        visible = self._visible_sidebar_item_ids()
        for station in bundle['stations']:
            key = station['sidebar_key']
            if not key:
                # Teaches something other than a leaf. Visible by definition.
                station['visible'], station['missing'] = True, False
                continue
            item = self.env.ref(key, raise_if_not_found=False)
            if not item:
                # The leaf's module is not installed here. Say so rather than
                # showing a station that opens nothing — an honest "not on
                # this tenant" beats a dead node the learner blames themselves
                # for.
                station['visible'], station['missing'] = False, True
            else:
                station['visible'], station['missing'] = item.id in visible, False

        bundle.update({
            'version': self._bundle_version(),
            'tokens': self.env['learn.tenant.override'].resolved_tokens(),
            'progress': self.env['learn.progress'].my_progress(),
            'confidence': self.env['learn.confidence'].my_scores(),
            'user': {
                'name': self.env.user.name,
                'lang': (self.env.user.lang or 'en_US').startswith('vi') and 'vi' or 'en',
            },
        })
        return bundle
