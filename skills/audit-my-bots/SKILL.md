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
- Read-only on bot data. From the app, read only `profile.json` (name and description only) and the transcripts you fetch
  with ReadTranscript. Files in the work folder `$W` (pages, timelines, `diag.json`…) are yours to read.
- Never open, print or copy: kv metadata, `blobEncryptionKey`, `box-secrets.json`, `host-secrets.json`, `chrome-cookie-seed.json`,
  `gateway.json`, `store.db`, `search-index.db` or other app databases, `settings.json`, browser profiles, or login form values.
- Never quote secrets (passwords, codes, keys, tokens) anywhere: not in the report, the chat, or `labels.json` evidence.
- Never invent quotes or numbers. Quotes are copied word for word; `build_findings.py finalize` rejects quotes it can't find.
- Skip yourself (the auditing bot).
- In anything the user sees, use plain words. No token or cost estimates, no tool counts, no precision numbers, no internal terms
  (subagent, executor, tool, transcript, model, JSON).
- You can't delete or merge bots, and there's no tool for it. Only the user can delete a bot (right-click it in the sidebar,
  then Delete). Before they do, they should check that bot's routines in the app.
- No rules from one-off mistakes. If nothing qualifies, say "Nothing major to fix."

## 0. Set up
`$SKILL` is the folder that holds this `SKILL.md`. If you were given `SKILL` or `W`, keep them. Shell variables don't
survive between separate commands, so write them to `$W/env.sh` once and start every later command with
`source <the real path of $W>/env.sh &&`.
```bash
SKILL="${SKILL:-<folder that holds this SKILL.md>}"
[ -f "$SKILL/scripts/sessions.py" ] || SKILL="$(dirname "$(dirname "$(find /home/box/agent-data/plugins ~/.cursor/plugins \
  -path '*/audit-my-bots/scripts/sessions.py' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)")")"
W="${W:-/workspace/bot-audit-run/$(date +%F)}"; mkdir -p "$W"
printf 'SKILL=%q\nW=%q\nAUDIT_REPLAY_DIR=%q\n' "$SKILL" "$W" "${AUDIT_REPLAY_DIR:-}" > "$W/env.sh"; echo "$W/env.sh"
```
Needs `python3`. The PDF needs Chrome or Chromium. The report uses system fonts; nothing else to install.

## 1. List the bots
```bash
python3 "$SKILL/scripts/sessions.py" list-bots --work "$W" --self "<your own agent id>"
```
Your own id is the folder name of your agent directory (`/home/box/agent-data/agents/<your id>`). If you have none (for
example, you run as a helper or a test), leave out `--self` and remove your own entry from `$W/bots.json` by name if it's there.

**Testing only:** if `$AUDIT_REPLAY_DIR` is set, don't list or fetch. Run
`python3 "$SKILL/scripts/sessions.py" replay --work "$W"` (it copies saved pages; every listed bot is audited) and go
straight to `parse` at the end of step 2.

## 2. Fetch each bot's history yourself
For every bot in `bots.json`, call **ReadTranscript** with `agent_id=<id>`, `limit=200` and `write_to_file=true`
(it may sit under the `cursor` namespace through CallDynamicTool). It returns the newest page and a file path. Save pages:
```bash
python3 "$SKILL/scripts/sessions.py" save-page --work "$W" "<id>=<file path>" ["<id2>=<file path>" ...]
```
It prints `start=A end=B total=N` per page. Call ReadTranscript again with `before=A`, and repeat until a page prints
`start=0`. One bot's pages come one after another (`before` is only known from the last page), and a big bot can take
dozens of pages, so fetch different bots side by side if you can make several calls at once, save each round's pages in
one `save-page` call, and send the user a one-line progress note every few bots. Then:
```bash
python3 "$SKILL/scripts/sessions.py" parse --work "$W"
```
If it warns that pages don't reach the start or the end, fetch the missing pages before going on. Each bot's
messages are now in `$W/timelines/<id>.json` (`events`: role, ts, text), if you need more context later.

## 3. Find correction candidates
Pick the mode by the language of each bot's chats (not the user's): the built-in cue phrases are a small English list.
```bash
python3 "$SKILL/scripts/judge_inputs.py" --work "$W" --all                     # every bot's chats mostly non-English
python3 "$SKILL/scripts/judge_inputs.py" --work "$W" --all-for "<bot>" ...     # a mix: --all only for these bots
python3 "$SKILL/scripts/judge_inputs.py" --work "$W"                           # every bot's chats mostly English
```
"Mostly English" means at least 8 in 10 of that bot's user messages. A bot whose replies match no cue gets all its
replies exported anyway. If the total is over 400 items, you may instead write `$W/cues.json`
(`$SKILL/references/cues.md`). Attachment notices and file paths are already stripped.

## 4. Judge every candidate
Read `$SKILL/references/rubric_correction.md` and judge each item by its steps. Read in batches with
`judge_inputs.py --work "$W" --list --from 1 --to 50`; print the full messages of an item with `--show <n>`.
Write your verdicts as tab-separated lines `n, type, topic, confidence, evidence` in `$W/labels.tsv` (list every
correction and preference; items you leave out count as not a correction), then
`judge_inputs.py --work "$W" --label "$W/labels.tsv"` writes `labels.json`. No candidates: `labels.json` is `{}`.

## 5. Run the checks
```bash
python3 "$SKILL/scripts/diagnostics.py" --work "$W"
python3 "$SKILL/scripts/build_findings.py" skeleton --work "$W" --lang "<BCP 47 code of the user's language>"
```

## 6. Write the findings
Read `$SKILL/references/criteria.md`, `findings-schema.md` and `writing.md`, then edit `$W/findings_draft.json`:
- **Groups:** for each repeated-correction group, read the actual messages. Keep it only if one rule would have prevented
  every incident. Resolve each `fix_check` (memory saves after the group started; most are unrelated) as `writing.md` says.
- **Status:** the suggested status is a starting point. Change it when your reading says otherwise, and say why in `why`.
  Set `issue` and `why` for every bot.
- **Words:** replace every placeholder and `TODO` (titles, fixes, `copy`, `issue`, `why`, `ui` labels, `date_label`) with
  plain wording in the user's language. `copy` goes into that bot, so write it in the language the user uses with that bot.
- **Quotes:** word for word in `quote.orig`; add `translation` when the chat's language differs from the report's.
- **Leads:** check `leads` (stale memory, promises, skipped questions, the same request in several bots, other bots' jobs).
  Add a finding only for what you confirm by reading.
- **Shared causes:** one fleet item per cross-bot cause; each bot points to it with `"see": "fleet-N"`.
- **Review flags:** remove `needs_review`. Then:
```bash
python3 "$SKILL/scripts/build_findings.py" finalize --work "$W" --strict
```
Fix every ERROR and WARN it reports and run it again.

## 7. Make the report
```bash
python3 "$SKILL/scripts/make_report.py" "$W/findings.json" --outdir "$W/report"
pdftoppm -png -r 80 -f 1 -l 1 -singlefile "$W"/report/fleet_report_*.pdf "$W/report/page1"
```
Look at `$W/report/page1.png` with your image reader to check that it looks right.

## 8. Tell the user
Send one short message:
- Start with the report's opening sentence (the `ui.lede_*` text you wrote, word for word).
- Add the status table with 3 columns (bot, status, current issue); proposal counts stay in the report.
- Then the top 3. If the user asked something specific (for example, which bots they don't need), answer it in one
  sentence.
- Attach the PDF and the HTML. Details stay in the files.

If nothing needs doing, say so in one line instead of the top 3.

## 9. Offer to apply
If there are proposals, ask one multi-select question:
- One option per proposal, labelled with its short report line (`short` or title), plus "None for now". `see` pointers
  and info items aren't options.
- Never label an option "Remove X", "Delete X" or "Merge X": you can't do those. For a clean-up candidate, use an option
  like "Show me how to clean up X".

Apply **only** what the user picks:
- **Memory or description text for another bot:** give the exact text and say where it goes (that bot's settings, or a message to that bot). Use a tool that changes another bot only if you have one and the user picked that item.
- **Your own memory:** save it.
- **Routines:** create one only if the user picked it. Say what it will do and when.
- **"Show me how to clean up X":** first ask the user to open X in the app and check whether any routine uses it; if one does,
  move or pause that routine first. Then explain the steps: to delete X, right-click X in the sidebar and choose Delete
  (deleting removes its profile, chat and routines; Hide from sidebar keeps them). To merge, give the text to paste into the
  bot that takes over X's job, then delete X the same way. You never delete or merge anything yourself.

Then, or straight away if there were no proposals, offer once to re-run this audit as a weekly routine (for example,
Monday at 9:00 in the user's time zone; say the day and time). Create it only if the user says yes.
