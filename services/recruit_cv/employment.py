"""Conservative employment extraction: retain evidence, never infer missing facts."""
import re
import unicodedata


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if unicodedata.category(c) != 'Mn').replace('đ', 'd')


MONTHS = {}
for number, names in enumerate([
    'jan january januari', 'feb february februari', 'mar march maret',
    'apr april', 'may mei', 'jun june juni', 'jul july juli',
    'aug august agustus', 'sep sept september', 'oct october oktober',
    'nov november', 'dec december desember'], 1):
    MONTHS.update({name: number for name in names.split()})
MONTH = '|'.join(sorted(MONTHS, key=len, reverse=True))
DATE = rf'(?:thang\s+\d{{1,2}}\s*[/, -]\s*\d{{4}}|(?:{MONTH})\.?\s+\d{{4}}|\d{{4}}[-/]\d{{1,2}}|\d{{1,2}}/\d{{4}}|\d{{4}})'
CURRENT = r'(?:present|current|now|hien tai|nay|sekarang|saat ini)'
RANGE = re.compile(rf'(?<!\w)(?P<start>{DATE})\s*(?:[-–—]|\bto\b|\bden\b|\bhingga\b|\bsampai\b)\s*(?P<end>{DATE}|{CURRENT})(?!\w)', re.I)


def date_value(value):
    value = fold(value).strip().rstrip('.')
    if re.fullmatch(CURRENT, value):
        return '', True
    numbers = re.findall(r'\d+', value)
    year = next((n for n in numbers if len(n) == 4), '')
    if not year or not 1900 <= int(year) <= 2100:
        return '', False
    month = next((MONTHS[w] for w in re.findall(r'[a-z]+', value) if w in MONTHS), None)
    if month is None:
        month = next((int(n) for n in numbers if len(n) < 4), None)
    if month is not None and not 1 <= month <= 12:
        return '', False
    return year + ('-%02d' % month if month else ''), False


def employment_records(experience):
    """Recognise explicit labels and 'role at employer' without guessing layouts.

    Dates close a block; blank lines also delimit blocks. Undated/ambiguous
    content remains in the original employment text, not invented records.
    """
    records, pending = [], []
    for raw in experience.splitlines():
        line = raw.strip()
        if not line:
            pending = []
            continue
        pending.append(line)
        match = RANGE.search(fold(line))
        if not match:
            pending = pending[-8:]
            continue
        start, _ = date_value(match['start'])
        end, current = date_value(match['end'])
        # Preserve offsets: Unicode decomposition can change string length.
        prefix = re.split(r'(?<!\w)(?:\d{4}|\d{1,2}/\d{4}|(?:' + MONTH + r')\.?\s+\d{4}|tháng\s+\d)', line, maxsplit=1, flags=re.I)[0].strip(' |,;:-–—()')
        evidence = '\n'.join(pending)[-4000:]
        employer = title = ''
        for item in pending[:-1] + ([prefix] if prefix else []):
            label, sep, value = item.partition(':')
            if sep and fold(label.strip()) in ('employer', 'company', 'cong ty', 'perusahaan'):
                employer = value.strip()
            elif sep and fold(label.strip()) in ('role', 'title', 'job title', 'position', 'vi tri', 'chuc danh', 'jabatan', 'posisi'):
                title = value.strip()
            else:
                parts = re.split(r'\s+(?:at|tại|tai|di|@)\s+', item, maxsplit=1, flags=re.I)
                if len(parts) == 2 and all(parts):
                    title, employer = parts
        warnings = []
        if not start or (not end and not current):
            warnings.append('Check unrecognised date against the source.')
        if start and end and start > end:
            warnings.append('End date precedes start date; correct before applying.')
        if not employer or not title:
            warnings.append('Confirm employer and job title; ambiguous fields are blank.')
        if any(len(d) == 4 for d in (start, end) if d):
            warnings.append('Only the year is supplied; no month or duration is assumed.')
        records.append({'employer': employer[:250], 'title': title[:250],
                        'start': start, 'end': end, 'current': current,
                        'source': evidence, 'note': ' '.join(warnings)})
        pending = []
        if len(records) >= 50:
            break
    return records
