from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['survey.question']._migrate_question_bank()
