# Agent personas

Specialist subagents for this repo. Each file is a Markdown system prompt with YAML
frontmatter, auto-discovered by Claude Code and callable via the Agent tool with
`subagent_type: <name>`.

| Persona | Role | Model | Tools | Best for |
|---|---|---|---|---|
| [code-reviewer](code-reviewer.md) | Senior Staff Engineer | opus | read-only | Five-axis review before merge, with a verdict |
| [test-engineer](test-engineer.md) | QA Engineer | sonnet | read + write | pytest strategy, coverage analysis, Prove-It tests |
| [research-analyst](research-analyst.md) | Independent grader | opus | read-only | One half of a replication pair (A or B) |
| [research-validator](research-validator.md) | Replication validator | sonnet | read-only | Reconciling analyst A vs B after both return |

## Rules

1. **One role per persona.** If you're adding a second role, add a second persona.
2. **Personas do not invoke other personas.** Composition is the user's job (or a
   slash command's). Claude Code enforces this anyway — subagents cannot spawn
   subagents. If a persona wants a second opinion, it recommends one in its report.
3. **Always set `model:` explicitly.** An omitted model inherits the main session's,
   which is the most expensive one. See the model-selection section of `CLAUDE.md`:
   `haiku` for lookups, `sonnet` for moderate edits and single-file analysis, `opus`
   for multi-file reasoning, architecture review, and open-ended design.
4. **Scope `tools:` deliberately.** Review and research personas are read-only on
   purpose: a reviewer that can edit will quietly fix instead of reporting, and a
   grader that can write can contaminate the artifact it's grading.
5. **Every persona ends with a Composition block** — invoke directly when / related /
   do not invoke from another persona.
6. Persona files carry the *perspective*. Cross-cutting facts (data contracts, column
   schemas) belong in `CLAUDE.md` and `ARCHITECTURE.md`; link to them rather than
   duplicating, or they drift.

Note: plugin/agent frontmatter does not support `hooks`, `mcpServers`, or
`permissionMode` — those fields are silently ignored.

## Relation to built-in skills

`code-reviewer` overlaps deliberately with the built-in `/code-review` skill:

- `/code-review` — diff-scoped bug hunt, findings rendered in the UI, supports
  `--fix` and `--comment`. Faster, tooling-integrated.
- `code-reviewer` persona — whole-change opinionated review across five axes with an
  explicit APPROVE / REQUEST CHANGES verdict and a verification story. Slower.

Also available: `/security-review` (credentials and dependency pass) and `/simplify`
(quality-only cleanup, no bug hunting).

## The research pair is a protocol, not a persona choice

`research-analyst` and `research-validator` implement
`config/backtest-tuning/replication-protocol.md`. Spawn analysts in pairs (A and B)
with identical prompts naming the exact input files, never one alone and never letting
one see the other's output; spawn the validator only after both have returned. This is
what keeps a tuning conclusion from being one model's single pass.

## Provenance

`code-reviewer` and `test-engineer` started as verbatim copies of
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) (`agents/`,
`docs/agents.md`) and were retargeted from a web/JS stack to this Python data
pipeline. Upstream also ships `security-auditor` and `web-performance-auditor`; both
were deliberately not adopted — see the note in the commit that added this file.

## Adding a persona

1. Create `.claude/agents/<role>.md` with `name`, `description`, `tools`, `model`.
2. Define the role, scope, output format, and rules; link to `ARCHITECTURE.md`
   for contracts instead of restating them.
3. Add a Composition block at the bottom.
4. Add a row to the table above.
