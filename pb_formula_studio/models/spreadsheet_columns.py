"""Formula-aware mapping metadata from XLSX cells, without evaluating formulas."""
from collections import defaultdict
from functools import lru_cache
from io import BytesIO
import re


_EXCEL_ERRORS = {'#NULL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!',
                 '#N/A', '#GETTING_DATA', '#SPILL!', '#CALC!'}


def _text(value):
    return '' if value is None else str(value).strip()


def _headers_at(ws, row):
    """Resolve vertical heading merges exactly at the reader's heading row."""
    resolved = {}
    vertical = {span.min_col: span for span in ws.merged_cells.ranges
                if span.min_col == span.max_col and span.min_row <= row <= span.max_row}
    for cell in ws[row]:
        value = cell.value
        span = vertical.get(cell.column)
        if value is None and span:
            value = ws.cell(span.min_row, span.min_col).value
        if _text(value):
            resolved[cell.column] = _text(value)
    return resolved


def _numbered_guide(row, number):
    """A numbered column guide is a heading aid, including its +1 formulas."""
    values = {}
    for cell in row:
        value = cell.value
        if value is None:
            continue
        if cell.data_type == 'f':
            match = re.fullmatch(r'=\s*\$?([A-Z]+)\$?(\d+)\s*\+\s*1\s*',
                                 _text(value).upper())
            if not match or int(match[2]) != number:
                return False
            from openpyxl.utils import column_index_from_string
            previous = values.get(column_index_from_string(match[1]))
            if previous is None:
                return False
            value = previous + 1
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or value != int(value) or not 1 <= value <= len(row)):
            return False
        values[cell.column] = value
    guide = list(values.values())
    return len(guide) >= 5 and guide[:2] == [1, 2] and max(guide) >= len(guide) * .7


def mapping_xlsx_columns(content, columns):
    """Add physical positions to the loader's keys without inventing any keys.

    Repeated leaf headings (Others, VND, USD) get their own physical cards.
    The original aliases stay available and point at the physical value the
    loader actually stores. This runs for every new/replacement XLSX, rather
    than relying on a one-off reviewed workbook catalogue.
    """
    import openpyxl
    book = openpyxl.load_workbook(BytesIO(content), data_only=False)
    try:
        default = next((c.get('sheet') for c in columns
                        if c.get('preferred') and c.get('sheet') in book.sheetnames),
                       book.active.title)
        sheets = list(dict.fromkeys(c.get('sheet') or default for c in columns))
        present = {c['key'] for c in columns}
        qualified = any(c.get('preferred') and c.get('sheet') for c in columns)
        physical, chosen, entries = {}, {}, []
        for title in sheets:
            if title not in book.sheetnames:
                continue
            ws = book[title]
            wanted = {_text(c.get('header')) for c in columns
                      if (c.get('sheet') or default) == title and c.get('header')}
            if not wanted:
                continue
            heading = max(range(1, min(40, ws.max_row) + 1), key=lambda row: (
                len(set(_headers_at(ws, row).values()) & wanted), -row))
            vertical = [span for span in ws.merged_cells.ranges
                        if span.min_col == span.max_col and span.min_row <= heading <= span.max_row]
            heading_start = min([heading] + [span.min_row for span in vertical])
            heading = max([heading] + [span.max_row for span in vertical])
            headers = _headers_at(ws, heading)
            heading_aliases = {label: index for row in range(heading_start, heading + 1)
                               for index, label in _headers_at(ws, row).items()}
            start = heading + 1
            if start <= ws.max_row and _numbered_guide(ws[start], start):
                start += 1
            repeats = defaultdict(list)
            for index, header in headers.items():
                repeats[header].append(index)
            for index, header in headers.items():
                letter = openpyxl.utils.get_column_letter(index)
                prefix = title + '|' if qualified else ''
                heading_key, letter_key = prefix + header, prefix + letter
                duplicate = len(repeats[header]) > 1
                key = letter_key if duplicate and letter_key in present else heading_key
                if key not in present:
                    key = letter_key
                if key not in present:
                    continue
                label = re.sub(r'\s+', ' ', header)
                if duplicate or label in {'USD', 'VND', 'IDR', 'INR', 'SGD', 'AUD', 'EUR', 'GBP'}:
                    parents = [span for span in ws.merged_cells.ranges
                               if span.min_row < heading and span.min_col <= index <= span.max_col
                               and span.max_col > span.min_col]
                    if parents:
                        span = max(parents, key=lambda s: s.min_row)
                        parent = re.sub(r'\s+', ' ', _text(ws.cell(span.min_row, span.min_col).value))
                        label = (parent + ' — ' + label if label in {'USD', 'VND', 'IDR', 'INR', 'SGD', 'AUD', 'EUR', 'GBP'}
                                 else label + ' — ' + parent)
                    elif duplicate:
                        label += ' — ' + letter
                meta = dict(key=key, sheet=title, header=header, label=label,
                            letter=letter, physical_letter=letter, preferred=True,
                            data_start_row=start)
                original = next((c for c in columns if c['key'] == key), {})
                meta['sample'] = original.get('sample') or ''
                physical[title, letter] = meta
                chosen[key] = meta
                entries.append(meta)
            # Duplicate heading keys carry the LAST occurrence in loader rows.
            for col in columns:
                sheet = col.get('sheet') or default
                if sheet != title or col['key'] in chosen:
                    continue
                tail = col['key'].split('|', 1)[-1]
                target = physical.get((title, tail)) if re.fullmatch(r'[A-Z]{1,3}', tail) else None
                matches = repeats.get(col.get('header') or tail)
                if target is None and matches:
                    target = physical.get((title, openpyxl.utils.get_column_letter(matches[-1])))
                if target is None and (col.get('header') or tail) in heading_aliases:
                    target = physical.get((title, openpyxl.utils.get_column_letter(
                        heading_aliases[col.get('header') or tail])))
                if target:
                    chosen[col['key']] = dict(target, key=col['key'], preferred=False,
                                              sample=col.get('sample') or '')
        canonical = {c['key'] for c in entries}
        return entries + [chosen.get(c['key'], dict(c)) for c in columns if c['key'] not in canonical]
    finally:
        book.close()


@lru_cache(maxsize=8)
def classify_xlsx_columns(content, columns, sheet_name='', data_start_row=0,
                          identity_headers=()):
    """Return column types and aliases for the actual headings on this board.

    `columns` contains (key, sheet, heading, letter, preferred) tuples from the
    existing reader. Match their headings in each worksheet, so section-title
    rows and merged-sheet alias positions cannot turn data into headers.
    Blank cells do not make a formula column mixed. A nonformula populated
    cell does: there is no percentage threshold or name-based inference.
    The sole exception is an exact generated sequence: one numeric seed of 1,
    then only contiguous same-column previous-row + 1 formulas. That seed is
    part of the generated sequence, rather than a separate upload input.
    """
    import openpyxl
    book = openpyxl.load_workbook(BytesIO(content), data_only=False)
    try:
        default_sheet = sheet_name if sheet_name in book.sheetnames else book.sheetnames[0]
        groups = defaultdict(list)
        for spec in columns:
            key, sheet, header, letter, preferred = spec[:5]
            physical, start, end = spec[5:] if len(spec) > 5 else ('', 0, 0)
            groups[(sheet or default_sheet, start, end)].append(
                (key, header, letter, preferred, physical))
        result = {}
        for (title, declared_start, declared_end), specs in groups.items():
            if title not in book.sheetnames:
                continue
            ws = book[title]
            wanted = {header or key.split('|', 1)[-1]
                      for key, header, _, preferred, _ in specs if preferred}
            if not wanted:
                wanted = {header for _, header, _, _, _ in specs if header}
            if not wanted:
                continue
            # Headers are already known from the loader. Locate their row rather
            # than guessing from labels such as Age, Salary, Total or employee IDs.
            rows = ws.iter_rows()
            prefix = []
            for _ in range(40):
                row = next(rows, None)
                if row is None:
                    break
                prefix.append(row)
            if not prefix:
                continue
            scored = [(len({_text(c.value) for c in row} & wanted), -i, row)
                      for i, row in enumerate(prefix)]
            score, negative_index, heading = max(scored, key=lambda x: x[:2])
            explicit = any(physical for _, _, _, _, physical in specs)
            if not score and not explicit:
                continue
            header_index = declared_start - 2 if declared_start else -negative_index
            positions = defaultdict(list)
            resolved = _headers_at(ws, -negative_index + 1)
            for index, label in resolved.items():
                positions[label].append(index - 1)
            # Curated multi-row headings can repeat or span currency columns.
            # Their physical position, rather than a duplicate heading's first
            # occurrence, determines whether that column contains formulas.
            if explicit:
                positions = defaultdict(list)
                for key, header, _, preferred, physical in specs:
                    if preferred and physical:
                        positions[header or key.split('|')[-1]].append(
                            openpyxl.utils.column_index_from_string(physical) - 1)
            counts = defaultdict(lambda: [0, 0])
            employee_counts = defaultdict(lambda: [0, 0])
            errors = defaultdict(list)
            sequences = {}
            populated_rows = 0
            headed_indexes = {i for indexes in positions.values() for i in indexes}
            start = max(header_index + 2, data_start_row or 0, declared_start)
            if not declared_start and start <= ws.max_row and _numbered_guide(ws[start], start):
                start += 1
            identity_indexes = {index - 1 for index, label in resolved.items()
                                if (title, label) in identity_headers}
            from itertools import chain
            for number, row in enumerate(chain(prefix[header_index + 1:], rows), header_index + 2):
                if number < start:
                    continue
                if declared_end and number > declared_end:
                    break
                # Footer literals must not turn an employee calculation into
                # an input. Keep all rows for missing/error input checks,
                # including malformed employee IDs that need review.
                employee_row = any(i < len(row) and row[i].value not in (None, '')
                                   for i in identity_indexes)
                if any(i < len(row) and row[i].value not in (None, '') for i in headed_indexes):
                    populated_rows += 1
                for i, cell in enumerate(row):
                    if cell.value is None or cell.value == '':
                        continue
                    counts[i][0 if cell.data_type == 'f' else 1] += 1
                    if employee_row:
                        employee_counts[i][0 if cell.data_type == 'f' else 1] += 1
                    value = _text(cell.value).upper()
                    if cell.data_type == 'e' or value in _EXCEL_ERRORS or (
                            cell.data_type == 'f' and value[1:].strip() in _EXCEL_ERRORS):
                        errors[i].append(number)
                    if i not in sequences:
                        sequences[i] = [cell.data_type != 'f' and
                                        not isinstance(cell.value, bool) and
                                        isinstance(cell.value, (int, float)) and cell.value == 1,
                                        number]
                    elif sequences[i][0]:
                        valid, previous = sequences[i]
                        letter = openpyxl.utils.get_column_letter(i + 1)
                        match = re.fullmatch(r'=\s*\$?' + letter + r'\$?(\d+)\s*\+\s*1\s*',
                                             value) if cell.data_type == 'f' else None
                        sequences[i] = [bool(valid and match and previous == number - 1 and
                                             int(match[1]) == previous), number]
            by_heading, by_letter = {}, {}
            entries = ([(label, [i]) for label, indexes in positions.items() for i in indexes]
                       if explicit else positions.items())
            for label, indexes in entries:
                formulas = sum(counts[i][0] for i in indexes)
                literals = sum(counts[i][1] for i in indexes)
                letter = openpyxl.utils.get_column_letter(indexes[0] + 1)
                sequence = bool(formulas and literals == 1 and len(indexes) == 1 and
                                sequences[indexes[0]][0])
                employee_formula = (sum(employee_counts[i][0] for i in indexes) > 0
                                    and not any(employee_counts[i][1] for i in indexes))
                kind = 'formula' if sequence or employee_formula else (
                    'mixed' if formulas and literals else 'formula' if formulas else 'input')
                error_cells = sum(len(errors[i]) for i in indexes)
                info = {'kind': kind, 'formula_cells': formulas, 'value_cells': literals,
                        'sheet': title, 'letter': letter, 'header': label,
                        'generated_sequence': sequence, 'data_rows': populated_rows,
                        'blank_cells': max(0, populated_rows * len(indexes) - formulas - literals),
                        'error_cells': error_cells,
                        'error_addresses': [openpyxl.utils.get_column_letter(i + 1) + str(r)
                                            for i in indexes for r in errors[i]][:10]}
                by_heading.setdefault(label, info)
                for i in indexes:
                    by_letter[openpyxl.utils.get_column_letter(i + 1)] = info
            for key, header, letter, _preferred, physical in specs:
                tail = key.split('|', 1)[-1]
                info = by_letter.get(physical) if physical else None
                info = info or by_heading.get(header) or by_heading.get(tail)
                if info is None:
                    info = by_letter.get(letter or tail)
                if info is None:
                    continue
                result[key] = info
                for alias in (title + '|' + info['header'], title + '|' + info['letter']):
                    result.setdefault(alias, info)
                # Bare spellings follow the loader's first-sheet precedence.
                result.setdefault(info['header'], info)
                result.setdefault(info['letter'], info)
        return result
    finally:
        book.close()
