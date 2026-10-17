"""Formula-aware mapping metadata from XLSX cells, without evaluating formulas."""
from collections import defaultdict
from functools import lru_cache
from io import BytesIO


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
    """
    import openpyxl
    book = openpyxl.load_workbook(BytesIO(content), data_only=False, read_only=True)
    try:
        default_sheet = sheet_name if sheet_name in book.sheetnames else book.sheetnames[0]
        groups = defaultdict(list)
        for key, sheet, header, letter, preferred in columns:
            groups[sheet or default_sheet].append((key, header, letter, preferred))
        result = {}
        for title, specs in groups.items():
            if title not in book.sheetnames:
                continue
            ws = book[title]
            wanted = {header or key.split('|', 1)[-1]
                      for key, header, _, preferred in specs if preferred}
            if not wanted:
                wanted = {header for _, header, _, _ in specs if header}
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
            if not score:
                continue
            header_index = -negative_index
            positions = defaultdict(list)
            for i, cell in enumerate(heading):
                label = _text(cell.value)
                if label:
                    positions[label].append(i)
            counts = defaultdict(lambda: [0, 0])
            start = max(header_index + 2, data_start_row or 0)
            from itertools import chain
            for number, row in enumerate(chain(prefix[header_index + 1:], rows), header_index + 2):
                if number < start:
                    continue
                for i, cell in enumerate(row):
                    if cell.value is None or cell.value == '':
                        continue
                    counts[i][0 if cell.data_type == 'f' else 1] += 1
            by_heading, by_letter = {}, {}
            for label, indexes in positions.items():
                formulas = sum(counts[i][0] for i in indexes)
                literals = sum(counts[i][1] for i in indexes)
                letter = openpyxl.utils.get_column_letter(indexes[0] + 1)
                kind = 'mixed' if formulas and literals else 'formula' if formulas else 'input'
                info = {'kind': kind, 'formula_cells': formulas, 'value_cells': literals,
                        'sheet': title, 'letter': letter, 'header': label}
                by_heading[label] = info
                for i in indexes:
                    by_letter[openpyxl.utils.get_column_letter(i + 1)] = info
            for key, header, letter, _preferred in specs:
                tail = key.split('|', 1)[-1]
                info = by_heading.get(header) or by_heading.get(tail)
                if info is None:
                    info = by_letter.get(letter or tail)
                if info is None:
                    continue
                result[key] = info
                for alias in (title + '|' + info['header'], title + '|' + info['letter']):
                    result[alias] = info
                # Bare spellings follow the loader's first-sheet precedence.
                result.setdefault(info['header'], info)
                result.setdefault(info['letter'], info)
        return result
    finally:
        book.close()
