# Live-Fire Validation Plan

## Goal

Validate the platform on real, mergeable tasks instead of artificial demo tasks.

The validation should prove that the platform can handle:

- issue-driven task setup;
- team selection and startup prompt materialization;
- multi-agent orchestration when appropriate;
- terminal, activity, and report UX;
- commit, push, and draft PR delivery;
- recovery and resume behavior when the host executor is interrupted.

## Approach

Validation is split into waves:

- `Wave 1`: real tasks in `stemirkhan/team-agent-platform` with limited blast radius
- `Wave 2`: a resilience drill with a forced host-executor restart during an active run
- `Wave 3`: a task in an external real-world repository after Waves 1 and 2 are stable

## Rules for live tasks

The first wave should use tasks that:

- can realistically be merged;
- have clear acceptance criteria;
- do not require destructive migrations;
- do not touch security-critical authentication flows;
- do not require large refactors;
- make success or failure obvious.

Avoid in the first wave:

- destructive data changes;
- deep architectural rewrites;
- tasks without a clear definition of done;
- changes that are hard to roll back.

## Preflight checklist

Before every run:

1. Check `/diagnostics`.
2. Check `/api/v1/host/readiness`.
3. Confirm the correct published team is selected.
4. Confirm the team startup prompt is configured.
5. Confirm the task has explicit scope and acceptance criteria.

## Wave 1

### Task 1: frontend-only

- GitHub issue: `#18`
- Theme: preserve the active tab in the run details URL
- Goal: validate a small, low-risk UI fix end to end

### Task 2: backend / observability

- GitHub issue: `#19`
- Theme: derive token usage when terminal output lacks `turn.completed`
- Goal: validate a backend-heavy fix and its tests end to end

### Task 3: cross-functional

- GitHub issue: `#20`
- Theme: add `Run again` / `Rerun` as a new run created from an existing run
- Goal: validate UI + backend + lifecycle integration

### Umbrella tracking

- GitHub issue: `#21`
- Purpose: track Wave 1, the resilience drill, and the postmortem

## Wave 2

### Resilience drill

Scenario:

1. Start a real task through the platform.
2. Wait until Codex execution is active.
3. Restart the host executor.
4. Verify:
   - whether the run survives;
   - whether `tmux` reattach or semantic resume occurs;
   - whether auto-recovery events appear in `Activity`;
   - whether the run completes without a manual relaunch.

## Wave 3

### External repository validation

After Waves 1 and 2 succeed:

1. Choose a small real external repository.
2. Pick one frontend, backend, or cross-functional task.
3. Run it through the same published team.
4. Compare the result quality with the runs in `team-agent-platform`.

## What to record for each run

For every run, capture:

- issue number;
- run id;
- PR number or URL;
- selected team;
- whether the startup prompt was materialized;
- whether real sub-agent calls occurred;
- whether checks passed;
- whether manual intervention was needed;
- final outcome: `mergeable` or `not mergeable`;
- a short list of platform problems found during the run.

## Evaluation rubric

### Delivery quality

- scope stayed within the task boundary;
- the diff is coherent;
- checks passed;
- the PR is reviewable and mergeable.

### Orchestration quality

- the correct specialist was invoked when needed;
- there were no false multi-agent claims;
- sub-agent output was useful.

### Operator UX

- `Activity` made the run understandable;
- `Terminal` gave enough operational detail;
- the final status and artifacts were easy to inspect.

### Reliability

- lifecycle behavior was consistent;
- cancel, resume, and recovery behaved correctly;
- no noisy or misleading states appeared.

## Stop conditions

Pause the next wave and fix the platform first if:

- runs regularly fail before draft PR creation;
- orchestration claims do not match the actual trace;
- PR body or summary becomes polluted by terminal output again;
- recovery corrupts session state;
- diffs repeatedly drift outside task scope.

## Exit criteria for Wave 1

Wave 1 is successful when:

- at least 3 real tasks are completed;
- at least one task is cross-functional;
- at least one run shows a confirmed sub-agent spawn;
- at least one run completes all the way to a draft PR;
- the resulting PRs are ready for normal human review without manual rewriting.

## Next step

After the Wave 1 issues are prepared:

1. run them one at a time, not in parallel;
2. write a short postmortem after each run;
3. only then move on to the resilience drill.
