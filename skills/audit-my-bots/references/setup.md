# Setup checks (groups, hand-offs, plugins, safety rules, routines)

Beyond each bot, the audit looks at how the bots are set up. These items come only from what the saved chats show;
when the evidence isn't there, say nothing. They never change a bot's status. `build_findings.py skeleton` drafts
them in `fleet` with a `kind`; the report shows them in their own section (`ui.setup`, `ui.setup_h`, `ui.setup_iss`:
write those labels too). The scripts set which items exist and their evidence; you write every word, in the user's
language, and you may delete an item that reading the chats doesn't confirm.

Use only the app paths named here (from the product docs). Never invent a menu, button or setting.

## Kinds
| kind | found when (diagnostics.py) | what to propose |
|---|---|---|
| `group` | the user pasted one bot's answer (the one it matches best) into another bot within 3 days, on 2+ days (`fleet.group_candidates`); bots already in a group chat together are skipped | one group chat per project with those bots (`group`: fill `project`, each member's `part`; keep `lead`, `order` and `blocked`) |
| `handoff_format` | 3+ bot-to-bot messages from one bot to another that are long (median 600+ characters) or mostly repeat the one before (200+ characters), or pasted hand-offs of 400+ characters (`fleet.handoff_format_candidates`) | one fixed short hand-off format (`format`: goal, where, done when, waiting on) |
| `redundant_groups` | two group chats with exactly the same bots (`fleet.redundant_groups`) | keep using one group for this work. Say which one was used last |
| `connector` | the bot used the browser on a site that has a plugin in the app, on 2+ days, and doesn't already call that plugin (`connector_candidates`) | connect the plugin: steadier than clicking through the site, and the login stays off the shared computer |
| `safety_rules` | a memory fact holds a safety boundary ("ask me before sending…"; `safety` cues, `cues.md`) (`memory_safety_rules`) | keep the memory, and also add the rule as an Auto-review rule, so it holds even when memory doesn't come up |
| `routine_cost` | a routine runs about every 15 minutes or more often, or 24+ times a day with most runs silent or the same as the run before (`routine_cost`) | run less often, end quietly when nothing changed, and stop once the job is done (an end condition) |

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
- **Rule review routine** (a correction finding's optional `review`, set by the skeleton when a fix candidate had an
  incident of that group after it, `came_back_candidate`): keep it only if you confirmed that a fix about this problem
  came back; then write `review.copy`, else delete `review` (finalize drops it if left empty). It is offered next to
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
- Quiet when nothing changed: pass the newest earlier `report/summary.json` under `/workspace/bot-audit-run/` to
  `make_report.py --previous`; if it prints `UNCHANGED`, end without sending anything.
- Safe to re-run: it only reads chats and writes a new folder, so a repeated or retried run does no harm.
Write the instruction in the user's language, with Monday 9:00 in the user's real time zone.
