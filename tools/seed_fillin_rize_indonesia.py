"""FILLIN P1 — set the usual answers and the words on rize's Indonesia flags.

Run ON rize ONLY, through the shell:

    sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d rize --no-http < tools/seed_fillin_rize_indonesia.py

What it does, on scheme 7121 "Rize Indonesia Payroll — focused payroll" only:

    IDBPJSTKCOVERE  usual answer 1   words 0=No;1=Yes
    IDBPJSHEALCOVE  usual answer 1   words 0=No;1=Yes
    IDERREIMBUBPJS  usual answer 0   words 0=No;1=Yes
    IDTAXALLOWMODE  usual answer 1   words 0=None;1=Insurance-premium tax only;2=All tax (net salary)

Idempotent (writes a field only when it differs). Touches the four RULES and
nothing else: it proves no contract component line changed by comparing the
line count and the newest write date before and after, and refuses to commit
if either moved. Changing a usual answer never changes an existing contract
(FILLIN ledger D1); only contracts created from now on are filled in.
"""

assert env.cr.dbname == 'rize', 'This seed belongs to the rize tenant only.'

SCHEME_ID = 7121
YES_NO = '0=No;1=Yes'
SPEC = {
    'IDBPJSTKCOVERE': {'default_value': 1.0, 'value_labels': YES_NO},
    'IDBPJSHEALCOVE': {'default_value': 1.0, 'value_labels': YES_NO},
    'IDERREIMBUBPJS': {'default_value': 0.0, 'value_labels': YES_NO},
    'IDTAXALLOWMODE': {
        'default_value': 1.0,
        'value_labels': '0=None;1=Insurance-premium tax only;'
                        '2=All tax (net salary)'},
}


def lines_fingerprint():
    env.cr.execute('SELECT count(*), max(write_date) FROM hr_contract_advantage')
    return env.cr.fetchone()


def show(label):
    print('--- %s' % label)
    for code in SPEC:
        rule = env['hr.formula.rule'].sudo().search(
            [('config_id', '=', SCHEME_ID), ('code', '=', code)], limit=1)
        print('%-16s id=%-6s default_value=%-4s value_labels=%r' % (
            code, rule.id, rule.default_value, rule.value_labels or ''))


config = env['hr.formula.config'].sudo().browse(SCHEME_ID).exists()
assert config, 'scheme %s not found' % SCHEME_ID
assert config.country_code == 'ID', config.country_code
assert config.state == 'active', config.state
print('scheme %s %r state=%s' % (config.id, config.name, config.state))

env.flush_all()
before = lines_fingerprint()
print('contract lines before: count=%s max(write_date)=%s' % before)
show('before')

result = config._pb_apply_usual_answers(SPEC)
print('written: %s' % (result['written'] or 'nothing (already set)'))
assert not result['missing'], 'missing rules: %s' % result['missing']

env.flush_all()
after = lines_fingerprint()
show('after')
print('contract lines after:  count=%s max(write_date)=%s' % after)
if after != before:
    env.cr.rollback()
    raise SystemExit('ABORTED: a contract component line changed; rolled back')

env.cr.commit()
print('committed')
