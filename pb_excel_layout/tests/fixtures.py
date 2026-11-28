# -*- coding: utf-8 -*-
"""Workbooks for the DOCSTUDIO X tests, made by code (no customer file is
ever committed). Built with openpyxl, then given the parts real Excel writes
and openpyxl does not model (chart style and colour parts, a text box shape,
a pivot cache, a calculation chain, a macro project) by editing the zip —
the same way the layout fill works."""
import io
import zipfile

CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
R_OFFICE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

CHART_STYLE = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<cs:chartStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle" '
    b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" id="201">'
    b'<cs:axisTitle><cs:lnRef idx="0"/><cs:fillRef idx="0"/><cs:effectRef idx="0"/>'
    b'<cs:fontRef idx="minor"><a:schemeClr val="tx1"/></cs:fontRef></cs:axisTitle>'
    b'</cs:chartStyle>')
CHART_COLORS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<cs:colorStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle" '
    b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" meth="cycle" id="10">'
    b'<a:schemeClr val="accent1"/><cs:variation/></cs:colorStyle>')
TEXT_BOX = (
    '<xdr:twoCellAnchor xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<xdr:from><xdr:col>10</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
    '<xdr:to><xdr:col>13</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>4</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
    '<xdr:sp macro="" textlink=""><xdr:nvSpPr><xdr:cNvPr id="9" name="Board note"/><xdr:cNvSpPr txBox="1"/></xdr:nvSpPr>'
    '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1800000" cy="600000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>'
    '<xdr:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Approved by the board</a:t></a:r></a:p></xdr:txBody></xdr:sp>'
    '<xdr:clientData/></xdr:twoCellAnchor>')


def wb_bytes(wb):
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def members(raw):
    """{name: crc} in zip order."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return {i.filename: i.CRC for i in zf.infolist()}


def read(raw, name):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return zf.read(name)


def rezip(raw, add=None, replace=None, drop=(), stored=()):
    """The same zip with members added, replaced or dropped."""
    add = add or {}
    replace = replace or {}
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as zin, \
            zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename in drop:
                continue
            data = replace.get(info.filename, zin.read(info.filename))
            if callable(data):
                data = data(zin.read(info.filename))
            zout.writestr(info.filename, data)
        for name, data in add.items():
            zout.writestr(name, data, compress_type=zipfile.ZIP_STORED
                          if name in stored else zipfile.ZIP_DEFLATED)
    return out.getvalue()


def _sub(xml, before, insert):
    text = xml.decode('utf-8') if isinstance(xml, bytes) else xml
    assert before in text, before
    return text.replace(before, insert + before, 1).encode('utf-8')


def _override(part, ctype):
    return '<Override PartName="/%s" ContentType="%s"/>' % (part, ctype)


def _rel(rid, rtype, target):
    return '<Relationship Id="%s" Type="%s" Target="%s"/>' % (rid, rtype, target)


def excel_like_chart(raw):
    """Give chart1 the style and colour parts Excel 2013+ writes, and the
    drawing a text box: things openpyxl does not model."""
    ms = 'http://schemas.microsoft.com/office/2011/relationships/'
    ct = _sub(read(raw, '[Content_Types].xml'), '</Types>',
              _override('xl/charts/style1.xml',
                        'application/vnd.ms-office.chartstyle+xml')
              + _override('xl/charts/colors1.xml',
                          'application/vnd.ms-office.chartcolorstyle+xml'))
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="%s">%s%s</Relationships>' % (
                REL, _rel('rId1', ms + 'chartStyle', 'style1.xml'),
                _rel('rId2', ms + 'chartColorStyle', 'colors1.xml')))
    import re
    text = read(raw, 'xl/drawings/drawing1.xml').decode('utf-8')
    close = re.search(r'</([A-Za-z0-9]+:)?wsDr>', text).group(0)
    drawing = _sub(text, close, TEXT_BOX)
    return rezip(raw, replace={'[Content_Types].xml': ct,
                               'xl/drawings/drawing1.xml': drawing},
                 add={'xl/charts/_rels/chart1.xml.rels': rels,
                      'xl/charts/style1.xml': CHART_STYLE,
                      'xl/charts/colors1.xml': CHART_COLORS})


def with_calc_chain(raw, cells=('B1',)):
    chain = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<calcChain xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             + ''.join('<c r="%s" i="2"/>' % c for c in cells) + '</calcChain>')
    ct = _sub(read(raw, '[Content_Types].xml'), '</Types>', _override(
        'xl/calcChain.xml',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml'))
    rels = _sub(read(raw, 'xl/_rels/workbook.xml.rels'), '</Relationships>',
                _rel('rIdCalc', R_OFFICE + '/calcChain', 'calcChain.xml'))
    return rezip(raw, replace={'[Content_Types].xml': ct,
                               'xl/_rels/workbook.xml.rels': rels},
                 add={'xl/calcChain.xml': chain})


def with_pivot_cache(raw):
    cache = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<pivotCacheDefinition xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
             'xmlns:r="%s" refreshedBy="Finance" recordCount="0">'
             '<cacheSource type="worksheet"><worksheetSource ref="B6:D20" sheet="Data"/></cacheSource>'
             '<cacheFields count="1"><cacheField name="Department" numFmtId="0"><sharedItems/></cacheField></cacheFields>'
             '</pivotCacheDefinition>' % R_OFFICE)
    ct = _sub(read(raw, '[Content_Types].xml'), '</Types>', _override(
        'xl/pivotCache/pivotCacheDefinition1.xml',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml'))
    return rezip(raw, replace={'[Content_Types].xml': ct},
                 add={'xl/pivotCache/pivotCacheDefinition1.xml': cache})


def with_macros(raw, blob=b'\xd0\xcf\x11\xe0VBA-PROJECT-' + bytes(range(256)) * 4):
    ct = read(raw, '[Content_Types].xml').decode('utf-8').replace(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
        'application/vnd.ms-excel.sheet.macroEnabled.main+xml').encode('utf-8')
    ct = _sub(ct, '</Types>', '<Default Extension="bin" '
              'ContentType="application/vnd.ms-office.vbaProject"/>')
    rels = _sub(read(raw, 'xl/_rels/workbook.xml.rels'), '</Relationships>',
                _rel('rIdVba', 'http://schemas.microsoft.com/office/2006/'
                     'relationships/vbaProject', 'vbaProject.bin'))
    return rezip(raw, replace={'[Content_Types].xml': ct,
                               'xl/_rels/workbook.xml.rels': rels},
                 add={'xl/vbaProject.bin': blob}), blob


def billion_laughs(raw):
    def bomb(xml):
        text = xml.decode('utf-8')
        if text.startswith('<?xml'):
            head, body = text.split('?>', 1)
            head += '?>'
        else:
            head, body = '', text
        dtd = ('<!DOCTYPE lolz [<!ENTITY lol "lol">'
               + ''.join('<!ENTITY lol%d "%s">' % (i, ('&lol%d;' % (i - 1) if i > 1 else '&lol;') * 10)
                         for i in range(1, 10))
               + ']>')
        body = body.replace('<sheetData>', '<sheetData><row r="999"><c r="A999" '
                            't="inlineStr"><is><t>&lol9;</t></is></c></row>', 1)
        return (head + dtd + body).encode('utf-8')
    return rezip(raw, replace={'xl/worksheets/sheet1.xml': bomb})


def zip_bomb():
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', '<Types/>')
        zf.writestr('xl/workbook.xml', '<workbook/>')
        zf.writestr('xl/padding.xml', b'\0' * (81 * 1024 * 1024))
    return out.getvalue()


def traversal(raw):
    return rezip(raw, add={'../evil.xml': b'<x/>'})


def big_file(raw, size=11 * 1024 * 1024):
    import os
    return rezip(raw, add={'xl/media/noise.bin': os.urandom(size)},
                 stored=('xl/media/noise.bin',))


def encrypted():
    # The start of an OLE compound file: what Excel writes for a file with a
    # password to open.
    return b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\0' * 4096
