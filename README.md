# Bot Audit

A Grok Bot plugin that checks up on your other bots from their own chat history and tells you, in plain words,
which ones work well, which need a small fix, and which you could merge or remove. Every proposal cites what was
actually said, and nothing changes until you pick it.

The analysis runs inside Grok Bot only. It uses each bot's chat history, its profile name and description,
and the memory the app shows it. No external APIs and no logins.

## What you get
- **A short chat summary**: one sentence, a status table (Fine / Needs work / Clean up) and the 3 things to do first.
- **An HTML report and a PDF** (English by default, Korean with `--lang ko`). For each bot:
  - why it has that status;
  - findings as *now → fix → apply?* with dated quotes and copy-ready text;
  - what is already improving.
  
  A fleet section covers shared problems, outages and keep/remove candidates. The HTML works offline, on a phone too, and has
  Apply boxes plus a "Copy selection" button.
- **An offer to apply** only the proposals you pick (memory or description text, routines). Bots are never deleted
  automatically; you're asked to check a bot's routines first.

## What it looks at
| area | how |
|---|---|
| Usage per bot | real requests, share of all use, active days, days since last use |
| Fewer corrections | user messages judged with a written rubric; the same correction on several days becomes a proposal, one-offs never do |
| Less waste | unanswered requests, outages across bots, stale or duplicated memory facts |
| Automation | the same request made by hand on many days becomes a routine candidate |
| Right bot for the job | the same job split across bots, requests that belong to another bot, empty or outdated descriptions |
| Merge / remove | idle bots with a very small share of use |

Rules and thresholds are in `skills/audit-my-bots/references/criteria.md`; the correction rubric is in `skills/audit-my-bots/references/rubric_correction.md`.

## Install
- **Local:** copy or clone this repository to `~/.cursor/plugins/local/bot-audit/`, then reload. The skill is found through `.cursor-plugin/plugin.json`.
- **From this repository:** the repo root has a one-plugin `.cursor-plugin/marketplace.json`, so it can be imported as a team marketplace
  ("Import from Repo") or from Customize → From GitHub Repository in Cursor.
- **Public marketplace:** not listed yet. Listing goes through review (see Cursor's plugin docs).

Then ask your bot something like "audit my bots" or "which of my bots do I actually need?".

Requirements on the machine running the bot:
- `python3` (standard library only);
- Chrome or Chromium for the PDF.

The report uses system fonts only, nothing is embedded. The HTML shows in the reader's own fonts (Apple SD Gothic Neo on Mac and
iPhone, Malgun Gothic on Windows, Noto on Android and Linux, Pretendard if installed); the PDF uses the fonts of the machine that made it.

## Components
| path | what |
|---|---|
| `skills/audit-my-bots/SKILL.md` | the end-to-end procedure the bot follows, including the safety rules |
| `skills/audit-my-bots/scripts/sessions.py` | list bots (name and description only), save transcript pages, build per-bot timelines |
| `skills/audit-my-bots/scripts/judge_inputs.py` | wide filter for messages that might be corrections; exports items for the rubric |
| `skills/audit-my-bots/scripts/diagnostics.py` | usage, correction groups, suggested status, outages, memory, repeated requests, overlap leads |
| `skills/audit-my-bots/scripts/build_findings.py` | `skeleton`: a draft findings file with verbatim evidence; `finalize`: checks quotes word for word, scores, caps 3 per bot, picks the top 3 |
| `skills/audit-my-bots/scripts/make_report.py` | renders the HTML and PDF (headless Chrome, temporary profile) |
| `skills/audit-my-bots/references/` | correction rubric, criteria, findings schema, design notes |
| `assets/` | plugin logo |
| `tests/` | synthetic fixture (fake bots, fake chats) and an offline end-to-end test |

## Privacy and safety
- Read-only on bot data. Only `profile.json` (name and description) and the history the bot fetches are read.
- Secret and key files, settings and stores are never opened.
- Quotes must match the chats word for word, or `finalize` fails. Numbers come only from the scripts.
- Work files go to `/workspace/bot-audit-run/<date>/` on the bot's own machine.

## Test
```bash
python3 tests/test_pipeline.py
```
This runs the whole pipeline offline on `tests/fixtures` (regenerate it with `python3 tests/make_fixture.py`) and checks that both
languages' HTML and PDF are produced. It also checks statuses, the outage, the routine candidate, the 3-per-bot cap and that an
invented quote is rejected.

## License
MIT (see `LICENSE`).
