# -*- coding: utf-8 -*-
"""LEARNING L7 — demo data for the learner's phone on payobook.
Idempotent and small.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l7_demo_seed.py

(Locally L7_SEED_LEARNER overrides the payobook default.)

What it does:
  1. Makes ONE small course, "DEMO Three-minute safety tips", flagged
     "Short lessons", with three reading lessons of 3, 4 and 5 minutes —
     each written in English AND Vietnamese, so "Three minutes today" and
     "Show both languages" have something to show. Unpublished lessons are
     never touched; nothing else is changed.
  2. Puts the HR lead (`demo.hr@example.com`, ledger LN40: the learner side
     is walked as the HR lead) on it as a member — no assignment, so no due
     date, no reminder and no "course added" email. The course's own author
     is taken off it again (LN46).
  3. NO AI CALL and no drafted course: "Draft it with PayAI" spends the
     provider's credit, so it is an owner step (L7 report, owner items).
  4. Prints, as the HR lead (English and Vietnamese), what the live walk
     should see: Next for you, Three minutes today, the streak, the badges
     on their certificates, and the both-languages payload of lesson one.
  5. NO EMAIL: anything queued by the run is cancelled (state "cancel",
     never deleted — the L3 lesson).
Nothing here contains a password or a real person's data.
"""
import os

COURSE = 'DEMO Three-minute safety tips'
LEARNER = os.environ.get('L7_SEED_LEARNER') or 'demo.hr@example.com'
LESSONS = [
    ('DEMO Wear your badge', 'DEMO Đeo thẻ nhân viên', 3,
     '<p>Wear your badge where people can see it, every day, on every site. '
     'It tells everyone you are meant to be there.</p>',
     '<p>Đeo thẻ ở chỗ mọi người nhìn thấy, mỗi ngày, ở mọi địa điểm. '
     'Thẻ cho mọi người biết bạn được phép có mặt ở đó.</p>'),
    ('DEMO Keep the aisle clear', 'DEMO Giữ lối đi thông thoáng', 4,
     '<p>Nothing stands in a walkway, not even for a minute. If you see a '
     'box in the aisle, move it or tell your supervisor.</p>',
     '<p>Không để gì trên lối đi, dù chỉ một phút. Nếu thấy thùng hàng trên '
     'lối đi, hãy dời đi hoặc báo người giám sát.</p>'),
    ('DEMO Report a near miss', 'DEMO Báo cáo sự cố suýt xảy ra', 5,
     '<p>A near miss is an accident that nearly happened. Tell your '
     'supervisor the same day: it is how the next one is stopped.</p>',
     '<p>Sự cố suýt xảy ra là tai nạn suýt nữa đã xảy ra. Hãy báo người giám '
     'sát ngay trong ngày: đó là cách ngăn sự cố tiếp theo.</p>'),
]


def say(msg, *args):
    print('L7 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
base = {k: v for k, v in env.context.items() if k != 'tz'}
env = env(context=dict(base, lang='en_US'))
mails_last = env['mail.mail'].sudo().search(
    [], order='id desc', limit=1).id or 0
vi_on = bool(env['res.lang'].sudo().search_count(
    [('code', '=', 'vi_VN'), ('active', '=', True)]))

# ------------------------------------------------------------- 1. the course
Channel = env['slide.channel'].sudo()
course = Channel.search([('name', '=', COURSE)], limit=1)
if not course:
    course = Channel.create({
        'name': COURSE, 'channel_type': 'training', 'visibility': 'members',
        'enroll': 'invite', 'completed_template_id': False,
        'is_published': True, 'pb_short': True,
        'description': '<p>Three short reads for a phone.</p>'})
    say('course %s made', course.id)
    authors = course.channel_partner_ids.mapped('partner_id')
    if authors:
        course._remove_membership(authors.ids)
else:
    course.write({'pb_short': True})
    say('course %s already here — kept, flagged short', course.id)
if vi_on:
    course.with_context(lang='vi_VN').write(
        {'name': 'DEMO Mẹo an toàn ba phút'})
Slide = env['slide.slide'].sudo()
for seq, (en, vi, mins, html_en, html_vi) in enumerate(LESSONS, start=1):
    slide = Slide.search([('channel_id', '=', course.id), ('name', '=', en)],
                         limit=1)
    if not slide:
        slide = Slide.with_context(lang='en_US').create({
            'channel_id': course.id, 'name': en, 'sequence': seq,
            'slide_category': 'article', 'html_content': html_en,
            'completion_time': mins / 60.0, 'is_published': True})
        say('lesson %s "%s" (%s min)', slide.id, en, mins)
    # The English text stays the source (rewritten in English, which also
    # mends a lesson an earlier run wrote over); the Vietnamese goes in as a
    # TRANSLATION of its words — writing a rich-text field in Vietnamese
    # when it has no translation yet replaces it in every language.
    slide.with_context(lang='en_US').write({'name': en, 'html_content': html_en})
    if vi_on:
        slide.with_context(lang='vi_VN').write({'name': vi})
        strip = lambda h: h.replace('<p>', '').replace('</p>', '')  # noqa: E731
        slide.update_field_translations(
            'html_content', {'vi_VN': {strip(html_en): strip(html_vi)}})

# ------------------------------------------------------------- 2. the learner
learner = env['res.users'].sudo().search([('login', '=', LEARNER)], limit=1)
if not learner:
    say('no user %s — nobody put on the course', LEARNER)
else:
    if not course._pb_membership(learner.partner_id):
        course._action_add_members(learner.partner_id)
        say('%s put on the course (member, no assignment)', LEARNER)
    else:
        say('%s already on the course', LEARNER)

# ------------------------------------------------------------- 4. what to see
if learner:
    for lang in ('en_US', 'vi_VN') if vi_on else ('en_US',):
        me = env(user=learner.id, context=dict(base, lang=lang))['pb.my.training']
        home = me.home()
        nb = home.get('next') or {}
        say('[%s] Next for you: %s · %s · %s · %s', lang, nb.get('kind'),
            nb.get('title'), nb.get('reason'), nb.get('url'))
        three = home.get('three') or {}
        say('[%s] Three minutes today: %s · %s · %s', lang, three.get('name'),
            three.get('duration'), three.get('url'))
        say('[%s] Streak: %s', lang, (home.get('streak') or {}).get('words'))
        certs = me.my_certificates()
        say('[%s] Badges: %s', lang, [
            (r['name'], r['badge']['initials'], r['badge']['tone'])
            for r in (certs.get('rows') or [])[:4]])
        first = Slide.search([('channel_id', '=', course.id)], order='sequence',
                             limit=1)
        lesson = me.lesson(course.id, first.id)
        both = (lesson or {}).get('both') or {}
        say('[%s] Both languages on "%s": other %s "%s"', lang,
            (lesson or {}).get('name'), both.get('other_code'), both.get('name'))

# ------------------------------------------------------------- 5. no email
queued = env['mail.mail'].sudo().search([('id', '>', mails_last),
                                         ('state', 'in', ('outgoing',
                                                          'exception'))])
if queued:
    queued.write({'state': 'cancel'})
say('%s queued mail cancelled', len(queued))
env.cr.commit()
say('done')
