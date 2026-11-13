# LEARNREV — closeout (2026-10-20)

The owner's brief (2026-10-17) was a major revamp of the lessons and coaching help. They chose Option C, "Help on
the screen", to be delivered in phases. The design is in `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html`.

## Delivered (all live, all pushed)
| Phase | What | Deploy record |
|---|---|---|
| P0 | Six quick fixes: chat opens at the latest message, "Open the lesson" lands on the lesson, plain "What next" answers, wording | P0_REPORT.md |
| P1 | Help generated from the code: a per-screen manifest, field cards, live "Right now" counts, and a truth gate | P1_DEPLOY.md |
| P2 | The Guide panel docked beside the screen (six sections above one chat), (i) cards, thumbs on fields | P2_DEPLOY.md |
| P3 | Library page (Continue card, path strip, menu groups, one search) | P3_DEPLOY.md |
| P4 | Lessons and walkthroughs play beside the real screen in four lines; checked Try; country variants | P4_DEPLOY.md |
| P5a (Sonnet) | 8 more manifests (16 in total), the "What people asked and rated" card, P2/P3 leftovers | P5A_DEPLOY.md |
| P5b (Opus) | All 42 lessons and 25 walkthroughs in four lines, step thumbs, Vietnamese pass (148 strings, incl. DUYỆT) | P5B_DEPLOY.md |

Badges, streaks and the overall ring were dropped, as the owner asked. Practice uses the demo company on payobook and
the hand-drawn replicas on tenants. `P5_REPLICA_NOTE.md` recommends keeping the hand-drawn replicas, kept honest by
the replica truth gate, which matches the owner's standing decision.

## Open items (none blocks use)
1. **Vietnamese outside Learn.** About 80 untranslated labels on the Lifecycle boards, plus poor machine Vietnamese:
   "Thiếu cú đấm" for a missing punch-out and "Hết tiền" for money out. This is the product .po files' work, not
   Learn's.
2. **Replicas outside the 16 gated screens** have drifted from the real screens. The fix is to extend the replica gate
   as more manifests are added.
3. **Wording mismatch.** Four English lessons say "These figures do not add up" where the run card says "Figures don't
   add up".
4. **Language switch.** The top-bar switch once reset the test user to English during the P5b walk. This is not Learn
   code.
5. **LR18.** gitlocal-d2 still has to confirm whether removing group_payai_user from internal users on payobook was
   intended.
6. **Not walked on the live site:** checked Try and the Indonesia variant (both walked on the clone).
