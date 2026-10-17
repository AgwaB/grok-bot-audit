---
name: audit-my-bots
description: Audit the user's Grok Bots from their own chat history and produce a plain-language report (HTML + PDF) with a status per bot, evidence-backed fixes and keep/clean-up suggestions. Use whenever the user asks to audit, check, check up on, review, clean up or tidy their bots, asks which bots they don't need or could merge, which bots they actually use, why a bot keeps getting things wrong, or how to use their bots better (e.g. "audit my bots", "check my bots", "review my bots", "which bots do I not need?"). Run it yourself in this chat; it needs ReadTranscript.
---

# Audit my bots

**Do this yourself, in this chat.**
- Make every ReadTranscript call yourself. Never hand the fetching to a background helper: helpers can't read other bots'
  chats.
- Never read `store.db`, `search-index.db` or any other app database or index file as a substitute for ReadTranscript.
- If ReadTranscript isn't available to you, stop and tell the user (in their language) that the audit can't run in this
  bot, and that they can ask a bot that has it. Don't try another way.
- A background helper may be used, if at all, only for the later file-only steps (5 to 7), never for fetching or judging.

The bundled scripts do the counting; you do the judging and the writing.

**Language.** Write every chat message (progress, summary, questions) and the whole report in the language the user
writes to you in. If that's unclear, use English. Quotes always keep the original words.

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
Report language: the user's language as a BCP 47 code (`en`, `es`, `ja`, `pt-BR`, ...); `en` when unclear. Call it `$LANG_CODE`.

## 1. List the bots
```bash
python3 "$SKILL/scripts/sessions.py" list-bots --work "$W" --self "<your own agent id>"
```
Your own id is the folder name in your agent directory (`/home/box/agent-data/agents/<your id>`). If you're not sure, check
`$W/bots.json` and remove your own entry by name.

## 2. Fetch each bot's history yourself
For every bot in `bots.json`, call **ReadTranscript** with `agent_id=<id>`, `limit=200` and `write_to_file=true`
(it may sit under the `cursor` namespace through CallDynamicTool). It returns the newest page and a file path. Save each page:
```bash
python3 "$SKILL/scripts/sessions.py" save-page "<file path from ReadTranscript>" --work "$W" --bot "<id>"
```
It prints `start=A end=B total=N`. Call ReadTranscript again with `before=A`, and repeat until a page prints `start=0`.
Then:
```bash
python3 "$SKILL/scripts/sessions.py" parse --work "$W"
```
If it warns that pages don't reach the start or the end, fetch the missing pages before going on.

## 3. Find correction candidates
If any bot chats in a language other than English, first write `$W/cues.json` for those languages
(see `$SKILL/references/cues.md`). Then:
```bash
python3 "$SKILL/scripts/judge_inputs.py" --work "$W"
```

## 4. Judge every candidate
Read `$SKILL/references/rubric_correction.md`. Judge each item in `$W/judge_inputs.json` strictly by its steps, then write
`$W/labels.json` as `{"<key>": {"label", "type", "topic", "confidence", "evidence"}}` with one entry for every key.

## 5. Run the checks
```bash
python3 "$SKILL/scripts/diagnostics.py" --work "$W"
python3 "$SKILL/scripts/build_findings.py" skeleton --work "$W" --lang "$LANG_CODE"
```

## 6. Write the findings
Read `$SKILL/references/criteria.md` and `findings-schema.md`, then edit `$W/findings_draft.json`:
- **Groups:** for each repeated-correction group, read the actual messages. Keep it only if one rule would have prevented every incident. If the bot already fixed it (a matching memory save or "from now on…" with no recurrence), move it to `improving`.
- **Language:** write every text field in the report language. For a non-English report, also translate every value in `ui`
  (keep the `{placeholders}`), then delete `"translate": true`.
- **Text:** rewrite each title, fix and `copy` in plain words. `copy` is the exact text to paste into a description, a memory or a routine, and it must not contradict what the bot already learned.
- **Quotes:** keep evidence word for word in `quote.orig`, in the chat's own language. Add `translation` (into the report
  language) only when the chat language differs from it.
- **Leads:** go through `leads`, which includes stale memory facts, promises, the same request in several bots and other bots' jobs. Add a finding only for what you confirm by reading. Drop noise.
- **Shared causes:** merge cross-bot root causes into one fleet item, and point to it from each bot with `"see": "fleet-N"`.
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
Send one short message in the user's language: one sentence ("Checked N bots. X need work, Y should be cleaned up."), the status table
(bot, status, current issue) and the top 3. Attach the PDF and the HTML. Details stay in the files, not in chat.

## 9. Offer to apply
Ask one multi-select question (in the user's language) listing the proposals by short title, plus "None for now".
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
