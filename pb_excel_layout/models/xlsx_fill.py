# -*- coding: utf-8 -*-
"""Fill ONE sheet of a customer's own workbook (DOCSTUDIO X, study line 920).

Why zip surgery and not openpyxl (ledger DS-2): openpyxl silently drops
charts, images, pivot tables and macros when it loads and re-saves a
workbook. A finance team's board pack is exactly those things. So the file is
treated as what it is — a zip of XML parts — and ONLY these parts change:

* the chosen worksheet's XML: cells from the start cell downward, inside the
  table's columns (rows above, cells to the left and to the right are kept);
* an Excel table (``xl/tables/tableN.xml``) that starts exactly at the
  table's heading row: its range, so it grows and shrinks with the result;
* ``xl/workbook.xml`` ``<calcPr fullCalcOnLoad="1"/>`` so formulas recalculate
  when the file is opened;
* every ``xl/pivotCache/pivotCacheDefinition*.xml`` ``refreshOnLoad="1"``;
* ``xl/calcChain.xml`` is removed together with its content-type and
  relationship entries (Excel rebuilds it; a stale one makes Excel "repair").

Every other member is written back with the same name, order, date and
compression and byte-identical content (same CRC) — rail R1, test 9.

openpyxl is used for READING only (sheet names, the 20 x 12 preview, and to
re-open the result as a last check before it is handed out).

Nothing here touches the database: these are pure functions over bytes, so the
fill can be tested without a server. Errors are raised as ``LayoutError`` with
a code; the model turns the code into words in the reader's language.
"""
import io
import math
import posixpath
import re
import zipfile
from datetime import date, datetime, time as dtime

from lxml import etree

# ------------------------------------------------------------------ limits
UPLOAD_MAX = 10 * 1024 * 1024          # the file as uploaded
UNZIPPED_MAX = 80 * 1024 * 1024        # all members together, unpacked
MEMBER_MAX = 4000                      # parts inside one workbook
TEXT_MAX = 32767                       # Excel's own limit for one cell
GRID_ROWS = 20
GRID_COLS = 12
MAX_ROW = 1048576
MAX_COL = 16384
SHEET_PEEK_MAX = 30                    # sheets described in one answer

OLE_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
ZIP_MAGIC = b'PK'
EXTENSIONS = ('.xlsx', '.xlsm')

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'

MIME = {
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
}

# XML 1.0 forbids these characters; a cell holding one makes the file
# unreadable, so they are dropped (test 11).
_ILLEGAL_XML = re.compile(
    '[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]')
_CELL = re.compile(r'^\$?([A-Za-z]{1,3})\$?([0-9]{1,7})$')
_PIVOT_CACHE = re.compile(r'^xl/pivotCache/pivotCacheDefinition[0-9]*\.xml$')

# The workbook element's children in schema order (CT_Workbook): calcPr is
# inserted before the first of these that exists when the file has none.
_AFTER_CALCPR = ('oleSize', 'customWorkbookViews', 'pivotCaches',
                 'smartTagPr', 'smartTagTypes', 'webPublishing',
                 'fileRecoveryPr', 'webPublishObjects', 'extLst')
# Number formats Excel shows as dates without a custom code.
_BUILTIN_DATES = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) \
    | set(range(50, 59))


class LayoutError(Exception):
    """A plain refusal. `code` is turned into words by the model."""

    def __init__(self, code, **params):
        super().__init__(code)
        self.code = code
        self.params = params


def _q(tag, ns=NS):
    return '{%s}%s' % (ns, tag)


def _parser():
    # No entities, no network, no huge trees (rail R3).
    return etree.XMLParser(resolve_entities=False, no_network=True,
                           huge_tree=False, load_dtd=False,
                           remove_blank_text=False)


def parse_xml(data):
    try:
        return etree.fromstring(data, parser=_parser())
    except etree.XMLSyntaxError as err:
        raise LayoutError('unreadable') from err


def dump_xml(root):
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8',
                          standalone=True)


# ------------------------------------------------------------ cell names
def col_letter(index):
    """1 -> A, 28 -> AB."""
    out = ''
    while index > 0:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def col_index(letters):
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def split_cell(ref):
    """'B6' -> (2, 6). Raises LayoutError('bad_cell') for anything else."""
    m = _CELL.match((ref or '').strip())
    if not m:
        raise LayoutError('bad_cell', cell=ref or '')
    col, row = col_index(m.group(1)), int(m.group(2))
    if not (1 <= col <= MAX_COL and 1 <= row <= MAX_ROW):
        raise LayoutError('bad_cell', cell=ref)
    return col, row


def cell_name(col, row):
    return '%s%d' % (col_letter(col), row)


def split_range(ref):
    """'B6:D20' -> (2, 6, 4, 20); a single cell is a 1 x 1 range."""
    parts = (ref or '').split(':')
    c1, r1 = split_cell(parts[0])
    c2, r2 = split_cell(parts[-1])
    return min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2)


def range_name(c1, r1, c2, r2):
    if (c1, r1) == (c2, r2):
        return cell_name(c1, r1)
    return '%s:%s' % (cell_name(c1, r1), cell_name(c2, r2))


# ------------------------------------------------------------- the package
class Package:
    """The uploaded workbook, checked and unpacked in memory (rail R3)."""

    def __init__(self, raw, file_name=''):
        self.file_name = file_name or ''
        ext = posixpath.splitext(self.file_name.lower())[1]
        if not isinstance(raw, (bytes, bytearray)):
            raise LayoutError('not_excel')
        if len(raw) > UPLOAD_MAX:
            raise LayoutError('too_big')
        if raw[:8] == OLE_MAGIC:
            # An old-format .xls and a password-protected .xlsx are both
            # this kind of container; the extension tells them apart.
            raise LayoutError('old_xls' if ext == '.xls' else 'password')
        if ext and ext not in EXTENSIONS:
            raise LayoutError('old_xls' if ext == '.xls' else 'wrong_ext')
        if raw[:2] != ZIP_MAGIC:
            raise LayoutError('not_excel')
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
            infos = zf.infolist()
        except (zipfile.BadZipFile, ValueError, OSError) as err:
            raise LayoutError('not_excel') from err
        if len(infos) > MEMBER_MAX:
            raise LayoutError('too_many_parts')
        total = 0
        self.infos = []
        self.data = {}
        for info in infos:
            name = info.filename
            parts = name.replace('\\', '/').split('/')
            if (name.startswith(('/', '\\')) or '\\' in name or '..' in parts
                    or ':' in parts[0]):
                raise LayoutError('bad_name')
            if info.flag_bits & 0x1:
                raise LayoutError('password')
            total += info.file_size
            if total > UNZIPPED_MAX:
                raise LayoutError('unzipped_too_big')
            try:
                with zf.open(info) as fh:
                    blob = fh.read(info.file_size + 1)
            except (zipfile.BadZipFile, RuntimeError, NotImplementedError,
                    ValueError, OSError, EOFError) as err:
                raise LayoutError('not_excel') from err
            if len(blob) > info.file_size:
                raise LayoutError('unzipped_too_big')
            if name in self.data:
                raise LayoutError('bad_name')
            self.infos.append(info)
            self.data[name] = blob
        if 'xl/workbook.xml' not in self.data:
            raise LayoutError('no_workbook')
        for name, blob in self.data.items():
            low = name.lower()
            if low.endswith(('.xml', '.rels', '.vml')) and _declares_dtd(blob):
                raise LayoutError('unsafe_xml')
        self.ext = ext if ext in EXTENSIONS else (
            '.xlsm' if self.has_macros else '.xlsx')
        self._parsed = {}

    # ---------------------------------------------------------- reading
    @property
    def has_macros(self):
        return any(n.lower().endswith('vbaproject.bin') for n in self.data)

    def xml(self, name):
        if name not in self._parsed:
            if name not in self.data:
                raise LayoutError('unreadable')
            self._parsed[name] = parse_xml(self.data[name])
        return self._parsed[name]

    def rels_of(self, part):
        """{rId: (type, resolved part name)} of one part's relationships."""
        folder, base = posixpath.split(part)
        rels_name = posixpath.join(folder, '_rels', base + '.rels')
        if rels_name not in self.data:
            return {}
        out = {}
        for rel in self.xml(rels_name).iter(_q('Relationship', PKG_REL)):
            target = rel.get('Target') or ''
            if rel.get('TargetMode') == 'External':
                continue
            if target.startswith('/'):
                resolved = target.lstrip('/')
            else:
                resolved = posixpath.normpath(posixpath.join(folder, target))
            out[rel.get('Id')] = ((rel.get('Type') or '').rsplit('/', 1)[-1],
                                  resolved)
        return out

    def sheets(self):
        """Every sheet in workbook order: dicts with name, kind, hidden, part."""
        wb = self.xml('xl/workbook.xml')
        rels = self.rels_of('xl/workbook.xml')
        out = []
        for el in wb.iter(_q('sheet')):
            kind, part = rels.get(el.get(_q('id', R_NS)), ('', ''))
            out.append({
                'name': el.get('name') or '',
                'kind': kind,
                'hidden': (el.get('state') or 'visible') != 'visible',
                'part': part if part in self.data else '',
            })
        return out

    def sheet(self, sheet_name):
        for entry in self.sheets():
            if entry['name'] == sheet_name:
                if entry['kind'] != 'worksheet':
                    raise LayoutError('chartsheet', sheet=sheet_name)
                if not entry['part']:
                    raise LayoutError('sheet_missing', sheet=sheet_name)
                return entry
        raise LayoutError('sheet_missing', sheet=sheet_name)

    @property
    def date1904(self):
        pr = self.xml('xl/workbook.xml').find(_q('workbookPr'))
        return pr is not None and (pr.get('date1904') or '').lower() in (
            '1', 'true')

    def date_styles(self):
        """The cell style indexes (`s`) whose number format is a date."""
        try:
            from openpyxl.styles.numbers import is_date_format
        except Exception:                                  # noqa: BLE001
            def is_date_format(code):
                code = re.sub(r'"[^"]*"|\[[^\]]*\]', '', code or '')
                return bool(re.search(r'[dmyhs]', code, re.I))
        part = None
        for kind, name in self.rels_of('xl/workbook.xml').values():
            if kind == 'styles':
                part = name
        if not part or part not in self.data:
            return set()
        root = self.xml(part)
        custom = {}
        fmts = root.find(_q('numFmts'))
        if fmts is not None:
            for fmt in fmts.iter(_q('numFmt')):
                try:
                    custom[int(fmt.get('numFmtId'))] = fmt.get('formatCode') or ''
                except (TypeError, ValueError):
                    continue
        out = set()
        xfs = root.find(_q('cellXfs'))
        if xfs is None:
            return out
        for index, xf in enumerate(xfs.findall(_q('xf'))):
            try:
                fid = int(xf.get('numFmtId') or 0)
            except ValueError:
                continue
            if fid in custom:
                if is_date_format(custom[fid]):
                    out.add(str(index))
            elif fid in _BUILTIN_DATES:
                out.add(str(index))
        return out

    def tables_of(self, sheet_part):
        """[(part name, table root)] of the Excel tables on one sheet."""
        out = []
        for kind, name in self.rels_of(sheet_part).values():
            if kind == 'table' and name in self.data:
                out.append((name, self.xml(name)))
        return out

    def merged_of(self, sheet_part):
        root = self.xml(sheet_part)
        block = root.find(_q('mergeCells'))
        if block is None:
            return []
        out = []
        for el in block.iter(_q('mergeCell')):
            try:
                out.append(split_range(el.get('ref')))
            except LayoutError:
                continue
        return out


def _declares_dtd(blob):
    """OOXML never carries a DTD; one that does is refused (billion laughs)."""
    for marker in (b'<!DOCTYPE', b'<!ENTITY',
                   '<!DOCTYPE'.encode('utf-16-le'),
                   '<!DOCTYPE'.encode('utf-16-be')):
        if marker in blob:
            return True
    return False


# -------------------------------------------------------------- the preview
def _display(cell):
    value = cell.value
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, datetime):
        if value.time() == dtime(0, 0):
            return value.date().isoformat()
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (date, dtime)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        fmt = getattr(cell, 'number_format', '') or ''
        if '%' in fmt:
            return '{:,.1f}%'.format(value * 100)
        if isinstance(value, float) and not value.is_integer():
            text = '{:,.2f}'.format(value) if ',' in fmt else ('%.2f' % value)
        else:
            text = '{:,}'.format(int(value)) if ',' in fmt else str(int(value))
        return text
    text = str(value)
    return text if len(text) <= 60 else text[:59] + '…'


def _look(cell):
    """A hint of the customer's own formatting for the preview: bold and a
    solid fill colour. Never required; any failure means plain."""
    out = {}
    try:
        if cell.font is not None and cell.font.b:
            out['b'] = 1
        fill = cell.fill
        if fill is not None and fill.fill_type == 'solid':
            rgb = fill.fgColor.rgb if fill.fgColor is not None else None
            if isinstance(rgb, str) and len(rgb) in (6, 8) and \
                    rgb[-6:].upper() not in ('000000', 'FFFFFF'):
                out['bg'] = '#' + rgb[-6:]
    except Exception:                                      # noqa: BLE001
        return {}
    return out


def _open_readonly(raw):
    from openpyxl import load_workbook
    try:
        return load_workbook(io.BytesIO(raw), read_only=True, data_only=True,
                             keep_links=False)
    except Exception as err:                               # noqa: BLE001
        raise LayoutError('unreadable') from err


def describe(raw, file_name='', only=None):
    """What the set-up screen shows: every sheet's name and kind, and for
    worksheets a 20 x 12 grid of what the customer sees, the merged ranges,
    the Excel tables and a suggested start cell."""
    pkg = Package(raw, file_name)
    entries = pkg.sheets()
    if not entries:
        raise LayoutError('unreadable')
    wb = _open_readonly(raw)
    try:
        sheets = []
        for entry in entries[:SHEET_PEEK_MAX]:
            item = {'name': entry['name'], 'kind': entry['kind'] or 'other',
                    'hidden': entry['hidden'], 'usable': False}
            if entry['kind'] == 'worksheet' and entry['part'] and (
                    only is None or entry['name'] == only):
                item.update(_describe_sheet(pkg, wb, entry))
                item['usable'] = True
            elif entry['kind'] == 'worksheet' and entry['part']:
                item['usable'] = True
            sheets.append(item)
    finally:
        try:
            wb.close()
        except Exception:                                  # noqa: BLE001
            pass
    return {'sheets': sheets, 'has_macros': pkg.has_macros,
            'ext': pkg.ext, 'more_sheets': max(0, len(entries) - SHEET_PEEK_MAX)}


def _describe_sheet(pkg, wb, entry):
    grid = []
    looks = []
    try:
        ws = wb[entry['name']]
        for row in ws.iter_rows(min_row=1, max_row=GRID_ROWS, min_col=1,
                                max_col=GRID_COLS):
            texts, styles = [''] * GRID_COLS, [None] * GRID_COLS
            for index, cell in enumerate(row[:GRID_COLS]):
                texts[index] = _display(cell)
                styles[index] = _look(cell) or None
            grid.append(texts)
            looks.append(styles)
    except Exception as err:                               # noqa: BLE001
        raise LayoutError('unreadable') from err
    while len(grid) < GRID_ROWS:
        grid.append([''] * GRID_COLS)
        looks.append([None] * GRID_COLS)
    last_row, last_col = _extent(pkg, entry['part'])
    tables = []
    for _part, root in pkg.tables_of(entry['part']):
        try:
            c1, r1, c2, r2 = split_range(root.get('ref'))
        except LayoutError:
            continue
        tables.append({'name': root.get('displayName') or root.get('name') or '',
                       'ref': range_name(c1, r1, c2, r2),
                       'cols': c2 - c1 + 1,
                       'start': cell_name(c1, r1),
                       'headers': (root.get('headerRowCount') or '1') != '0'})
    merged = [range_name(*m) for m in pkg.merged_of(entry['part'])]
    return {'grid': grid, 'looks': looks, 'rows': last_row, 'cols': last_col,
            'merged': merged, 'tables': tables,
            'suggested': _suggest(grid, tables)}


def _extent(pkg, part):
    """(last row, last column) that hold a cell, read from the XML."""
    root = pkg.xml(part)
    data = root.find(_q('sheetData'))
    last_row = last_col = 0
    if data is None:
        return 0, 0
    for row in _rows(data):
        for c, _cell in _cells(row):
            last_col = max(last_col, c)
            last_row = max(last_row, int(row.get('r')))
    return last_row, last_col


def _suggest(grid, tables):
    """Where the table should start when the customer has not said: at the
    heading row of the sheet's Excel table; else the first empty row under
    the heading rows at the top, in the column those headings start in; A1
    on an empty sheet."""
    if tables:
        first = tables[0]
        return {'cell': first['start'], 'headers': bool(first['headers']),
                'why': 'table', 'table': first['name']}
    filled = [i for i, row in enumerate(grid) if any(t for t in row)]
    if not filled:
        return {'cell': 'A1', 'headers': True, 'why': 'empty'}
    r = filled[0]
    while r < len(grid) and any(t for t in grid[r]):
        r += 1
    block = grid[filled[0]:r]
    cols = [j for row in block for j, t in enumerate(row) if t]
    col = (min(cols) + 1) if cols else 1
    return {'cell': cell_name(col, r + 1), 'headers': True, 'why': 'below'}


# ------------------------------------------------------------- sheet rows
def _rows(sheet_data):
    """The <row> elements, every one given its `r` (implied numbering is
    legal and some writers use it)."""
    prev = 0
    out = []
    for row in sheet_data.findall(_q('row')):
        try:
            r = int(row.get('r') or 0)
        except ValueError:
            r = 0
        if r <= prev:
            r = prev + 1
        row.set('r', str(r))
        prev = r
        out.append(row)
    return out


def _cells(row):
    """[(column, <c>)] of one row, every cell given its `r`."""
    prev = 0
    out = []
    r = row.get('r')
    for cell in row.findall(_q('c')):
        ref = cell.get('r')
        col = 0
        if ref:
            m = _CELL.match(ref)
            if m:
                col = col_index(m.group(1))
        if col <= prev:
            col = prev + 1
        cell.set('r', '%s%s' % (col_letter(col), r))
        prev = col
        out.append((col, cell))
    return out


# ------------------------------------------------------------ the values
def _clean_text(value, notes):
    text = _ILLEGAL_XML.sub('', str(value))
    if len(text) > TEXT_MAX:
        text = text[:TEXT_MAX]
        notes['text_cut'] = notes.get('text_cut', 0) + 1
    return text


def _serial(value, date1904):
    epoch = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.replace(tzinfo=None)
        delta = value - epoch
    else:
        delta = datetime.combine(value, dtime(0, 0)) - epoch
    serial = delta.days + (delta.seconds + delta.microseconds / 1e6) / 86400.0
    return _number(serial)


def _number(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    value = float(value)
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(round(value, 10))


def _make_cell(ref, value, style, date_ok, date1904, notes):
    """One <c>. Text is ALWAYS an inline string, never a formula (R4)."""
    cell = etree.Element(_q('c'))
    cell.set('r', ref)
    if style:
        cell.set('s', style)
    if value is None:
        return cell if style else None
    if isinstance(value, bool):
        cell.set('t', 'b')
        etree.SubElement(cell, _q('v')).text = '1' if value else '0'
        return cell
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return cell if style else None
        etree.SubElement(cell, _q('v')).text = _number(value)
        return cell
    if isinstance(value, (date, datetime)):
        if date_ok:
            etree.SubElement(cell, _q('v')).text = _serial(value, date1904)
            return cell
        # A date written as a number with no date format shows as 46000:
        # as plain text it stays readable (handover §3 step 4).
        if isinstance(value, datetime):
            value = value.strftime('%Y-%m-%d %H:%M') \
                if value.time() != dtime(0, 0) else value.date().isoformat()
        else:
            value = value.isoformat()
    text = _clean_text(value, notes)
    if not text:
        return cell if style else None
    cell.set('t', 'inlineStr')
    inline = etree.SubElement(cell, _q('is'))
    t = etree.SubElement(inline, _q('t'))
    t.text = text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return cell


def _blank(cell):
    """Empty a cell but keep its look: no stale figure stays behind, and the
    rows the customer formatted in advance keep their borders and colours."""
    for child in list(cell):
        cell.remove(child)
    for attr in ('t', 'cm', 'vm', 'ph'):
        if attr in cell.attrib:
            del cell.attrib[attr]
    return bool(cell.get('s'))


# ----------------------------------------------------------------- filling
def headings(table):
    """The heading text of each column, unique and never empty (an Excel
    table refuses two columns with the same name)."""
    seen = {}
    out = []
    for j, col in enumerate(table.get('columns') or [], start=1):
        label = _ILLEGAL_XML.sub('', str(col.get('label') or '')).strip()
        label = (label or 'Column %d' % j)[:255]
        base, n = label, 1
        while label.lower() in seen:
            n += 1
            label = '%s %d' % (base, n)
        seen[label.lower()] = True
        out.append(label)
    return out


def area_problems(pkg, sheet_part, c0, r0, c_last):
    """Things that make filling from (c0, r0) across to c_last impossible:
    merged cells, a shared or array formula that reaches outside the area, an
    Excel table whose headings sit inside it. Raised as a LayoutError."""
    for c1, r1, c2, r2 in pkg.merged_of(sheet_part):
        if c2 >= c0 and c1 <= c_last and r2 >= r0:
            raise LayoutError('merged', ref=range_name(c1, r1, c2, r2))
    root = pkg.xml(sheet_part)
    data = root.find(_q('sheetData'))
    if data is not None:
        for row in _rows(data):
            for col, cell in _cells(row):
                f = cell.find(_q('f'))
                if f is None or not f.get('ref') or f.get('t') not in (
                        'shared', 'array'):
                    continue
                try:
                    fc1, fr1, fc2, fr2 = split_range(f.get('ref'))
                except LayoutError:
                    continue
                inside_master = c0 <= col <= c_last and int(row.get('r')) >= r0
                touches = fc2 >= c0 and fc1 <= c_last and fr2 >= r0
                within = fc1 >= c0 and fc2 <= c_last and fr1 >= r0
                if f.get('t') == 'shared' and inside_master and not within:
                    raise LayoutError('formula_in_way',
                                      ref=range_name(fc1, fr1, fc2, fr2))
                if f.get('t') == 'array' and touches and not within:
                    raise LayoutError('formula_in_way',
                                      ref=range_name(fc1, fr1, fc2, fr2))


def fill(raw, sheet_name, start_cell, write_headers, table, file_name=''):
    """The customer's file with `table` written from `start_cell` on the sheet
    `sheet_name`. Returns (bytes, notes). `notes` is a dict:
    text_cut (int), table_left (list of names), table_resized (list)."""
    pkg = Package(raw, file_name)
    entry = pkg.sheet(sheet_name)
    part = entry['part']
    columns = table.get('columns') or []
    rows = table.get('rows') or []
    ncols = len(columns)
    if not ncols:
        raise LayoutError('no_columns')
    c0, r0 = split_cell(start_cell)
    c_last = c0 + ncols - 1
    if c_last > MAX_COL:
        raise LayoutError('too_wide', cell=start_cell, cols=ncols)
    head_row = r0 if write_headers else None
    data_r0 = r0 + 1 if write_headers else r0
    last_written = data_r0 + len(rows) - 1
    if last_written > MAX_ROW:
        raise LayoutError('too_long', cell=start_cell, rows=len(rows))
    area_problems(pkg, part, c0, r0, c_last)

    notes = {'text_cut': 0, 'table_left': [], 'table_resized': []}
    date1904 = pkg.date1904
    date_styles = pkg.date_styles()
    labels = headings(table)

    root = pkg.xml(part)
    data = root.find(_q('sheetData'))
    if data is None:
        data = etree.SubElement(root, _q('sheetData'))
    by_row = {int(row.get('r')): row for row in _rows(data)}
    old_last = max(by_row) if by_row else 0

    def cell_at(r, c):
        row = by_row.get(r)
        if row is None:
            return None
        for col, cell in _cells(row):
            if col == c:
                return cell
        return None

    # Step 3 — the look of the first row is the look of every row.
    head_styles = []
    data_styles = []
    for j in range(ncols):
        hc = cell_at(r0, c0 + j)
        dc = cell_at(data_r0, c0 + j)
        head_styles.append(hc.get('s') if hc is not None else None)
        data_styles.append(dc.get('s') if dc is not None else None)
    tpl_row = by_row.get(data_r0)
    row_look = {}
    if tpl_row is not None:
        for key, value in tpl_row.attrib.items():
            local = etree.QName(key).localname
            if local in ('ht', 'customHeight', 's', 'customFormat',
                         'dyDescent'):
                row_look[key] = value

    def ensure_row(r):
        row = by_row.get(r)
        if row is not None:
            return row
        row = etree.Element(_q('row'))
        row.set('r', str(r))
        for key, value in row_look.items():
            row.set(key, value)
        # keep <row> elements in ascending order
        after = [k for k in by_row if k < r]
        if after:
            by_row[max(after)].addnext(row)
        else:
            data.insert(0, row)
        by_row[r] = row
        return row

    def put(row, new_cells):
        """Replace this row's cells inside the table columns."""
        keep = []
        for col, cell in _cells(row):
            if c0 <= col <= c_last:
                row.remove(cell)
            else:
                keep.append((col, cell))
        for col, cell in new_cells:
            if cell is None:
                continue
            before = [k for k in keep if k[0] > col]
            ext = row.find(_q('extLst'))
            if before:
                before[0][1].addprevious(cell)
            elif ext is not None:
                ext.addprevious(cell)
            else:
                row.append(cell)
            keep.append((col, cell))
            keep.sort(key=lambda k: k[0])
        if 'spans' in row.attrib:
            del row.attrib['spans']

    if head_row is not None:
        row = ensure_row(head_row)
        put(row, [(c0 + j, _make_cell(cell_name(c0 + j, head_row), labels[j],
                                      head_styles[j], False, date1904, notes))
                  for j in range(ncols)])
    for i, values in enumerate(rows):
        r = data_r0 + i
        row = ensure_row(r)
        made = []
        for j in range(ncols):
            value = values[j] if j < len(values) else None
            style = data_styles[j]
            made.append((c0 + j, _make_cell(
                cell_name(c0 + j, r), value, style,
                bool(style) and style in date_styles, date1904, notes)))
        put(row, made)
    # Step 5 — a shorter result leaves no stale figures below it.
    # (`last_written` is the heading row, or the row above the start, when
    # the result has no rows at all.)
    for r in range(last_written + 1, old_last + 1):
        row = by_row.get(r)
        if row is None:
            continue
        for col, cell in _cells(row):
            if c0 <= col <= c_last and not _blank(cell):
                row.remove(cell)
        if 'spans' in row.attrib:
            del row.attrib['spans']

    _fix_dimension(root, data)
    changed = {part: root}

    # Step 7 — an Excel table that starts at the heading row follows the rows.
    top = r0 if write_headers else r0 - 1
    for tpart, troot in pkg.tables_of(part):
        try:
            tc1, tr1, tc2, tr2 = split_range(troot.get('ref'))
        except LayoutError:
            continue
        name = troot.get('displayName') or troot.get('name') or ''
        has_head = (troot.get('headerRowCount') or '1') != '0'
        totals = int(troot.get('totalsRowCount') or 0)
        cols_el = troot.find(_q('tableColumns'))
        tcols = cols_el.findall(_q('tableColumn')) if cols_el is not None else []
        overlap_cols = tc2 >= c0 and tc1 <= c_last
        if tc1 == c0 and tr1 == top and has_head and top >= 1:
            if len(tcols) == ncols and not totals:
                new_bottom = max(last_written, tr1 + 1)
                ref = range_name(c0, tr1, c_last, new_bottom)
                troot.set('ref', ref)
                auto = troot.find(_q('autoFilter'))
                if auto is not None:
                    auto.set('ref', ref)
                    for sort in auto.findall(_q('sortState')):
                        auto.remove(sort)
                for sort in troot.findall(_q('sortState')):
                    troot.remove(sort)
                if write_headers:
                    for j, tcol in enumerate(tcols):
                        tcol.set('name', labels[j])
                notes['table_resized'].append(name)
                changed[tpart] = troot
                continue
            notes['table_left'].append(name)
            if write_headers:
                # Headings were written over the table's own: its column names
                # must say the same or Excel "repairs" the file.
                for j, tcol in enumerate(tcols):
                    if c0 <= tc1 + j <= c_last:
                        tcol.set('name', labels[tc1 + j - c0])
                changed[tpart] = troot
            continue
        if has_head and overlap_cols and tr1 >= r0:
            raise LayoutError('table_in_way', table=name,
                              ref=range_name(tc1, tr1, tc2, tr2))

    # Step 8 — recalculate on open; refresh pivots; drop the stale chain.
    wb = pkg.xml('xl/workbook.xml')
    calc = wb.find(_q('calcPr'))
    if calc is None:
        calc = etree.Element(_q('calcPr'))
        anchor = None
        for tag in _AFTER_CALCPR:
            anchor = wb.find(_q(tag))
            if anchor is not None:
                break
        if anchor is not None:
            anchor.addprevious(calc)
        else:
            wb.append(calc)
    calc.set('fullCalcOnLoad', '1')
    changed['xl/workbook.xml'] = wb
    for name in pkg.data:
        if _PIVOT_CACHE.match(name):
            proot = pkg.xml(name)
            proot.set('refreshOnLoad', '1')
            changed[name] = proot
    dropped = set()
    if 'xl/calcChain.xml' in pkg.data:
        dropped.add('xl/calcChain.xml')
        ct = pkg.xml('[Content_Types].xml')
        for el in list(ct.iter(_q('Override', CT_NS))):
            if (el.get('PartName') or '').lower() == '/xl/calcchain.xml':
                el.getparent().remove(el)
        changed['[Content_Types].xml'] = ct
        rels_name = 'xl/_rels/workbook.xml.rels'
        if rels_name in pkg.data:
            rels = pkg.xml(rels_name)
            for el in list(rels.iter(_q('Relationship', PKG_REL))):
                if (el.get('Target') or '').lower().endswith('calcchain.xml'):
                    el.getparent().remove(el)
            changed[rels_name] = rels

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as zout:
        for info in pkg.infos:
            name = info.filename
            if name in dropped:
                continue
            blob = dump_xml(changed[name]) if name in changed else pkg.data[name]
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zi.create_system = info.create_system
            zi.comment = info.comment
            zout.writestr(zi, blob)
    result = out.getvalue()
    check(result, sheet_name)
    notes['text_cut'] = notes.get('text_cut', 0)
    return result, notes


def _fix_dimension(root, data):
    """<dimension ref> = the used range after the fill."""
    c_min = r_min = None
    c_max = r_max = 0
    for row in _rows(data):
        r = int(row.get('r'))
        for col, _cell in _cells(row):
            c_min = col if c_min is None else min(c_min, col)
            r_min = r if r_min is None else min(r_min, r)
            c_max = max(c_max, col)
            r_max = max(r_max, r)
    ref = range_name(c_min, r_min, c_max, r_max) if c_min else 'A1'
    dim = root.find(_q('dimension'))
    if dim is None:
        dim = etree.Element(_q('dimension'))
        pr = root.find(_q('sheetPr'))
        if pr is not None:
            pr.addnext(dim)
        else:
            root.insert(0, dim)
    dim.set('ref', ref)


def check(result, sheet_name):
    """Step 9 — the file must open again before anybody receives it."""
    try:
        Package(result, 'check.xlsx')
        wb = _open_readonly(result)
        try:
            ws = wb[sheet_name]
            for _row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
                pass
        finally:
            wb.close()
    except LayoutError as err:
        raise LayoutError('check_failed') from err
    except Exception as err:                               # noqa: BLE001
        raise LayoutError('check_failed') from err


def mimetype(ext):
    return MIME.get(ext, MIME['.xlsx'])


def area_size(table, write_headers):
    return len(table.get('columns') or []), \
        len(table.get('rows') or []) + (1 if write_headers else 0)

