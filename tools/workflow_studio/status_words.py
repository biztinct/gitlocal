"""WF2 P4b (D12): every area's status words, side by side. Changes nothing.

Run through `odoo-bin shell -d <db> < tools/workflow_studio/status_words.py`.
Prints, per area and status value: the word Workflow Studio uses (the area's
contract), the word(s) the employee home uses (My requests, and the area's
own request page where it has one), and the word(s) on the area's own staff
screens (the status field's labels, plus any screen that words it itself).
Reads only; the transaction is rolled back.
"""
import json
import os
import re

from odoo.modules.module import get_module_path

AREAS = [
    ('pb.expense.claim', 'Expense claim'),
    ('hr.leave', 'Time off'),
    ('biz.approval.generic.request', 'Other request'),
    ('hr.payslip.run', 'Pay run'),
    ('hr.applicant', 'Candidate'),
]


def inline_words(module, relpath, anchor):
    """A {value: word} dict a screen writes inline (read from the source,
    so the tool needs no record of that status to exist)."""
    path = get_module_path(module)
    if not path:
        return {}
    text = open(os.path.join(path, relpath), encoding='utf-8').read()
    at = text.find(anchor)
    if at < 0:
        return {}
    block = text[at:text.find('}', at) + 1]
    return dict(re.findall(r"'(\w+)':\s*_\('([^']*)'\)", block))


studio = env['pb.workflow.studio'].sudo()
home = env['pb.me.home'].sudo()
sources = {}
for src in home._my_requests_sources():
    sources.setdefault(src['model'], {}).update({k: v[0] for k, v in src['states'].items()})
claim_page = {k: v[0] for k, v in env['pb.me.expense']._labels().items()} if 'pb.me.expense' in env else {}
screens = {
    'hr.leave': ('Time off board', inline_words('pb_timeoff', 'models/pb_timeoff.py', 'state_label = {')),
}
out = []
for model, label in AREAS:
    if model not in env:
        continue
    contract = studio._contract(model)
    field = contract.get('stage_field') or 'state'
    selection = {}
    info = env[model]._fields.get(field)
    if info is not None and info.type == 'selection':
        selection = dict(info._description_selection(env))
    for stage in contract['stages']:
        key = str(stage['key'])
        row = {'area': label, 'value': key, 'studio': stage['name'],
               'home_my_requests': sources.get(model, {}).get(key, ''),
               'home_request_page': claim_page.get(key, '') if model == 'pb.expense.claim' else '',
               'screen_field': selection.get(key, stage['name'] if info is not None and info.type == 'many2one' else ''),
               'screen_other': ''}
        if model in screens:
            name, words = screens[model]
            row['screen_other'] = ('%s: %s' % (name, words[key])) if key in words else ''
        words = {w for w in (row['studio'], row['home_my_requests'], row['home_request_page'], row['screen_field'],
                             row['screen_other'].split(': ', 1)[-1]) if w}
        row['differs'] = len(words) > 1
        out.append(row)
print('STATUS_WORDS=' + json.dumps(out, ensure_ascii=False))
for row in out:
    print('%-14s %-12s studio=%-24r my_requests=%-26r page=%-24r field=%-22r other=%r%s' % (
        row['area'], row['value'], row['studio'], row['home_my_requests'], row['home_request_page'],
        row['screen_field'], row['screen_other'], '   <- differs' if row['differs'] else ''))
env.cr.rollback()
