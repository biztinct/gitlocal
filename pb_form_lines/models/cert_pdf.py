# -*- coding: utf-8 -*-
"""One person's year-end certificate as a PDF (WDGAP S2-B).

Drawn with the PDF library the payslip designer already uses (ReportLab, with
the DejaVu fonts shipped in `pb_hr_payroll_formula/static/fonts/dejavu`), not
through the browser engine: so the file is the same on every server, a test
can read it on a machine with no PDF engine (ledger S9A-4), and every word of
its metadata is set here — title, author, subject, creator AND producer
(ledger S5M-5: a framework default title is a white-label leak).

`build(spec) -> bytes` takes a plain dict, so each country's renderer only
says WHAT goes on the certificate:

    {
      'title': str, 'subtitle': str, 'official': str, 'author': str,
      'mark': str,                         # adviser sentence or ''
      'banner': str,                       # e.g. "Information copy" or ''
      'blocks': [{'title': str, 'rows': [(label, value), ...]}],
      'tables': [{'title': str, 'head': [str, str, str],
                  'rows': [(code, label, amount_text, kind)]}],
                                           # kind: '' | 'total' | 'note'
      'notes': [str], 'footer': str,
    }
"""
import io

PRIMARY = '#5A4BB0'
INK = '#1F2433'
MUTED = '#6B7280'
LINE = '#E3E5EE'
TINT = '#F4F3FB'
AMBER_BG = '#FFF7E6'
AMBER = '#B45309'

FONT = 'PBPS-sans-0-0'
FONT_BOLD = 'PBPS-sans-1-0'


def _fonts():
    from odoo.addons.pb_hr_payroll_formula.models.payslip_document import register_fonts
    register_fonts()


def _esc(text):
    return (str(text if text is not None else '')
            .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def build(spec):
    """The certificate's bytes. Raises ValueError when the fonts are missing
    (the caller turns it into a plain sentence)."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    _fonts()
    ink = colors.HexColor(INK)
    muted = colors.HexColor(MUTED)
    st = {
        'h1': ParagraphStyle('h1', fontName=FONT_BOLD, fontSize=16, leading=20,
                             textColor=ink, spaceAfter=2),
        'sub': ParagraphStyle('sub', fontName=FONT, fontSize=9.5, leading=12.5,
                              textColor=muted),
        'brand': ParagraphStyle('brand', fontName=FONT_BOLD, fontSize=10, leading=13,
                                textColor=colors.HexColor(PRIMARY)),
        'h2': ParagraphStyle('h2', fontName=FONT_BOLD, fontSize=10.5, leading=14,
                             textColor=ink, spaceBefore=8, spaceAfter=4),
        'cell': ParagraphStyle('cell', fontName=FONT, fontSize=8.5, leading=11,
                               textColor=ink),
        'cellb': ParagraphStyle('cellb', fontName=FONT_BOLD, fontSize=8.5, leading=11,
                                textColor=ink),
        'small': ParagraphStyle('small', fontName=FONT, fontSize=7.5, leading=9.5,
                                textColor=muted),
        'num': ParagraphStyle('num', fontName=FONT, fontSize=8.5, leading=11,
                              textColor=ink, alignment=TA_RIGHT),
        'numb': ParagraphStyle('numb', fontName=FONT_BOLD, fontSize=8.5, leading=11,
                               textColor=ink, alignment=TA_RIGHT),
        'mark': ParagraphStyle('mark', fontName=FONT_BOLD, fontSize=9, leading=12,
                               textColor=colors.HexColor(AMBER)),
        'banner': ParagraphStyle('banner', fontName=FONT_BOLD, fontSize=9.5, leading=13,
                                 textColor=colors.HexColor(PRIMARY)),
        'note': ParagraphStyle('note', fontName=FONT, fontSize=7.5, leading=10,
                               textColor=muted),
    }
    out = io.BytesIO()
    width = A4[0] - 32 * mm
    doc = SimpleDocTemplate(
        out, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title=spec.get('title') or '', author=spec.get('author') or '',
        subject=spec.get('subtitle') or '', creator='Payobook')
    story = []
    if spec.get('author'):
        story.append(Paragraph(_esc(spec['author']), st['brand']))
    story.append(Paragraph(_esc(spec.get('title')), st['h1']))
    if spec.get('official'):
        story.append(Paragraph(_esc(spec['official']), st['sub']))
    if spec.get('subtitle'):
        story.append(Paragraph(_esc(spec['subtitle']), st['sub']))
    story.append(Spacer(1, 4 * mm))
    if spec.get('mark'):
        box = Table([[Paragraph(_esc(spec['mark']), st['mark'])]], colWidths=[width])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(AMBER_BG)),
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor(AMBER)),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story += [box, Spacer(1, 3 * mm)]
    if spec.get('banner'):
        box = Table([[Paragraph(_esc(spec['banner']), st['banner'])]], colWidths=[width])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(TINT)),
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor(PRIMARY)),
            ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story += [box, Spacer(1, 3 * mm)]

    # two-column facts blocks (employer, employee)
    blocks = [b for b in spec.get('blocks') or [] if b.get('rows')]
    if blocks:
        cells = []
        for block in blocks:
            rows = [[Paragraph(_esc(block.get('title')), st['h2']), '']]
            for label, value in block['rows']:
                rows.append([Paragraph(_esc(label), st['small']),
                             Paragraph(_esc(value) or '—', st['cell'])])
            inner = Table(rows, colWidths=[width / 2 * 0.40, width / 2 * 0.56])
            inner.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 1), (-1, -1), 1.5),
            ]))
            cells.append(inner)
        pairs = [cells[i:i + 2] for i in range(0, len(cells), 2)]
        for pair in pairs:
            if len(pair) == 1:
                pair.append('')
            grid = Table([pair], colWidths=[width / 2, width / 2])
            grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                      ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
            story.append(grid)
        story.append(Spacer(1, 2 * mm))

    for table in spec.get('tables') or []:
        head = table.get('head') or ['', '', '']
        rows = [[Paragraph(_esc(h), st['cellb'] if i < 2 else st['numb'])
                 for i, h in enumerate(head)]]
        styles = [
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(PRIMARY)),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]
        for i, (code, label, amount, kind) in enumerate(table.get('rows') or [], start=1):
            bold = kind == 'total'
            rows.append([Paragraph(_esc(code), st['cellb'] if bold else st['cell']),
                         Paragraph(label, st['cellb'] if bold else st['cell']),
                         Paragraph(_esc(amount), st['numb'] if bold else st['num'])])
            styles.append(('LINEBELOW', (0, i), (-1, i), 0.4, colors.HexColor(LINE)))
            if bold:
                styles.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(TINT)))
        grid = Table(rows, colWidths=[width * 0.12, width * 0.63, width * 0.25], repeatRows=1)
        grid.setStyle(TableStyle(styles))
        story.append(KeepTogether([Paragraph(_esc(table.get('title')), st['h2'])]))
        story.append(grid)
        story.append(Spacer(1, 2 * mm))

    for note in spec.get('notes') or []:
        story.append(Paragraph(_esc(note), st['note']))
    footer = spec.get('footer') or ''

    def on_page(canvas, document):
        canvas.saveState()
        canvas.setProducer('Payobook')
        canvas.setFont(FONT, 7)
        canvas.setFillColor(muted)
        canvas.drawString(16 * mm, 9 * mm, footer[:150])
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, str(document.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out.getvalue()


def row_label(label, official=''):
    """A table label: the screen words, the form's own words under them."""
    text = _esc(label)
    if official and official != label:
        text += '<br/><font size="7" color="%s">%s</font>' % (MUTED, _esc(official))
    return text
