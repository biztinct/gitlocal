# NEWHIRE P6 release gate (read-only): is any SHIPPED row this release translates renamed on a live
# database? The upgrade's own translation loader fills a missing language on every shipped row without
# comparing the English (ledger NH78), so a renamed row would get our words: the release stops if one
# exists. A row whose English differs only by the database's brand rewrite (white-label tenants: the
# product word replaced by the brand) counts as unchanged - the migration treats it the same way.
# Root: python3 nh6_shipped.py <staged addons dir>   -> one line per database, "renamed: none" expected
import glob, os, subprocess, sys
sys.path.insert(0, '/odoo/odoo-server')
import logging
logging.disable(logging.CRITICAL)
from odoo.tools.translate import PoFileReader

STAGE = sys.argv[1]
DBS = ('payobook', 'payobook_template', 'p0clone', 'rize', 'sudima')
TARGETS = {'pb_onboarding': {'pb.journey.template': ['name'], 'pb.journey.template.step': ['name', 'description']},
           'pb_training': {'pb.journey.template.step': ['name', 'description']},
           'pb_goals': {'pb.journey.template.step': ['name', 'description']},
           'pb_assets': {'pb.asset.category': ['name']}}
TABLE = {'pb.journey.template': 'pb_journey_template', 'pb.journey.template.step': 'pb_journey_template_step',
         'pb.asset.category': 'pb_asset_category'}


def psql(db, sql):
    r = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-X', '-At', '-d', db, '-c', sql],
                       capture_output=True, text=True)
    return r.stdout.strip()


rows = {}
for module, targets in TARGETS.items():
    with open(os.path.join(STAGE, module, 'i18n', 'vi_VN.po'), 'rb') as f:
        for r in PoFileReader(f):
            model, _s, field = r['name'].partition(',')
            if r['type'] == 'model' and r['module'] == module and field in targets.get(model, ()):
                rows[(model, field, module, r['imd_name'])] = r['src']
for db in DBS:
    brand = psql(db, "select value from ir_config_parameter where key='biz_debrand.brand_name'")
    product = psql(db, "select value from ir_config_parameter where key='biz_debrand.product_name'")
    renamed, branded, missing = [], [], []
    for (model, field, module, name), src in sorted(rows.items()):
        rid = psql(db, "select res_id from ir_model_data where module='%s' and name='%s' and model='%s'" % (module, name, model))
        if not rid:
            missing.append('%s.%s' % (module, name))
            continue
        typ = psql(db, "select data_type from information_schema.columns where table_name='%s' and column_name='%s'" % (TABLE[model], field))
        expr = '"%s"->>\'en_US\'' % field if typ == 'jsonb' else '"%s"' % field
        en = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-X', '-At', '-d', db, '-c',
                             'select %s from %s where id=%s' % (expr, TABLE[model], rid)],
                            capture_output=True, text=True).stdout.rstrip('\n')
        if en == src:
            continue
        if product and brand and en == src.replace(product, brand):
            branded.append('%s.%s:%s' % (module, name, field))
            continue
        renamed.append('%s.%s:%s=%r' % (module, name, field, en[:60]))
    print('%s: shipped rows %s; renamed: %s; brand-rewritten only: %s; not on this database: %s' % (
        db, len(rows), renamed or 'none', branded or 'none', missing or 'none'))
