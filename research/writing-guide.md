# Writing guide for research prose

This folder is read by someone who has lost the thread: a future session, or the
operator six weeks later. Every entry is written for that reader. Clarity beats
compression, and a link beats a re-explanation.

Adopted 2026-09-05. It governs new writing in `research/` and `docs/`. It does
not license rewriting the archive (see [What not to rewrite](#what-not-to-rewrite)).

## Who the reader is

Write for a technically competent engineer who understands the domain but has
not been inside your reasoning process. They should understand the decision
and its implications on the first pass, without reconstructing the logic. Clarity
and navigability beat formal-sounding precision.

Adopted 2026-09-08 (operator). This section replaces the earlier "one idea per
sentence" rule; the numbered rules below were rewritten to match it.

## Structure

1. **State the main point or conclusion first.** The first sentence of an entry
   is the verdict in plain words. The second is what it changes in production,
   or "Nothing ships". Reasoning, implementation, exceptions and edge cases come
   after, never before. The reader must never have to infer the conclusion from
   the middle or end of a paragraph.
2. **Separate the rule, the current behaviour, and the implementation** when
   they are different things. Use headings, bullets or short paragraphs to make
   that separation visible.
3. **Say plainly what is unresolved.** For any ambiguity or open decision state:
   what is ambiguous, what the current default is, why that default is used, how
   it can be changed, and whether changing it affects the actual result.
4. **Numbers live in tables.** Prose says what a number means; the table holds
   the number, its confidence interval, and its population. A sentence carrying
   more than two figures becomes a table row.
5. **Name the population once**, in one provenance line at the top of the
   entry: era, export timestamp, row counts. Bullets below it do not repeat them.
6. **Say what happens next.** End with what the finding does to the queue in
   [`next-steps.md`](next-steps.md): a new item, a closed item, or nothing.

## Sentences

- **One main claim per sentence.** Do not force every sentence to hold only one
  idea. Combine closely related cause-and-effect, qualification, or consequence
  clauses when that makes the relationship clearer.
- Avoid sentences that introduce a rule, an exception, an implementation
  choice, an audit requirement and a future state all at once. Split those.

## Language

- **Plain technical English.** Prefer concrete verbs over abstract nouns: "the
  code reports", not "the reporting mechanism provides"; "the ACK changes the
  default", not "the ACK constitutes a modification of the default
  interpretation".
- **No legalistic or bureaucratic phrasing** unless it carries a precise
  technical meaning. Do not use *scoped*, *reading*, *presentation*,
  *pre-empts*, *retro-fitted*, *disposition*, *mechanism*, *posture*,
  *resolution* because they sound precise; use them only when ordinary language
  cannot draw the distinction.
- **Define project-specific terms the first time they matter.** A study-local
  label (`ARM P`, `B2`, `G0`, `H4`, `E3`) is linked to its study's entry in
  [`arm-index.md`](arm-index.md) on first use in a section and qualified with
  the study name. A metric (`R`, `E`, `meanR`, `CI`, `LOO`, `MWU`) is linked to
  [`glossary.md`](glossary.md) on first use in a document. A rule number (§1.4,
  §5) is linked to its section of
  [`docs/deployment-rules.md`](../docs/deployment-rules.md). A coined term goes
  into the glossary in the same commit.
- **Do not make ordinary ideas sound like subtle distinctions.** "The hedge
  lost money on gap-up days" beats "GAP-UP came back CONTRARY on both money
  arms".
- **One emphasis per point.** Bold the verdict token once. Capitals only to
  quote a token the study itself printed (`UNDERPOWERED`, `NULL`, `CONTRARY`,
  `PRECONDITION-NULL`), quoted verbatim.

## What to cut

- Repeating the same idea in progressively different wording.
- Explaining every implication, unless someone needs it to implement, review
  or audit the system.
- Defensive prose whose only purpose is to show that every edge case was
  considered.
- Formal qualifications wrapped around a straightforward implementation
  decision.
- Any sentence about how the text will be read: no meta-language about graders,
  breaches, sanctions or compliance. Where two registered clauses conflict, name
  the conflict in one sentence and the chosen interpretation in one.

## The test

Before finalising, ask: could a competent engineer explain what this section
means after reading it once? If not, restructure it rather than adding more
explanation. Be rigorous in the underlying logic, but make the rigour visible
through structure rather than dense prose.

## The entry template for `current.md`

```markdown
## 2026-09-05 — exit_drawdown — nothing ships, every primary cell underpowered

No walk-forward exit rule can be judged on this book. All seven primary cells
print `UNDERPOWERED`, the outcome the
[pre-registration](pre-registrations/f2_management/exit_drawdown.md) named as
most likely.

_Era v4 · exports 2026-09-04 20:31 · 535 real / 1,303 proxy rows · report:
`backtests/study_output/exit_drawdown-latest.txt` · recorded in
[study-results](study-results/f2_management/exit_drawdown.md)._

**In production.** Nothing changes. The shipped debit exit profile
([§5](../docs/deployment-rules.md#s5)) stays.

**Evidence.**

| Cell | Verdict | Δ max drawdown | CI | Dates |
|---|---|---|---|---|
| [ARM W/wf](arm-index.md#exit_drawdown) | UNDERPOWERED | — | — | 9 |
| ARM O/vol (`all` cut) | NULL | +0.4 pts | [−1.1, +1.9] | 41 |

**Caveats.** The `all` cut has no verdict standing; it was disclosed, not
registered.

**Next.** [`next-steps.md`](next-steps.md) §2.6 closes. No new item.
```

Keep the heading to one line: date, study, verdict in a few words. The heading
must start with the date, because the site map sorts entries by it. The first
paragraph under the heading is quoted onto the site map as the entry's summary,
so it is the finding, not the provenance line. The archive index quotes the
headings, so a heading that needs a second line says too much.

## Linking conventions

Links are how a reader gets a definition without leaving the page they are on.
Every link is checked by `make check-doc-links` (also run by
`tests/test_doc_links.py`), so a moved heading fails the suite rather than
silently rotting.

| To refer to… | Write | Target anchor comes from |
|---|---|---|
| a metric or term | `[meanR](glossary.md#meanr)` | the term's own `###` heading in `glossary.md` |
| an arm, gate, or criterion | `[hedge_timing ARM R](arm-index.md#hedge_timing)` | the study's `####` heading in `arm-index.md`, which is the bare study slug |
| a deployment rule | `[§1.4](../docs/deployment-rules.md#s1)` | an explicit `<a id="sN">` above each numbered section of the card |
| a study's plan | `[pre-registration](pre-registrations/f5_hedging/hedge_timing.md)` | file path; the family folder mirrors `scripts/backtest_study/` |
| what a study last printed | `[record](study-results/f5_hedging/hedge_timing.md)` | file path |
| a study's standing verdict | `[study map](study-map.md#deployment)` | the family heading in `study-map.md` |
| an archived entry | `[archive/16](archive/16-first-runs-on-v3.md)` | file path; add `#slug` only for a long volume |

Anchor slugs follow GitHub's rule: lowercase the heading text, drop every
character that is not a letter, digit, space, hyphen, or underscore, then turn
spaces into hyphens. `scripts/check_doc_links.py::slugify` is the reference
implementation; run it on a heading when unsure.

Heading text that is a link target should therefore be short and stable. Put
file paths and qualifiers in the first line under the heading, not in it.

## What not to rewrite

- **`archive/`** is history. Its volumes carry a status line and nothing else
  in them changes. Rewriting an old conclusion for style risks changing what
  it claimed.
- **`pre-registrations/`** are fixed in substance, not in prose. Wording may be
  clarified, but every number, arm label, gate id, verdict token, and quotation
  is held verbatim, and a diff should be able to prove it. The 2026-08-31 pass
  did exactly this.
- **`study-results/`** is machine-written by `scripts/study_results.py`.
  Do not hand-edit a section.

Everything else in `research/` and `docs/` may be rewritten for clarity at any
time, provided the facts, dates, and figures survive unchanged.
