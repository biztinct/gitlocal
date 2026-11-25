# -*- coding: utf-8 -*-
"""Put a module's shipped translations onto the shipped rows already stored.

NEWHIRE P6. A translation fix is two fixes (LOOK rule): the `.po` file AND the
values already in the database. Seeded checklist steps, checklist names and
equipment categories are `noupdate` data, so the words a database already holds
are never re-read from the XML. This helper is called from a module's own
post-migrate script and reads that module's OWN `.po` files (the single source
of the words — no second copy of the translations in Python):

* only `model:` entries of records whose xml id belongs to that module and whose
  model / field is in ``targets``;
* only rows whose stored English still IS the shipped English (the entry's
  msgid). On a white-label tenant the stored English went through the brand
  rewrite, so the shipped English is compared after the same rewrite too;
* only languages that are active on the database, and only where that language
  holds nothing yet, or holds the English words themselves (a fallback copy the
  ORM makes when a record is written in that language);
* never the English itself, never a row a company renamed, never a row a
  company made (no xml id of the module).

Idempotent: a second run finds every language filled and writes nothing.

Note for the next reader (ledger NH78): right after the post-migrate the
framework's own upgrade loads the same `.po` into every shipped row that lacks
a language, WITHOUT comparing the English. This helper does not try to stop
that; the release checks that no shipped row was renamed before it runs.
"""

import logging
import os

from psycopg2.extras import Json

from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)


def _po_rows(module, lang):
    """`model:` rows of ``<module>/i18n/<lang>.po``: (model, field, xmlid, msgid, msgstr)."""
    from odoo.tools.translate import PoFileReader
    path = get_module_path(module)
    po = os.path.join(path, 'i18n', '%s.po' % lang) if path else ''
    if not po or not os.path.isfile(po):
        return []
    out = []
    with open(po, 'rb') as f:
        for row in PoFileReader(f):
            if row.get('type') != 'model' or not row.get('value') or not row.get('src'):
                continue
            model, _sep, field = (row.get('name') or '').partition(',')
            if row.get('module') != module or not row.get('imd_name'):
                continue
            out.append((model, field, '%s.%s' % (module, row['imd_name']),
                        row['src'], row['value']))
    return out


def _brand_rewrite(env):
    """The database's own brand rewrite of a text, or ``None`` when it has none."""
    try:
        from odoo.addons.biz_debrand.models.brand import (
            brand_for_env, debrand_text, product_for_env, product_rules)
    except ImportError:
        return None
    try:
        brand, website = brand_for_env(env)
        product = product_for_env(env)
        if not product_rules(product, brand):
            product = None
    except Exception:                       # noqa: BLE001 — a comparison aid, never a blocker
        return None
    return lambda text: debrand_text(text, brand, website, product)


def _same_as_shipped(stored, shipped, rewrite):
    if stored is None:
        return False
    if stored == shipped:
        return True
    return bool(rewrite) and stored == rewrite(shipped)


def apply_seed_translations(env, module, targets, langs=None):
    """Write the shipped vi/id words onto the shipped rows of ``module``.

    ``targets`` = ``{model_name: [field, ...]}`` (translated `translate=True`
    fields only). Returns ``{'written': n, 'renamed': [(xmlid, field)],
    'missing': [xmlid]}`` — renamed rows are reported, never written.
    """
    active = set(env['res.lang'].sudo().search([('active', '=', True)]).mapped('code'))
    langs = [code for code in (langs or ('vi_VN', 'id_ID')) if code in active and code != 'en_US']
    rewrite = _brand_rewrite(env)
    # (model, field, xmlid) -> {'src': English, lang: words}
    wanted = {}
    for lang in langs:
        for model, field, xmlid, src, value in _po_rows(module, lang):
            if field not in (targets.get(model) or ()):
                continue
            entry = wanted.setdefault((model, field, xmlid), {'src': src})
            entry[lang] = value
    result = {'written': 0, 'renamed': [], 'missing': []}
    for (model, field, xmlid), entry in sorted(wanted.items()):
        if model not in env:
            continue
        Model = env[model].sudo()
        fld = Model._fields.get(field)
        if not fld or fld.translate is not True or not fld.store:
            continue
        record = env.ref(xmlid, raise_if_not_found=False)
        if not record or record._name != model:
            result['missing'].append(xmlid)
            continue
        Model.flush_model([field])
        env.cr.execute('SELECT "%s" FROM "%s" WHERE id = %%s' % (field, Model._table), (record.id,))
        row = env.cr.fetchone()
        stored = (row[0] if row else None) or {}
        if not isinstance(stored, dict):
            continue
        english = stored.get('en_US')
        if not _same_as_shipped(english, entry['src'], rewrite):
            result['renamed'].append((xmlid, field))
            continue
        add = {}
        for lang in langs:
            if lang not in entry:
                continue
            now = stored.get(lang)
            if (now is None or now == english) and now != entry[lang]:
                add[lang] = entry[lang]
        if not add:
            continue
        env.cr.execute(
            'UPDATE "%s" SET "%s" = COALESCE("%s", \'{}\'::jsonb) || %%s WHERE id = %%s'
            % (Model._table, field, field), (Json(add), record.id))
        record.invalidate_recordset([field])
        result['written'] += len(add)
    _logger.info('%s: shipped translations written: %s language values; renamed rows left alone: %s; '
                 'xml ids not found: %s', module, result['written'], result['renamed'] or 'none',
                 result['missing'] or 'none')
    return result
