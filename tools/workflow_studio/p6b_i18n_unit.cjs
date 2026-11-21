/* WF2 P6b — unit checks of the workbench's `_t` (static/workflow/i18n.js).
     node tools/workflow_studio/p6b_i18n_unit.cjs
   Runs i18n.js in a sandbox with a minimal document, three times: no
   dictionary (English), a Vietnamese dictionary, and a dictionary that
   could not be read. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const src = fs.readFileSync(path.join(__dirname, '../../pb_lifecycle/static/workflow/i18n.js'), 'utf8');

function load() {
  const doc = {documentElement: {lang: 'en'}, querySelector: () => null, addEventListener: () => {}};
  const ctx = {document: doc, MutationObserver: class { observe() {} disconnect() {} }, Object, String};
  vm.createContext(ctx);
  vm.runInContext(src + '\n;this._t=_t;', ctx);
  return ctx;
}
let n = 0;
const check = (fn, why) => { fn(); n++; console.log('ok', n, why); };

// 1. English: exactly what it was given, holes filled.
let c = load(), t = c._t;
check(() => assert.equal(t('Save'), 'Save'), 'English phrase unchanged');
check(() => assert.equal(t('%(n)s steps', {n: 3}), '3 steps'), 'holes filled');
check(() => assert.equal(t('%(n)s steps'), '%(n)s steps'), 'no values: text as written');
check(() => assert.equal(t('a %(x)s b', {y: 1}), 'a %(x)s b'), 'an unknown hole stays as written');
check(() => assert.equal(t.n(1, '%(n)s step', '%(n)s steps'), '1 step'), '_t.n singular');
check(() => assert.equal(t.n(2, '%(n)s step', '%(n)s steps'), '2 steps'), '_t.n plural');
check(() => assert.equal(t.later('Done'), 'Done'), '_t.later returns the phrase');
check(() => assert.equal(t.on, false), 'English: grammar helpers on');
check(() => assert.equal(t('%(a)s and %(b)s', {a: '%(b)s', b: 'x'}), '%(b)s and x'), 'a value is never filled again');
check(() => assert.equal(t('Done', {}), 'Done'), 'empty values');

// 2. A dictionary.
c = load(); t = c._t;
t.load({lang: 'vi_VN', words: {'Save': 'Lưu', '%(n)s steps': '%(n)s bước', '%(n)s step': '%(n)s bước', 'Every %(days)s at %(time)s': 'Mỗi %(days)s lúc %(time)s'}});
check(() => assert.equal(t('Save'), 'Lưu'), 'translated');
check(() => assert.equal(t('Not in the file'), 'Not in the file'), 'a missing phrase stays English');
check(() => assert.equal(t.n(2, '%(n)s step', '%(n)s steps'), '2 bước'), '_t.n translated');
check(() => assert.equal(t('Every %(days)s at %(time)s', {days: 'Thứ Hai', time: '9:00'}), 'Mỗi Thứ Hai lúc 9:00'), 'holes in the translation');
check(() => assert.equal(t.on, true), 'translated: English grammar helpers off');
check(() => assert.equal(c.document.documentElement.lang, 'vi'), 'page language set');
check(() => assert.equal(t('constructor'), 'constructor'), 'no prototype lookups');

// 3. An English login's empty dictionary, and a broken payload.
c = load(); t = c._t;
t.load({lang: 'en_US', words: {}});
check(() => assert.equal(t.on, false), 'English dictionary: off');
t.load(null); t.load({lang: 'vi_VN'}); t.load({lang: 'vi_VN', words: 'x'});
check(() => assert.equal(t('Save'), 'Save'), 'nothing loaded: English, no error');
console.log(`P6B_I18N_UNIT ${n} passed`);
