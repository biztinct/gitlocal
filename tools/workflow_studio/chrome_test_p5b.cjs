/* WORKFLOW-2 P5b browser checks — LOCAL DISPOSABLE DATABASES ONLY.
     WORKFLOW_UI_URL=http://127.0.0.1:8097 P5B_FIXTURE=/path/to/fixture.json SHOTS=/dir \
     node tools/workflow_studio/chrome_test_p5b.cjs
   Run once per language after `ui_fixture_p5b.py` with P5B_LANG set (the
   fixture file holds the local logins; nothing secret is in this file).
   Shoots, in the fixture's language: the task page, the employee home list
   (/my/todo), the no-login link page, the record strip on the claim, the
   Approvals inbox Tasks group with line tasks, and the link email. Fails on
   console errors, on the banned words, and on the English sentences each
   screen is known to carry when it is NOT translated. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8097';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P5B_FIXTURE, 'utf8'));
const lang = fx.lang;
const shots = process.env.SHOTS || '/tmp';
const tag = lang.slice(0, 2);
const report = [];
const errors = [];
const ok = (k, v) => { report.push([k, v]); console.log('CHECK', k, JSON.stringify(v).slice(0, 300)); };
const banned = (t) => /\bodoo\b|odoobot/i.test(t);
// English that must be gone when the screen speaks another language
const ENGLISH = {
  todo: [/Waiting for you/, /Things a workflow has asked you to do/],
  task: [/Nothing more to do here|Needed by|receipt \d of \d/],
  link: [/It takes a minute|Needed by|I confirm|This link is just for you/],
  strip: [/receipts done|Waiting for/],
  inbox: [/Do all in turn|one for each line|to do,/],
  mail: [/You have something to do|there is one thing for you to do/],
};
function english(key, text) {
  if (lang === 'en_US') return;
  for (const re of ENGLISH[key]) assert.ok(!re.test(text), `${key}: English left (${re}) in ${lang}:\n${text.slice(0, 600)}`);
}

async function session(browser, loginName, width = 1400, height = 900) {
  const context = await browser.newContext({viewport: {width, height}, locale: lang.replace('_', '-')});
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(loginName + ': ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|\/web\/image\/|Failed to load resource|web_tour/.test(m.text() + (m.location()?.url || ''))) errors.push(loginName + ': ' + m.text());
  });
  if (loginName) {
    const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login: loginName, password: fx.password}}})).json();
    assert.ok(auth.result?.uid, 'Login failed for ' + loginName);
  }
  return {context, page};
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    // 1-2. employee home: the list, then a task page
    const h = await session(browser, fx.home, 1200, 900);
    await h.page.goto(base + '/my/todo');
    const list = await h.page.locator('main').innerText();
    ok('todo list', list.slice(0, 300));
    english('todo', list);
    await h.page.screenshot({path: path.join(shots, `${tag}_1_my_todo.png`), fullPage: true});
    await h.page.locator('a.pbwt-item').first().click();
    await h.page.waitForLoadState('domcontentloaded');
    const task = await h.page.locator('main').innerText();
    ok('task page', task.slice(0, 300));
    english('task', task);
    await h.page.screenshot({path: path.join(shots, `${tag}_2_task_page.png`), fullPage: true});

    // 3. the no-login link page (a visitor, through the link in the email)
    const v = await session(browser, null, 1200, 900);
    const link = (fx.link_mail_html.match(/href="([^"]+\/workflow\/t\/[^"]+)"/) || [])[1];
    assert.ok(link, 'link in the email');
    ok('link url', link.replace(/\/t\/.*/, '/t/…'));
    await v.page.goto(link);
    const linkText = await v.page.locator('main').innerText();
    ok('link page', linkText.slice(0, 300));
    english('link', linkText);
    await v.page.screenshot({path: path.join(shots, `${tag}_3_link_page.png`), fullPage: true});

    // 4. the record strip on the claim (staff)
    const c = await session(browser, fx.checker);
    await c.page.goto(base + `/odoo/pb.expense.claim/${fx.claim_id}`).catch(() => {});
    await c.page.locator('.pbwfs-host').waitFor({timeout: 20000});
    await c.page.waitForTimeout(1500);
    const strip = await c.page.locator('.pbwfs-host').innerText();
    ok('strip', strip);
    english('strip', strip);
    await c.page.screenshot({path: path.join(shots, `${tag}_4_record_strip.png`)});

    // 5. the Approvals inbox, Tasks group with line tasks
    await c.page.goto(base + '/odoo/action-pb_approval_config.action_pb_approval_inbox');
    await c.page.locator('.pbwfi-group').waitFor({timeout: 20000});
    await c.page.waitForTimeout(800);
    const inbox = await c.page.locator('.pbwfi-group').innerText();
    ok('inbox tasks group', inbox.slice(0, 400));
    english('inbox', inbox);
    await c.page.screenshot({path: path.join(shots, `${tag}_5_inbox_tasks.png`)});

    // 6. the link email, as it was queued
    const m = await session(browser, null, 760, 900);
    await m.page.setContent(`<html><body style="margin:0"><div style="padding:12px 16px;font:14px sans-serif;border-bottom:1px solid #ddd"><b>${fx.link_mail_subject.replace(/</g, '&lt;')}</b></div>${fx.link_mail_html}</body></html>`);
    const mail = fx.link_mail_subject + '\n' + await m.page.locator('body').innerText();
    ok('mail', mail.slice(0, 300));
    english('mail', mail);
    await m.page.screenshot({path: path.join(shots, `${tag}_6_link_email.png`), fullPage: true});
    assert.ok(!banned(list + task + linkText + strip + inbox + mail), 'banned word on a screen');
  } finally {
    await browser.close();
  }
  ok('console errors', errors);
  fs.writeFileSync(path.join(shots, `report_${tag}.json`), JSON.stringify({lang, report, errors}, null, 1));
  if (errors.length) process.exitCode = 1;
})().catch((e) => { console.error('FAILED', e.stack || e.message); fs.writeFileSync(path.join(shots, `report_${tag}.json`), JSON.stringify({lang, report, errors, failed: e.message}, null, 1)); process.exitCode = 2; });
