# Audit criteria

Every input comes from inside Grok Bot: each bot's own chat history (saved transcript pages), its profile name and description,
and the memory block the app shows the bot. No external APIs, no logins.
`diagnostics.py` writes facts to `diag.json`; you judge them; `build_findings.py finalize` checks and scores.

## 1. Facts (diag.json) and what they mean
- **Real request**: a message the user typed. App prompts, routine wake-ups, background results and messages from other bots don't count.
- **Message id** (`ref`): `<bot prefix>:<i>`, the event's place in that bot's timeline. Every finding cites one or more.
- **Correction**: judged by you with `rubric_correction.md` (labels.json).
- **Incident**: corrections on the same topic in the same bot within 60 minutes count once (`incidents`).
- **Occasion**: incidents more than 6 hours apart are separate occasions (`correction_topics.*.occasions`). A late-night
  session that crosses midnight is one occasion, not two days.
- **Repeated correction**: same bot and topic, 2 or more incidents on 2 or more separate occasions. Incidents that all
  fall in one occasion are steering of one task, never repeated on their own. Apply section 5 before proposing anything.
- **Fixes after** (`fixes_after`): memory saves and replies you marked as promising a lasting change, from the topic's
  first incident on, each with `incidents_after` (this topic's incidents after it) and `active_days_after` (days of use
  after it); texts in the bot's `fixes`. Whether one is about the problem is yours to decide. The latest relevant one decides:
  - **Fixed** (improving): `incidents_after` = 0 and `active_days_after` >= 2. Goes under "Already improving", no proposal.
  - **Too early to tell**: `incidents_after` = 0 but `active_days_after` < 2: judged as if unfixed, `"too_early": true`.
  - **Came back after a fix**: `incidents_after` >= 1; impact +1.
- **Waits** (`waits`): a real request with no bot reply for 6 hours or more (a lower bound, up to the next reply). The
  last messages in the data (`unanswered_at_end`) may simply not have been answered yet. Waits that overlap with another
  bot's (`overlaps_other_bot`, `fleet.overlapping_waits`) point to a fleet outage (usually a plan limit), not one bot.
- **Usage**: `age_days` = now minus the first message; `idle_days` = now minus the last use (a real request, a routine
  run or a message from another bot); `idle_typed_days` counts typed requests only; `share` = the bot's real requests
  / all real requests. `active_days` count working sessions (messages under 6 hours apart are one session, on the day it
  started). `typical_gap_days` and `longest_gap_days` are the gaps between those days: the bot's own rhythm.
- **Exact repeats**: `resends` (the same text again within 30 minutes: one request), `repeated_texts` (the same text on
  2+ days), `fleet.same_text_in_bots`, and `fleet.group_messages` (a group turn is mirrored into every member's chat:
  one message, not one per bot). Requests that repeat in different words are for you to find in the digest.
- **Keep** (`user_keep`): the latest message you labelled `keep` (the user said to keep the bot or that it is paused on purpose).

## 2. Status (you decide; first match wins)
| status | when |
|---|---|
| Clean up (`red`) | The user has stopped using it: it has been idle for long compared with its age and its own rhythm, no routine or other bot still uses it, and nothing in its chats says it is still wanted (a keep statement, seasonal or periodic use, a bot set up recently). *Or* its whole job is already done by another bot that is in use, and its history shows no use of its own. |
| Needs work (`yellow`) | A repeated correction with a shared cause that is not fixed (section 5); *or* unanswered requests caused by the bot itself (not a fleet outage); *or* a safety problem visible in its chats (for example, it printed another bot's internal settings). |
| Fine (`green`) | Everything else. An empty description, a stated preference or another lead (section 4) can still produce a proposal, but it doesn't change the status. A one-off correction never does: no rules from one mistake. |

Judge use against the bot's own history, not against a fixed count: a small share is not a reason on its own (a bot used
once a month for one job is in use), and a fleet may have only a few days of history. Read the last messages before
calling a bot Clean up: a user who parks a bot on purpose usually says so there. A bot with `user_keep` is never Clean
up and gets no clean-up item (finalize refuses it). Name the reason for every status in `why`.

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

## 4. What to look for (facts in diag.json, the digest, and the chats)
Keep an item only after reading the actual messages; cite them by `ref`.
| check | facts to start from | usually |
|---|---|---|
| Unanswered requests / outage | `waits`, `unanswered_runs` (3+ messages in a row with no reply), `fleet.overlapping_waits` | real when the bot itself went silent: an info item, never scored. One outage across bots: one fleet info item. Messages sent while a bot could not run may be missing, so silent outages can be undercounted |
| Skipped question cards | `skipped_questions` (the app reports the user moved on without tapping a choice) | mostly noise; a finding only when one bot asks several of the same kind of unneeded question (impact 1) |
| Promises without delivery | `promises` (replies you marked `later`, with the user's next message) | check by reading; often already delivered |
| Chat language | `scripts` (writing systems of the user's messages, replies in another script, days) | low priority: a finding (impact 1) only if the user minded it |
| Memory facts | `memory.facts` with learned dates, `past_dates`, `exact_duplicates`, and `newer_labelled` (what you labelled in that chat after the oldest fact) | a finding only if later chats contradict the fact or it has clearly expired (impact 1; 2 if the bot acted on it) |
| Description vs. use | `description`, `description_empty`, how the bot is used | real; the fix is text the user sends that bot to remember |
| Repeated work across days | the digest (every message with its date), `repeated_texts` | the same request by hand on 3+ days: a routine candidate (effort 2). The same follow-up after the bot's answers ("test it too"): a standing rule (`kind` `follow_up`, effort 1). Not a request: thanks, approvals, keep statements, resends, group turns, corrections (they are in the correction topics) |
| Same request in several bots / one bot doing another's job | the digest, `fleet.same_text_in_bots`, `fleet.pasted_answers` | confirm by topic; a shared link or one post pasted around is not overlap |
| Safety events | seen while reading: a secret or code printed in a chat or written to a log, another bot's internal settings shown, a risky action taken without asking | one fleet info item per kind of event, naming the bot and date; never quote or repeat the secret. Counts toward "Needs work" for that bot only if it did it itself |
| Secrets the user typed | the user pasted a password, key or login code into a chat themselves | not a bot's safety event and no status effect. A lasting secret gets one line in the safety info item ("consider changing it"); an expired one-time code gets nothing. Never quote it |
| Bots not in the list | an event about a bot that isn't in `bots.json`, seen only in another bot's chat | the fleet safety info item, named as written in that chat; never a row and no status effect. Don't open files it may have written |

Leads that are not corrections can become scored findings with the default impact above, confidence from how clear
the evidence is, and effort 1. Setup checks (group chats, plugins instead of the browser, safety rules kept only in
memory, routines that run very often) are in `setup.md`. They never change a bot's status.

## 5. Decision procedure (apply in this order; two runs on the same data should reach the same answer)
1. **Shared cause.** For each repeated group, read every incident and write the one rule that would have prevented it.
   It is a shared cause only if all of these hold:
   - the rule is **specific to this bot's job or the user's situation and names what to check or do** (a fact, a source,
     a format, a step, or the kinds of detail to confirm), so that someone reading it knows exactly when it applies;
   - the same rule would have prevented **every** incident (or all but one, when there are 4+);
   - it doesn't conflict with what the data shows: a "confirm/ask more" rule is never a shared cause for a bot whose
     question cards the user often skips (`skipped_questions`), because it would make that worse.

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
   for both (the judge put one problem under two topics). Recount incidents and occasions. Never merge just because the topics sound related.
3. **Normal iteration, not a problem.** Drop a group (no proposal, no status effect) when any of these holds:
   - all incidents in one occasion while building or designing one new thing (steering a draft is the work);
   - the user changes their own mind about taste (they asked for X, saw it, now want Y) and the bot did what was asked;
   - the corrections are rounds of edits on one output, each asking for a new change rather than repeating an old one.
   A group is a problem when the user has to repeat the **same** instruction, or the bot breaks a rule it was given or saved.
4. **Fixes.** Use `fixes_after` with the definitions in section 1: the latest relevant fix and the numbers decide,
   not your impression.
5. **Status.** Set it with section 2 after steps 1-4: a repeated group still standing (shared cause, not normal
   iteration, not fixed) makes the bot `yellow`; name the reason in `why`. A bot with `user_keep` is never `red`.
