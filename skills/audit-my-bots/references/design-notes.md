# Report design notes

The report is a checkup record for the user's bots, not a dashboard. It should read like a well-set printed table,
not like a generated landing page. `make_report.py` already follows these rules; keep them if you change it.

## Avoid (the common "AI-made" look)
- Uniform rounded cards with the same radius and shadow on everything; card grids with no focal point.
- Emoji as icons or status lights; pastel traffic-light backgrounds; cards with a colored left border.
- One default sans (Inter or the system stack) with no weight contrast; blue default buttons; purple-to-blue gradients.
- Hover lift on every card; motion that isn't a response to the user.
- Meta strings joined with middle dots ("A · B · C"), arrows after every link, all-caps eyebrow labels, monospace for small labels.
- Second-tier defaults too: cream paper with terracotta, black with neon green, decorative 01/02/03 numbering, newspaper hairlines as decoration.

## Do
- Start from the subject: a status **table** first (each row links to that bot), then the top 3 (numbered because the order matters),
  then one section per bot, separated by thin rules, not boxes.
- Restrained color: near-white paper `#FCFCFA`, ink `#1E2226`, secondary `#5F666D`, rules `#DCDDD8`, one accent `#1F5A54` (links, checkboxes).
  Status uses colored text plus a small square: brick `#A23B2A` (Clean up), ochre `#8C5D00` (Needs work), moss `#3F6B47` (Fine). No filled backgrounds.
- A deliberate pairing of two typefaces: a sans for text and a serif for the user's own words and the title. Hierarchy comes from weight, not size jumps.
  Lines stay under ~80 characters.
- Quotes: the report language on the main line; when it is a translation, the original goes underneath in smaller type.
  Dates sit in a fixed left column.
- Plain words on controls that say what they do: "Copy", "Copy selection", "Apply".
- Print/PDF: every section open; checkboxes, buttons and the bottom bar hidden; A4; findings never split across pages.

## Words
- No token counts, cost estimates, tool counts, precision numbers or internal terms (subagent, executor, tool, transcript, model) in anything the user sees.
- Every finding reads "now → fix → apply?": evidence (dated quotes or plain facts), one-line fix, copy-ready text, an Apply box.
- When nothing qualifies, say "Nothing major to fix."

## Fonts
System fonts only; nothing is bundled or embedded. Two stacks, defined once in `make_report.py`:
- Sans (body): system UI fonts (`-apple-system`, `Segoe UI`, Roboto, Helvetica Neue, Arial), then fallbacks for
  non-Latin scripts (Noto Sans and Noto Sans CJK, PingFang, Hiragino, Apple SD Gothic Neo, Microsoft YaHei, Yu Gothic,
  Malgun Gothic, Noto Sans Arabic / Devanagari / Thai), then `sans-serif`.
- Serif (title, quotes): Iowan Old Style, Charter, Sitka Text, Cambria, Georgia, then non-Latin fallbacks (Noto Serif and
  Noto Serif CJK, Songti, Hiragino Mincho, SimSun, Yu Mincho), then `serif`.
The order doesn't favor any report language. The HTML uses the reader's fonts, so it can look slightly different per device.
The PDF embeds whatever the printing machine has.

## Language
The report and the chat messages are in the user's language (English when unclear). Labels come from `ui` in
`findings.json`; `lang` sets the HTML `lang` attribute. Quotes keep the original words; a translation into the report
language is added only when the chat was in another language.
