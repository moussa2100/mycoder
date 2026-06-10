---
name: plan
description: Guides Claude through disciplined plan-mode workflows for non-trivial coding tasks. Use whenever the user enters plan mode, asks for a plan, says "think before coding", "draft a plan", "explore first", or whenever a change cannot be described as a single-sentence diff. Enforces the 4-phase Explore → Plan → Review → Implement workflow, mandatory user-feedback checkpoints, and small-scope plans that fit a 30-minute implementation window.
---

# Plan Mode Best Practices

A disciplined approach to planning code changes. The goal is **separating thinking from execution** so the user reviews and approves the approach before any file is modified.

> **Core principle:** if you cannot describe the change in one sentence as a diff, you must plan first.

---

## When to use this skill

Activate this workflow when **any** of the following is true:

- The user is in plan mode (`shift+tab` engaged) or explicitly asks to plan
- The task touches more than one file, or any unfamiliar file
- The task involves migrations, refactors, new features, or anything with side effects
- The user says: *"plan this"*, *"think first"*, *"don't code yet"*, *"explore the codebase"*
- The change has non-obvious edge cases, security implications, or breaks public APIs

**Skip this skill when** the change is trivially describable in one sentence (e.g. *"rename variable `x` to `userId` in `auth.ts`"*). Don't plan for plan's sake.

---

## The 4-Phase Workflow

Follow these phases **in order**. Do not collapse them.

### Phase 1 — Explore (read-only)

Goal: understand the user's request and the relevant code before proposing anything.

- Read the files the request touches; trace imports and call sites
- Run **read-only** tools in parallel (grep, file reads, `git log`, `git blame`)
- Identify conventions, existing patterns, tests, and prior decisions
- Do **not** write, edit, run migrations, change configs, or make commits
- If the request is ambiguous, list the ambiguities — do not guess

**Checklist before leaving Phase 1:**
- [ ] I have read every file the change will touch
- [ ] I have identified the relevant tests and how they exercise the code
- [ ] I have listed open questions for the user

### Phase 2 — Clarify (ask the user)

Goal: resolve ambiguity **before** drafting the plan, not after.

Always ask the user clarifying questions when:

- Multiple valid implementation paths exist (pick one or ask which)
- The request implies a design decision (naming, schema shape, API contract)
- There's a conflict between the request and existing conventions
- Scope is unclear (e.g. *"add auth"* — to which endpoints?)

Use a single, batched question block. Format:

```
I have a few questions before I draft the plan:

1. [specific question with options A / B / C]
2. [specific question]
3. [specific question]

Default if you don't answer: I'll go with option A in #1, the existing convention for #2, and skip #3.
```

Provide a **sensible default for every question** so the user can answer "go with defaults" if they want to move fast.

### Phase 3 — Draft Plan (write the plan file)

Goal: produce a concise, scannable, executable plan.

**Required plan structure:**

```markdown
# Plan: <short title>

## Goal
One paragraph. What the user actually wants. Not a restatement of the request — the underlying intent.

## Scope
- In scope: <bullets>
- Out of scope: <bullets>  ← prevents creep

## Files to modify
- `path/to/file1.ts` — what changes and why
- `path/to/file2.ts` — what changes and why

## Implementation steps
1. <ordered, atomic step>
2. <ordered, atomic step>
3. ...

## Edge cases & risks
- <case>: <how it's handled>
- <risk>: <mitigation>

## Tests
- <new tests to add>
- <existing tests that must still pass>

## Rollback plan
How to undo this cleanly if it goes wrong.

## Open questions
Anything still unresolved that needs the user's call before/during implementation.
```

**Rules for the draft:**

- Keep it **scannable** — the user must be able to read it in under 90 seconds
- Include only the **recommended approach**, not every alternative considered
- Prefer **30-minute implementation scope**. If bigger, split into multiple plans
- List **file paths verbatim** so the user can spot mistakes
- No code blocks longer than ~10 lines in the plan — pseudocode or signatures only
- Use forward slashes (`/`) in paths for cross-platform consistency

### Phase 4 — Review & Iterate (mandatory user checkpoint)

Goal: get the user's explicit approval — or their edits — before executing anything.

After writing the plan:

1. Surface it to the user with a brief verbal summary (3–5 bullets)
2. **Explicitly invite feedback** using this template:

   ```
   Plan ready for review.

   Summary:
   - <bullet 1>
   - <bullet 2>
   - <bullet 3>

   Before I implement, please:
   • Approve as-is → reply "go" / "ship it" / "approved"
   • Edit directly → press Ctrl+G to open the plan in your editor, save, then say "go"
   • Request changes → tell me what to adjust
   • Cancel → say "stop" or "scrap it"

   Open questions still needing your call: <list, or "none">
   ```

3. **Wait for explicit approval.** Do not exit plan mode on your own initiative.
4. If the user edits the plan file directly, **re-read it** before implementing — their edits are authoritative.
5. If the user requests changes, update the plan and loop back to step 1. Do not skip the second review.

**The two-correction rule:** if the user has rejected or corrected the plan twice and it's still wrong, the context is polluted with failed approaches. Suggest the user `/clear` and restart with a sharper initial prompt. Don't keep grinding.

---

## User Feedback Patterns

How to incorporate the kinds of feedback users actually give:

| User says | What to do |
|---|---|
| *"go" / "ship it" / "approved"* | Exit plan mode, execute the plan as written |
| *"looks good but also do X"* | Update the plan with X, re-summarize, ask again |
| *"simplify"* | Cut steps, narrow scope, drop optional items, re-present |
| *"too big"* | Split into 2+ plans, present the first, defer the rest |
| *"why did you choose X over Y?"* | Explain the trade-off in chat, ask if they want to switch |
| *"start over"* | Acknowledge, run `/clear` mentally — drop prior assumptions, ask for a fresh prompt |
| *"silence after the plan"* | Do **not** assume approval. Ask once more: *"Ready to proceed?"* |
| direct edits to the plan file | Re-read the file, confirm the new version in one line, then proceed |

---

## Anti-Patterns to Avoid

- ❌ Writing code or editing files (other than the plan file) in plan mode
- ❌ Exiting plan mode without the user's explicit approval
- ❌ Plans longer than ~150 lines or that read like a design doc
- ❌ Burying the recommendation under three alternatives — pick one
- ❌ Skipping clarifying questions and guessing at intent
- ❌ Iterating on the plan more than twice without suggesting `/clear`
- ❌ Mixing exploration findings into the plan body — keep the plan about *what will change*, not *what you learned*
- ❌ Restating the user's request as the goal — dig for the underlying intent
- ❌ Vague steps like *"update the auth logic"* — use concrete, atomic steps

---

## Useful Tools While in Plan Mode

- **Subagents (`Task` tool):** for deep code investigation that would clutter the main context (e.g. *"trace how this middleware is wired across the request lifecycle"*). The subagent's findings come back as a summary, not raw transcripts.
- **Parallel reads:** when exploring, batch `read_file` / `grep` / `glob` calls in parallel. Plan mode is read-only, so there's no risk.
- **`git log` / `git blame`:** for understanding *why* code looks the way it does before proposing changes to it.

---

## Storage Convention

- Plans live in `./docs/plans/` in the project, named `YYYY-MM-DD-short-slug.md`
- Commit plans to version control — they're the historical record of *why* changes were made
- Reference prior plans when proposing related changes: *"This extends the auth refactor planned in `2026-05-12-auth-refactor.md`."*

---

## Quick Reference Card

```
Trigger:        non-trivial change OR user says "plan"
Phases:         Explore → Clarify → Draft → Review
Mandatory:      explicit user approval before exiting plan mode
Scope target:   30 minutes of implementation work
Plan length:    ≤ 150 lines, scannable in 90 seconds
Two-correction: stop and suggest /clear if rejected twice
File path:      ./docs/plans/YYYY-MM-DD-slug.md
```
