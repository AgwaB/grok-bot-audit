---
name: audit-my-bots
description: Audit the user's Grok Bots from their own chat history and produce a plain-language report (HTML + PDF) with a status per bot, evidence-backed fixes and keep/clean-up suggestions. Use whenever the user asks to audit, check, check up on, review, clean up or tidy their bots, asks which bots they don't need or could merge, which bots they actually use, why a bot keeps getting things wrong, or how to use their bots better (e.g. "audit my bots", "check my bots", "review my bots", "which bots do I not need?"). Run it yourself in this chat; it needs ReadTranscript.
---

# Audit my bots

**Do this yourself, in this chat.**
- Make every ReadTranscript call yourself. Never hand the fetching to a background helper: helpers can't read other bots'
  chats.
- Never read `store.db`, `search-index.db` or any other app database or index file as a substitute for ReadTranscript.
- If ReadTranscript isn't available to you, stop and tell the user that the audit can't run in this
  bot, and that they can ask a bot that has it. Don't try another way.
- A background helper may be used, if at all, only for the later file-only steps (5 to 7), never for fetching or judging.

The bundled scripts do the counting; you do the judging and the writing.

**Shape is fixed, words are yours.** The scripts own the structure: sections, table, order, scores, quote checks and
the HTML/PDF layout. You write everything the user reads (chat messages and the whole report: text, labels, dates,
translations) in the language the user writes to you in; English if unclear. Quotes keep the original words.

What the user gets: a short chat summary (status table + top 3), an HTML and a PDF report, and an offer to apply
the proposals they pick. Nothing changes without their pick.

## Safety rules (always)
- Read-only on bot data. Only read `profile.json` (name and description only) and the transcripts you fetch with ReadTranscript.
- Never open, print or copy: kv metadata, `blobEncryptionKey`, `box-secrets.json`, `host-secrets.json`, `chrome-cookie-seed.json`,
  `gateway.json`, `store.db`, `search-index.db` or other app databases, `settings.json`, browser profiles, or login form values. If a transcript contains secrets, never quote them.
- Never invent quotes or numbers. Quotes are copied word for word; `build_findings.py finalize` rejects quotes it can't find.
- Skip yourself (the auditing bot).
- In anything the user sees, use plain words. No token or cost estimates, no tool counts, no precision numbers, no internal terms
  (subagent, executor, tool, transcript, model, JSON).
- You can't delete or merge bots, and there's no tool for it. Only the user can delete a bot (right-click it in the sidebar,
  then Delete). Before they do, they should check that bot's routines in the app.
- No rules from one-off mistakes. If nothing qualifies, say "Nothing major to fix."

## 0. Set up
`$SKILL` is the folder that holds this `SKILL.md`; `scripts/` and `references/` sit next to it.
If you don't know that folder, the fallback below finds the newest installed copy.
```bash
SKILL="<folder that holds this SKILL.md>"
[ -f "$SKILL/scripts/sessions.py" ] || SKILL="$(dirname "$(dirname "$(find /home/box/agent-data/plugins ~/.cursor/plugins \
  -path '*/audit-my-bots/scripts/sessions.py' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)")")"
W="/workspace/bot-audit-run/$(date +%F)"; mkdir -p "$W"; echo "$SKILL" "$W"
```
Marketplace installs are cached under `/home/box/agent-data/plugins/cache/<marketplace>/bot-audit/<commit>/`;
local copies live under `~/.cursor/plugins/local/bot-audit/`.
Needs `python3`. The PDF needs Chrome or Chromium. The report uses system fonts; nothing else to install.

For testing only: if `$AUDIT_REPLAY_DIR` is set, run `python3 "$SKILL/scripts/sessions.py" replay --work "$W"` instead of
steps 1 and 2 (it copies pre-saved pages; see the repo's `tests/EVAL.md`), then continue with `parse`.

## 1. List the bots
```bash
python3 "$SKILL/scripts/sessions.py" list-bots --work "$W" --self "<your own agent id>"
```
Your own id is the folder name in your agent directory (`/home/box/agent-data/agents/<your id>`). If you're not sure, check
`$W/bots.json` and remove your own entry by name.

## 2. Fetch each bot's history yourself
For every bot in `bots.json`, call **ReadTranscript** with `agent_id=<id>`, `limit=200` and `write_to_file=true`
(it may sit under the `cursor` namespace through CallDynamicTool). It returns the newest page and a file path. Save pages:
```bash
python3 "$SKILL/scripts/sessions.py" save-page --work "$W" "<id>=<file path>" ["<id2>=<file path>" ...]
```
It prints `start=A end=B total=N` per page. Call ReadTranscript again with `before=A`, and repeat until a page prints
`start=0`. One bot's pages must come one after another (`before` is only known from the last page), and a big bot can
take dozens of pages, so:
- If you can make several calls at once, fetch different bots side by side, then save that round's pages in one
  `save-page` call.
- Every few bots, send the user a one-line progress note (for example "Read 3 of 7 bots…"), so a long fetch doesn't
  look stuck.

Then:
```bash
python3 "$SKILL/scripts/sessions.py" parse --work "$W"
```
If it warns that pages don't reach the start or the end, fetch the missing pages before going on.

## 3. Find correction candidates
```bash
python3 "$SKILL/scripts/judge_inputs.py" --work "$W" --all      # chats not mostly in English (the default choice)
python3 "$SKILL/scripts/judge_inputs.py" --work "$W"            # chats mostly in English: built-in cue filter
```
The built-in cue phrases are a small English list. If most user messages aren't in English, use `--all`: you judge every
reply that follows a bot message, in any language. Only if `--all` gives more items than you can judge carefully (several
hundred), write `$W/cues.json` from words in the actual chats and run without `--all`; `$SKILL/references/cues.md` says
how. Attachment notices and file paths are already stripped from user messages.

## 4. Judge every candidate
Read `$SKILL/references/rubric_correction.md`. Judge each item in `$W/judge_inputs.json` strictly by its steps, then write
`$W/labels.json` as `{"<key>": {"label", "type", "topic", "confidence", "evidence"}}` with one entry for every key.
Long messages are cut to their start and end. If that isn't enough to judge (for example, whether the bot admitted a
mistake), print the full messages: `python3 "$SKILL/scripts/judge_inputs.py" --work "$W" --show <key> [<key> ...]`.

## 5. Run the checks
```bash
python3 "$SKILL/scripts/diagnostics.py" --work "$W"
python3 "$SKILL/scripts/build_findings.py" skeleton --work "$W" --lang "<BCP 47 code of the user's language>"
```

## 6. Write the findings
Read `$SKILL/references/criteria.md` and `findings-schema.md`, then edit `$W/findings_draft.json`:
- **Groups:** for each repeated-correction group, read the actual messages. Keep it only if one rule would have prevented every incident. If the bot already fixed it (a matching memory save or "from now on…" with no recurrence), move it to `improving`.
- **Words:** replace the placeholder English everywhere (titles, fixes, `copy`, `issue`, `why`, `ui` labels, `date_label`)
  with your own plain wording in the user's language. `copy` is the exact text to paste into a description, a memory or a routine, and it must not contradict what the bot already learned.
- **Quotes:** keep evidence word for word in `quote.orig`. Add `translation` when the chat's language differs from the report's.
  A memory fact or a bot description may be quoted as evidence: set `"source": "memory"` or `"description"` on that
  evidence line. Never quote file paths or attachment notices; finalize rejects them.
- **Leads:** go through `leads`, which includes stale memory facts, promises, the same request in several bots and other bots' jobs. Add a finding only for what you confirm by reading. Drop noise.
- **Skipped questions:** `leads.skipped_questions` lists choice questions a bot asked that the user moved past without
  answering. One or two mean nothing; drop them. If one bot has several of the same kind (for example, it keeps asking
  which next step to take, or for permission it didn't need), propose a rule such as "go ahead with the recommended
  option and say what you did" for that bot.
- **Shared causes:** merge cross-bot root causes into one fleet item, and point to it from each bot with `"see": "fleet-N"`.
  When the fix needs different text per bot (for example, a description for each), make `copy` a list of
  `{"bot": "<name>", "text": "..."}`.
- **Status:** set `issue` (2–6 words) and `why` for every bot. If you change a status, say why in `why`.
- **Review flags:** remove `needs_review`. Then:
```bash
python3 "$SKILL/scripts/build_findings.py" finalize --work "$W" --strict
```
Fix every ERROR it reports (usually a quote that isn't word for word) and run it again.

## 7. Make the report
```bash
python3 "$SKILL/scripts/make_report.py" "$W/findings.json" --outdir "$W/report"
```
Open the HTML or a PDF page once to check it looks right.

## 8. Tell the user
Send one short message: one sentence ("Checked N bots. X need work, Y should be cleaned up."), the status table
(bot, status, current issue) and the top 3. Attach the PDF and the HTML. Details stay in the files, not in chat.

## 9. Offer to apply
Ask one multi-select question listing the proposals by short title, plus "None for now".
Never label an option "Remove X", "Delete X" or "Merge X": you can't do those. For a clean-up candidate, use an option like
"Show me how to clean up X". Apply **only** what the user picks:
- **Memory or description text for another bot:** give the exact text and say where it goes (that bot's settings, or a message to that bot). Use a tool that changes another bot only if you have one and the user picked that item.
- **Your own memory:** save it.
- **Routines:** create one only if the user picked it. Say what it will do and when.
- **"Show me how to clean up X":** first ask the user to open X in the app and check whether any routine uses it; if one does,
  move or pause that routine first. Then explain the steps: to delete X, right-click X in the sidebar and choose Delete
  (deleting removes its profile, chat and routines; Hide from sidebar keeps them). To merge, give the text to paste into the
  bot that takes over X's job, then delete X the same way. You never delete or merge anything yourself.

Afterwards, offer once to re-run this audit weekly as a routine. Create it only if the user says yes.
