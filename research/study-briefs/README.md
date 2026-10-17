# Study briefs

A brief is a plain-language summary of one study's pre-registration: the
question, the arms, how it is judged, the possible verdicts and what could
ship. Read the brief to understand a study in five minutes. The registration in
[`../pre-registrations/`](../pre-registrations/) stays the binding text; where
the two differ, the registration wins.

Adopted 2026-10-17. Briefs exist because a registration has two jobs that pull
against each other. Blind graders need every commitment and the date each was
fixed. A reader needs the design in plain words. Rewriting a registration for
readability strips the dating markers the graders rely on, so the plain version
lives here instead.

## Rules

- **One brief per registration**, at the same relative path: the brief for
  `pre-registrations/f2_management/exit_drawdown.md` is
  `f2_management/exit_drawdown.md` here.
- **Graders never read a brief.** `scripts/study_review` reads only
  `pre-registrations/`, so a brief may link the latest outcome.
- **The only result in a brief** is the "Latest outcome" line, copied from the
  [index](../pre-registrations/README.md). When a study re-runs, update both.
- **Every threshold, label and token matches the registration exactly.** A rule
  too intricate to summarise gets one line and a link to the registration
  section, never a loose paraphrase.
- **Each brief is fact-checked** against its registration by a second reader
  before it is committed.
- **Writing** follows [`../writing-guide.md`](../writing-guide.md), with ASD-STE100
  Issue 9 as inspiration: sentences of 25 words or fewer, active voice, one
  topic per paragraph, vertical lists for parallel items, one term per thing.

## Layout

1. `# <study> — brief`, then a blockquote: not the registration, link to it,
   the registration wins; Latest outcome with date and record link.
2. `## The question` — two to four sentences.
3. `## What it compares` — a table of arms: label, what it does, kind.
4. `## How it is judged` — measure, population, gates as a list, the bar as a
   numbered list.
5. `## Possible verdicts` — a table: token, what it means.
6. `## What could ship` — one short paragraph.
7. `## What this study cannot tell you` — three to five bullets.

A commitment rather than a study (`holdout_seal`, `programme_gate`) replaces
sections 3–5 with what it commits to and what each outcome triggers.

The reference brief is
[`f2_management/exit_drawdown.md`](f2_management/exit_drawdown.md).
