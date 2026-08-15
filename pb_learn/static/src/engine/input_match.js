/** @odoo-module **/
/* =============================================================================
   The loose match — LEARNOS Phase 5.

   WHAT THIS IS FOR
   ----------------
   A Try step may ask the learner to TYPE something. The engine then has to
   decide whether what they typed is what was asked for, and every way of
   getting that decision wrong is bad in a different direction:

     too strict  a learner who typed the right amount with the wrong thousands
                 mark is stuck on a walkthrough with no way past the step, in
                 the one mode whose whole promise is that nothing can go wrong;
     too loose   the step advances on a value that is not the answer, which
                 makes the exercise a button-press with extra steps.

   So the rule is written here, once, as a PURE FUNCTION over two strings — no
   DOM, no state, no engine — which is what lets tools/replay_tests.py execute
   every case rather than describe it.

   THE RULES, AND WHY EACH ONE EARNS ITS PLACE
   -------------------------------------------
     * TRIM AND COLLAPSE. A trailing space is not a different value.
     * CASEFOLD. Nobody is being taught capitalisation here.
     * TONE MARKS ARE OPTIONAL, in the text kind. A Vietnamese name typed on a
       keyboard with no Vietnamese layout is the ordinary case, not the
       exception — the ledger's own redaction work says the unaccented
       spelling is the one people reach for in a hurry. `Nguyen Van An`
       matches `Nguyễn Văn An`; `Nguyen Van Anh` still does not, which is the
       property that matters.
     * THOUSANDS MARKS ARE OPTIONAL, in the number kind. Vietnamese groups
       with `.` and English with `,`, and the SAME step is played in both
       languages, so a rule that insisted on one of them would be a rule that
       failed for half the readers. `1.200.000`, `1,200,000`, `1 200 000` and
       `1200000` are one value.
     * EMPTY NEVER MATCHES. Not as a policy — as the first statement, before
       anything is compared, because the ordinary way to reach this function
       is a blur on a field nobody has typed in yet.

   WHAT IT DELIBERATELY DOES NOT DO: near-misses. There is no edit distance and
   no prefix rule. A value that is nearly right is wrong, and the step says so
   and waits; the alternative is an engine that decides on somebody's behalf
   what they meant to type.
   ========================================================================== */

/* Every separator a person might put inside a number: the two thousands marks,
   the space forms (ordinary, non-breaking, narrow no-break), the apostrophe
   some locales use, and the đồng sign if they copied the figure off a screen.
   Everything that is not a digit or a leading minus goes. */
const NON_DIGIT_RE = /[^0-9-]/g;

/* Combining marks, after NFD has split them off their letters. `đ` has no
   decomposition, so it is handled by name below — and only in the TEXT kind,
   where it is a letter; in the number kind it is a currency mark and is
   already gone with everything else that is not a digit. */
const COMBINING_RE = /[̀-ͯ]/g;
const WS_RE = /\s+/g;

/** Fold a text value to the form two spellings of the same thing share. */
export function foldText(value) {
    return String(value === null || value === undefined ? "" : value)
        .normalize("NFD")
        .replace(COMBINING_RE, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toLowerCase()
        .replace(WS_RE, " ")
        .trim();
}

/** Fold a number value to its digits. Returns "" when there are none, which
 *  is what makes "abc" fail against "1200000" rather than matching "". */
export function foldNumber(value) {
    const digits = String(value === null || value === undefined ? "" : value)
        .replace(NON_DIGIT_RE, "")
        .replace(/(?!^)-/g, "");
    return digits === "-" ? "" : digits;
}

/** The one comparison. `kind` is "number" or anything else, and it comes from
 *  the INPUT_ANCHORS table in the fixture — the same table the replica draws
 *  the field from and the generator validates the step against, so the three
 *  cannot disagree about what a field holds. */
export function looseMatch(typed, expected, kind) {
    const fold = kind === "number" ? foldNumber : foldText;
    const a = fold(typed);
    const b = fold(expected);
    if (!a || !b) {
        return false;
    }
    return a === b;
}
