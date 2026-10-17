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
- **Strong repeated correction**: a repeated correction that also has 3+ incidents (and at least 1 incident per 100 real
  requests, so a very busy bot isn't flagged for a handful of slips), or incidents in 5%+ of the bot's real requests.
  It needs at least one incident of medium or high confidence.
- **Fix candidates**: memory saves, "from now on…" sentences the bot said **to the user** (not text inside a draft,
  quote or code it produced), and replies the judge marked as promising a lasting change. Listed once per bot
  (`fix_candidates`, with ids), in time order, from the topic's first incident in the whole history; each group's
  `fix_check` refers to them by id with `incidents_after` (this group's incidents after it) and `active_days_after` (days
  the user used the bot after it). Every candidate an incident came after is kept, however old (a fix that may have
  failed); of the rest, the 12 latest. A group with more saves than that has `fix_check_omitted` (how many, and their
  time span) in the draft. The scripts can't tell whether one is about the group's problem, so candidates change neither
  status nor impact until you confirm one (`writing.md`).
- **The latest relevant fix decides.** Among the candidates you confirm as about this problem, look only at the latest:
  - **Fixed** (improving): its `incidents_after` = 0 and `active_days_after` ≥ 2. Goes under "Already improving", no
    proposal. This holds even if an earlier fix failed before it.
  - **Too early to tell**: `incidents_after` = 0 but `active_days_after` < 2. Judged as if unfixed; the finding gets
    `"too_early": true` and says when the rule was saved.
  - **Came back after a fix**: an incident came after the latest fix (`incidents_after` ≥ 1); impact +1.
- **Unanswered request**: a real request with no bot reply for 6 hours or more (a lower bound, taken from the next timestamp).
  A request that is the last message in the data is not counted: the bot may not have had time to answer.
  If several bots go quiet in the same window, it is a fleet outage (usually a plan limit), not a problem with one bot.
- **Age** = now minus the first message. **Idle** = now minus the last use: a real request, a routine run or a message
  from another bot (a bot that works by routine or for other bots is in use even if the user never types to it). **Share** = the bot's real requests ÷ all real requests.
- **Rhythm** = the typical gap between the days the user typed to it (needs 2+ such days). **Within its rhythm**: idle ≤ 1.5 × that gap + 1 day.
- **Stopped habit**: used on 5+ days with a rhythm of a week or less, and now idle ≥ max(14 days, 4 × that rhythm).
- **Too new to judge**: age under 14 days, and the bot started in the later half of the history covered (a bot added
  recently to an older fleet). It gets no clean-up verdict; its other checks still run.

## 2. Status (first match wins)
| status | rule |
|---|---|
| Clean up (`red`) | Age ≥ 3 days, idle ≥ max(3 days, half its age), share < 5% or a stopped habit (any share), not within its rhythm, and not too new to judge. *Or* its whole job is already done by another bot that is in use, and its history shows no use of its own. |
| Needs work (`yellow`) | A strong repeated correction with a shared cause that is not fixed; *or* unanswered requests caused by the bot itself (not a fleet outage); *or* a safety problem visible in its chats (for example, it printed another bot's internal settings). |
| Fine (`green`) | Everything else. An empty description, a weak repeated correction, a stated preference or another lead (section 4) can still produce a proposal, but it doesn't change the status. A one-off correction never does: no rules from one mistake. |

Why relative thresholds: a fleet may have only a few days of history, so fixed counts ("5 corrections a week") mean nothing yet.
Share, half-of-age idle and per-request rates scale with however much history exists. A bot younger than 3 days can't be "Clean up" by the idle rule,
nor can a bot used on a slow but steady rhythm (monthly), one that is too new to judge, or one whose routine still runs.
`diagnostics.py` suggests a status from these rules; you set the final one with the procedure in section 5.

## 3. Proposal scoring
Every proposal carries `score = {impact, confidence, effort, reversibility, basis}`. `basis` is an internal note (it goes
to `scores.md` only and is never shown in the report), so it needs no translation:
- **impact** (1–3): 3 = 4+ incidents, repeated work on 5+ days, or 3+ bots affected; 2 = 2–3 incidents, 3–4 days or 2 bots; 1 = less.
  Add 1 (max 3) if the problem came back after a fix you confirmed.
- **confidence**: `high` 1.0 / `medium` 0.7 / `low` 0.4, from the rubric confidence of the incidents and whether the evidence is a direct quote.
- **effort**: 1 = send one text for a bot to remember, or change one setting; 2 = set up a routine, a group chat, or merge bots; 3 = needs a new tool.
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
| Description vs. use | no saved job description, or one that contradicts what the bot learned or what the user said later | real; the fix is text the user sends that bot to remember (personal bots may have no description field) |
| Repeated work across days | similar requests on 3+ different days | routine candidate (score with effort 2) |
| Same request in several bots | similar text across bots (attachment notices and file paths are stripped first) | noisy (shared links, the same post pasted to several bots); confirm by topic |
| One bot doing another's job | a request closer to another bot's description than its own, counted only after that bot existed | noisy; keep only clear cases on 2+ days |
| Safety events | seen while reading: a secret or code printed in a chat or written to a log, another bot's internal settings shown, a risky action taken without asking | one fleet info item per kind of event, naming the bot and date; never quote or repeat the secret. Counts toward "Needs work" for that bot only if it did it itself |
| Secrets the user typed | the user pasted a password, key or login code into a chat themselves | not a bot's safety event and no status effect. A lasting secret (password, key, token) gets one line in the safety info item ("you shared a password in X's chat on DATE; consider changing it"); a one-time code that has expired gets nothing. Never quote it |
| Bots not in the list | an event about a bot that isn't in `bots.json` (removed, renamed, or someone else's), seen only in another bot's chat | the fleet safety info item, named as written in that chat and said to be no longer in the list; never a row and no status effect on any listed bot. Don't open files it may have written to check |

Leads that are not corrections (skipped questions, stale memory, promises without delivery) can become scored findings
with the default impact above, confidence from how clear the evidence is, and effort 1.
Stale memory and promises are also found without words (a memory fact with a date that has passed; a very short
"…?" after an hour of silence), so chats in any language get these leads.
Setup checks (group chats, plugins instead of the browser, safety rules kept only in memory, routines that run very
often) are in `setup.md`. They never change a bot's status.

## 5. Decision procedure (apply in this order; two runs on the same data should reach the same answer)
1. **Shared cause.** For each repeated group, read every incident and write the one rule that would have prevented it.
   It is a shared cause only if all of these hold:
   - the rule is **specific to this bot's job or the user's situation and names what to check or do** (a fact, a source,
     a format, a step, or the kinds of detail to confirm), so that someone reading it knows exactly when it applies;
   - the same rule would have prevented **every** incident (or all but one, when there are 4+);
   - it doesn't conflict with what the data shows: a "confirm/ask more" rule is never a shared cause for a bot whose
     question cards the user often skips (the group's `confirm_conflict` is true), because it would make that worse.

   **The paste test decides specific vs generic.** Could the rule be pasted into any other bot unchanged and still make
   sense? Then it is generic and decides nothing: "confirm unclear requests in one line", "ask if ambiguous", "read the
   request carefully", "double-check before answering", "be more accurate". If the rule names the concrete fields or
   kinds of detail in this bot's domain (it would be nonsense in an unrelated bot), it is specific, even when each
   incident got a different one of those details wrong. A "confirm first" rule counts as soon as it lists what to
   confirm. Don't drop a group because a generic rule would also cover it; look for the specific one first.

   **Same kind of action.** The incidents must come from the same kind of action in this bot's job (each time it
   booked something, each time it drafted a post), and the details that went wrong must be details of that action.
   Misreads spread over unrelated actions (a reminder set for the wrong hour one day, a letter to the wrong office the
   next, a sheet sorted by the wrong column another day) are one-offs, even if a rule could list them all: a rule that
   just strings together each incident's detail ("confirm the hour, the office and the column") is a list of past
   mistakes, not a shared cause.
   Read each incident's `request` (`judge_inputs.py --show <n>`) to see which action led to it.

   | counts (specific: names the fields or the check) | doesn't count (generic: fits any bot) |
   |---|---|
   | "Before ordering prints, confirm paper size, number of copies and delivery date." | "Confirm unclear requests first." |
   | "For plant questions, ask for the light level and pot size before advising." | "Ask if the request is ambiguous." |
   | "Quote prices from the supplier's current list, never from memory." | "Be more accurate." |

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
