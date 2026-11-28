# DOCSTUDIO W1B probe (odoo-bin shell; read-only in effect: everything is rolled back).
# As the administrator: the Document studio answers (gallery, one letter opened, the field list,
# people, the page settings, a live preview for a real person in two languages, a sample PDF made by
# the real PDF engine when PROBE_PDF=1). Nothing is saved; prints PROBE lines, never values.
import base64, os
def p(*a):
    print('PROBE', *a)
try:
    admin = env.ref('base.user_admin')
    cids = admin.company_ids.ids
    uenv = env(user=admin.id, context=dict(env.context, allowed_company_ids=cids))
    m = env['ir.module.module'].search([('name', '=', 'pb_doc_studio')])
    p('module', 'pb_doc_studio=%s:%s' % (m.state, m.latest_version) if m else 'pb_doc_studio=absent')
    p('templates', env['pb.letter.template'].sudo().with_context(active_test=False).search_count([]),
      'letters', env['pb.hr.letter'].sudo().search_count([]))
    if 'pb.doc.studio' in env and m.state == 'installed':
        DS = uenv['pb.doc.studio']
        b = DS.board()
        cards = b['cards']
        p('board cards', len(cards), 'kinds', len(b['kinds']), 'edited', sum(1 for c in cards if c['edited']),
          'copies', sum(1 for c in cards if c.get('variant_of')), 'langs', len(b['langs']), 'coach', b['coach'])
        p('page styles', len(DS.page_styles()))
        people = DS.people('')
        p('people offered', len(people))
        card = next((c for c in cards if c.get('key') == 'experience' or 'xperience' in (c.get('name') or '')), cards[0] if cards else None)
        if card and people:
            o = DS.open(card['id'])
            p('open', 'ok', 'keys', len(o) if isinstance(o, dict) else type(o).__name__)
            emp_id = people[0]['id']
            pv = DS.preview(card['id'], {}, emp_id)
            p('preview', 'html chars', len(pv['html']), 'hidden', pv['hidden'], 'missing', len(pv['missing']),
              'lang', pv['lang'], 'read_lang', pv['read_lang'], 'vendor word', 'odoo' in pv['html'].lower())
            other = next((l['code'] for l in b['langs'] if l['code'] != pv['lang']), None)
            if other:
                pv2 = DS.preview(card['id'], {}, emp_id, other)
                p('preview other language', other, 'html chars', len(pv2['html']), 'read_lang', pv2['read_lang'])
            if os.environ.get('PROBE_PDF') == '1':
                pdf = DS.sample_pdf(card['id'], {}, emp_id)
                if pdf.get('ok'):
                    raw = base64.b64decode(pdf['data'])
                    p('sample pdf ok', 'bytes', len(raw), 'is pdf', raw[:5] == b'%PDF-',
                      'vendor in name', 'odoo' in pdf['name'].lower())
                else:
                    p('sample pdf FAILED', pdf.get('msg'))
        p('doc versions', env['pb.doc.version'].sudo().search_count([]))
        p('studio data on templates', env['pb.letter.template'].sudo().with_context(active_test=False).search_count(
            ['|', '|', ('pbds_edited', '=', True), ('pbds_replaces_id', '!=', False), ('pbds_main_lang', '!=', False)]))
        p('letters after', env['pb.hr.letter'].sudo().search_count([]))
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
