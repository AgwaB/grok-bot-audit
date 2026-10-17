# Audit criteria

Every input comes from inside Grok Bot: each bot's own chat history (saved transcript pages), its profile name and description,
and the memory block the app shows the bot. No external APIs, no logins.
`diagnostics.py` applies the rules below and writes `diag.json`; `build_findings.py finalize` applies the scoring.

## 1. Definitions
- **Real request**: a message the user typed. App prompts, routine wake-ups, background results and messages from other bots don't count.
- **Correction**: judged with `rubric_correction.md` (labels.json).
- **Incident**: corrections on the same topic in the same bot within 60 minutes count once.
- **Occasion**: incidents more than 6 hours apart are separate occasions (`sessions` in diag.json). A late-night session
  that crosses midnight is one occasion, not two days.
- **Repeated correction**: same bot and topic, 2 or more incidents on 2 or more separate occasions. Incidents that all fall
  in one occasion (`one_session`) are never repeated on their own. Before proposing anything, apply the decision procedure
  in section 5.
- **Strong repeated correction**: a repeated correction that also has 3+ incidents, or incidents in 5%+ of the bot's real requests.
  It needs at least one incident of medium or high confidence.
- **Fix candidates**: memory saves, "from now on…" sentences the bot said **to the user** (not text inside a draft,
  quote or code it produced), and replies the judge marked as promising a lasting change. Listed once per bot
  (`fix_candidates`, with ids), in time order, from the topic's first incident in the whole history; each group's
  `fix_check` refers to them by id with `incidents_after` (this group's incidents after it) and `active_days_after` (days
  the user used the bot after it), at most the 12 latest. The scripts can't tell whether one is about the group's
  problem, so candidates change neither status nor impact until you confirm one (`writing.md`).
- **The latest relevant fix decides.** Among the candidates you confirm as about this problem, look only at the latest:
  - **Fixed** (improving): its `incidents_after` = 0 and `active_days_after` ≥ 2. Goes under "Already improving", no
    proposal. This holds even if an earlier fix failed before it.
  - **Too early to tell**: `incidents_after` = 0 but `active_days_after` < 2. Judged as if unfixed; the finding gets
    `"too_early": true` and says when the rule was saved.
  - **Came back after a fix**: an incident came after the latest fix (`incidents_after` ≥ 1); impact +1.
- **Unanswered request**: a real request with no bot reply for 6 hours or more (a lower bound, taken from the next timestamp).
  A request that is the last message in the data is not counted: the bot may not have had time to answer.
  If several bots go quiet in the same window, it is a fleet outage (usually a plan limit), not a problem with one bot.
- **Age** = now minus the first message. **Idle** = now minus the last real request. **Share** = the bot's real requests ÷ all real requests.

## 2. Status (first match wins)
| status | rule |
|---|---|
| Clean up (`red`) | Age ≥ 3 days, idle ≥ max(3 days, half its age), and share < 5%. *Or* its whole job is already done by another bot that is in use, and its history shows no use of its own. |
| Needs work (`yellow`) | A strong repeated correction with a shared cause that is not fixed; *or* unanswered requests caused by the bot itself (not a fleet outage); *or* a safety problem visible in its chats (for example, it printed another bot's internal settings). |
| Fine (`green`) | Everything else. An empty description, a single correction or a weak repeated correction can still produce a proposal, but it doesn't change the status. |

Why relative thresholds: a fleet may have only a few days of history, so fixed counts ("5 corrections a week") mean nothing yet.
Share, half-of-age idle and per-request rates scale with however much history exists. A bot younger than 3 days can't be "Clean up" by the idle rule.
`diagnostics.py` suggests a status from these rules; you set the final one with the procedure in section 5.

## 3. Proposal scoring
Every proposal carries `score = {impact, confidence, effort, reversibility, basis}`:
- **impact** (1–3): 3 = 4+ incidents, repeated work on 5+ days, or 3+ bots affected; 2 = 2–3 incidents, 3–4 days or 2 bots; 1 = less.
  Add 1 (max 3) if the problem came back after a fix you confirmed.
- **confidence**: `high` 1.0 / `medium` 0.7 / `low` 0.4, from the rubric confidence of the incidents and whether the evidence is a direct quote.
- **effort**: 1 = paste one text into a description or memory; 2 = set up a routine or merge bots; 3 = needs a new tool.
- **reversibility**: 1.0 for text or routine changes; 0.8 for merging bots; 0.6 for removing a bot (never done automatically).

`value = impact × confidence × reversibility ÷ √effort`

- **Cap**: at most 3 scored proposals per bot in the main list (highest first); the rest go under "More".
- **Dedupe**: when several bots share one root cause (empty descriptions, the same job split across bots, one plan-limit outage), make ONE fleet item.
  It counts the affected bots for impact. Each bot section keeps its own evidence and points to it with `"see": "fleet-N"`.
- **Top 3**: the three highest values across bot and fleet proposals. Ties go to the bot with more use.
- **Information only** (`"info": true`): one-time events and keep/remove summaries. They get no score and no Apply box.
- **Nothing qualifies**: say so. A bot with no proposal shows "Nothing major to fix."

## 4. Extra checks (diagnostics.py)
Each check gives leads; keep a lead only after reading the actual messages.
| check | definition | usually |
|---|---|---|
| Unanswered requests / outage | real request with no reply for 6+ hours; overlapping windows across bots = fleet outage | real; an info item (the bot's own, or once for the fleet), never scored. Limit: messages sent while a bot could not run at all (e.g. after a plan limit) may be missing from its history, so silent outages can be undercounted |
| Skipped question cards | the app reports that the user moved on without tapping a choice | mostly noise (the user often answers in text instead); a finding only when one bot asks several of the same kind of unneeded question (default impact 1) |
| Promises without delivery | "I'll let you know…", then the user nudges ("hello?") | check by reading; often already delivered |
| Memory facts | facts with "currently/now" older than 3 days; near-duplicates | a finding only if later chats contradict the fact or it has clearly expired (default impact 1; 2 if the bot acted on the stale fact); duplicates rarely matter |
| Description vs. use | empty description, or a description that contradicts what the bot learned or what the user said later | real |
| Repeated work across days | similar requests on 3+ different days | routine candidate (score with effort 2) |
| Same request in several bots | similar text across bots (attachment notices and file paths are stripped first) | noisy (shared links, the same post pasted to several bots); confirm by topic |
| One bot doing another's job | a request closer to another bot's description than its own, counted only after that bot existed | noisy; keep only clear cases on 2+ days |
| Safety events | seen while reading: a secret or code printed in a chat or written to a log, another bot's internal settings shown, a risky action taken without asking | one fleet info item per kind of event, naming the bot and date; never quote or repeat the secret. Counts toward "Needs work" for that bot only if it did it itself |

Leads that are not corrections (skipped questions, stale memory, promises without delivery) can become scored findings
with the default impact above, confidence from how clear the evidence is, and effort 1.

## 5. Decision procedure (apply in this order; two runs on the same data should reach the same answer)
1. **Shared cause.** For each repeated group, read every incident and write the one rule that would have prevented it.
   It is a shared cause only if all of these hold:
   - the rule is **specific to this bot's job or the user's situation and names what to check or do** (a fact, a source,
     a format, a step), so that someone reading it knows exactly when it applies;
   - the same rule would have prevented **every** incident (or all but one, when there are 4+);
   - it doesn't conflict with what the data shows: a "confirm/ask more" rule is never a shared cause for a bot whose
     question cards the user often skips (the `skipped_questions` lead), because it would make that worse.

   Generic behaviour rules don't count, whatever the topic: "confirm unclear requests in one line", "read the request
   carefully", "double-check before answering", "be more accurate". They would fit any group, so they decide nothing.

   | counts (specific, names the check) | doesn't count (generic) |
   |---|---|
   | "Before booking, confirm hostel vs hotel and the price cap." | "Confirm unclear requests first." |
   | "For logos, find the official file before drawing one." | "Be more careful with images." |

   If no specific rule covers the incidents, there is no shared cause: drop the group (it can stay a lead).
   **Sub-part:** if a specific rule covers only some incidents, and those fall on 2+ separate occasions, keep that part
   as the group (recount it) and drop the rest.
2. **Merge across topics.** Merge two groups of the same bot into one only if the specific rule from step 1 is the same
   for both (the judge put one problem under two topics). Recount incidents and occasions and apply the strong rule
   from section 1 to the merged numbers. Never merge just because the topics sound related.
3. **Normal iteration, not a problem.** Drop a group (no proposal, no status effect) when any of these holds:
   - `one_session`: all incidents in one occasion while building or designing one new thing (steering a draft is the work);
   - the user changes their own mind about taste (they asked for X, saw it, now want Y) and the bot did what was asked;
   - the corrections are rounds of edits on one output, each asking for a new change rather than repeating an old one.
   A group is a problem when the user has to repeat the **same** instruction, or the bot breaks a rule it was given or saved.
4. **Fixes.** Resolve `fix_check` with the definitions in section 1: the latest relevant fix and the numbers decide,
   not your impression.
5. **Status.** Start from the suggested status. Change it only for these reasons, and name them in `why`:
   (a) step 1 found no shared cause for a strong group → it no longer counts; (b) step 3 dropped it → it no longer
   counts; (c) its latest relevant fix is fixed per section 1 → it no longer counts; (d) after a merge or sub-part in
   steps 1–2 a group became strong → `yellow`; (e) a safety event the bot caused itself → `yellow`; (f) the bot's whole
   job is done by another bot in use → `red`.
   Reasons combine: when a bot has several strong groups, each needs its own reason from (a)–(c) before the bot can
   become `green` (e.g. "(a) for format, (c) for tone"). If any strong group remains, the bot stays `yellow`. No other
   reason changes the status.
