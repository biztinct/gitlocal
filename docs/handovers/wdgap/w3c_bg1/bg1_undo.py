# WDGAP W3-C BG1 — UNDO: withdraw the waiting bank-copy batch of this site.
# odoo shell (stdin). Optional prepended LIMIT = <n> withdraws only the first n
# (rehearsal); default all. Uses the product's own withdraw
# (`biz.approval.engine.cancel`, what "take it back" does): every waiting change
# goes back to draft, NOTHING is written to either bank store, and the batch's
# to-dos close (they follow the count, pb_bank_ocr 19.0.1.5.0).
import json

DB = env.cr.dbname  # noqa: F821
KEY = 'bank-gap-copy,%s,2026-11-17' % DB
try:
    LIMIT  # noqa: F821
except NameError:
    LIMIT = 0
Req = env['pb.bank.change.request'].sudo()  # noqa: F821
engine = env['biz.approval.engine'].sudo()  # noqa: F821
waiting = Req.search([('pb_import_key', '=', KEY),
                      ('state', 'in', ('hr_review', 'finance_review'))], order='id')
todo = waiting[:LIMIT] if LIMIT else waiting
done = 0
for r in todo:
    request = r._chain_open_request()
    if request:
        engine.cancel(request, 'Bank-gap copy batch withdrawn')
        done += 1
env.invalidate_all()  # noqa: F821
left = Req.search_count([('pb_import_key', '=', KEY),
                         ('state', 'in', ('hr_review', 'finance_review'))])
print(json.dumps({'db': DB, 'withdrawn': done, 'still_waiting': left,
                  'states': Req.read_group([('pb_import_key', '=', KEY)], ['state'],
                                           ['state'])}, default=str))
env.cr.commit()
print('COMMITTED')
