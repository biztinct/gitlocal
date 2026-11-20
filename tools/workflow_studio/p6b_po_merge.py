"""WF2 P6b — add the Studio workbench's phrases to pb_lifecycle's .po files.

    python3 tools/workflow_studio/p6b_po_merge.py PHRASES.json LANG TRANSLATIONS.json [--check]
    … [--python models/workflow_definition.py]   (server sentences: `#. odoo-python`
                                                   and that file as the occurrence)

PHRASES.json is `node tools/workflow_studio/p6b_words.cjs extract`; LANG is
vi_VN or id_ID; TRANSLATIONS.json is {msgid: msgstr} for the phrases the .po
does not translate yet.

Text edits only (the file is never re-exported, so no existing line moves or
is re-wrapped): an entry that already has the msgid gets the
`#. odoo-javascript` marker (right after its `#. module:` line) and one
`#: code:addons/pb_lifecycle/static/workflow/<file>:0` occurrence per
workbench file, and keeps its translation; a new msgid is appended as a new
entry with the three things every entry needs (module, marker, occurrence).
Running it twice changes nothing.
"""
import json
import re
import sys

PO = 'pb_lifecycle/i18n/%s.po'
WB = 'code:addons/pb_lifecycle/static/workflow/'


def unquote(lines):
    return ''.join(json.loads(x) for x in re.findall(r'"(?:[^"\\]|\\.)*"', ' '.join(lines)))


def quote(text):
    return '"%s"' % text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')


def parse(text):
    """Blocks separated by blank lines; for each: lines, msgid, msgstr span."""
    blocks = []
    for raw in re.split(r'\n\s*\n', text.strip('\n')):
        lines = raw.split('\n')
        msgid = msgstr = None
        i = 0
        spans = {}
        while i < len(lines):
            m = re.match(r'^(msgid|msgstr|msgctxt|msgid_plural) ', lines[i])
            if m:
                j = i + 1
                while j < len(lines) and lines[j].startswith('"'):
                    j += 1
                spans[m.group(1)] = (i, j)
                i = j
            else:
                i += 1
        if 'msgid' in spans:
            a, b = spans['msgid']
            msgid = unquote([lines[a][6:]] + lines[a + 1:b])
        if 'msgstr' in spans:
            a, b = spans['msgstr']
            msgstr = unquote([lines[a][7:]] + lines[a + 1:b])
        blocks.append({'lines': lines, 'msgid': msgid, 'msgstr': msgstr, 'spans': spans,
                       'ctx': 'msgctxt' in spans})
    return blocks


def main():
    phrases = json.load(open(sys.argv[1]))
    lang = sys.argv[2]
    tr = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else {}
    marker, python_file = '#. odoo-javascript', None
    if '--python' in sys.argv:
        marker, python_file = '#. odoo-python', sys.argv[sys.argv.index('--python') + 1]
    path = PO % lang
    text = open(path, encoding='utf-8').read()
    blocks = parse(text)
    index = {b['msgid']: b for b in blocks if b['msgid'] and not b['ctx']}
    changed_entries = appended = 0
    missing = []
    for p in phrases:
        msgid, files = p['msgid'], p['files']
        places = (['#: code:addons/pb_lifecycle/%s:0' % python_file] if python_file else
                  ['#: %s%s:0' % (WB, f) for f in files])
        b = index.get(msgid)
        if b:
            lines = b['lines']
            before = list(lines)
            if not any(l.strip() == marker for l in lines):
                k = next(i for i, l in enumerate(lines) if l.startswith('#. module'))
                lines.insert(k + 1, marker)
            for place in places:
                if place not in lines:
                    last = max([i for i, l in enumerate(lines) if l.startswith('#:')] or
                               [max(i for i, l in enumerate(lines) if l.startswith('#.'))])
                    lines.insert(last + 1, place)
            if not b['msgstr']:
                if msgid not in tr:
                    missing.append(msgid)
                else:
                    a, e = _span(lines, 'msgstr')
                    lines[a:e] = ['msgstr ' + quote(tr[msgid])]
            if lines != before:
                changed_entries += 1
            continue
        if msgid not in tr:
            missing.append(msgid)
            continue
        blocks.append({'lines': ['#. module: pb_lifecycle', marker] + places +
                       ['msgid ' + quote(msgid), 'msgstr ' + quote(tr[msgid])], 'msgid': msgid})
        index[msgid] = blocks[-1]
        appended += 1
    if missing:
        print('NO TRANSLATION for %d phrases, e.g. %r' % (len(missing), missing[:5]))
        sys.exit(1)
    out = '\n\n'.join('\n'.join(b['lines']) for b in blocks) + '\n'
    if '--check' in sys.argv:
        print('%s: would change %d entries, append %d' % (lang, changed_entries, appended))
        return
    open(path, 'w', encoding='utf-8').write(out)
    print('%s: %d existing entries given the workbench marker/occurrence, %d appended' % (lang, changed_entries, appended))


def _span(lines, key):
    a = next(i for i, l in enumerate(lines) if l.startswith(key + ' '))
    e = a + 1
    while e < len(lines) and lines[e].startswith('"'):
        e += 1
    return a, e


if __name__ == '__main__':
    main()
