# FS-12: publish a My Payobook page as the site administrator (odoo-bin shell).
#   rehearsal copies (default): a section with two standard fields + a banner, COMMITTED on the
#   copy (the copy is dropped after), so the probe can open the pages with a page published.
#   PUBLISH_DEMO=1 (payobook.com only): the showcase the handover asks for — today's page plus
#   one "DEMO" section with "DEMO Shirt size" and two standard fields, and a banner. Kept.
# Prints counts only.
import base64
import os
import struct
import zlib

admin = env.ref('base.user_admin')
if not admin.has_group('base.group_system'):
    admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
        lambda u: u.has_group('base.group_system'))[:1]
S = env['pb.form.studio'].with_user(admin).with_context(
    allowed_company_ids=env['res.company'].search([]).ids)


def png(w, h, rgb):
    """A plain banner picture: one colour from the locked palette, a lighter band."""
    rows = []
    for y in range(h):
        c = rgb if y < h * 0.62 else tuple(min(255, v + 40) for v in rgb)
        rows.append(b'\x00' + bytes(c) * w)
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))


data = S.page_studio()
spec = data['standard']
fields_ = data['fields']
demo = os.environ.get('PUBLISH_DEMO') == '1'
items = []
if demo:
    shirt = next((n for n, f in fields_.items() if f['custom'] and f['label'] == 'DEMO Shirt size'), None)
    if shirt:
        items.append({'name': shirt, 'width': 'half'})
for name in ('mobile_phone', 'birthday'):
    if name in fields_ and len(items) < 3:
        items.append({'name': name, 'width': 'half'})
spec['sections'].append({'id': 'demo', 'cols': 2, 'fields': items,
                         'title': {'en_US': 'DEMO About me', 'vi_VN': 'DEMO Về tôi',
                                   'id_ID': 'DEMO Tentang saya'}})
banner = S.page_upload_banner('banner.png', base64.b64encode(png(1200, 240, (90, 75, 176))).decode())
spec['header']['banner'] = banner['id']
spec['header']['tint'] = 'brand'
spec['header']['banner_alt'] = {'en_US': 'DEMO banner', 'vi_VN': 'DEMO ảnh bìa', 'id_ID': 'DEMO spanduk'}
res = S.page_publish({'spec': spec, 'companies': {}, 'updates': {}, 'base_version': data['version'],
                      'changes': ['DEMO page' if demo else 'Rehearsal page']})
env.cr.commit()
print('PUB ok %s version %s sections %s fields %s shirt %s' % (
    res.get('ok'), res.get('version'), len(spec['sections']),
    sum(len(s['fields']) for s in spec['sections']), bool(demo and items and items[0]['name'].startswith('x_'))))
