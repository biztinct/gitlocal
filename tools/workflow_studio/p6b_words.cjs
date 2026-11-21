#!/usr/bin/env node
/* WORKFLOW-2 P6b — the Studio workbench's words: extract and coverage.

     node tools/workflow_studio/p6b_words.cjs extract   > phrases.json
     node tools/workflow_studio/p6b_words.cjs coverage [--po-dir pb_lifecycle/i18n] [--verbose]

   The workbench (pb_lifecycle/static/workflow/*.js) is a set of classic
   scripts. Every visible English phrase is the first argument of `_t(...)`
   (or the 2nd/3rd of `_t.n(count, one, many)`), always a plain string
   literal so this script and the `.po` can find it.

   extract  — every msgid with its file occurrences (JSON), in file order.
   coverage — every string literal (and the text parts of template
              literals) that looks like visible English and is NOT a `_t`
              argument, per file; with --po-dir, also the msgids that have
              no Vietnamese / Indonesian entry. Exit code 1 when anything is
              left outside the allow-list.

   A small hand-written tokenizer (strings, template literals with nested
   `${}`, comments, regular-expression literals) — no dependency. */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const DIR = path.join(ROOT, 'pb_lifecycle/static/workflow');
const FILES = ['icons.js', 'graph.js', 'app.js', 'forms.js', 'conditions.js', 'templates.js', 'record-context.js',
  'stages.js', 'steps.js', 'actions.js', 'drag.js', 'people.js', 'insights.js', 'schedule.js', 'repeat.js'];

const KEYWORDS_BEFORE_REGEX = new Set(['return', 'typeof', 'case', 'in', 'of', 'new', 'delete', 'void', 'throw', 'else', 'do', 'instanceof', 'yield', 'await']);

/* Tokenize: returns [{kind:'str'|'tpl', value, start, end, parts?}] plus the
   significant tokens needed to know what precedes a literal. */
function scan(src) {
  const out = [];
  let i = 0;
  const n = src.length;
  let prev = ''; // last significant token text (identifier / punctuator)
  function readString(q) {
    const start = i; i++;
    let v = '';
    while (i < n && src[i] !== q) {
      if (src[i] === '\\') {
        const c = src[i + 1];
        const map = {n: '\n', t: '\t', r: '\r', '\\': '\\', "'": "'", '"': '"', '`': '`', '0': '\0'};
        if (c === 'u') {
          if (src[i + 2] === '{') { const e = src.indexOf('}', i); v += String.fromCodePoint(parseInt(src.slice(i + 3, e), 16)); i = e + 1; continue; }
          v += String.fromCharCode(parseInt(src.slice(i + 2, i + 6), 16)); i += 6; continue;
        }
        if (c === 'x') { v += String.fromCharCode(parseInt(src.slice(i + 2, i + 4), 16)); i += 4; continue; }
        if (c === '\n') { i += 2; continue; }
        v += map[c] !== undefined ? map[c] : c; i += 2; continue;
      }
      v += src[i]; i++;
    }
    i++;
    return {kind: 'str', value: v, start, end: i};
  }
  function readTemplate() {
    const start = i; i++;
    const parts = []; let cur = ''; let curStart = i;
    while (i < n && src[i] !== '`') {
      if (src[i] === '\\') { cur += src.slice(i, i + 2); i += 2; continue; }
      if (src[i] === '$' && src[i + 1] === '{') {
        parts.push({text: cur, start: curStart});
        i += 2;
        const inner = readExprUntilBrace();
        out.push(...inner);
        cur = ''; curStart = i;
        continue;
      }
      cur += src[i]; i++;
    }
    parts.push({text: cur, start: curStart});
    i++;
    return {kind: 'tpl', parts, start, end: i};
  }
  function readExprUntilBrace() {
    // scan an expression inside ${ … } until the matching }
    const toks = [];
    let depth = 0;
    while (i < n) {
      const c = src[i];
      if (c === '}' && depth === 0) { i++; prev = '}'; return toks; }
      const t = step();
      if (t === '{') depth++;
      else if (t === '}') depth--;
      if (t && typeof t === 'object') toks.push(t);
    }
    return toks;
  }
  function step() {
    const c = src[i];
    if (c === '/' && src[i + 1] === '/') { const e = src.indexOf('\n', i); i = e < 0 ? n : e; return null; }
    if (c === '/' && src[i + 1] === '*') { const e = src.indexOf('*/', i + 2); i = e < 0 ? n : e + 2; return null; }
    if (/\s/.test(c)) { i++; return null; }
    if (c === "'" || c === '"') { const s = readString(c); s.prev = prevBefore(s.start); prev = 'str'; return s; }
    if (c === '`') { const t = readTemplate(); t.prev = prevBefore(t.start); prev = 'tpl'; return t; }
    if (c === '/') {
      const regex = !(prev === 'str' || prev === 'tpl' || prev === ')' || prev === ']' || /^[\w$]+$/.test(prev) && !KEYWORDS_BEFORE_REGEX.has(prev));
      if (regex) {
        i++; let cls = false;
        while (i < n) {
          const d = src[i];
          if (d === '\\') { i += 2; continue; }
          if (d === '[') cls = true; else if (d === ']') cls = false;
          else if (d === '/' && !cls) break;
          i++;
        }
        i++; while (/[a-z]/i.test(src[i] || '')) i++;
        prev = 'regex'; return null;
      }
      i++; prev = '/'; return '/';
    }
    if (/[\w$]/.test(c)) { let e = i; while (e < n && /[\w$]/.test(src[e])) e++; prev = src.slice(i, e); i = e; return prev; }
    i++; prev = c; return c;
  }
  function prevBefore(pos) {
    // the source text just before a literal (up to 12 chars, spaces removed)
    return src.slice(Math.max(0, pos - 14), pos).replace(/\s+/g, '');
  }
  while (i < n) {
    const t = step();
    if (t && typeof t === 'object') out.push(t);
  }
  return out;
}

/* Is a literal an argument of _t / _t.n?  `_t(` directly before it, or `_t.n(x,` / `_t.n(x,'one',` */
function isWrapped(lit, src) {
  const before = src.slice(Math.max(0, lit.start - 200), lit.start);
  if (/(^|[^\w$.])_t\(\s*$/.test(before)) return 'msgid';
  if (/(^|[^\w$.])_t\.later\(\s*$/.test(before)) return 'msgid';
  // _t.n(count, 'one', 'many', …): find the last "_t.n(" and check we are its 2nd or 3rd argument
  const k = before.lastIndexOf('_t.n(');
  if (k >= 0) {
    const seg = before.slice(k + 5);
    // count top-level commas in seg
    let depth = 0, commas = 0, q = null;
    for (let j = 0; j < seg.length; j++) {
      const ch = seg[j];
      if (q) { if (ch === '\\') j++; else if (ch === q) q = null; continue; }
      if (ch === "'" || ch === '"' || ch === '`') { q = ch; continue; }
      if ('([{'.includes(ch)) depth++;
      else if (')]}'.includes(ch)) { depth--; if (depth < 0) return false; }
      else if (ch === ',' && depth === 0) commas++;
    }
    if (depth === 0 && (commas === 1 || commas === 2) && /,\s*$/.test(seg)) return 'msgid';
  }
  return false;
}

/* Allow-list: literals that look like words but are not shown as English
   text (keys, CSS, symbols, names, technical values). */
const ALLOW = [
  /^Workflow Studio$/, /^Payobook$/,
];
function looksVisible(s) {
  const t = s.trim();
  if (!t) return false;
  if (!/[A-Za-z]{2,}/.test(t)) return false;
  if (ALLOW.some((r) => r.test(t))) return false;
  if (/^[a-z0-9_.:\-\/#\[\]=*>+~^$|() ,]+$/.test(t) && !/\b(the|a|an|to|of|and|or|is|for|this|it|you|on|in)\b/.test(t)) return false; // keys, selectors, classes
  if (/^[a-z][\w-]*$/.test(t)) return false; // one lowercase word: a key or a class
  if (/^[A-Z][A-Za-z]+$/.test(t) && /^(Escape|Enter|Tab|Backspace|Delete|Arrow\w+|Home|End|Page\w+|DOMContentLoaded|Object|Array|String|Number|Boolean|Date|Error|Map|Set|JSON|Math|Promise)$/.test(t)) return false;
  if (/^(https?:|\/|\.\/|data:|#|<svg|<path|<circle|<rect|<line|<polyline|<polygon)/.test(t)) return false;
  if (/^[A-Z_]+$/.test(t)) return false;
  if (/^(GET|POST|Content-Type|application\/json|text\/|image\/)/.test(t)) return false;
  if (/^[\w.-]+\.(js|css|png|svg|woff2?)$/.test(t)) return false;
  if (/^(var|calc|rgba?|hsla?)\(/.test(t)) return false;
  if (/^[\w-]+:[^ ]/.test(t) && !/\s/.test(t)) return false;
  return true;
}

/* Visible text inside an HTML-ish template part: text between tags, and the
   values of title / aria-label / placeholder / alt / data-tip attributes. */
function visibleInHtml(text) {
  const found = [];
  const attrs = /\b(title|aria-label|placeholder|alt|data-tip|data-label)=(["'])([^"'$]*)\2/g;
  let m;
  while ((m = attrs.exec(text))) if (looksVisible(m[3])) found.push(m[3]);
  // Plain text with no markup at all: the whole string.
  if (!/[<>="]/.test(text)) { if (looksVisible(text)) found.push(text.trim()); return found; }
  // Otherwise only what sits between a ">" and the next "<" (or the end).
  const re = />([^<>]*)(?=<|$)/g;
  while ((m = re.exec(text))) {
    const c = m[1].replace(/&[a-z]+;|&#\d+;/g, ' ').trim();
    if (c && !/[="]/.test(c) && looksVisible(c)) found.push(c);
  }
  // Text before the first "<" when the part does not start inside a tag.
  const head = /^([^<>="]*)</.exec(text);
  if (head && looksVisible(head[1])) found.push(head[1].trim());
  return found;
}

function analyse(file) {
  const src = fs.readFileSync(path.join(DIR, file), 'utf8');
  const lits = scan(src);
  const msgids = [];
  const left = [];
  const line = (pos) => src.slice(0, pos).split('\n').length;
  for (const lit of lits) {
    if (lit.kind === 'str') {
      const w = isWrapped(lit, src);
      if (w) { msgids.push({msgid: lit.value, line: line(lit.start)}); continue; }
      // property keys ({key:'x'}) and comparisons are values; only flag words
      for (const v of visibleInHtml(lit.value)) left.push({text: v, line: line(lit.start)});
    } else {
      // a template literal directly wrapped is a mistake (holes are not msgids)
      if (/(^|[^\w$.])_t\(\s*$/.test(src.slice(Math.max(0, lit.start - 10), lit.start))) left.push({text: '`' + lit.parts.map((p) => p.text).join('${…}') + '` (template literal inside _t)', line: line(lit.start)});
      for (const p of lit.parts) for (const v of visibleInHtml(p.text)) left.push({text: v, line: line(p.start)});
    }
  }
  return {file, msgids, left};
}

function loadAllow() {
  const f = path.join(__dirname, 'p6b_words_allow.json');
  if (!fs.existsSync(f)) return {};
  return JSON.parse(fs.readFileSync(f, 'utf8'));
}

function poMsgids(file) {
  // minimal .po reader: msgid → msgstr (multi-line strings joined)
  if (!fs.existsSync(file)) return new Map();
  const txt = fs.readFileSync(file, 'utf8');
  const res = new Map();
  const unq = (s) => JSON.parse(s.replace(/\\'/g, "'"));
  for (const block of txt.split(/\n\s*\n/)) {
    const m = /(?:^|\n)msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)msgstr ((?:"(?:[^"\\]|\\.)*"\s*)+)/.exec(block);
    if (!m) continue;
    const join = (x) => (x.match(/"(?:[^"\\]|\\.)*"/g) || []).map(unq).join('');
    res.set(join(m[1]), {msgstr: join(m[2]), block});
  }
  return res;
}

const mode = process.argv[2] || 'coverage';
const results = FILES.map(analyse);
if (mode === 'extract') {
  const map = new Map();
  for (const r of results) for (const m of r.msgids) {
    if (!map.has(m.msgid)) map.set(m.msgid, []);
    if (!map.get(m.msgid).includes(r.file)) map.get(m.msgid).push(r.file);
  }
  process.stdout.write(JSON.stringify([...map].map(([msgid, files]) => ({msgid, files})), null, 1) + '\n');
} else {
  const verbose = process.argv.includes('--verbose');
  const poDirArg = process.argv.indexOf('--po-dir');
  const allow = loadAllow();
  let total = 0;
  const rows = [];
  for (const r of results) {
    const okList = new Set(allow[r.file] || []);
    const rest = r.left.filter((x) => !okList.has(x.text));
    total += rest.length;
    rows.push({file: r.file, phrases: new Set(r.msgids.map((m) => m.msgid)).size, calls: r.msgids.length, english_left: rest.length, allowed: r.left.length - rest.length});
    if (verbose) for (const x of rest) console.log(`  ${r.file}:${x.line}  ${JSON.stringify(x.text).slice(0, 160)}`);
  }
  if (poDirArg > 0) {
    const dir = path.resolve(process.argv[poDirArg + 1]);
    for (const lang of ['vi_VN', 'id_ID']) {
      const po = poMsgids(path.join(dir, lang + '.po'));
      for (const row of rows) {
        const r = results.find((x) => x.file === row.file);
        const ids = [...new Set(r.msgids.map((m) => m.msgid))];
        const missing = ids.filter((id) => !po.has(id) || !po.get(id).msgstr || !/odoo-javascript/.test(po.get(id).block) || !po.get(id).block.includes('static/workflow/' + row.file));
        row['no_' + lang] = missing.length;
        total += missing.length;
        if (verbose) for (const x of missing) console.log(`  ${row.file} [${lang}] no entry: ${JSON.stringify(x).slice(0, 120)}`);
      }
    }
  }
  console.table(rows);
  const all = new Set(); for (const r of results) for (const m of r.msgids) all.add(m.msgid);
  console.log('DISTINCT_PHRASES=' + all.size + ' LEFT=' + total);
  process.exit(total ? 1 : 0);
}
