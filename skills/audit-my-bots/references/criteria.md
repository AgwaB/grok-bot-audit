# Audit criteria

Every input comes from inside Grok Bot: each bot's own chat history (saved transcript pages), its profile name and description,
and the memory block the app shows the bot. No external APIs, no logins.
`diagnostics.py` applies the rules below and writes `diag.json`; `build_findings.py finalize` applies the scoring.

## 1. Definitions
- **Real request**: a message the user typed. App prompts, routine wake-ups, background results and messages from other bots don't count.
- **Correction**: judged with `rubric_correction.md` (labels.json).
- **Incident**: corrections on the same topic in the same bot within 60 minutes count once.
- **Repeated correction**: same bot and topic, 2 or more incidents on 2 or more different days, or 3 or more incidents.
  Before proposing anything, check that one written rule would have prevented every incident in the group (a shared cause).
  Groups without a shared cause (for example, normal back-and-forth edits on an image) are not proposals.
- **Strong repeated correction**: a repeated correction that also has 3+ incidents, or incidents in 5%+ of the bot's real requests.
  It needs at least one incident of medium or high confidence.
- **Fix candidates**: memory saves and "from now on…" messages in the same bot after the group's first incident
  (`fix_candidates_between`, `fix_candidates_after_last`). The scripts can't tell whether one is about the group's problem,
  so candidates change neither status nor impact. You confirm or drop them (`writing.md`).
- **Fixed**: a confirmed fix after the last incident, with no incident since. Fixed groups go under "Already improving" and
  produce no proposal. **Came back after a fix**: a confirmed fix between incidents; impact +1.
- **Unanswered request**: a real request with no bot reply for 6 hours or more (a lower bound, taken from the next timestamp).
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
`diagnostics.py` suggests a status from these rules; you set the final one. If you override it (for example, the only strong
group had no shared cause, or a fix was confirmed), write the reason in `why`.

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
| Skipped question cards | the app reports that the user moved on without tapping a choice | mostly noise (the user often answers in text instead); a finding only when one bot asks several of the same kind of unneeded question |
| Promises without delivery | "I'll let you know…", then the user nudges ("hello?") | check by reading; often already delivered |
| Memory facts | facts with "currently/now" older than 3 days; near-duplicates | a finding only if later chats contradict the fact or it has clearly expired; duplicates rarely matter |
| Description vs. use | empty description, or a description that contradicts what the bot learned or what the user said later | real |
| Repeated work across days | similar requests on 3+ different days | routine candidate (score with effort 2) |
| Same request in several bots | similar text across bots (attachment notices and file paths are stripped first) | noisy (shared links, the same post pasted to several bots); confirm by topic |
| One bot doing another's job | a request closer to another bot's description than its own, counted only after that bot existed | noisy; keep only clear cases on 2+ days |
