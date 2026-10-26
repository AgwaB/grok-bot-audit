# Checkpoints (incremental audits)

A later audit reads and labels only what is new. The findings still rest on the whole history: saved pages are
put back before `parse`, and saved labels are merged with the new ones before diagnostics. You still judge every
new item yourself. The scripts only remember, merge and check.

The checkpoint is not in the plugin and not in the work folder you may copy around. It lives on this computer:

```text
/workspace/bot-audit-run/state/     mode 0700 (the run area is private; group and others have no access)
    bots/<id>.json                  name, label version, total, anchor, hash of every raw entry
    pages/<id>/page_*.txt           the pages that hash was built from
    labels/<id>.json                that bot's labels
```

Override the directory with `--state` or `$AUDIT_STATE_DIR` (tests only). Never copy it into the repo, a fixture,
or anything you send. It holds the user's chats.

`LABEL_VERSION` in `scripts/checkpoint.py` is the labeling generation. Bump it when the rubric or the label schema
changes what an old label means (a new type that must be judged again, or a changed meaning of correction,
preference, keep or ack). Do not bump it for report wording or for facts `diagnostics.py` counts. A mismatch
makes every bot a full read.

## Commands
`plan` writes `$W/tmp/plan.json` and prints one line per bot:

```text
<id>  <name>  full|incremental  <reason>  anchor=<n|->
```

`next` (after each `save-page`) prints:

```text
<id>  full|incremental  stop|before=<n>|newest  <reason>
```

- `newest`: ReadTranscript with no `before` (the newest page).
- `before=N`: ReadTranscript with that `before`.
- `stop`: this bot's read is done. Do not keep paging.

`assemble` copies stored pages back for bots that are still incremental (it does not overwrite a page you just
saved), writes `$W/tmp/carried_labels.json` and `$W/tmp/scan_mode.txt`, and refuses while a bot is short of pages.
`parse` comes after assemble. `commit` runs only once `make_report` checks are OK (step 7). It refuses otherwise
and leaves the previous checkpoint in place. A replay (`AUDIT_REPLAY_DIR` or `$W/replay.json`) makes `plan` mark
every bot `replay` and makes `commit` print `commit skipped: test mode` without writing state.

## What you fetch
For an `incremental` bot, one newest page is enough when it still contains the anchor (the last raw entry of the
previous run) and the entries you re-read match. When a lot was said since then, page backward only until `next`
prints `stop`: that is the first page that overlaps the anchor and the pages cover everything after it. You do
not continue to `start=0`.

A `full` bot is read the old way: follow `next` until `stop` (the pages reach the start and the end, with no hole).

`assemble` then fills in the pages you did not re-read, from the checkpoint. `parse` builds one timeline for the
whole chat. Old messages keep their indexes, so old label keys (`<bot id>:<event index>`) still point at the same
messages. `--list` hides items already in the carried labels. Label only what it prints. `--label` keeps the
carried labels, refuses a line for one of them, and records every other new item you didn't mention as `none`.
The digest and `diag.json` still cover the whole history. Read them as before.

## When the checkpoint is not used
`plan` decides, in this order, before any fetch. The first reason wins.

| reason | what happened |
|---|---|
| `replay` | test mode. No checkpoint is read or written. |
| `full re-run` | `plan --full` (the user asked to start over). |
| `new bot` | no checkpoint for this id. |
| `labeling changed` | `LABEL_VERSION` in the checkpoint is not the one in the script. |
| `renamed` | the profile name is not the name that was saved. |
| `labels missing` | the labels file is gone. |
| `labels unreadable` | the labels file is not valid JSON, doesn't match the label schema, or doesn't match the hash saved with the checkpoint (truncated or edited). |
| `checkpoint incomplete` | the saved pages are missing, don't cover every position, or don't match the saved hashes. |
| `continued` | none of the above. Read only what is new. |

`next` can still abandon a bot that `plan` called `continued`, after seeing the new pages:

| reason | what happened |
|---|---|
| `shorter` | the transcript total is smaller than the one that was saved. |
| `compacted` | a re-read position overlaps the saved history but its raw entry changed (rewritten or summarized in place), while at least one overlapping entry is unchanged. |
| `recreated` | the re-read overlap shares no raw entry with the checkpoint (the chat was replaced). The same id with a new name is `renamed` instead, at `plan`. |

A bot switched to `full` stays `full` for the rest of the run. Keep fetching until `stop`. `assemble` does not
copy the stored pages or the stored labels for it, so you judge that chat again from the pages you just fetched.
Say the reason in the chat summary, in the user's language and in plain words (no internal terms).

`$W/tmp/scan_mode.txt` is one line per bot: `mode`, id, name, reason. In the chat summary, name the bots you read
in full and the bots you continued from the last audit. One sentence is enough.

## Starting over
If the user asks for a full re-run ("audit from scratch", "from scratch", "start over", or the same wish in their
language), run `plan --full`. Every bot is `full re-run`. `commit` still runs at the end and replaces the
checkpoint, so the run after that is incremental again.

## Second run, nothing new
When nobody has spoken since the last finished audit:

1. `plan` prints `incremental` / `continued` for each bot that still matches.
2. One ReadTranscript per bot (the newest page, no `before`). `next` prints `stop`.
3. `assemble` restores the saved pages. `parse` rebuilds the same timeline (same event indexes and text).
4. `--list` prints `-- no new items`. Leave `labels.tsv` empty and still run `--label`. `labels.json` is the
   carried labels again.
5. Diagnostics, the digest and the report still describe the whole history. Statuses can change with no new
   messages, because a bot can become idle as time moves on. The weekly check stays quiet only when
   `make_report.py --previous` prints `UNCHANGED`.
6. `commit` rewrites the checkpoint at the same resume point.

## Weekly re-check
The routine in `setup.md` uses this path. It does not pass `--full`. It still passes the newest earlier
`report/summary.json` to `make_report.py --previous` and sends nothing when that prints `UNCHANGED`. `commit`
runs after the checks pass even when the routine then stays quiet, so the next Monday does not re-read this week.
A run that fails before `commit` leaves the old checkpoint; the retry reads from there again.
