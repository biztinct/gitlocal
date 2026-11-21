"""Refresh stored usage metadata after correcting comparison operands."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    last_id = 0
    while True:
        rules = env['hr.formula.rule'].search(
            [('column_type', '=', 'formula'), ('id', '>', last_id)],
            order='id', limit=500)
        if not rules:
            break
        rules._compute_formula_operand_roles()
        last_id = rules[-1].id
