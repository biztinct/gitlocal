# DOCSTUDIO W2: owner rulings checked as real logins of payobook.com, inside odoo-bin shell,
# everything ROLLED BACK (precedent S5M-4). Prints PROBE lines: counts and yes/no only.
#  1. view-only people on a contract can download the contract document but not file it;
#  2. offer letter language: unknown -> the hiring company's language; the recruiter's choice wins
#     (board verb offer_letter_lang, the screen twin beside "Which letter").
import base64
from odoo.exceptions import AccessError, UserError


def p(*a):
    print('PROBE', *a)


try:
    def uenv(u):
        cids = [u.company_id.id] + [c for c in u.company_ids.ids if c != u.company_id.id]
        return env(user=u.id, context=dict(env.context, allowed_company_ids=cids))

    qa = env['res.users'].browse(6672)
    k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False),
                                           ('company_id', '=', qa.company_id.id)], order='id', limit=1)
    p('qa', 'contract read', uenv(qa)['pb.contracts']._cd_may_read(),
      'may file', uenv(qa)['pb.contracts']._pbdc_may_file(), 'may design', uenv(qa)['pb.contracts']._pbdc_may_design())
    # view-only candidates: internal, active, may read contracts, may NOT create employee documents
    cands = env['res.users'].search([('share', '=', False), ('active', '=', True), ('id', '>', 2)], order='id')
    viewers = []
    for u in cands:
        e = uenv(u)
        try:
            if e['pb.contracts']._cd_may_read() and not e['pb.contracts']._pbdc_may_file():
                viewers.append(u)
        except Exception:
            pass
    p('view-only users (read contracts, cannot file)', len(viewers), 'ids', ' '.join(str(u.id) for u in viewers[:8]))
    for u in viewers[:2]:
        e = uenv(u)
        kk = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False),
                                                ('company_id', 'in', e.context['allowed_company_ids'])], order='id', limit=1)
        if not kk:
            p('viewer', u.id, 'no contract in their companies'); continue
        C = e['pb.contracts']
        d = C.contract_document(kk.id)
        pdf = C.contract_document_pdf(kk.id)
        sv = C.contract_document_save(kk.id)
        p('viewer', u.id, 'button', C.contract_document_available(kk.id), 'preview ok', d.get('ok'),
          'can_file', d.get('can_file'), 'file message shown', bool(d.get('file_msg')),
          'download ok', pdf.get('ok'), 'is pdf', base64.b64decode(pdf['data'])[:5] == b'%PDF-' if pdf.get('ok') else pdf.get('msg'),
          'filing refused', not sv.get('ok'))
    # offers: language rule
    Off = env['pb.hiring.offer'].sudo()
    offers = Off.search([], order='id')
    rows = []
    for o in offers:
        known = o._pbds_known_lang()
        rows.append('%s:known=%s,writes=%s,company=%s' % (o.id, known or '-', o._pbds_offer_lang(),
                                                          o.company_id.partner_id.lang))
    p('offers language', ' '.join(rows))
    unknown = [o for o in offers if not o._pbds_known_lang()]
    p('unknown language -> company language', all(o._pbds_offer_lang() == o.company_id.partner_id.lang
                                                   or o.company_id.partner_id.lang not in env['pb.doc.studio']._pbds_active_langs()
                                                   for o in unknown), 'of', len(unknown))
    if offers:
        o = next((x for x in offers if x.state in ('draft', 'submitted', 'manager_ok', 'hr_ok')), offers[0])
        other = next((c for c, _n in env['res.lang'].get_installed() if c != o._pbds_offer_lang()), None)
        try:
            with env.cr.savepoint():
                r = uenv(qa)['pb.hiring'].act('offer_letter_lang', {'offer_id': o.id, 'lang': other})
                o.invalidate_recordset()
                p('recruiter choice', 'state', o.state, 'chosen', other, 'now writes in', o._pbds_offer_lang(),
                  'wins', o._pbds_offer_lang() == other, 'note', bool((r or {}).get('note')))
        except (AccessError, UserError) as e:
            p('recruiter choice refused for qa', type(e).__name__, str(e)[:160])
        except Exception as e:
            p('recruiter choice error', type(e).__name__, str(e)[:200])
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
