"""Formula-aware mapping metadata from XLSX cells, without evaluating formulas."""
from collections import defaultdict
from functools import lru_cache
from io import BytesIO
import re


_EXCEL_ERRORS = {'#NULL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!',
                 '#N/A', '#GETTING_DATA', '#SPILL!', '#CALC!'}


def _text(value):
    return '' if value is None else str(value).strip()


@lru_cache(maxsize=8)
def classify_xlsx_columns(content, columns, sheet_name='', data_start_row=0):
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
    book = openpyxl.load_workbook(BytesIO(content), data_only=False, read_only=True)
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
            for i, cell in enumerate(heading):
                label = _text(cell.value)
                if label:
                    positions[label].append(i)
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
            errors = defaultdict(list)
            sequences = {}
            populated_rows = 0
            headed_indexes = {i for indexes in positions.values() for i in indexes}
            start = max(header_index + 2, data_start_row or 0, declared_start)
            from itertools import chain
            for number, row in enumerate(chain(prefix[header_index + 1:], rows), header_index + 2):
                if number < start:
                    continue
                if declared_end and number > declared_end:
                    break
                if any(i < len(row) and row[i].value not in (None, '') for i in headed_indexes):
                    populated_rows += 1
                for i, cell in enumerate(row):
                    if cell.value is None or cell.value == '':
                        continue
                    counts[i][0 if cell.data_type == 'f' else 1] += 1
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
                kind = 'formula' if sequence else (
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
