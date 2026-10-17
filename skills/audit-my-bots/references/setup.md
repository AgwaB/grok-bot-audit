# Setup checks (groups, plugins, safety rules, routines)

Beyond each bot, the audit looks at how the bots are set up. These items come only from what the saved chats show;
when the evidence isn't there, say nothing. They never change a bot's status. `build_findings.py skeleton` drafts
them in `fleet` with a `kind`; the report shows them in their own section (`ui.setup`, `ui.setup_h`, `ui.setup_iss`:
write those labels too). The scripts set which items exist and their evidence; you write every word, in the user's
language, and you may delete an item that reading the chats doesn't confirm.

Use only the app paths named here (from the product docs). Never invent a menu, button or setting.

## Kinds
| kind | found when (diagnostics.py) | what to propose |
|---|---|---|
| `group` | the user pasted one bot's answer into another bot within 3 days, on 2+ days (`fleet.group_candidates`); bots already in a group chat together are skipped | a group chat with those bots. `group.lead` is the bot whose answers start the chain; say what each bot does and who owns the next step |
| `redundant_groups` | two group chats with exactly the same bots (`fleet.redundant_groups`) | keep using one group for this work. Say which one was used last |
| `connector` | the bot used the browser on a site that has a plugin in the app, on 2+ days, and doesn't already call that plugin (`connector_candidates`) | connect the plugin: steadier than clicking through the site, and the login stays off the shared computer |
| `safety_rules` | a memory fact holds a safety boundary ("ask me before sending…"; `safety` cues, `cues.md`) (`memory_safety_rules`) | keep the memory, and also add the rule as an Auto-review rule, so it holds even when memory doesn't come up |
| `routine_cost` | a routine runs about every 15 minutes or more often, or 24+ times a day with most runs silent or the same as the run before (`routine_cost`) | run less often, end quietly when nothing changed, and stop once the job is done (an end condition) |

## How the user does it (give these steps; you can't do them for the user)
- **Group chat:** in the sidebar choose New chat (the + button), select two to six bots, and describe the outcome and
  who owns the next step. In the group, `@` hands a request to one bot. `copy` (`copy_kind` `group`) is the first
  message for the group: one line per bot with its part, and who starts. Bot-to-group hand-offs are text only.
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
"Set up a group chat for X and Y", "Show me how to connect the Gmail plugin", "Add an Auto-review rule for X",
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
