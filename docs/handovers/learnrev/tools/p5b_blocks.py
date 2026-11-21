#!/usr/bin/env python3
"""LEARNREV P5b — splice rewritten lesson / walkthrough blocks into data.js, and
validate them on a private mirror without touching the real tree.

A BLOCK FILE holds exactly one top-level entry, copied out of
docs/tutorial_poc/author/data.js and rewritten:

  * a lesson:   starts with the line `  L10: {` and ends with the line `  },`
  * a scenario: starts with the line `  {`, its next line is `    key: "sc_x",`,
                and it ends with the line `  },`

Usage
-----
  p5b_blocks.py extract <data.js> <key> > block.js     # copy one entry out
  p5b_blocks.py splice  <data.js> <block.js>...        # replace in place
  p5b_blocks.py validate <block.js>...                 # mirror + every gate
  p5b_blocks.py shape   <block.js>...                  # four-line inventory

`validate` builds a mirror of the repo under $P5B_MIRROR (default: a temp dir):
every top-level entry is a symlink to the real tree except docs/, whose
tutorial_poc/author is a COPY. The blocks are spliced into the copy and
`gen_learn_data.py --check` runs against it: exit 1 ("STALE") means every gate
passed (the copy differs from the shipped content, as it should); any other
non-zero exit is a gate failure and is printed. Nothing in the real tree is
written.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))  # docs/handovers/learnrev/tools
AUTHOR_REL = os.path.join('docs', 'tutorial_poc', 'author')

LESSON_HEAD = re.compile(r'^  (L[0-9A-Z]+): \{\s*$')
SC_KEY = re.compile(r'^    key: "(sc_[a-z0-9_]+)",\s*$')
CLOSE = re.compile(r'^  \},?\s*$')


def block_key(text):
    lines = text.rstrip('\n').split('\n')
    # tolerate leading comment lines
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith(('/*', '*', '//'))):
        i += 1
    m = LESSON_HEAD.match(lines[i])
    if m:
        return m.group(1), lines[i:]
    if lines[i].rstrip() == '  {' and i + 1 < len(lines):
        m = SC_KEY.match(lines[i + 1])
        if m:
            return m.group(1), lines[i:]
    raise SystemExit('block does not start with "  Lx: {" or "  {" + key line: %r' % lines[i][:60])


def find_region(lines, key):
    """(start, end) line indexes, end inclusive, of the entry `key`."""
    start = None
    if key.startswith('sc_'):
        for i, l in enumerate(lines):
            if SC_KEY.match(l) and SC_KEY.match(l).group(1) == key:
                assert lines[i - 1].rstrip() == '  {', 'scenario %s: no "  {" above key' % key
                start = i - 1
                break
    else:
        for i, l in enumerate(lines):
            m = LESSON_HEAD.match(l)
            if m and m.group(1) == key:
                start = i
                break
    if start is None:
        raise SystemExit('entry %s not found' % key)
    for j in range(start + 1, len(lines)):
        if CLOSE.match(lines[j]):
            return start, j
    raise SystemExit('entry %s: no closing "  }," found' % key)


def extract(data_js, key):
    lines = open(data_js, encoding='utf-8').read().split('\n')
    s, e = find_region(lines, key)
    return '\n'.join(lines[s:e + 1]) + '\n'


def splice(data_js, blocks):
    text = open(data_js, encoding='utf-8').read()
    lines = text.split('\n')
    for path in blocks:
        key, blines = block_key(open(path, encoding='utf-8').read())
        # the block must end with the closing line
        while blines and not blines[-1].strip():
            blines.pop()
        if not CLOSE.match(blines[-1]):
            raise SystemExit('%s: last line must be "  }," (got %r)' % (path, blines[-1]))
        if not blines[-1].rstrip().endswith(','):
            blines[-1] = blines[-1].rstrip() + ','
        s, e = find_region(lines, key)
        lines[s:e + 1] = blines
        print('spliced %s from %s (%d lines)' % (key, os.path.basename(path), len(blines)))
    open(data_js, 'w', encoding='utf-8').write('\n'.join(lines))


def mirror():
    root = os.environ.get('P5B_MIRROR') or tempfile.mkdtemp(prefix='p5b_mirror_')
    if os.path.exists(root):
        shutil.rmtree(root)
    os.makedirs(root)
    for name in os.listdir(REPO):
        if name in ('.git', 'docs'):
            continue
        os.symlink(os.path.join(REPO, name), os.path.join(root, name))
    os.makedirs(os.path.join(root, 'docs', 'tutorial_poc'))
    for name in os.listdir(os.path.join(REPO, 'docs')):
        if name == 'tutorial_poc':
            continue
        os.symlink(os.path.join(REPO, 'docs', name), os.path.join(root, 'docs', name))
    for name in os.listdir(os.path.join(REPO, 'docs', 'tutorial_poc')):
        src = os.path.join(REPO, 'docs', 'tutorial_poc', name)
        dst = os.path.join(root, 'docs', 'tutorial_poc', name)
        if name == 'author':
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            os.symlink(src, dst)
    return root


def dump(author):
    out = subprocess.run(['node', os.path.join(author, 'tools', 'dump_content.js')],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit('data.js does not load:\n' + out.stderr[-3000:])
    return json.loads(out.stdout)


def en(p):
    return (p or {}).get('en') if isinstance(p, dict) else (p or '')


def shape_report(data, keys):
    bad = 0
    for key in keys:
        if key.startswith('sc_'):
            sc = next(s for s in data['scenarios'] if s['key'] == key)
            steps = [(st.get('key'), st.get('anchor') or '', st.get('say') or {}, st) for st in sc['steps']]
        else:
            steps = [(i, st.get('anchor') or '', st, st) for i, st in enumerate(data['lessons'][key]['steps'])]
        four = legacy = 0
        for k, anchor, holder, st in steps:
            g = ((holder.get('variants') or {}).get('generic') or {})
            has_look = en(holder.get('look')) or en(g.get('look'))
            is_field = bool(holder.get('field') or st.get('field'))
            if has_look and (is_field or (en(holder.get('means')) or en(g.get('means')))):
                four += 1
                if en(holder.get('body')):
                    print('  %s step %s: still carries a body beside the four lines' % (key, k))
                    bad += 1
            else:
                legacy += 1
                print('  %s step %s: NOT in the four lines (anchor %s)' % (key, k, anchor))
                bad += 1
            if not holder.get('vi_checked', True):
                pass
        print('%-16s steps=%2d four-line=%2d legacy=%d' % (key, len(steps), four, legacy))
    return bad


def validate(blocks):
    root = mirror()
    author = os.path.join(root, AUTHOR_REL)
    splice(os.path.join(author, 'data.js'), blocks)
    data = dump(author)
    keys = [block_key(open(b, encoding='utf-8').read())[0] for b in blocks]
    bad = shape_report(data, keys)
    gen = subprocess.run([sys.executable, os.path.join(author, 'tools', 'gen_learn_data.py'),
                          '--check', '--warnings'], capture_output=True, text=True, cwd=root)
    out = gen.stdout + gen.stderr
    if gen.returncode not in (0, 1):
        print(out[-6000:])
        print('GATES FAILED (exit %d)' % gen.returncode)
        return 2
    # only the warning-band sentences that belong to these blocks
    mine = [l for l in out.split('\n') if any(re.search(r'\b%s\b' % re.escape(k), l) for k in keys)
            and 'word' in l]
    for l in mine[:60]:
        print('  warn: ' + l.strip())
    shp = subprocess.run([sys.executable, os.path.join(author, 'tools', 'test_step_shape.py')],
                         capture_output=True, text=True, cwd=root)
    if shp.returncode:
        print(shp.stdout[-3000:])
        print('STEP-SHAPE NEGATIVE CONTROLS FAILED')
        return 3
    print('GATES PASSED for %s%s' % (', '.join(keys), '' if not bad else ' — but %d step(s) not four-line' % bad))
    if not os.environ.get('P5B_KEEP'):
        shutil.rmtree(root, ignore_errors=True)
    return 1 if bad else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == 'extract':
        sys.stdout.write(extract(argv[2], argv[3]))
        return 0
    if cmd == 'splice':
        splice(argv[2], argv[3:])
        return 0
    if cmd == 'validate':
        return validate(argv[2:])
    if cmd == 'shape':
        root = mirror()
        author = os.path.join(root, AUTHOR_REL)
        splice(os.path.join(author, 'data.js'), argv[2:])
        keys = [block_key(open(b, encoding='utf-8').read())[0] for b in argv[2:]]
        r = shape_report(dump(author), keys)
        shutil.rmtree(root, ignore_errors=True)
        return 1 if r else 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
