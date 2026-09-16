/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **The Announcements lens on the People hub.** Registered into
 *      `pb_people_hub`'s soft registry (`PEOPLE_LENSES`) rather than imported
 *      into its config, because the dependency runs the other way: this
 *      module depends on the hub, so the hub cannot import this one back.
 *
 *      Records took 40, Pay 45, Assets 50, Praise 60 and Goals 70, so
 *      Announcements takes **80** — and that is also the right place in the
 *      story the rail tells: who works here, what their record says, what
 *      they were handed, what colleagues said about them, what they are
 *      working towards, and then what the company is about to tell them.
 *
 *      R63 — THE LENS RAIL'S LABEL BOX IS 60px and it wraps between words but
 *      never inside one. "Announcements" is thirteen characters with no break
 *      in it, which is wider than "Improvement" (76px) and "Recognition",
 *      both of which had to be renamed — so the label is **"Announce"**,
 *      measured live before shipping.
 *
 *   2. **The Home lens "Coming up".** Wall took 20, the Decision Room 30 and
 *      Goals 40, so this takes **50**. Thirty-five was free and would have
 *      put it before Goals; it is deliberately not used. Every sequence in
 *      every hub in this product is a multiple of ten, and the reading order
 *      that matters here is that the two cards which need somebody to DO
 *      something come before the one that is telling them about something.
 *
 *   3. **⌘K palette rows, in the 3700 block.** A took 3500, B 3600, D 3800
 *      and E 3900; C takes **3700**, as the wave plan says.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed". `requires` is the PRESENCE PROBE — the
 *      actions registry holding this tag is what says the module shipped its
 *      JS, and trusting a version number is what R110/R116 are about.
 *
 *   4. **Settings → Announcements**, sequence 50 (Vendors 20, Access 30,
 *      Approvals and Hiring 40).
 *
 * Every icon comes from the shared `ic()` set in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbHrCommCalendar } from "@pb_hr_comm/js/comm_calendar";
import { PbHrCommHome } from "@pb_hr_comm/js/comm_home";

/**
 * THE CALENDAR IS THE HR TEAM'S SCREEN AND THE GATE SAYS SO.
 *
 * This is the opposite call from the Goals lens, and deliberately. A goal
 * sheet belongs to everybody and a line manager holds no goals group by
 * definition, so gating that lens on a group made it invisible to the very
 * people it was for (R209). An announcements CALENDAR is a planning surface
 * for whoever writes announcements: an ordinary employee has nothing behind
 * it, and a lens that opens on an empty month for four thousand people is a
 * dead end with a label on it.
 *
 * The person who LOOKS AFTER one announcement and holds no group is not
 * forgotten — R157 is the same rule read the other way. They have three real
 * doors: the reminder email two days before, the to-do it puts on their list,
 * and the "Announcements I look after" row in the command bar below, which is
 * open to everybody with a login and shows exactly their own.
 */
export const COMM_GATE = [
    "pb_hr_comm.group_comm_user",
    "pb_hr_comm.group_comm_manager",
    "pb_hr_comm.group_comm_admin",
];

/** The library and who posts land on are the administrator's. */
export const COMM_ADMIN = [
    "pb_hr_comm.group_comm_manager",
    "pb_hr_comm.group_comm_admin",
    "base.group_system",
];

registry.category(PEOPLE_LENSES).add("announcements", {
    key: "announcements",
    icon: "megaphone",
    label: _t("Announce"),
    Component: PbHrCommCalendar,
    groups: COMM_GATE,
}, { sequence: 80 });

/**
 * THE HOME CARD IS OPEN TO EVERYBODY WITH A LOGIN, and that is the point. An
 * announcement is about to be sent TO these people; telling them it is coming
 * is not a permission, it is the courtesy this module exists for. What is
 * behind each row is still decided by the record rules.
 */
registry.category(HOME_LENSES).add("coming_up", {
    key: "coming_up",
    icon: "megaphone",
    label: _t("Coming up"),
    Component: PbHrCommHome,
    groups: ["base.group_user"],
}, { sequence: 50 });

/* ------------------------------------------------------------ Settings ---- */
registry.category(SETTINGS_CATEGORIES).add("announcements", {
    key: "announcements",
    icon: "megaphone",
    label: _t("Announcements"),
    blurb: _t("The announcements somebody has already written once, and who "
              + "they land on in each company."),
    groups: COMM_ADMIN,
    cards: [{
        id: "comm_templates",
        xmlid: "pb_hr_comm.action_pb_hr_comm_template",
        icon: "layoutList",
        label: _t("Templates"),
        sub: _t("The town hall, the holiday notice — written once, copied "
                + "onto a new announcement whenever it is needed."),
    }, {
        id: "comm_responsibles",
        xmlid: "pb_hr_comm.action_pb_hr_comm_default",
        icon: "userCheck",
        label: _t("Who looks after them"),
        sub: _t("The HR lead of each company, unless you name somebody else "
                + "here."),
    }],
}, { sequence: 50 });

/* ---------------------------------------------------------- command bar --- */
const palette = registry.category("pb_hub_palette");

palette.add("comm_calendar", {
    id: "comm_calendar",
    label: _t("Announcements"),
    sublabel: _t("People"),
    icon: "megaphone",
    groups: COMM_GATE,
    requires: "pb_hr_comm_calendar",
    action: { xmlid: "pb_people_hub.action_pb_people_hub",
              lens: "announcements" },
}, { sequence: 3700 });

palette.add("comm_new", {
    id: "comm_new",
    label: _t("Write an announcement"),
    sublabel: _t("Announcements"),
    icon: "plus",
    groups: COMM_GATE,
    requires: "pb_hr_comm_calendar",
    action: { xmlid: "pb_hr_comm.action_pb_hr_comm_post" },
}, { sequence: 3710 });

palette.add("comm_templates", {
    id: "comm_templates",
    label: _t("Announcement templates"),
    sublabel: _t("Announcements"),
    icon: "layoutList",
    groups: COMM_ADMIN,
    requires: "pb_hr_comm_calendar",
    action: { xmlid: "pb_hr_comm.action_pb_hr_comm_template" },
}, { sequence: 3720 });

/**
 * THE SAME SCREEN, FOUND BY THE OTHER WORD. Somebody looking for whose
 * birthday it is does not type "announcements" — they type "birthday", and
 * the week's celebrations are a panel on the announcements calendar. A second
 * row is how a command bar answers a word it would otherwise have no row for;
 * the sublabel says where it lands, so nobody is surprised by what opens.
 */
palette.add("comm_celebrations", {
    id: "comm_celebrations",
    label: _t("Birthdays and anniversaries this week"),
    sublabel: _t("On the announcements calendar"),
    icon: "cake",
    groups: COMM_GATE,
    requires: "pb_hr_comm_calendar",
    action: { xmlid: "pb_people_hub.action_pb_people_hub",
              lens: "announcements" },
}, { sequence: 3730 });

/**
 * THE ONE ROW THAT IS OPEN TO EVERYBODY. The person who looks after an
 * announcement holds no group by definition (see COMM_GATE above): this is
 * their own door, and it shows exactly the announcements they are responsible
 * for and nothing else.
 */
palette.add("comm_mine", {
    id: "comm_mine",
    label: _t("Announcements I look after"),
    sublabel: _t("Your own"),
    icon: "userCheck",
    groups: ["base.group_user"],
    requires: "pb_hr_comm_calendar",
    action: { xmlid: "pb_hr_comm.action_pb_hr_comm_post_mine" },
}, { sequence: 3740 });
