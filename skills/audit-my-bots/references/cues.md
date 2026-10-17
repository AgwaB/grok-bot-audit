# Language cues (`cues.json`)

The scripts look for a few kinds of short phrases. The built-in lists are English (`CUES_EN` in `scripts/common.py`).
When any audited bot chats in another language, write `$W/cues.json` with the same five keys for those languages
before step 3. Entries are case-insensitive regular expressions or plain words; they are added to the English ones.

| key | what it finds | English examples |
|---|---|---|
| `directive` | a user message that may correct the bot (wide net; the rubric decides) | no, not that, instead, don't, wrong, I meant, too long, already, again, from now on, are you sure |
| `fix` | the bot saying it saved a rule | from now on, I'll remember, I've saved, going forward |
| `promise` | the bot promising to come back later | I'll let you know, working on it, give me a minute |
| `nudge` | a short user check-in after silence (matched at the start of the message) | hi, hello, any update, status? |
| `timely` | a memory fact that goes stale | currently, now, at the moment, as of |

```json
{
  "directive": ["<word for no>", "<word for instead>", "<phrase for too long>"],
  "fix": ["<phrase for from now on>"],
  "promise": ["<phrase for I'll let you know>"],
  "nudge": ["^<greeting>"],
  "timely": ["<word for currently>"]
}
```

Write the cues from the actual chats: read a sample of messages first and add the words people really use.
Without `cues.json`, `judge_inputs.py` keeps every reply written mostly in a non-Latin script as a candidate (so
corrections are not missed), and the other checks use English cues only.
