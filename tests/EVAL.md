# Evaluating the audit-my-bots skill

Unit tests check the scripts. This file is about testing the **skill**: whether a fresh agent that reads `SKILL.md`
produces a correct, useful audit. The method follows published practice (sources at the end), cut down to what fits
this skill.

## Method
1. **Scenarios first.** A few realistic user requests with expected properties (`eval_prompts.md`, machine-readable in
   `evals.json`): a Korean user, an English user, a Japanese user with a synthetic fleet, and a tiny fleet with nothing
   to fix. Few and real beats many and synthetic; add a scenario whenever a real run finds a new failure.
2. **Replay, so runs repeat.** Real chats change and fetching needs ReadTranscript, so evals run on frozen inputs: a
   replay folder holds `bots.json`, `transcripts/<id>/page_*.txt` and `replay.json` (`{"now": ..., "self": <id, optional>}` so idle days
   don't drift; `self` is the auditing bot to skip, if it is in the fleet). With `AUDIT_REPLAY_DIR` set, `SKILL.md` tells the agent to run `sessions.py replay` instead of steps 1-2.
   Everything after that is the normal path.
3. **Fresh agent per run, with and without the change.** Each run is a new agent that has only the prompt below. Run the
   current skill (`with_skill`) and a baseline (`old_skill`: a snapshot of the last release, for example
   `git worktree add /workspace/bot-audit-eval/skill-v0.1.0 v0.1.0`) in the same round, on the same scenarios.
4. **Grade objectively first.** `tests/grade.py` checks what can be checked by code (files, strict finalize, verbatim
   quotes, no paths or notices in quotes, no jargon, report language, no Delete/Merge options, at most 3 proposals per
   bot, counts without pointers, forbidden reads, scenario statuses) and writes `grading.json`
   (`text` / `passed` / `evidence`, as in skill-creator).
5. **Then read.** Open the report and the agent's transcript. Judge what code can't: are the findings real, would one
   rule really prevent the incidents, is the wording plain, did the agent waste effort or skip steps? For "is v2 better
   than v1", show both reports to a reviewer without saying which is which.
6. **Iterate.** Fix causes that generalize (a clearer instruction, a script that does what every run re-did by hand),
   not tweaks for one scenario. Re-run every scenario, including the baseline, into the next iteration folder. Stop
   when grades are all green and the read-through finds nothing new, or when changes stop helping.

## Layout (outside the repo)
```
/workspace/bot-audit-eval/
  replay-ko/ replay-en/            # from real runs: user data, never commit
  replay-synth-ja/ replay-tiny/    # python3 tests/make_replay.py /workspace/bot-audit-eval
  iteration-1/<scenario>/with_skill/{work/, chat.md, commands.log, grading.json}
  iteration-1/<scenario>/old_skill/...
  iteration-1/benchmark.md         # one row per scenario x config: score, failed checks, notes
```
Make a real-run replay folder from a finished work folder:
`mkdir -p R && cp -r W/transcripts W/bots.json R/ && echo '{"now": "<diag.json now>"}' > R/replay.json`.
**`self` in a replay.** The bot that ran the recorded audit skipped itself, so its own chat is normally not in
`bots.json`. If it is (for example, `bots.json` was copied from a run with no `--self`), add
`"self": "<its agent id>"` to `replay.json`; `sessions.py replay --from R --self <id>` does the same for one run. Never
skip by name: the fleet may hold a bot with the same name as the agent running the test (both called like the app's
default bot, say), and that bot is part of the recorded fleet, so it is audited. `replay` prints which bot it skipped as
self, or that nothing was skipped; SKILL.md's testing note tells the agent the same. When a scenario's statuses look
off, check that line first.
**Consistency:** run one scenario two or more times with fresh agents (plus the same fleet in another language) and
compare: `python3 tests/compare_runs.py a=<work1> b=<work2> ...` prints the per-bot status table, the share of bots with
the same status in every run (and pairwise), and the top-3 overlap by target bot. Trace each difference to the judgment
or rule that caused it.

## Prompt for a fresh agent
Fill in the four values (see `eval_prompts.md` for each scenario) and paste:

```text
You are testing a skill. Act as the bot the user is talking to.
Skill: read /workspace/bot-audit-plugin/skills/audit-my-bots/SKILL.md and follow it. Its folder is $SKILL.
Test mode: export AUDIT_REPLAY_DIR=<replay folder>. Use W=<work folder> as the work folder (not the dated default).
Don't call ReadTranscript: run `sessions.py replay --work "$W"` instead of steps 1-2, as SKILL.md says for testing.
The user's message, in their language (<language>): "<prompt>"
Do every step through 7. For steps 8 and 9, don't send anything: write the chat message you would send and the
multi-select options you would offer (one per line, starting with "- ") to $W/chat.md. Don't apply anything, don't
create routines, don't message anyone or post anywhere.
Append every shell command you run, one per line, to $W/commands.log.
When done, reply with the paths of the report and chat.md.
```

Then grade:
```bash
python3 tests/grade.py <work folder> --lang <code> --scenario <id> --chat <work folder>/chat.md \
  --log <work folder>/commands.log --out <run folder>/grading.json
```

For an `old_skill` snapshot that has no `replay` command, replace the "Don't call ReadTranscript" line with: "Instead of
steps 1-2, run `mkdir -p $W && cp -r <replay folder>/transcripts <replay folder>/bots.json $W/`, and pass
`--now "<now from replay.json>"` to diagnostics.py."

## Unit tests
```bash
python3 tests/test_pipeline.py      # end to end on the synthetic fleet, English and Japanese rendering
python3 tests/test_regressions.py   # issues found in real runs (fetch batching, --all, excerpts, notices, copy lists...)
python3 tests/test_iteration2.py    # consistency fixes: occasions, fix facts, safer labels, placeholders, quotes
python3 tests/test_iteration3.py    # lede file, whole-report checks, deduped fix candidates, chat label, compare_runs
python3 tests/test_iteration4.py    # size-cut batches, "who": "bot", count-neutral ledes, footer, fix-candidate cap, links, self
python3 tests/test_iteration4b.py   # paste test / no generic default fix, compact all-keep fleet, undated evidence, test-mode note
python3 tests/test_grade.py         # grade.py itself: a clean run scores 1.0, known-bad outputs fail
```

## Sources
- Anthropic, skill-creator skill: test prompts in `evals/evals.json`; spawn with-skill and baseline runs in the same
  turn (baseline = no skill, or a snapshot of the old skill); objectively checkable assertions, scripted where
  possible; `grading.json` with `text`/`passed`/`evidence`; benchmark with pass rate; `iteration-N/` folders; read the
  transcripts, generalize instead of overfitting, keep the prompt lean; optional blind comparison.
  https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- Anthropic, Skill authoring best practices, "Evaluation and iteration": build evaluations first, three scenarios,
  measure a baseline without the skill, write minimal instructions, iterate; one agent refines the skill while fresh
  agents use it; watch how they navigate the files. There is no built-in runner.
  https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices
- OpenAI, "Testing Agent Skills Systematically with Evals": define success, run the agent, record what happened,
  deterministic checks over the recorded commands and files first, then rubric grading with structured output.
  https://developers.openai.com/blog/eval-skills
- OpenAI, Evaluate agent workflows: trace grading (right tool? instruction or safety violations?) before datasets.
  https://developers.openai.com/api/docs/guides/agent-evals
- Cursor, Agent Skills docs: `SKILL.md` format (`name`, `description`, `scripts/`, `references/`), relevance decided
  from the description. They describe no eval method. Cursor's 2.4 announcement notes that subagents can't load
  skills and suggests telling them to read the `SKILL.md`, which is what the prompt above does.
  https://cursor.com/docs/skills, https://forum.cursor.com/t/cursor-2-4-skills/149402
- agent-skills-eval (community): runs each prompt `with_skill` and `without_skill` and judge-grades both against the
  same assertions. https://github.com/anmho/agent-skills-eval
