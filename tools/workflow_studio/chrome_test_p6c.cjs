/* WORKFLOW-2 P6c browser checks — LOCAL DISPOSABLE DATABASES ONLY.
     WORKFLOW_UI_URL=http://127.0.0.1:8089 P6C_FIXTURE=/outside/repo/p6c.json SHOTS=/dir \
     node tools/workflow_studio/chrome_test_p6c.cjs
   After `ui_fixture_p6c.py` (the fixture file holds the local logins; nothing
   secret is in this file). For English, Vietnamese and Indonesian:
     1. My Leave at 390 px: the sent-back request says "Sent back", the reason
        and "Ask again";
     2. "Ask again" opens the request form filled in from it; the employee
        changes the morning to the afternoon and sends it;
     3. the new request is waiting for approval and names the old one; the old
        one says "Asked again on …" and has no button any more;
     4. the staff Time off cockpit, "Sent back" view: the card's chip and
        reason.
   English also: staff "Ask again" from a card (the "Apply for" drawer filled
   in) through to the new request, and the standard form's one-line note.
   Fails on console errors and on the word "Odoo" anywhere on a page. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8089';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P6C_FIXTURE, 'utf8'));
const shots = process.env.SHOTS || '/tmp';
const errors = [];
const ok = (k, v) => console.log('CHECK', k, JSON.stringify(v).slice(0, 500));
const branded = (t) => /\bodoo\b|odoobot/i.test(t);

const WORDS = {
  en_US: {tag: 'en', back: 'Sent back', again: 'Ask again', why: 'It was not refused',
          banner: 'Filled in from your request that was sent back', flash: 'Asked again. Your new request is waiting for approval.',
          waiting: 'Waiting approval', of: 'Asked again after the request for', as: 'Asked again on',
          staffBack: 'Sent back', staffWhy: 'Sent back:'},
  vi_VN: {tag: 'vi', back: 'Đã bị trả lại', again: 'Gửi lại', why: 'Đơn không bị từ chối',
          banner: 'Đã điền sẵn từ đơn của bạn bị trả lại', flash: 'Đã gửi lại. Đơn mới của bạn đang chờ phê duyệt.',
          waiting: null, of: 'Đã gửi lại sau khi đơn nghỉ phép ngày', as: 'Đã gửi lại vào',
          staffBack: 'Đã bị trả lại', staffWhy: 'Đã bị trả lại:'},
  id_ID: {tag: 'id', back: 'Dikembalikan', again: 'Ajukan lagi', why: 'Permintaan ini tidak ditolak',
          banner: 'Diisi dari permintaan Anda yang dikembalikan', flash: 'Sudah diajukan lagi. Permintaan baru Anda menunggu persetujuan.',
          waiting: null, of: 'Diajukan lagi setelah permintaan cuti untuk', as: 'Diajukan lagi pada',
          staffBack: 'Dikembalikan', staffWhy: 'Dikembalikan:'},
};

async function session(browser, loginName, width, height) {
  const context = await browser.newContext({viewport: {width, height}, deviceScaleFactor: 2});
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(loginName + ': ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|\/web\/image\/|Failed to load resource|web_tour/.test(m.text() + (m.location()?.url || ''))) errors.push(loginName + ': ' + m.text());
  });
  const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login: loginName, password: fx.password}}})).json();
  assert.ok(auth.result?.uid, 'Login failed for ' + loginName);
  return {context, page};
}

async function noBrand(page, what) {
  const text = await page.locator('body').innerText();
  assert.ok(!branded(text), what + ': the word Odoo is on the page');
  return text;
}

async function employee(browser, lang) {
  const w = WORDS[lang];
  const person = fx.people[lang];
  const {context, page} = await session(browser, person.login, 390, 844);
  // 1. My Leave: the sent-back request
  await page.goto(base + '/my/work/leave');
  const row = page.locator('#pbew-lv-' + person.leave_id);
  await row.waitFor({timeout: 30000});
  const rowText = await row.innerText();
  ok(w.tag + ' 1 row', rowText);
  // the badge style capitalises each word (the page's existing look)
  assert.ok(rowText.toLowerCase().includes(w.back.toLowerCase()), 'chip');
  assert.ok(rowText.includes(w.why), 'why line');
  assert.ok(rowText.includes(w.again), 'Ask again button');
  assert.equal(await row.locator('.pbme-badge--sent_back').count(), 1);
  await noBrand(page, w.tag + ' my leave');
  await row.scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_1_sent_back_390.png`)});
  // 1b. the employee home's "My requests": sent back, your turn
  await page.goto(base + '/my/requests');
  await page.waitForLoadState('networkidle');
  const turn = (await noBrand(page, w.tag + ' my requests before')).toLowerCase();
  assert.ok(turn.includes(w.back.toLowerCase()), 'My requests says sent back (your turn)');
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_1b_my_requests_your_turn_390.png`)});
  await page.goto(base + '/my/work/leave');
  await row.waitFor({timeout: 30000});
  // 2. Ask again: the same form, filled in
  await row.locator('.pbew-again-btn').click();
  await page.waitForURL(/again=/);
  const card = page.locator('#pbew-ask.pbew-ask--again');
  await card.waitFor({timeout: 15000});
  const cardText = await card.innerText();
  ok(w.tag + ' 2 form', cardText.slice(0, 300));
  assert.ok(cardText.includes(w.banner), 'banner');
  assert.equal(await card.locator('input[name=again_of]').inputValue(), String(person.leave_id));
  assert.equal(await card.locator('input[name=date_from]').inputValue(), person.day);
  assert.equal(await card.locator('input[name=date_to]').inputValue(), person.day);
  assert.equal(await card.locator('select[name=period_from]').inputValue(), 'am');
  assert.equal(await card.locator('input[name=note]').inputValue(), 'Family visit');
  // the approver asked for the afternoon: change it, as the person would
  await card.locator('select[name=period_from]').selectOption('pm');
  await card.locator('[data-pbew-preview]:not(.d-none)').waitFor({timeout: 10000});
  await card.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_2_ask_again_form_390.png`)});
  await card.screenshot({path: path.join(shots, `p6c_${w.tag}_2b_ask_again_card_390.png`)});
  await noBrand(page, w.tag + ' form');
  // 3. send it: a new request, waiting for approval, linked both ways
  await Promise.all([page.waitForURL(/done=leave_again/), card.locator('button[type=submit]').click()]);
  const flash = await page.locator('.pbew-flash').innerText();
  ok(w.tag + ' 3 flash', flash);
  assert.ok(flash.includes(w.flash));
  const oldRow = page.locator('#pbew-lv-' + person.leave_id);
  const oldText = await oldRow.innerText();
  assert.ok(oldText.includes(w.as), 'old: asked again on');
  assert.equal(await oldRow.locator('.pbew-again-btn').count(), 0, 'old: no button any more');
  const link = oldRow.locator('.pbew-lv-link');
  const newId = (await link.getAttribute('href')).replace('#pbew-lv-', '');
  const newRow = page.locator('#pbew-lv-' + newId);
  const newText = await newRow.innerText();
  ok(w.tag + ' 3 new row', newText);
  assert.ok(newText.includes(w.of), 'new: asked again after');
  assert.equal(await newRow.locator('.pbme-badge--confirm').count(), 1, 'new: waiting for approval');
  if (w.waiting) assert.ok(newText.toLowerCase().includes(w.waiting.toLowerCase()));
  await page.locator('.pbew-lvlist').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_3_new_request_390.png`)});
  // the old row's link lands on the new one
  await link.click();
  await page.waitForTimeout(500);
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_3b_link_lands_390.png`)});
  // the employee home's "My requests" list
  await page.goto(base + '/my/requests');
  await page.waitForLoadState('networkidle');
  const req = await noBrand(page, w.tag + ' my requests');
  ok(w.tag + ' 3c my requests', req.slice(0, 400));
  assert.ok(req.toLowerCase().includes(w.back.toLowerCase()), 'My requests says sent back');
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_3c_my_requests_390.png`)});
  await context.close();
  return newId;
}

async function staffCard(browser, lang) {
  const w = WORDS[lang];
  const {context, page} = await session(browser, fx.staff[lang], 1400, 900);
  await page.goto(base + '/odoo/action-pb_timeoff.action_pb_timeoff', {timeout: 180000});
  await page.locator('.pbf-tab').first().waitFor({timeout: 30000});
  // the first-visit "Welcome" tour card is not part of this proof
  await page.waitForTimeout(1500);
  const later = page.getByRole('button', {name: /^(Later|Để sau|Nanti)$/});
  if (await later.count()) { await later.first().click(); }
  const tab = page.locator('.pbf-tab', {has: page.locator('.pbf-tab-l', {hasText: new RegExp('^' + w.staffBack + '$')})});
  await tab.click();
  await page.locator('.q-card .st.back').first().waitFor({timeout: 20000});
  const cards = page.locator('.q-card', {has: page.locator('.st.back')});
  const text = await cards.first().innerText();
  ok(w.tag + ' 4 staff card', text);
  assert.ok(text.includes(w.staffBack));
  assert.ok(text.includes(w.staffWhy));
  await noBrand(page, w.tag + ' cockpit');
  await page.locator('.q-filter').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(shots, `p6c_${w.tag}_4_staff_card.png`)});
  return {context, page};
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    for (const lang of ['en_US', 'vi_VN', 'id_ID']) {
      await employee(browser, lang);
      const {context, page} = await staffCard(browser, lang);
      if (lang === 'en_US') {
        // 5. staff "Ask again" from a card: the "Apply for" drawer, filled in
        const id = fx.people.en_US.staff_leave_id;
        const card = page.locator('.q-card', {has: page.locator('.again-btn')}).filter({hasText: 'whose wedding'});
        // centred, so the floating "Ask PayAI" button is not over it
        await card.locator('.again-btn').evaluate((el) => el.scrollIntoView({block: 'center'}));
        await card.locator('.again-btn').click();
        const drawer = page.locator('.pbto-modal');
        await drawer.locator('.again-box').waitFor({timeout: 10000});
        const dt = await drawer.innerText();
        ok('en 5 drawer', dt);
        assert.match(dt, /Ask again/);
        assert.match(dt, /Filled in from the request that was sent back/);
        assert.match(dt, /Documents are not copied/);
        assert.notEqual(await drawer.locator('select').inputValue(), '', 'the kind is filled in');
        await page.screenshot({path: path.join(shots, 'p6c_en_5_staff_drawer.png')});
        await drawer.locator('textarea').fill('Wedding — my sister’s');
        await drawer.locator('.m-f .pbto-btn.primary').click();
        await page.locator('.o_notification').filter({hasText: 'Asked again'}).waitFor({timeout: 15000});
        await page.waitForTimeout(600);
        await page.screenshot({path: path.join(shots, 'p6c_en_5b_staff_asked_again.png')});
        // 5c. the plain "Apply for" drawer is unchanged (no "Ask again" box)
        await page.locator('.pbto-btn.primary', {hasText: 'Apply for'}).first().click();
        await page.locator('.pbto-modal .m-h', {hasText: 'Apply for'}).waitFor({timeout: 10000});
        assert.equal(await page.locator('.pbto-modal .again-box').count(), 0);
        await page.locator('.pbto-modal .m-f .pbto-btn.ghost').click();
        // 6. the standard form of the sent-back request: one plain line
        await page.goto(base + '/odoo/hr.leave/' + id);
        const note = page.locator('.alert-warning', {hasText: 'Sent back to the employee, not refused'});
        await note.waitFor({timeout: 20000});
        ok('en 6 form note', await note.innerText());
        await noBrand(page, 'standard form');
        await page.screenshot({path: path.join(shots, 'p6c_en_6_standard_form.png')});
      }
      await context.close();
    }
    ok('console errors', errors);
    assert.deepEqual(errors, []);
    console.log('P6C_BROWSER_OK');
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
