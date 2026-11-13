"""Map rize's "Reporting Manager" column to the employee's Manager (MANAGERCOL §1.7).

With this mapping in place, every import of a pay data file on these schemes
sets each person's manager from the file (pb_orgchart 19.0.1.4.0,
`hr.payroll.import.batch._sync_employee_manager`). Run ON rize ONLY, through
the shell; the service may stay up:

    ODOO="python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d rize --no-http"
    sudo cat tools/map_rize_reporting_manager.py | sudo -u odoo $ODOO                 # dry run
    sudo cat tools/map_rize_reporting_manager.py | sudo -u odoo PB_MGR_APPLY=1 $ODOO  # write

(settings go AFTER `sudo -u odoo`: sudo drops a variable set in front of it.)

The mapping is made through the product's own door,
`pb.formula.studio.employee_mapping_create(config, False, rule, 'f:hr.employee:parent_id')`
— the call the mapping board makes when a person draws the wire — as the admin
user. Never raw SQL. Idempotent: a scheme already mapped this way is left
alone; a scheme whose Manager is mapped from a DIFFERENT column stops the run.

The four schemes are the ones every real Rize client file has been loaded
against and the only ones that carry the column (seed report §Sources): the
"archived master-data" schemes. The active "focused payroll" schemes (since
2026-10-21) do not read the column at all; the run lists them so the gap is
visible (MANAGERCOL_REPORT.md §5).

Undo: delete the printed mapping ids (mapping board: remove the wire, or
`env['pb.formula.studio'].employee_mapping_delete(<id>)`).
"""
import os

from odoo.addons.pb_hr_payroll_formula.models.column_role_classifier import is_manager_header

assert env.cr.dbname == 'rize', 'Rize-only configuration task.'  # noqa: F821

TARGETS = {4760: 'VN', 7096: 'ID', 6382: 'IN', 7095: 'SG'}
SPEC = 'f:hr.employee:parent_id'


def manager_rules(cfg):
    return cfg.rule_ids.filtered(
        lambda r: r.column_type == 'input'
        and (is_manager_header(r.name) or is_manager_header(r.data_source_field)))


def manager_mapping(env, cfg):
    return env['hr.payslip.import.mapping'].sudo().search([
        ('salary_structure_id', '=', cfg.id), ('destination_type', '=', 'field'),
        ('target_model_id.model', '=', 'hr.employee'),
        ('target_field_id.name', '=', 'parent_id')])


def main(env):
    admin = env.ref('base.user_admin')
    env = env(user=admin.id, context=dict(
        env.context, allowed_company_ids=env['res.company'].search([]).ids))
    apply = os.environ.get('PB_MGR_APPLY') == '1'
    Config = env['hr.formula.config'].with_context(active_test=False)
    Studio = env['pb.formula.studio']

    done = []
    for cid, cc in TARGETS.items():
        cfg = Config.browse(cid).exists()
        assert cfg, 'scheme %s is gone' % cid
        assert cfg.country_code == cc, 'scheme %s is %s, expected %s' % (cid, cfg.country_code, cc)
        rules = manager_rules(cfg)
        assert len(rules) == 1, 'scheme %s: %d manager columns (%s)' % (
            cid, len(rules), ', '.join(rules.mapped('name')))
        existing = manager_mapping(env, cfg)
        if existing and existing.component_id == rules:
            print('ALREADY [%s] %s: mapping %s  %s -> Manager'
                  % (cc, cfg.name, existing.id, rules.name))
            done.append((cc, cfg, existing))
            continue
        if existing:
            raise SystemExit('STOP: [%s] %s already maps Manager from "%s" (mapping %s)'
                             % (cc, cfg.name, existing.component_id.name, existing.ids))
        res = Studio.employee_mapping_create(cfg.id, False, rules.id, SPEC)
        assert res.get('ok'), 'scheme %s refused: %s' % (cid, res)
        made = manager_mapping(env, cfg)
        assert len(made) == 1 and made.component_id == rules, made
        print('MAPPED  [%s] %s: mapping %s  %s (rule %s %s) -> Manager%s'
              % (cc, cfg.name, made.id, rules.name, rules.id, rules.code,
                 ('  note: %s' % res['msg']) if res.get('msg') else ''))
        done.append((cc, cfg, made))

    print('\nACTIVE SCHEMES and whether they read a manager column:')
    for cfg in Config.search([('state', '=', 'active')], order='id'):
        rules = manager_rules(cfg)
        print('  %s %s [%s]: %s; mapped: %s' % (
            cfg.id, cfg.name, cfg.country_code,
            ', '.join(rules.mapped('name')) or 'NO manager column',
            manager_mapping(env, cfg).ids or 'no'))

    print('\nMAPPINGS:', ', '.join('%s=%s' % (cc, m.id) for cc, _c, m in done))
    if not apply:
        env.cr.rollback()
        print('DRY RUN - nothing written. Add PB_MGR_APPLY=1 after `sudo -u odoo` to write.')
        return
    env.cr.commit()
    print('WRITTEN.')


main(env)  # noqa: F821 - `env` comes from odoo-bin shell
