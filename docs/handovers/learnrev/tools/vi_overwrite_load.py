# odoo shell stdin: overwrite-load Vietnamese for the three modules whose existing msgstrs P1 reworded (LR20).
mods = ['pb_hr_payroll_formula', 'pb_payruns', 'pb_scheme_map']
inst = env['ir.module.module'].search([('name', 'in', mods), ('state', '=', 'installed')]).mapped('name')
env['ir.module.module']._load_module_terms(inst, ['vi_VN'], overwrite=True)
env.cr.commit()
print('VILOAD_DONE', env.cr.dbname, sorted(inst))
