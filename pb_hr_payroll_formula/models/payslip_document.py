"""Validated, non-executable visual payslip documents and their shared renderer.

The page artwork is an embedded JPEG; fields use PDF points with a top-left
origin. Only bindings to this scheme's components and the fixed metadata
vocabulary are accepted. Source amounts are never used as payroll values.
"""
import base64
import hashlib
import html
import io
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP, Context

from PIL import Image


FONTS = {'serif': 'DejaVuSerif', 'sans': 'DejaVuSans', 'mono': 'DejaVuSansMono'}
FORMATS = ('auto', 'number', 'integer', 'decimal', 'currency', 'percentage', 'text')


def revision(document):
    return hashlib.sha256(json.dumps(document or {}, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def finite(value, default=0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def colour(value, default='#ffffff'):
    return value.lower() if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) else default


def validate_document(document, rule_ids, meta_keys):
    if not isinstance(document, dict) or document.get('version') != 1:
        raise ValueError('Unsupported payslip document version.')
    pages = document.get('pages')
    if not isinstance(pages, list) or not 1 <= len(pages) <= 8:
        raise ValueError('Use a document with 1 to 8 pages.')
    result = {'version': 1, 'name': str(document.get('name') or 'Payslip')[:128], 'pages': []}
    image_bytes = 0
    ids = set()
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError('Invalid payslip page.')
        width, height = finite(page.get('width')), finite(page.get('height'))
        if not (72 <= width <= 1800 and 72 <= height <= 2400):
            raise ValueError('Invalid page dimensions.')
        image = str(page.get('image') or '')
        if len(image) > 17 * 1024 * 1024:
            raise ValueError('The page artwork is too large.')
        if not image.startswith('data:image/jpeg;base64,'):
            raise ValueError('The page artwork must be a JPEG image.')
        try:
            raw = base64.b64decode(image.split(',', 1)[1], validate=True)
            image_bytes += len(raw)
            if image_bytes > 12 * 1024 * 1024:
                raise ValueError('The combined page artwork must be 12 MB or smaller.')
            with Image.open(io.BytesIO(raw)) as picture:
                if picture.format != 'JPEG' or picture.width * picture.height > 20_000_000:
                    raise ValueError('Invalid or oversized page artwork.')
                if abs(picture.width / picture.height - width / height) > .03:
                    raise ValueError('Page artwork and page dimensions do not agree.')
                picture.verify()
        except (OSError, base64.binascii.Error) as error:
            raise ValueError('The page artwork could not be read.') from error
        fields = page.get('fields', [])
        if not isinstance(fields, list) or len(fields) > 250:
            raise ValueError('Use at most 250 fields per page.')
        clean = {'width': width, 'height': height, 'image': image, 'fields': []}
        for index, field in enumerate(fields):
            if not isinstance(field, dict):
                raise ValueError('Invalid document field.')
            ident = str(field.get('id') or 'p%s-f%s' % (page_index + 1, index + 1))
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident) or ident in ids:
                raise ValueError('Document field identifiers must be unique.')
            ids.add(ident)
            x = max(0, min(width - 1, finite(field.get('x'))))
            y = max(0, min(height - 1, finite(field.get('y'))))
            binding = field.get('binding') if field.get('binding') in ('component', 'meta', 'text', 'blank') else 'blank'
            rule_id = int(finite(field.get('rule_id')))
            rate_id = int(finite(field.get('rate_rule_id')))
            if binding == 'component' and rule_id not in rule_ids:
                raise ValueError('A field refers to a component outside this configuration.')
            if rate_id and rate_id not in rule_ids:
                raise ValueError('An exchange rate refers to a component outside this configuration.')
            meta_key = str(field.get('meta_key') or '')
            if binding == 'meta' and meta_key not in meta_keys:
                raise ValueError('Unknown employee or period field.')
            clean['fields'].append({
                'id': ident, 'label': str(field.get('label') or 'Field')[:240],
                'x': round(x, 3), 'y': round(y, 3),
                'w': round(max(1, min(width - x, finite(field.get('w'), 100))), 3),
                'h': round(max(1, min(height - y, finite(field.get('h'), 18))), 3),
                'binding': binding, 'rule_id': rule_id if binding == 'component' else False,
                'meta_key': meta_key if binding == 'meta' else '',
                'text': str(field.get('text') or '')[:2000],
                'rate_rule_id': rate_id or False,
                'rate_operation': 'multiply' if field.get('rate_operation') == 'multiply' else 'divide',
                'format': field.get('format') if field.get('format') in FORMATS else 'auto',
                'decimals': max(0, min(6, int(finite(field.get('decimals'), 0)))),
                'currency': str(field.get('currency') or '')[:8],
                'font': field.get('font') if field.get('font') in FONTS else 'serif',
                'font_size': max(4, min(72, finite(field.get('font_size'), 10))),
                'bold': bool(field.get('bold')), 'italic': bool(field.get('italic')),
                'align': field.get('align') if field.get('align') in ('left', 'center', 'right') else 'right',
                'color': colour(field.get('color'), '#111111'),
                'background': colour(field.get('background')),
                'cover': field.get('cover') is not False,
                'empty': str(field.get('empty') if field.get('empty') is not None else '—')[:40],
            })
        result['pages'].append(clean)
    return result


def field_value(field, rules, values, currency, meta, auto_format):
    binding = field['binding']
    if binding == 'text':
        return re.sub(r'\{\{pb_meta:([a-z_]+)\}\}',
                      lambda m: str(meta.get(m[1]) or field['empty']), field['text'])
    if binding == 'meta':
        return str(meta.get(field['meta_key']) or field['empty'])
    if binding != 'component':
        return field['empty']
    rule = rules.get(field['rule_id'])
    value = values.get(field['rule_id'])
    if rule is None or value is None or value == '':
        return field['empty']
    if field['rate_rule_id']:
        rate = finite(values.get(field['rate_rule_id']))
        if rate <= 0:
            return field['empty']
        try:
            value = float(value) * rate if field['rate_operation'] == 'multiply' else float(value) / rate
        except (TypeError, ValueError):
            return field['empty']
    if field['format'] == 'auto' and not field['rate_rule_id']:
        return auto_format(rule, value, currency)
    if field['format'] == 'text':
        return str(value)
    try:
        number = float(value)
        if not math.isfinite(number):
            return field['empty']
    except (TypeError, ValueError):
        return str(value)
    if field['format'] == 'percentage':
        number *= 100
    decimals = 0 if field['format'] == 'integer' else field['decimals']
    rounded = Decimal(str(number)).quantize(
        Decimal(1).scaleb(-decimals), context=Context(prec=400, rounding=ROUND_HALF_UP))
    output = ('{:,.%sf}' % decimals).format(rounded)
    if field['format'] == 'percentage':
        return output + '%'
    return (field['currency'] + output) if field['format'] == 'currency' else output


def render_pages(document, rules, values, currency, meta, auto_format):
    pages = []
    for page in document.get('pages', []):
        rendered = dict(page, fields=[])
        for field in page['fields']:
            value = field_value(field, rules, values, currency, meta, auto_format)
            size, lines = fit_text(value, field)
            rendered['fields'].append(dict(field, value='\n'.join(lines), font_size=size))
        pages.append(rendered)
    return pages


def render_html(pages):
    parts = []
    stacks = {'serif': "'PB Payslip Serif','Times New Roman',serif",
              'sans': "'PB Payslip Sans',Arial,sans-serif", 'mono': "'PB Payslip Mono',monospace"}
    for page in pages:
        parts.append('<div class="pb-payslip-document-page" style="position:relative;width:%spt;height:%spt;overflow:hidden;page-break-after:always">'
                     '<img alt="Payslip artwork" src="%s" style="position:absolute;inset:0;width:100%%;height:100%%"/>' %
                     (page['width'], page['height'], page['image']))
        for field in page['fields']:
            style = ('position:absolute;box-sizing:border-box;left:%spt;top:%spt;width:%spt;height:%spt;'
                     'font-size:%spt;font-family:%s;font-weight:%s;font-style:%s;text-align:%s;'
                     'color:%s;background:%s;overflow:hidden;white-space:pre-wrap;line-height:1.15;padding:1pt 2pt') % (
                         field['x'], field['y'], field['w'], field['h'], field['font_size'],
                         stacks[field['font']], 'bold' if field['bold'] else 'normal',
                         'italic' if field['italic'] else 'normal', field['align'], field['color'],
                         field['background'] if field['cover'] else 'transparent')
            parts.append('<div style="%s">%s</div>' % (html.escape(style, quote=True), html.escape(field['value'])))
        parts.append('</div>')
    return ''.join(parts)


def register_fonts():
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_root = Path(__file__).resolve().parent.parent / 'static' / 'fonts' / 'dejavu'
    for family, filename in FONTS.items():
        for bold, italic in ((False, False), (True, False), (False, True), (True, True)):
            suffix = ('-BoldOblique' if bold and italic else '-Bold' if bold else '-Oblique' if italic else '')
            if family == 'serif':
                suffix = suffix.replace('Oblique', 'Italic')
            font_name = 'PBPS-%s-%s-%s' % (family, int(bold), int(italic))
            if font_name not in pdfmetrics.getRegisteredFontNames():
                font_path = font_root / (filename + suffix + '.ttf')
                if not font_path.exists():
                    raise ValueError('Install the DejaVu fonts to print visual payslip documents.')
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def fit_text(text, field):
    from reportlab.pdfbase import pdfmetrics
    register_fonts()
    font = 'PBPS-%s-%s-%s' % (field['font'], int(field['bold']), int(field['italic']))
    size = field['font_size']
    while True:
        lines = []
        for paragraph in str(text).split('\n'):
            line = ''
            for word in paragraph.split(' '):
                candidate = (line + ' ' + word).strip()
                if line and pdfmetrics.stringWidth(candidate, font, size) > field['w'] - 4:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        if size <= 4 or (len(lines) * size * 1.15 <= field['h'] - 2 and
                         all(pdfmetrics.stringWidth(line, font, size) <= field['w'] - 4 for line in lines)):
            return size, lines
        size = max(4, size - .25)


def render_pdf(pages):
    """Native page sizes, embedded Unicode fonts, no browser or external URLs."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import ImageReader
    register_fonts()
    out = io.BytesIO()
    pdf = canvas.Canvas(out, pageCompression=1)
    pdf.setTitle('Payslip')
    for page in pages:
        width, height = page['width'], page['height']
        pdf.setPageSize((width, height))
        artwork = base64.b64decode(page['image'].split(',', 1)[1])
        pdf.drawImage(ImageReader(io.BytesIO(artwork)), 0, 0, width, height)
        for field in page['fields']:
            x, y, w, h = field['x'], height - field['y'] - field['h'], field['w'], field['h']
            if field['cover']:
                pdf.setFillColor(HexColor(field['background']))
                pdf.rect(x, y, w, h, stroke=0, fill=1)
            pdf.saveState()
            path = pdf.beginPath()
            path.rect(x, y, w, h)
            pdf.clipPath(path, stroke=0, fill=0)
            font = 'PBPS-%s-%s-%s' % (field['font'], int(field['bold']), int(field['italic']))
            size, lines = fit_text(field['value'], field)
            pdf.setFont(font, size)
            pdf.setFillColor(HexColor(field['color']))
            baseline = y + h - size - 1
            for line in lines:
                if field['align'] == 'right':
                    pdf.drawRightString(x + w - 2, baseline, line)
                elif field['align'] == 'center':
                    pdf.drawCentredString(x + w / 2, baseline, line)
                else:
                    pdf.drawString(x + 2, baseline, line)
                baseline -= size * 1.15
            pdf.restoreState()
        pdf.showPage()
    pdf.save()
    return out.getvalue()
