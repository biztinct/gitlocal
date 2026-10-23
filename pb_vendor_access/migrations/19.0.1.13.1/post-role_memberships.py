from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    # Product membership registration is available after its own module loads.
    api.Environment(cr, SUPERUSER_ID, {})['pb.access']._migrate_assignments(include_memberships=True)
