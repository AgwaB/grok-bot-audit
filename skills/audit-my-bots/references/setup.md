# Setup checks (groups, hand-offs, plugins, safety rules, routines)

Beyond each bot, the audit looks at how the bots are set up. These items come only from what the saved chats show;
when the evidence isn't there, say nothing. They never change a bot's status. You add them to
`fleet` with a `kind` when the facts and the chats show the need; the report shows them in their own section
(`ui.setup`, `ui.setup_h`, `ui.setup_iss`: write those labels too). Every word is yours, in the user's language.

Use only the app paths named here (from the product docs). Never invent a menu, button or setting.

## Kinds
| kind | facts to start from (diag.json) | what to propose |
|---|---|---|
| `group` | `fleet.pasted_answers`: the user pasted one bot's answer into another bot within 3 days, on several days, and they share no group chat (`shared_groups` empty) | one group chat per project with those bots (`group`: `project`, `lead`, `order`, each member's `part`, `blocked`: `ask_user`) |
| `handoff_format` | `fleet.bot_to_bot` (messages per pair, median length, `same_headings`, `within_15_min_share`) and long `pasted_answers` | one fixed short hand-off format (`format`: goal, where, done when, waiting on). Not for a machine-made template (same headings) or one fan-out burst |
| `redundant_groups` | `fleet.same_member_groups`: two group chats with exactly the same bots | keep using one group for this work. Say which one was used last |
| `connector` | `browser_sites`: the bot used the browser on a site that has a plugin in the app, on 2+ days, and doesn't call that plugin (`plugin_used` false) | connect the plugin: steadier than clicking through the site, and the login stays off the shared computer |
| `safety_rules` | `memory.facts`: a fact that holds a safety boundary ("ask me before sending...") | keep the memory, and also add the rule as an Auto-review rule, so it holds even when memory doesn't come up |
| `routine_cost` | `routines`: `median_gap_min`, `runs_per_day_last7`, `max_runs_per_day`, `no_reply_or_same` (share of runs with no reply or the same reply as the run before) | when it runs far more often than its job needs: run less often, end quietly when nothing changed, and stop once the job is done |

## How the user does it (give these steps; you can't do them for the user)
- **Group chat:** one group per project. If the pasted hand-offs cover more than one project, propose one group for
  each (split the item). In the sidebar choose New chat (the + button), select two to six bots, and describe the
  outcome and who owns the next step. In the group, `@` hands a request to one bot. `copy` (`copy_kind` `group`) is
  the first message for the group, in this order: the project and its outcome; the lead bot, which starts each round
  and owns the next step; one line per bot with its part (`group.order`); and the blocked step: "if you are blocked or
  unsure, stop and ask me" (the user), never guess or work around it. Bot-to-group hand-offs are text only.
- **Hand-off format:** `copy` is the format, one short line per field in `format`: goal (what this step must
  achieve), where (paths, links or the file to use), done when (how the next bot knows it is finished), waiting on
  (what is still needed, or "nothing"). The user sends it to each bot named in the evidence as a message to remember,
  or puts it in the group's first message. Hand-offs then carry these lines instead of long or repeated text.
- **Rule review routine** (a correction finding's optional `review`: `{"cadence_days": 14, "copy": "..."}`): add it only
  when you confirmed that a fix about this problem came back (finalize drops it if `copy` is empty). It is offered next to
  the rule text, as its own option right after that finding's option. If picked, ask that bot in chat to set up the
  routine (say what and when). Low cadence (`review.cadence_days`, every two weeks, or monthly). Its text: look at the chats since the last review for corrections about
  this kind of mistake; if there is none, end without a message; if there is, send the user a short note with the
  correction and a suggested rule change, and change nothing until the user says so. That is the `review.copy` text.
- **Plugin:** open Connect apps in the sidebar and connect the plugin for that service, then tell the bot to use it
  instead of the browser. A plugin shown as disabled by a team admin can't be used: then nothing to do.
- **Auto-review rule:** open Settings (the account button at the bottom left of the sidebar, or Cmd+,), General tab,
  Auto-review rules. Some accounts don't show every row; if the user can't find it, say so. `copy` is the rule in
  one plain sentence.
- **Routine:** click the bot's name at the top of its chat, Details tab, Routines: open the routine and choose Edit
  (or ask that bot in chat to change its routine). `copy` (`copy_kind` `routine`) is the change to send, for example
  "Run every 2 hours instead of every 10 minutes. If nothing changed since the last run, end without a message. Stop
  this routine once the report is filed." Pausing is on the same page.
- **Two groups with the same bots:** say which group to keep using for this work; don't suggest deleting anything.

## Options (SKILL.md step 9)
Each setup item with a score is one option, labelled with its `short` line in the user's language, for example
"Set up a group chat for project P", "Give X and Y a short hand-off format", "Also add a rule-review routine to X", "Show me how to connect the Gmail plugin", "Add an Auto-review rule for X",
"Make X's routine run less often", "Show me how to tidy the two X groups". Never "Remove", "Delete" or "Merge".

## Weekly re-check routine (SKILL.md step 9)
Create it only if the user says yes. It runs without the user watching, so its instruction must make each run safe:
- Report only: run this skill through step 8 with a new work folder, send the chat summary and the files. No
  multi-select question and no changes inside the routine (approval requests expire after about 10 minutes); end
  the message by saying the user can reply to pick items.
- Incremental: follow the skill, including its checkpoint (`checkpoint.md`). Do not pass `plan --full`. Each run
  reads and labels only what is new; the report still covers the whole history. `commit` still runs after the
  checks pass, including when you then stay quiet, so the next Monday starts after this run.
- Quiet when nothing changed: pass the newest earlier `report/summary.json` under `/workspace/bot-audit-run/` to
  `make_report.py --previous`; if it prints `UNCHANGED`, end without sending anything. A chat with no new messages
  can still change the summary, because a bot can become idle as time passes; stay quiet only when it prints `UNCHANGED`.
- Safe to re-run: it only reads chats and writes a new folder, so a repeated or retried run does no harm. A checkpoint
  is saved only after the report checks pass. A failed run leaves the previous one, and the next run reads that part again.
Write the instruction in the user's language, with Monday 9:00 in the user's real time zone.
