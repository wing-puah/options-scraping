# Model Analysis Methods

This folder documents how each model applies the shared rules in
`config/analysis-framework.md`.

The shared framework defines the required vocabulary, setup labels, and output
schema. Files here describe model-specific judgment: how signals are weighted,
how conflicting evidence is resolved, and how plays and invalidations are
selected.

Current methods:

- `codex.md` - Codex / OpenAI analysis method
- `claude.md` - Claude / Anthropic analysis method

When adding another model, create a separate file matching this naming. Each file
can be structured however best expresses that model's own judgment — they need
not share section headings. What matters is that every file covers the same
ground (regime, signal weighting, conflict resolution, plays, invalidations) so
the approaches remain comparable.

These documents should describe an auditable decision process, not private
chain-of-thought. Record the evidence used, weighting rules, assumptions,
limitations, and conditions that change the conclusion.
