# DOCSTUDIO W1B: phase F's R1 golden script (copy of the phase-F scratch golden.py), run before and
# after `-i pb_doc_studio` on the hidden rehearsal copy and the local test database ONLY — it creates
# letters (rolled back) and would spend letter sequence numbers on a live database.
# Template rows md5(name/subject/body) + rendered HTML md5 of 9 shipped letters (test mode: no PDF engine).
# usage: ... shell -d DB < w1b_golden.py > out.txt
import hashlib
from odoo.tools import config
config['test_enable'] = True
import json
OUT = {}
env.cr.execute("SELECT id, md5(body_html::text), md5(coalesce(subject::text,'')), md5(name::text), active, company_id FROM pb_letter_template ORDER BY id")
OUT['templates'] = [list(r) for r in env.cr.fetchall()]
emp = env['hr.employee'].search([('contract_ids', '!=', False)], order='id', limit=1) or env['hr.employee'].search([], order='id', limit=1)
refs = ['pb_lifecycle.letter_template_experience', 'pb_lifecycle.letter_template_probation_pass',
        'pb_lifecycle.letter_template_incentive', 'pb_probation.letter_template_probation_extend',
        'pb_probation.letter_template_probation_fail', 'pb_contract_lifecycle.letter_template_extension',
        'pb_pip.letter_template_pip', 'pb_offboarding.letter_template_ff_cover',
        'pb_me_letters.letter_template_employment_cert']
OUT['letters'] = {}
for ref in refs:
    t = env.ref(ref, raise_if_not_found=False)
    if not t:
        continue
    letter = env['pb.hr.letter'].sudo().with_context(lang='en_US').create({
        'employee_id': emp.id, 'template_id': t.id, 'subject': t.subject,
        'context_json': json.dumps({'extra': 'GOLDEN extra', 'new_trial_end': '2026-12-01'})})
    try:
        letter.with_context(lang='en_US').action_generate()
        OUT['letters'][ref] = [hashlib.md5(str(letter.rendered_html).encode()).hexdigest(),
                               letter.template_id.id, len(str(letter.rendered_html))]
    except Exception as exc:
        OUT['letters'][ref] = ['ERROR %s' % exc]
print('GOLDEN ' + json.dumps(OUT, sort_keys=True))
env.cr.rollback()
