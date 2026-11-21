#!/usr/bin/env python3
"""LEARNREV P4 T1 — negative controls for the four-line step gates.

    python3 docs/tutorial_poc/author/tools/test_step_shape.py

Each gate the generator added in P4 gets a fixture that breaks exactly it, and
a positive control last (a gate that refused everything would pass the rest):

  * a `look` step without `means` / `affects` fails;
  * `press` on a `rep-*` (practice copy) or an unknown anchor fails;
  * a `field:` reference to something no manifest describes fails, and a field
    step may not author its own `means` / `affects`;
  * country `variants` must carry `generic`, and only the lines a variant may set;
  * a real field step gets its "It means" from the field's own help and its
    "It affects" from what changing it does, with the first three readers.

Pure functions of the authoring tree and the manifest export: no odoo-bin.
Exit status 1 on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_learn_data as gen                                      # noqa: E402
import export_manifests                                           # noqa: E402

FAILED = []
P = lambda en, vi=None: {'en': en, 'vi': vi or ('VI ' + en)}      # noqa: E731
PRODUCT = gen._product_anchors()


def case(label, ok):
    print('  %s %s' % ('ok  ' if ok else 'FAIL', label))
    if not ok:
        FAILED.append(label)


def shape(step, anchor=''):
    problems = []
    gen._shape_problems('probe', step, anchor, PRODUCT, problems)
    return problems


four = {'look': P('Look at the header.'), 'means': P('It means this.'),
        'affects': P('It affects that.')}

# -- look needs means and affects ------------------------------------------
case('look without means fails',
     any('must also say' in p for p in shape({'look': P('Look.'), 'affects': P('x.')})))
case('look without affects fails',
     any('must also say' in p for p in shape({'look': P('Look.'), 'means': P('x.')})))
case('the four lines pass', not shape(dict(four), 'tr-head'))

# -- press only on a real control --------------------------------------------
case('press on a rep-* anchor fails',
     any('real product anchor' in p for p in shape(dict(four, press=P('Press it.')), 'rep-ct-warn')))
case('press on an unknown anchor fails',
     any('real product anchor' in p for p in shape(dict(four, press=P('Press it.')), 'no-such-anchor')))
case('press with no anchor fails',
     any('real product anchor' in p for p in shape(dict(four, press=P('Press it.')), '')))
case('press on a retired anchor fails',
     any('real product anchor' in p for p in shape(dict(four, press=P('Press it.')), 'fs-views')))
case('press on a product anchor passes', not shape(dict(four, press=P('Press it.')), 'tr-head'))
case('press inside a variant is gated too',
     any('real product anchor' in p for p in shape(dict(four, variants={
         'generic': {'press': P('Press.')}}), 'rep-ct-warn')))

# -- variants ------------------------------------------------------------------
case('a country variant without generic fails',
     any('generic' in p for p in shape(dict(four, variants={'ID': {'means': P('BPJS.')}}), 'tr-head')))
case('an unknown country key fails',
     any('unknown variant' in p for p in shape(dict(four, variants={
         'XX': {'means': P('x.')}, 'generic': {'means': P('y.')}}), 'tr-head')))
case('a variant may not set a title',
     any('may not set' in p for p in shape(dict(four, variants={
         'generic': {'title': P('x.')}}), 'tr-head')))
case('generic + ID variants pass', not shape(dict(four, variants={
    'ID': {'means': P('BPJS.')}, 'generic': {'means': P('Insurance.')}}), 'tr-head'))

# -- field steps ---------------------------------------------------------------
MAN = export_manifests.export()
data = {'lessons': {'LX': {'steps': [
    {'field': 'treatment.pay_role', 'look': P('Look at the Pay role column.')},
    {'field': 'treatment.no_such_field', 'look': P('Look.')},
    {'field': 'treatment.rollup', 'look': P('Look.'), 'means': P('Authored.')},
]}}, 'scenarios': []}
problems = gen.fill_field_steps(data, MAN)
case('a field reference no manifest describes fails',
     any('no_such_field' in p and 'not a field' in p for p in problems))
case('a field step may not author its means',
     any('does not author' in p for p in problems))
good = data['lessons']['LX']['steps'][0]
pay_role = MAN['treatment']['fields']['pay_role']
case('a field step means = the field help, first sentence',
     good.get('means', {}).get('en') == gen._first(pay_role['help']['en'])
     and good['means']['vi'] == gen._first(pay_role['help']['vi']))
case('a field step affects = what changing it does',
     good.get('affects') == pay_role['if_changed'])
case('a field step uses = the first three readers',
     [u['en'] for u in good.get('uses') or []] == [u['en'] for u in pay_role['used_by'][:3]])
case('a filled field step passes the shape gate', not shape(good, 'tr-col-role'))

# -- the shipped authoring source passes every gate ------------------------------
real = gen.dump()
problems = gen.fill_field_steps(real, MAN)
case('the authoring source has no field-step problem: %s' % problems[:2], not problems)
bad = []
for lkey, lesson in real['lessons'].items():
    for i, st in enumerate(lesson['steps']):
        bad += shape(st, st.get('anchor') or '')
case('the authoring source has no shape problem: %s' % bad[:2], not bad)

print('%d failed' % len(FAILED))
sys.exit(1 if FAILED else 0)
