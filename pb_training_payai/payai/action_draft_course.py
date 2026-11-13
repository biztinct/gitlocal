# -*- coding: utf-8 -*-
"""PayAI's "draft a course from <a document>" (LEARNING L7, LD9).

Tier PREPARE, and it only NAVIGATES (PayAI rule PA19: doors are navigation):
the slot is the name of a document the person can already read among the
courses' files; the plan card has no "Do it" — only "Open New course with
this file", which opens Learning › Courses with the "New course" drawer open
and that file picked. The draft itself is made from the drawer, where the
person picks the language and presses "Draft the course" (and where the
PayAI provider is asked — never from the chat).

Registered into PayAI's catalogue from here, so `pb_payai_actions` itself is
unchanged. Gates: the training team's own right (`pb.training._can_write`,
judged for the person, never su — PA12) and the Learning entry of the left
menu (PA-R1). Every id comes from a search made as the person (PA-R3).
"""
import logging

from odoo.exceptions import AccessError
from odoo.tools.translate import LazyTranslate

from odoo.addons.pb_payai_actions.payai import cards
from odoo.addons.pb_payai_actions.payai.actions_amber import (
    fingerprint, plan_actions, screen_action, slot_row)
from odoo.addons.pb_payai_actions.payai.i18n import T
from odoo.addons.pb_payai_actions.payai.registry import (
    Action, Slot, payai_action)
from odoo.addons.pb_payai_actions.payai.resolve import (
    ambiguous, missing, resolved)

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

LEARNING_SCREEN = 'pb_learning_hub.item_learning'
LEARNING_HUB = 'pb_learning_hub.action_pb_learning_hub'
#: The files a course can be drafted from (as the drawer takes them).
DRAFT_MIMES = ('application/pdf', 'text/plain',
               'application/vnd.openxmlformats-officedocument.'
               'wordprocessingml.document')


@payai_action
class DraftCourse(Action):
    key = 'draft_course'
    title = _lt('Draft a course from a document')
    tier = 'prepare'
    priority = 45
    summary = _lt('Open Learning › New course with a document the person '
                  'already has picked, so PayAI can draft a course from it '
                  '(an outline, lessons and a quiz) for a trainer to edit and '
                  'publish. Nothing is drafted or published from the chat.')
    examples = (_lt('Draft a course from the forklift procedure'),
                _lt('Make a course out of fire-safety.pdf'))
    slots = (Slot('file', _lt('Document'), 'text', True,
                  "The document's file name in the person's own words, for "
                  "example 'forklift procedure' or 'fire-safety.pdf'. Never "
                  "an id."),)
    screen_keys = (LEARNING_SCREEN,)
    right_subject = _lt('Drafting courses')
    right_label = _lt('Learning')
    phrases = (
        r'^(?:draft|make|create|build|write|turn)\s+(?:me\s+)?(?:a\s+|the\s+)?'
        r'(?:new\s+)?(?:training\s+)?course\s+(?:from|out\s+of|using|based\s+on)\s+'
        r'(?:the\s+|my\s+|a\s+)?(?:document\s+|file\s+)?(?P<file>.+?)$',
        r'^turn\s+(?:the\s+|my\s+)?(?P<file>.+?)\s+into\s+a\s+(?:training\s+)?course$',
    )
    phrases_vi = (
        r'^(?:soạn|tạo|làm|viết)\s+(?:giúp\s+tôi\s+)?(?:một\s+)?khóa\s+'
        r'(?:học|đào\s+tạo)\s+(?:từ|theo|dựa\s+trên)\s+(?:tài\s+liệu\s+|tệp\s+|file\s+)?'
        r'(?P<file>.+?)$',
    )

    def method_gate(self, env, user):
        if 'pb.training' not in env or 'pb_draft_source_id' not in \
                env['slide.channel']._fields:
            return False
        return bool(env['pb.training'].with_user(user)._can_write())

    def _files(self, ctx, text):
        """Documents the PERSON can read among the courses' files, by name."""
        Att = ctx.env['ir.attachment']
        domain = [('res_model', '=', 'slide.channel'),
                  ('mimetype', 'in', DRAFT_MIMES)]
        words = [w for w in (text or '').replace('.', ' ').split() if len(w) > 1]
        for word in words[:4]:
            domain.append(('name', 'ilike', word))
        try:
            return Att.search(domain, order='id desc', limit=8)
        except AccessError:
            return Att.browse()

    def resolve_slot(self, ctx, slot, text):
        if slot.key != 'file':
            return super().resolve_slot(ctx, slot, text)
        if not (text or '').strip():
            return missing(T(_lt('Which document? Say its file name.')))
        found = self._files(ctx, text)
        if not found:
            return missing(T(_lt(
                'I could not find a document called "%s" among the courses\' '
                'files. Upload it in Learning › Courses › New course.'))
                % (text or '')[:60])
        if len(found) == 1:
            return resolved(found.id, found.name or '', 'said')
        return ambiguous([{'value': a.id, 'label': a.name or '',
                           'sublabel': ''} for a in found])

    def plan(self, ctx, params):
        file_ = params['file']
        context = {'pb_training_new_course': 'payai',
                   'pb_training_draft_attachment': int(file_['value'] or 0)}
        screen = screen_action(
            _lt('Open New course with this file'),
            hub={'xmlid': LEARNING_HUB, 'lens': 'courses'},
            context=context, style='primary')
        card = cards.card(
            'plan', ctx.task, 'prepare', title=self.title,
            subtitle=_lt('Prepare · opens the screen · nothing is drafted yet'),
            slots=[slot_row('file', _lt('Document'), file_['label'],
                            file_.get('origin'), True)],
            notes=[cards.note('info', _lt(
                'The draft is made on the screen: pick the language and press '
                '"Draft the course". It stays unpublished until a trainer '
                'publishes it.'))],
            actions=plan_actions(None, screen, can_do=False),
            state='planned', icon='file')
        vals = {'attachment_id': int(file_['value'] or 0)}
        return {'card': card, 'vals': vals, 'fingerprint': fingerprint(vals),
                'speak': T(_lt('I will open New course with %s picked.'))
                % file_['label']}

    def confirm(self, ctx, task, params, data):
        """Never reached: the card has no "Do it" (navigation only, PA19)."""
        return cards.card('blocked', task, 'prepare', title=self.title,
                          notes=[cards.note('info', _lt(
                              'Open New course with this file to draft it.'))])
