# -*- coding: utf-8 -*-
"""DECLARED-ONLY ACTIONS. Amber moved to `actions_amber.py` in P2, Red to
`actions_red.py` in P3; what is left is the `never` tier (destructive asks)
and the `_Stub` shape for anything declared before it is built.

A stub is a full catalogue entry (tier, screen, right, door, phrasings) so
the gate, the refusals, "What can you do?" and the audit already know about
it. `execute` is not built: a sentence that names one gets the honest answer
("I cannot do that for you yet") with the screen's door. Stubs are never
offered to the model as tools.
"""
import re

from odoo.tools.translate import LazyTranslate

from . import gate
from .registry import MARKED_ONLY, Action, payai_action

_lt = LazyTranslate(__name__)


class _Stub(Action):
    stub = True
    priority = 20

    def execute(self, ctx, params):
        raise NotImplementedError(self.key)


@payai_action
class NeverThroughPayAI(_Stub):
    """Destructive asks. Never through PayAI, whatever the right."""
    key = 'never_destructive'
    title = _lt('Delete or clear records')
    tier = 'never'
    priority = 15
    summary = _lt('Deleting pay runs or payslips is never done through PayAI.')
    examples = (_lt('Delete the May run'),)
    door_id = 'payhub_runs'
    phrases = (
        r'^(?=.*\b(?:runs?|pay\s*runs?|payslips?|payroll|records?|employees?|'
        r'contracts?|batch(?:es)?)\b)'
        r'(?:delete|remove|erase|wipe|purge|destroy|drop|clean\s+and\s+run)\s+'
        r'(?:out\s+)?(?:all\s+)?(?:the\s+)?(?P<what>.+)$',
    )


#: FIX-1b (owner ruling 2026-10-13) — an order about access. Second pass:
#: the first table caught ordinary approvals ("approve the Sales Manager
#: role", "approve the exit hand-over for Lan", "approve the access card
#: request") and missed plain hand-over orders ("give my approvals to Lan
#: while I'm away", "make Lan admin"). Three verb families now, each with
#: its own nouns:
#:   * LOOK verbs (open, show …) + the Access home's nouns;
#:   * CHANGE verbs (change, give, lend …) + those nouns, or admin;
#:   * DECIDE verbs (approve, reject, send back …) only with an access
#:     REQUEST — any other decision is a Red Action's, and the Red Actions
#:     refuse a request about access themselves (`gate.access_request`).
#: The noun must sit in the order's own words: never after a comma, a
#: reason ("because …") or a "for …" ("show the run for the access team").
_LOOK_VERBS = (
    # FIX-1b third pass: the usual slips ("opne", "shwo").
    r'(?:opne|oepn|opn|shwo|sohw|open(?:\s+up)?|show(?:\s+me)?|view|see|check|list|display|find|go\s+to|goto|'
    r'take\s+me\s+to|bring\s+(?:me\s+)?(?:to|up)|navigate\s+to|jump\s+to|switch\s+to|'
    r'pull\s+up)')
_CHANGE_VERBS = (
    r'(?:change|edit|update|set(?:\s+up)?|give|grant|assign|reassign|add|remove|revoke|'
    r'take\s+away|take|strip|lend|hand(?:\s+over)?|handover|delegate|transfer|pass|share|'
    r'make|promote|demote|allow|let|unlock|lock|block|deny|restore|swap|move|copy|reset|'
    r'disable|enable|manage|lift|cancel|end|stop|withdraw|delete|erase|wipe|drop|clear|'
    r'appoint|limit|restrict|extend|expand|upgrade|downgrade|turn\s+(?:on|off)|'
    # FIX-1b third pass: "create a delegation for Lan", "start a hand-over
    # to Lan", "request access for Lan".
    r'create|start|begin|schedule|arrange|draft|raise|request|reroute|redirect|route|'
    r'replace|hide|unhide)')
_DECIDE_VERBS = (
    r'(?:approve|reject|accept|decline|turn\s+down|send(?:\s+back)?|sign\s+off|ok(?:ay)?|'
    r'confirm|agree\s+to)')
#: Where the order's own words end.
_OWN_WORDS = (r'(?:(?![,;:—]|\b(?:because|since|saying|reason|note|for|so\s+that|but|'
              r'while|until|as\s+(?:she|he|they|it|the|we|i)\b)\b).)*?')
_ADMIN = r'\b(?:admin(?:istrator)?s?|super\s*users?)\b'
#: FIX-1b third pass: a bare "admin" is not an access noun after a CHANGE
#: verb ("add the admin fee", "move Lan to admin", "change Lan's department
#: to admin") — only admin AS a right: "admin rights / access / role".
_ADMIN_RIGHT = (r'\b(?:admin(?:istrator)?|super\s*user)\s+(?:rights?|access|roles?|privileges?|'
                r'permissions?|accounts?|status|level|powers?)\b')
#: An app's own role ("payroll manager", "HR officer", "approver") — what
#: "make Lan a payroll manager" hands out.
_APP_ROLE_NAMED = (r'(?:(?:payroll|hr|people|approvals?|finance|accounting|accounts|system|app|'
                   r'settings|access)\s+(?:managers?|officers?|users?|admins?|administrators?|'
                   r'approvers?|leads?|viewers?|editors?|owners?|team\s+leads?))')
_APP_ROLE = (r'(?:' + _APP_ROLE_NAMED + r'|approvers?|admin(?:istrator)?s?|super\s*users?)')
#: What somebody may be let do (FIX-1b fourth pass: shared by "let Lan …"
#: and "Lan needs to be able to …"). Seeing or editing counts only for a
#: screen or the payroll ("let Lan see her payslip" is not access; "let Lan
#: cover the night shift" is a shift).
_MAY_DO = (r'(?:approve|decide|sign(?:\s+off)?|reject|send\s+back|act\s+(?:for|on)|'
           r'stand\s+in\s+(?:for\s+(?:me|us)\b|on\s+my\b|in\s+my\b|as\b)|'
           r'cover\s+(?:for\s+(?:me|us)\b|my\b|on\s+my\b)|'
           r'(?:see|view|access|edit|run|manage|open|use)\s+(?:(?:the|all|all\s+the|our|every|'
           r'everyone\'?s)\s+)?(?:(?:\S+\s+){0,2}?(?:screens?|menus?|pages?|tabs?|apps?|modules?|'
           r'sections?|settings)\b|(?:payroll|pay\s+runs?|payslips|salaries|everything|'
           r'approvals)\b))')
_ABLE_TO = (r'(?:be\s+(?:able|allowed|permitted|authori[sz]ed|given\s+(?:the\s+)?(?:right|rights|'
            r'ability|power|access)|cleared)\s+to|have\s+(?:the\s+)?(?:right|rights|ability|'
            r'power|access)\s+to|get\s+(?:the\s+)?(?:right|rights|ability|power|access)\s+to)\s+')
#: A person-order's subject: not me, not a verb of the order itself.
#: FIX-1b seventh pass: nor a joining word ("so approve the June run for
#: me", "ok so …", "and …", "then …" — the order is PayAI's, not a person's).
_SUBJECT = (r'(?!(?:i|we|you|me|us|it|they|this|that|the|a|an|my|our|please|approve|reject|'
            r'send|open|show|give|make|set|change|let|have|get|run|pay|payroll|'
            r'so|and|then|ok|okay|just|also|now|but|or|well|can|could|would|will)\b)')
#: FIX-1b seventh pass: what may come before "…, Lan will approve for me" —
#: only the asker's own news ("I'm going on leave", "I'm away next week",
#: "while I'm off"), never an order ("approve the June run so Lan can sign
#: off for me" is an approval; Lan signs off after it).
_MY_NEWS = (r"(?:(?:i|we)\s*(?:'m|’m|am|are|'re|’re|'ll|’ll|will|won't|shall|'ve|’ve|have|"
            r"had|was|were)|im|(?:while|when|since|as|because|until)\s+(?:i|we)|"
            r"(?:next|this)\s+week|tomorrow|from\s+\S+)\b(?:(?![,;:—]|\b(?:so|and|then)\b).)*?")
_LEAD_IN = (r'(?:' + _MY_NEWS + r'(?:[,;:—]|\s+(?:so|and|then))(?:\s+(?:so|and|then))?\s+|'
            r'(?:so|and|then|ok(?:ay)?)\s+(?:(?:so|then)\s+)?)?')
#: Signing for somebody: "sign off", or "sign" straight before "for me /
#: on my behalf" — never "sign the contract for me" (a document).
_SIGNS_FOR = (r'(?:signs?\s+off|signs?(?=\s+(?:for\s+(?:me|us)|on\s+my\s+behalf|in\s+my\s+place|'
              r'instead\s+of\s+me)\b))')
_ACCESS_REQUEST = (
    r'\b(?:access\s+requests?|permission\s+requests?|role[\s-]+changes?|'
    r'delegation\s+requests?|requests?\s+(?:for|to\s+(?:get|have))\s+(?:more\s+|extra\s+|'
    r'admin\s+|new\s+)?(?:access|permissions?|rights|privileges|a\s+role\s+change))\b')
#: FIX-1b third pass: "approve the request to make Lan payroll manager".
_ACCESS_REQUEST = (r'(?:' + _ACCESS_REQUEST + r'|\brequests?\s+to\s+(?:make|set|add|promote|'
                   r'appoint|name)\s+(?:\S+\s+){1,3}?(?:as\s+|to\s+)?(?:(?:an?|the|our|my)\s+)?'
                   + _APP_ROLE + r'\b|'
                   # FIX-1b fourth pass: "approve the request from Lan for the
                   # payroll manager role". A bare "admin" / "approver" only
                   # as a right ("for admin rights"), never "the request from
                   # Lan for admin leave"; and "the Payroll Officer role" on
                   # its own stays Hiring's opening (P3 fb12).
                   r'\brequests?\s+(?:from\s+(?:\S+\s+){1,2}?)?(?:for|to\s+(?:get|have|become|be))\s+'
                   r'(?:(?:an?|the|our)\s+)?(?:new\s+)?(?:' + _APP_ROLE_NAMED + r'|' + _APP_ROLE +
                   r'\s+(?:roles?|rights|access|status|privileges))\b)')
_MY_THINGS = (r'(?:approvals|approval\s+(?:rights|work|tasks|duties|inbox|queue)|inbox|'
              r'sign[\s-]?offs|access|roles?|rights|permissions|duties)\b')
#: Who is let / made something: a person, never "me" or a thing ("let the
#: June run go ahead", "set the June run as draft").
_NOT_ME = (r'(?!(?:me|us|it|them|this|that|these|those|the|a|an|my|our|all|every\w*|'
           r'payroll|pay)\b)')
_NOT_HIRING = r'(?!.*' + gate.HIRING_EN + r')'
#: "view as list", "see it as a percentage", "show it as PDF" — a format.
_NOT_A_FORMAT = (r'(?!(?:a|an|the|list|lists|table|tables|cards?|grid|chart|charts|graph|graphs|'
                 r'pdf|excel|csv|xlsx|kanban|text|image|images|percent(?:age)?s?|numbers?|'
                 r'totals?|draft|done|read|unread|new|well|before|usual|is|planned|expected)\b|\d)')
#: FIX-1b sixth pass: who "see it as …" names must look like a person — the
#: words for somebody else, or a name (`_SEE_NAME`, read with its capitals in
#: `phrase_ok`). Any other word after "as" is a pay item, a format, a period
#: or a state ("show it as net pay", "open this as Word", "view as monthly").
_OTHER_PERSON_EN = (r'(?:(?:some(?:one|body)|any(?:one|body))\s+else|another\s+(?:user|person|'
                    r'employee|staff\s+member|manager|approver|officer)|(?:an?|the)\s+other\s+'
                    r'(?:user|person)|other\s+(?:users|people)|a\s+different\s+(?:user|person))')
_OTHER_PERSON_VI = (r'(?:(?:một\s+)?người\s+(?:dùng\s+)?khác|(?:một\s+)?tài\s+khoản\s+khác|'
                    r'(?:một\s+)?nhân\s+viên\s+khác)')
#: A name group: one to three words, each read as a name in `phrase_ok`.
_SEE_NAME = r'(?P<seename>\S+(?:\s+\S+){0,2})'
#: "see it as …": the app itself as the thing seen, and the "as" words.
_SEE_APP = (r'(?:payobook|the\s+(?:app|menu|left\s+menu|system|screens?)|my\s+screens?)')
_SEE_AS = (r'(?:as|through(?:\s+the\s+eyes\s+of)?|from\s+the\s+(?:view|eyes|side)\s+of)\s+')
_SEE_OBJ_VI = r'(?:(?:mọi\s+thứ|tất\s+cả|ứng\s+dụng|màn\s+hình|menu|nó|cái\s+này)\s+)?'
_SEE_AS_VI = (r'(?:như|với\s+tư\s+cách(?:\s+là)?|dưới\s+góc\s+nhìn\s+của|bằng\s+góc\s+nhìn\s+của|'
              r'bằng\s+tài\s+khoản(?:\s+của)?)\s+')
#: Capitalised words that are not people. FIX-1b seventh pass: a label
#: copied from a screen keeps its capitals ("view as Net Pay", "see it as
#: Approved", "xem như Phiếu Lương"), so the app's own kinds of words are
#: here, not one word at a time: a run's or payslip's state, a pay item, a
#: period, a way to lay a screen out, a part of the company, a country or
#: city the app pays in, a currency.
_NOT_NAMES = frozenset((
    # Apps, days, months.
    'word', 'excel', 'sheets', 'google', 'pdf', 'csv', 'monday', 'tuesday', 'wednesday',
    'thursday', 'friday', 'saturday', 'sunday', 'january', 'february', 'march', 'april', 'may',
    'june', 'july', 'august', 'september', 'october', 'november', 'december', 'payobook',
    'payai', 'admin', 'hr', 'it', 'tet', 'tết', 'thứ', 'tháng', 'chủ',
    # States.
    'draft', 'drafts', 'approved', 'approve', 'approval', 'paid', 'unpaid', 'confirmed',
    'confirm', 'posted', 'done', 'cancelled', 'canceled', 'rejected', 'pending', 'waiting',
    'verified', 'verify', 'submitted', 'locked', 'unlocked', 'closed', 'open', 'opened', 'sent',
    'new', 'returned', 'review', 'reviewed', 'completed', 'complete', 'finished', 'final',
    'processed', 'computed', 'calculated', 'ready', 'active', 'inactive', 'archived', 'blocked',
    'overdue', 'late', 'due', 'scheduled', 'failed', 'ok', 'okay', 'signed', 'held', 'queued',
    'running', 'current', 'previous', 'last', 'next', 'latest', 'old', 'planned', 'expected',
    'actual', 'estimated', 'forecast', 'budget', 'budgeted',
    # Pay items and pay words.
    'net', 'gross', 'basic', 'base', 'bonus', 'bonuses', 'overtime', 'ot', 'allowance',
    'allowances', 'deduction', 'deductions', 'tax', 'taxes', 'pit', 'insurance', 'salary',
    'salaries', 'wage', 'wages', 'pay', 'payslip', 'payslips', 'payroll', 'run', 'runs', 'cost',
    'costs', 'total', 'totals', 'contribution', 'contributions', 'benefit', 'benefits',
    'commission', 'commissions', 'expense', 'expenses', 'advance', 'advances', 'loans',
    'leave', 'holiday', 'holidays', 'income', 'earnings', 'amount', 'amounts', 'rate', 'rates',
    'hours', 'hourly', 'cash', 'bank', 'arrears', 'refund', 'severance', 'pension', 'cpf', 'epf',
    'socso', 'bpjs', 'sss', 'thr', 'take-home', 'net-pay', 'gross-pay',
    # Periods.
    'daily', 'weekly', 'fortnightly', 'biweekly', 'monthly', 'quarterly', 'yearly', 'annual',
    'annually', 'year', 'month', 'week', 'quarter', 'today', 'yesterday', 'tomorrow', 'ytd',
    'mtd', 'period',
    # How a screen is laid out.
    'summary', 'summaries', 'detail', 'details', 'detailed', 'compact', 'full', 'short',
    'simple', 'overview', 'breakdown', 'list', 'table', 'report', 'reports', 'chart', 'graph',
    'grid', 'card', 'cards', 'kanban', 'default', 'standard', 'normal', 'classic', 'plain', 'raw',
    'export', 'print', 'preview', 'dark', 'light', 'spreadsheet', 'statement',
    # Parts of the company, and who is who in general.
    'company', 'companies', 'department', 'departments', 'team', 'teams', 'branch', 'branches',
    'group', 'groups', 'division', 'office', 'site', 'location', 'region', 'entity', 'scheme',
    'schemes', 'staff', 'employee', 'employees', 'employer', 'manager', 'managers', 'owner',
    'user', 'users', 'guest', 'everyone', 'all', 'administrator', 'approver', 'officer',
    'director', 'finance', 'accounting', 'accounts', 'sales', 'retail', 'marketing',
    'operations', 'ops', 'head', 'hq',
    # Countries and cities the app pays in; currencies.
    'vietnam', 'malaysia', 'thailand', 'singapore', 'indonesia', 'india', 'cambodia',
    'philippines', 'laos', 'myanmar', 'china', 'japan', 'korea', 'australia', 'hanoi', 'saigon',
    'danang', 'bangkok', 'jakarta', 'kuala', 'lumpur', 'manila', 'melbourne',
    'vnd', 'usd', 'sgd', 'myr', 'thb', 'idr', 'inr', 'khr', 'aud', 'eur', 'dollar',
    'dollars', 'ringgit', 'baht', 'rupiah', 'rupee', 'rupees', 'riel',
    # Vietnamese pay and app words that are never a given name ("Lương"
    # leads "Lương Gộp", "Lương Cơ Bản"). Never here, in any language: a
    # word that is also a given name (Long, Loan, Chi, Công, Quý, Sydney).
    'lương', 'phiếu', 'đợt', 'thưởng', 'phụ', 'cấp', 'thuế', 'hiểm', 'viên', 'hợp', 'đồng',
    'phí', 'nhận', 'tổng', 'nháp', 'gộp', 'bản', 'cơ', 'khoản', 'tiền', 'kỳ', 'quỹ', 'khấu',
    'trừ', 'trợ', 'ca', 'ngày', 'giờ', 'tuần', 'nội', 'duyệt', 'chờ', 'hủy',
    'huỷ', 'trả', 'gửi', 'xong', 'mới', 'cũ', 'tạm', 'ứng', 'nghỉ', 'phép', 'thức',
    'thử', 'việc', 'ròng', 'gốc', 'khoán', 'nghiệp', 'phòng', 'ban', 'nhóm',
    'nhánh', 'tóm', 'tắt', 'tiết', 'báo', 'cáo', 'biểu', 'mẫu'))
#: Vietnamese pairs whose words are names one by one but a place or a pay
#: word together ("Việt Nam", "Bảo Hiểm", "Nhân Viên", "Chi Phí").
_NOT_NAME_PAIRS_VI = frozenset((
    'việt nam', 'hà nội', 'sài gòn', 'đà nẵng', 'hồ chí', 'chí minh', 'bảo hiểm', 'nhân viên',
    'nhân sự', 'chi phí', 'thực nhận', 'thực lĩnh', 'cơ bản', 'hợp đồng', 'kế toán'))
#: The Vietnamese order, written FOLDED (no marks): the registry tries it on
#: the marked text and on the text with its marks folded away, so "mở phân
#: quyền" and "mo phan quyen" are both read. "quyền" alone is only read
#: as typed WITH marks (`MARKED_ONLY`): it folds to "quyen", and Quyên is a
#: name; a capital "Quyền" mid-sentence is a name too (`phrase_ok`).
_ACCESS_VERBS_VI = (
    r'(?:mo|xem|vao|di\s+toi|den|doi|thay\s+doi|sua|chinh(?:\s+sua)?|cap|gan|them|bot|'
    r'xoa|go|thu\s+hoi|cho\s+muon|cho|ban\s+giao|uy|chuyen|trao|dat|cai|bat|tat|khoa|'
    r'mo\s+khoa|lay|nang|ha|phan|quan\s+ly|giao|huy)')
#: The nouns are `gate.ACCESS_NOUNS_VI` ("bàn giao quyền": "bàn" folds to
#: "bạn" (you), which the polite lead cuts — so "giao quyền" (hand access
#: over) on its own as well; FIX-1b third pass: "menu bên trái").
_ACCESS_NOUNS_VI = gate.ACCESS_NOUNS_VI
_DECIDE_VERBS_VI = r'(?:duyet|phe\s+duyet|tu\s+choi|tra\s+lai|chap\s+thuan|dong\s+y)'
_ACCESS_REQUEST_VI = (
    r'\byeu\s+cau\s+(?:\S+\s+){0,2}?(?:truy\s+cap|cap\s+quyen|phan\s+quyen|quyen\s+truy\s+cap|'
    r'uy\s+quyen|giao\s+quyen|quyen\s+han|doi\s+vai\s+tro|cap\s+vai\s+tro)\b')
_BEFORE_REASON_VI = r'(?:(?!\b(?:vi|ly\s+do|ghi\s+chu)\b|[:—,;]).)*?'
_NOT_HIRING_VI = (r'(?!.*\b(?:tuyen\s+dung|ung\s+vien|dot\s+tuyen|tuyen\s+nguoi|'
                  r'vi\s+tri\s+tuyen)\b)')
#: Marked: the verbs that change what somebody may do, before "quyền".
_QUYEN_VERBS = (r'(?:đổi|thay\s+đổi|sửa|chỉnh(?:\s+sửa)?|xóa|xoá|gỡ|bỏ|thu\s+hồi|tước|cắt|'
                r'cấp|mở|khóa|khoá|nâng|hạ|chuyển|trao|giao|bàn\s+giao|ủy|uỷ|mượn|'
                r'cho\s+mượn|thêm|lấy|bật|tắt|gán|xem|kiểm\s+tra|'
                # FIX-1b third pass: "cho Lan quyền duyệt" (give Lan the right).
                r'cho|để|nhờ)')
#: FIX-1b third pass: an app's own role in Vietnamese ("quản lý lương",
#: "người duyệt", "quản trị") — what "cho Lan làm quản lý lương" hands out.
_APP_ROLE_VI = (r'(?:quản\s+lý\s+(?:lương|tiền\s+lương|bảng\s+lương|nhân\s+sự|hệ\s+thống|'
                r'phê\s+duyệt|quyền)|quản\s+trị(?:\s+viên)?|admin|dự\s+phòng|thay\s+thế|'
                r'duyệt|phê\s+duyệt)')
#: Who is not somebody else ("tôi", "mình", "em").
_NOT_ME_VI = r'(?!(?:tôi|mình|em|chúng\s+tôi|bạn)\b)'
#: A Vietnamese group that is about access ("nhóm quản lý lương").
#: FIX-1b sixth pass: "quản lý" only as one of the app's roles ("nhóm quản
#: lý lương"); a bare "nhóm quản lý" or "nhóm quản lý dự án" is a team.
_GROUP_VI = (r'nhóm\s+(?:quyền|quản\s+lý\s+(?:lương|tiền\s+lương|bảng\s+lương|nhân\s+sự|'
             r'hệ\s+thống|phê\s+duyệt|quyền)|quản\s+trị|người\s+dùng|bảo\s+mật|'
             r'(?:người\s+)?(?:phê\s+)?duyệt|admin)')


@payai_action
class NeverAccess(_Stub):
    """FIX-1b — OWNER RULING 2026-10-13: PayAI never opens, offers or changes
    Settings › Access and delegations — roles, people's access, lent roles,
    delegations and hand-overs, approval hand-overs, access requests, the
    left menu's permissions. Any order about them is this card: plain words,
    no door (the deny-list is `gate.ACCESS_*`; `OpenScreen` sends a screen
    name about access here too, and the Red Actions never decide an access
    request)."""
    key = 'never_access'
    title = _lt('Change access or roles')
    tier = 'never'
    #: Before every other Action: "approve Lan's access request" and "open
    #: roles" are this card, never a decision or a door.
    priority = 5
    summary = _lt('Opening or changing access, roles and delegations is never done '
                  'through PayAI.')
    examples = (_lt('Change Lan\'s role'),)
    never_text = _lt('PayAI does not open or change access. Go to Settings › Access and '
                     'delegations yourself.')
    door_id = ''
    phrases = (
        # Open / show the Access home's screens. A LOOK reads "roles", not a
        # bare "role" ("show my role", "open the Sales Manager role" — a job).
        r'^' + _NOT_HIRING + _LOOK_VERBS + r'\b(?=' + _OWN_WORDS + gate.ACCESS_NOUNS_LOOK_EN +
        r')(?P<what>.*)$',
        # "open users", "show the users list" — the Users screen.
        r'^' + _LOOK_VERBS + r'\s+(?:the\s+)?(?:app\s+|system\s+|all\s+)?users?'
        r'(?:\s+(?:screen|list|page|tab|settings|menu))?$',
        # Change roles, access, permissions, delegations — or admin as a right.
        r'^' + _NOT_HIRING + _CHANGE_VERBS + r'\b(?=' + _OWN_WORDS + r'(?:' +
        gate.ACCESS_NOUNS_EN + r'|' + _ADMIN_RIGHT + r'))(?P<what>.*)$',
        # Decide an access request.
        r'^' + _DECIDE_VERBS + r'\b(?=' + _OWN_WORDS + _ACCESS_REQUEST + r')(?P<what>.*)$',
        # Hand my approvals / access over: "give my approvals to Lan while
        # I'm away", "transfer my approvals to Lan", "give Lan my access".
        # Plural "approvals" only: "give my approval to the June run" is an
        # approval, not a hand-over.
        r'^(?:give|pass|transfer|hand(?:\s+over)?|handover|lend|delegate|move|forward|'
        r'reassign|assign|share|leave)\s+(?:(?:all|both)\s+(?:of\s+)?)?my\s+' + _MY_THINGS +
        r'(?P<what>.*)$',
        r'^(?:give|pass|lend|hand|leave)\s+' + _NOT_ME + r'\S+(?:\s+\S+)?\s+my\s+' + _MY_THINGS +
        r'(?P<what>.*)$',
        # "route / redirect / send my approvals to Lan".
        r'^(?:route|reroute|redirect|divert|send|forward|point|switch)\s+(?:all\s+)?my\s+' +
        _MY_THINGS + r'\s*(?:\S+\s+){0,3}?to\s+(?P<what>.+)$',
        r'^(?:route|reroute|redirect|divert|forward)\s+(?:all\s+)?(?:the\s+)?(?:approvals|'
        r'approval\s+(?:requests|tasks|inbox|queue))\s+(?:\S+\s+){0,3}?to\s+' + _NOT_ME +
        r'(?P<what>.+)$',
        # "take back my approvals", "take my access back".
        r'^(?:take|get|bring|pull)\s+(?:back\s+(?:all\s+)?my\s+' + _MY_THINGS + r'|(?:all\s+)?my\s+' +
        _MY_THINGS + r'\s*back\b)(?P<what>.*)$',
        r'^(?:reclaim|recall|retrieve|revoke)\s+(?:all\s+)?my\s+' + _MY_THINGS + r'(?P<what>.*)$',
        # "let Lan approve on my behalf", "allow Minh to sign off payroll".
        # Seeing or editing counts only for a screen or the payroll ("let
        # Lan see her payslip" is not access; "let Lan cover the night
        # shift" is a shift).
        r'^(?:let|allow|authori[sz]e|enable|permit)\s+' + _NOT_ME + r'(?P<who>(?:\S+\s+){1,3}?)'
        r'(?:to\s+)?' + _MAY_DO + r'(?P<what>.*)$',
        # FIX-1b fourth pass: "Lan needs to be able to approve payroll",
        # "Minh should be allowed to see the Runs screen", "I need Lan to be
        # able to sign off". What a person may do is the Access home's.
        r'^' + _SUBJECT + r'(?P<who>(?:\S+\s+){1,2}?)(?:needs?|must|should|has\s+to|have\s+to|'
        r'wants?|ought\s+to)\s+(?:to\s+)?' + _ABLE_TO + _MAY_DO + r'(?P<what>.*)$',
        r'^(?:i|we)\s+(?:want|need|would\s+like|\'d\s+like|wish)\s+' + _NOT_ME +
        r'(?P<who>(?:\S+\s+){1,3}?)to\s+' + _ABLE_TO + _MAY_DO + r'(?P<what>.*)$',
        # "cover for me, Lan", "stand in for me".
        r'^(?:cover|stand\s+in)\s+for\s+me\b(?P<what>.*)$',
        # "I'm away next week, Lan covers my approvals".
        # FIX-1b seventh pass: after the asker's own news only, never after
        # an order ("approve the June run, Lan covers my approvals").
        r'^' + _LEAD_IN + _SUBJECT + r'(?P<who>\w+)\s+(?:will\s+|can\s+|should\s+)?(?:covers?|'
        r'takes?\s+over|handles?|looks?\s+after|deals?\s+with)\s+(?:all\s+)?my\s+'
        r'(?:approvals|approval\s+(?:work|tasks|duties|inbox|queue)|inbox|sign[\s-]?offs)\b'
        r'(?P<what>.*)$',
        # "show Lan the Payslips screen", "give Minh the Runs menu".
        r'^(?:show|unhide|give)\s+' + _NOT_ME + r'\S+\s+(?:the\s+)?(?:\S+\s+){0,2}?'
        r'(?:screens?|menus?|tabs?|pages?|apps?|modules?)$',
        # "I want Lan to approve on my behalf", "have Lan approve for me".
        r'^(?:i|we)\s+(?:want|need|would\s+like|\'d\s+like|wish)\s+' + _NOT_ME +
        r'(?P<who>(?:\S+\s+){1,3}?)to\s+(?:approve|decide|sign(?:\s+off)?|act\s+(?:for|on)|'
        r'stand\s+in|cover\s+for\s+(?:me|us)|handle\s+my\s+approvals|take\s+over\s+my)\b'
        r'(?P<what>.*)$',
        # "Lan approves on my behalf", "have Lan sign off in my place".
        # FIX-1b fourth pass: after a reason ("I'm going on leave, Lan will
        # approve for me"), and a bare "for me" at the end.
        # FIX-1b sixth pass: no comma inside the person ("Lan, approve this
        # for me" asks Lan, not PayAI).
        # FIX-1b seventh pass: only the asker's own news before it
        # (`_LEAD_IN`), and "sign" only as signing for me (`_SIGNS_FOR`).
        r'^' + _LEAD_IN + r'(?:have\s+)?' + _SUBJECT +
        r'(?P<who>(?:[^\s,;:—]+\s+){1,2}?)(?:(?:should|will|can|may|is\s+to|has\s+to|'
        r'is\s+going\s+to)\s+)?'
        r'(?:approves?|decides?|' + _SIGNS_FOR + r'|acts?|stands?\s+in)\b'
        r'(?=.*\b(?:on\s+my\s+behalf|in\s+my\s+place|instead\s+of\s+me|for\s+me\s+while|'
        r'for\s+(?:me|us)\s*[.!]*$|while\s+i(?:\s+am|\'m)\s+(?:away|out|off|on\s+leave))\b)'
        r'(?P<what>.*)$',
        r"^" + _LEAD_IN + _SUBJECT + r"(?P<who>\w+)'ll\s+"
        r"(?:approve|decide|" + _SIGNS_FOR + r"|act|stand\s+in)\b"
        r"(?=.*\b(?:on\s+my\s+behalf|in\s+my\s+place|instead\s+of\s+me|for\s+(?:me|us)\s*[.!]*$))"
        r"(?P<what>.*)$",
        # "Lan needs access to payroll", "Minh should get admin rights".
        r'^' + _SUBJECT + r'(?P<who>(?:\S+\s+){1,2}?)(?:needs?|wants?|requires?|is\s+missing|'
        r'lacks?|(?:should|must|has\s+to|have\s+to)\s+(?:have|get)|gets?)\s+'
        r'(?:more\s+|extra\s+|full\s+|edit\s+|view\s+|new\s+|the\s+|an?\s+)?'
        r'(?=(?:\S+\s+){0,2}?(?:' + gate.ACCESS_WORD_EN + r'|permissions?\b|rights\b|'
        r'privileges?\b|roles?\b|' + _ADMIN_RIGHT + r'|' + _APP_ROLE + r'\b))(?P<what>.*)$',
        # "Lan should be a payroll manager", "Minh becomes an approver".
        r'^' + _SUBJECT + r'(?P<who>(?:\S+\s+){1,2}?)(?:(?:should|must|will|is\s+to|has\s+to)\s+'
        r'(?:be|become)|becomes?|is\s+now)\s+(?:(?:an?|the|our|my)\s+)?(?:new\s+)?' + _APP_ROLE +
        r'\b(?P<what>.*)$',
        # "change who approves payroll", "pick who signs off".
        r'^(?:change|switch|swap|update|set|pick|choose|decide|edit|reassign)\s+who\s+'
        r'(?:approves|signs|decides|can|may|has|gets|sees|is\s+(?:the\s+)?(?:approver|backup|'
        r'admin))\b(?P<what>.*)$',
        # "replace the approver with Lan", "swap my backup for Minh".
        r'^(?:replace|swap|switch|change|remove|reassign)\s+(?:the\s+|my\s+|our\s+|\S+\'s\s+)?'
        r'(?:\S+\s+)?(?:approvers?|backups?|back-ups?|deput(?:y|ies)|delegates?|stand[\s-]?ins?|'
        r'admins?|administrators?|super\s*users?)\b'
        # FIX-1b fourth pass: the person, not a thing of theirs ("change the
        # approver note", "remove the approver comment").
        # FIX-1b sixth pass: "to" only before a person ("change my backup to
        # Lan"), never a time or a thing ("change the backup to Monday").
        r'(?=\s*$|\s*[,.;!?]|\s+(?:with|for|by|from|on|of|in|at|and|so|because|while|until|'
        r'this|next|today|tomorrow|now|please|back|out|off|as)\b|\s+to\s+(?:' + _OTHER_PERSON_EN +
        r'|' + _NOT_ME + r'(?P<backupto>[^\W\d_][\w\'’-]*)))(?P<what>.*)$',
        # "lock the Payslips screen for Lan", "hide Payslips from Lan".
        r'^(?:lock|unlock|hide|unhide|block|unblock|restrict|grey\s+out|gray\s+out)\s+'
        r'(?:the\s+)?(?:\S+\s+){0,3}?(?:screens?|menus?|pages?|tabs?|items?|apps?|modules?|'
        r'sections?)\s+(?:for|from|to)\s+' + _NOT_ME + r'(?P<what>.+)$',
        r'^(?:hide|unhide|block|unblock)\s+(?:\S+\s+){1,4}?from\s+' + _NOT_ME + r'(?P<what>.+)$',
        # FIX-1b fourth pass: "put Lan in the payroll managers group", "move
        # Minh into the admin group" — a group of the app's roles, never a
        # team ("put Lan in the sales team", "move Lan to admin").
        r'^(?:put|place|move|get|enrol+|include|stick|bring)\s+' + _NOT_ME +
        r'(?P<who>(?:\S+\s+){1,3}?)(?:in|into|to|onto|among|inside)\s+(?:(?:the|a|an|our|my)\s+)?'
        r'(?:(?:' + _APP_ROLE + r')s?\s+groups?|(?:user|security|access|permission|rights?|'
        r'roles?|approvals?)\s+groups?|' + _APP_ROLE_NAMED + r's?'
        # FIX-1b sixth pass: a bare role name ends the order ("put Lan in
        # the HR managers bonus pool / department", "the payroll managers'
        # bonus" are not a group).
        r'(?=\s*$|\s*[,.;!?]|\s+(?:please|now|today|tomorrow|too|as\s+well|from|starting|'
        r'until|while|because|so)\b))\b(?P<what>.*)$',
        # "see it as Lan", "view as Lan", "log in as Lan", "impersonate Lan"
        # — the Access home's "See it as somebody else". Never a format
        # ("view as list", "see it as a percentage").
        # FIX-1b seventh pass: a bare name after "as" only with a SEE verb
        # ("open it as Net Pay" is a screen, "check it as Approved" /
        # "show it as Bonus" a status or a format); any verb with the words
        # for somebody else, or with the app itself ("open the app as Minh").
        r'^(?:see|view|look\s+at|show(?:\s+me)?|preview|browse|check|open)\s+'
        r'(?:(?:it|this|that|everything|things|' + _SEE_APP + r')\s+)?' + _SEE_AS +
        r'(?P<who>' + _OTHER_PERSON_EN + r')$',
        r'^(?:see|view|look\s+at|show(?:\s+me)?|preview|browse|check|open)\s+' + _SEE_APP +
        r'\s+' + _SEE_AS + r'(?P<who>' + _NOT_ME + _NOT_A_FORMAT + _SEE_NAME + r')$',
        r'^(?:see|view|look\s+at|preview|browse)\s+(?:(?:it|this|that|everything|things)\s+)?' +
        _SEE_AS + r'(?P<who>' + _NOT_ME + _NOT_A_FORMAT + _SEE_NAME + r')$',
        r'^(?:log\s*in|login|sign\s+in|signin)\s+as\s+' + _NOT_ME + r'(?P<who>.+)$',
        r'^impersonate\s+(?P<who>.+)$',
        # "what roles does Lan have", "which permissions does Minh hold",
        # "what screens can Lan open", "what can Lan see". ("who has access
        # …" opens as a question — `registry._QUESTION` — and goes to the
        # question path, which never opens or changes anything.)
        r'^' + _NOT_HIRING + r'(?:what|which)\s+(?:(?:kinds?|sorts?|types?)\s+of\s+)?'
        r'(?:roles?|permissions?|rights|access(?:es)?|privileges?|groups|screens|menus?)\s+'
        r'(?:does|do|did|has|have|is|are|can|will|should)\s+' + _SUBJECT +
        r'(?P<who>(?:\S+\s+){1,3}?)(?:have|hold|get|got|carry|own|been\s+given|see|open|use|'
        r'access|in)\b'
        # FIX-1b sixth pass: nothing after it but where or when — "what
        # rights does Lan have under the contract", "… to the building" are
        # not the Access home's.
        r'(?P<what>(?:\s+(?:in|on|inside|to|for|at)\s+(?:the\s+)?(?:app|payobook|system|'
        r'payroll|pay\s+runs?|payslips|approvals|menu|left\s+menu|settings|screens?))?'
        r'(?:\s+(?:now|today|right\s+now|currently|at\s+the\s+moment))?)\s*[?.!]*$',
        r'^what\s+(?:can|may|does|do)\s+' + _SUBJECT + r'(?P<who>(?:\S+\s+){1,2}?)'
        r'(?:see|open|access|view|reach)(?:\s+(?:in|on)\s+(?:the\s+)?(?:app|payobook|system|'
        r'menu|left\s+menu))?\s*[?.!]*$',
        # "set Lan as my backup", "make Lan admin", "add Minh as an approver",
        # "make Lan a payroll manager", "add Lan to the payroll managers".
        r'^(?:make|set|name|appoint|add|choose|pick|nominate|assign|promote|demote|turn|'
        r'upgrade|downgrade|remove|take|drop|kick)\s+' + _NOT_ME +
        r'(?P<who>(?:\S+\s+){1,3}?)(?:as\s+|to\s+|into\s+|from\s+|off\s+|out\s+of\s+)?'
        r'(?:(?:my|the|a|an|our)\s+)?'
        r'(?:backup|back-up|deputy|stand[\s-]?in|delegate|substitute|proxy|' + _APP_ROLE +
        r')s?\b(?P<what>.*)$',
        # "delegate", "delegate the June run to Lan": a delegation of any kind
        # hands somebody an approver's place. "new delegation for Lan".
        r'^delegat(?:e|ion|ions)\b(?P<what>.*)$',
        r'^new\s+(?:delegations?|hand[\s-]?overs?|access\s+requests?|role\s+changes?)\b'
        r'(?P<what>.*)$',
        # "grant admin to Lan", "give Lan admin rights".
        r'^(?:give|grant|assign)\s+(?:\S+\s+){0,3}?' + _ADMIN + r'(?P<what>.*)$',
        # "revoke admin from Lan", "remove admin for Minh".
        r'^(?:remove|revoke|take\s+away|strip|withdraw)\s+(?:the\s+)?' + _ADMIN +
        r'\s+(?:from|for)\s+' + _NOT_ME + r'(?P<what>.+)$',
    )
    phrases_vi = (
        r'^' + _NOT_HIRING_VI + r'(?=' + _BEFORE_REASON_VI + _ACCESS_NOUNS_VI + r')(?:' +
        _ACCESS_VERBS_VI + r'\b(?P<what>.*)|' +
        # The screen's name alone ("phân quyền", "quyền truy cập").
        r'(?:phan\s+quyen|quyen\s+truy\s+cap|uy\s+quyen)(?:\s+(?P<who>.+))?)$',
        # Decide an access request ("duyệt yêu cầu truy cập của Lan").
        r'^' + _DECIDE_VERBS_VI + r'\b(?=' + _BEFORE_REASON_VI + _ACCESS_REQUEST_VI + r')'
        r'(?P<what>.*)$',
        # "quyền" typed with its marks after a verb that changes it: "đổi
        # quyền của Lan", "gỡ quyền", "cấp cho Lan quyền quản lý",
        # "chuyển quyền duyệt cho Lan", "mở quyền cho Lan".
        MARKED_ONLY + r'^' + _QUYEN_VERBS + r'\s+(?:\S+\s+){0,4}?quyền\b(?P<what>.*)$',
        # "cho Lan mượn quyền (duyệt)".
        MARKED_ONLY + r'^cho\s+(?:\S+\s+){1,4}?mượn\s+(?:\S+\s+){0,2}?quyền\b(?P<what>.*)$',
        # "để Lan duyệt thay tôi", "nhờ Lan duyệt thay" — let somebody
        # approve in my place.
        MARKED_ONLY + r'^(?:để|cho|nhờ)\s+(?:\S+\s+){1,3}?(?:duyệt|phê\s+duyệt|ký|quyết\s+định)\s+'
        r'(?:\S+\s+){0,4}?thay\b(?P<what>.*)$',
        # "Lan duyệt thay tôi tuần sau" — somebody named first.
        MARKED_ONLY + r'^' + _NOT_ME_VI + r'(?!(?:hãy|xin|vui|làm|giúp|duyệt|phê)\b)'
        r'(?:\S+\s+){1,3}?(?:sẽ\s+|được\s+|có\s+thể\s+)?(?:duyệt|phê\s+duyệt|ký|quyết\s+định)\s+'
        r'thay\s+(?:cho\s+)?(?:tôi|mình|em|anh|chị)\b(?P<what>.*)$',
        # "giao việc duyệt cho Lan", "chuyển việc phê duyệt cho Lan".
        MARKED_ONLY + r'^(?:chuyển|giao|bàn\s+giao|nhờ)\s+(?:việc\s+|các\s+|hết\s+)?'
        r'(?:duyệt|phê\s+duyệt)\s+(?:\S+\s+){0,3}?cho\b(?P<what>.*)$',
        # "đặt Lan làm người dự phòng", "chọn Minh làm người duyệt", "cho
        # Lan làm quản lý lương", "nâng Lan lên quản trị".
        MARKED_ONLY + r'^(?:đặt|chọn|cử|chỉ\s+định|thêm|cho|để|bổ\s+nhiệm|nâng|đưa|đổi)\s+'
        + _NOT_ME_VI + r'(?:\S+\s+){1,3}?(?:làm|thành|lên)\s+(?:người\s+)?' + _APP_ROLE_VI +
        r'\b(?P<what>.*)$',
        # "khóa màn hình phiếu lương cho Lan", "ẩn menu lương với Minh".
        MARKED_ONLY + r'^(?:khóa|khoá|mở\s+khóa|mở\s+khoá|ẩn|bỏ\s+ẩn|giấu|chặn|bỏ\s+chặn)\s+'
        r'(?:màn\s+hình|menu|trang|mục|thẻ|ứng\s+dụng|phân\s+hệ)\s+(?:\S+\s+){0,4}?'
        r'(?:cho|với|khỏi|đối\s+với)\s+' + _NOT_ME_VI + r'(?P<what>\S.*)$',
        # "ẩn phiếu lương khỏi Lan" — hidden from a PERSON ("ẩn dòng bằng 0
        # khỏi phiếu lương" hides lines from a payslip).
        MARKED_ONLY + r'^(?:ẩn|giấu|chặn)\s+(?:\S+\s+){1,4}?(?:khỏi|với|đối\s+với)\s+' +
        _NOT_ME_VI + r'(?!(?:phiếu|bảng|danh|báo|file|tệp|màn|trang|dòng|cột|mục|đợt|kỳ|tháng|'
        r'lương|hợp|hồ|các|những|tất)\b)(?P<what>\S.*)$',
        # "mở bàn giao" — the Hand-overs screen named alone.
        r'^(?:mo|xem|vao|di\s+toi|den)\s+(?:man\s+hinh\s+|trang\s+|muc\s+|cac\s+)?ban\s+giao$',
        # "mở người dùng", "xem danh sách người dùng" — the Users screen.
        r'^(?:mo|xem|vao|di\s+toi|den)\s+(?:man\s+hinh\s+|danh\s+sach\s+|trang\s+|muc\s+)?'
        r'(?:cac\s+)?nguoi\s+dung(?:\s+(?:he\s+thong|ung\s+dung))?$',
        # FIX-1b fifth pass: "xem như Lan", "xem như người khác" — the Access
        # home's "Xem như" (See it as); "đăng nhập như Lan" (log in as).
        # Never "consider it done" ("xem như đã duyệt", "xem như xong") or a
        # format ("xem như bảng"). FIX-1b sixth pass: typed with marks only,
        # and the person must look like one — "người khác", or a name with
        # its capital ("xem như Lan"); "xem như lương tháng 6", "xem như
        # hoàn thành", "mở như phiếu lương" keep what they did before.
        # FIX-1b seventh pass: "mở như …" (open as) only with "người khác"
        # — "mở như Phiếu Lương" opens the Payslips screen.
        MARKED_ONLY + r'^(?:xem|nhìn|mở|đăng\s+nhập)\s+' + _SEE_OBJ_VI + _SEE_AS_VI +
        r'(?P<who>' + _OTHER_PERSON_VI + r')$',
        MARKED_ONLY + r'^(?:xem|nhìn|đăng\s+nhập)\s+' + _SEE_OBJ_VI + _SEE_AS_VI + r'(?P<who>' +
        _NOT_ME_VI + r'(?!(?:đã|là|vậy|thế|này|đó|thường|bình|cũ|trước|sau|xong|được|chưa|không|bảng|danh|'
        r'biểu|đồ|thẻ|lưới|số|phần|tệp|file|excel|pdf|csv|văn|ảnh|hình|kế|dự|một|mới|nhau|'
        r'cái|các|những|mọi|tất|ban|lúc|khi)\b)' + _SEE_NAME + r')$',
        # "thêm Lan vào nhóm quản lý lương", "gỡ Lan khỏi nhóm quyền".
        r'^(?:thêm|đưa|cho)\s+(?:\S+\s+){1,5}?vào\s+' + _GROUP_VI + r'\b(?P<what>.*)$',
        r'^(?:xóa|xoá|gỡ|bỏ|loại|đưa|rút)\s+(?:\S+\s+){1,5}?(?:ra\s+)?khỏi\s+' + _GROUP_VI +
        r'\b(?P<what>.*)$',
    )

    def phrase_ok(self, m, source):
        """May this reading stand on the order's own words?

        * A capital "Quyền" / "Quyên" mid-sentence is a person's name, not
          "quyền" (access): the match must stand without it ("xóa phiếu
          lương của Quyền" is not about access; "đổi vai trò của Quyên"
          still is). In a sentence typed in Title Case ("Đổi Quyền Của
          Lan", FIX-1b third pass) a capital is no sign of a name: only a
          "Quyền" after "của / cho / với / anh / chị …" is one there.
        * FIX-1b third pass: an access noun that names something else — a
          pay item or a team ("admin allowance", "phụ cấp vai trò"), a
          right in law ("leave rights", "quyền lợi", "quyền nghỉ phép"), a
          volume ("quyển sổ"), a job's role — is not about access
          (`gate.mask_not_access`): the match must stand without it.
        * FIX-1b sixth pass: "see it as …" / "xem như …" and "change my
          backup to …" stand only on a person: every word a name with its
          capital (`_name_like`) — not "net pay", "VND", "Word", "Monday",
          "lương tháng 6", "Lan đã nghỉ"."""
        for group in ('seename', 'backupto'):
            if group in m.re.groupindex and m.group(group) is not None:
                if not _name_like(source, *m.span(group)):
                    return False
        masked = gate.mask_not_access(source)
        if not source.isupper():
            before = (r'(\b(?:của|cho|với|và|anh|chị|em|ông|bà)\s)' if _title_case(source)
                      else r'(\s)')
            masked = re.sub(before + r'(Quy(?:ền|ên))\b',
                            lambda x: x.group(1) + 'x' * len(x.group(2)), masked,
                            flags=re.I if _title_case(source) else 0)
        if masked == source:
            return True
        low = masked.lower()
        from .resolve import fold_keep
        return bool(m.re.match(low) or m.re.match(fold_keep(low)))


def _name_like(source, start, end):
    """Do `source[start:end]`'s words read as a person's name? Each word
    starts with a capital and goes on in small letters ("Lan", "Lan Nguyen",
    "Quyên"; not "VND", "net pay", "Lan's payslip"), and is not a month, a
    day or an app ("June", "Monday", "Word"). In a sentence typed all in
    capitals or in Title Case a capital says nothing: no name."""
    if source.isupper() or _title_case(source):
        return False
    words = (source[start:end] or '').split()
    if not words:
        return False
    low = [w.lower() for w in words]
    if any(' '.join(pair) in _NOT_NAME_PAIRS_VI for pair in zip(low, low[1:])):
        return False
    for word in words:
        if not re.fullmatch(r'[^\W\d_][^\W\d_]*(?:-[^\W\d_]+)?', word, re.U):
            return False
        if not (word[0].isupper() and (len(word) == 1 or word[1:].replace('-', '').islower())):
            return False
        if word.lower() in _NOT_NAMES:
            return False
    return True


def _title_case(text):
    """True when every word of two letters or more starts with a capital
    ("Đổi Quyền Của Lan") — then a capital says nothing about a name."""
    words = [w for w in re.findall(r'[^\W\d_]+', text or '', re.U) if len(w) > 1]
    return len(words) > 1 and all(w[:1].isupper() for w in words)
