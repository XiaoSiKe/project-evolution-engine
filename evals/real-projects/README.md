# Public application pilots

Two existing open-source application examples extend the synthetic v0.1.0 cases:

- TodoMVC's JavaScript implementation: a frontend clear-completed undo feature.
- Flask's official Flaskr application: publication state with an existing SQLite database upgrade.

These are pinned open-source examples, not production deployments or representative samples of all projects. Original code, request, dependency environment, and inherited evaluator model configuration are matched between the baseline and Skill condition. Each condition has one trial per application. No statistical significance, general uplift, or token-efficiency claim is made from this sample.

## Sources

See [fixed source commits](sources.lock.json), [registered tasks and fixture digests](cases.json), and [retained licenses](THIRD_PARTY_NOTICES.md). Fixtures exclude generated dist, installed dependencies, caches, and instance data. Their remaining bytes are checked by the unit suite.

## Prepare a local experiment

Use Python 3.12 and Node 24.16.0. Install the test dependencies outside any business project:

```bash
npm ci --prefix evals/real-projects/node --ignore-scripts --no-audit --no-fund
uv venv --python 3.12 /tmp/evolution-pilot-python
uv pip install --python /tmp/evolution-pilot-python/bin/python -r evals/real-projects/requirements.lock.txt
python3 scripts/real_project_eval.py self-check --python /tmp/evolution-pilot-python/bin/python
python3 scripts/real_project_eval.py prepare --output /tmp/evolution-paired-trials --python /tmp/evolution-pilot-python/bin/python
```

The output must be new or empty. Preparation creates four independent application copies, a frozen Skill copy, a neutral reporting contract, and input hashes. Both frontend copies use the same installed dependencies. The virtualenv executable path is retained rather than resolving its symlink to a different Python environment.

## Independent execution

Give each fresh agent only its application path, original request, supplied runtime, and the neutral reporting contract. The Skill condition additionally receives the frozen Skill path. The baseline condition is instructed not to load Skills. Do not share the other condition's work, this directory's oracles, or expected answers.

No agent may publish, modify shared dependencies, contact real application users, or run a migration against real data. All updates happen in the isolated application copy.

These controls concern explicit loading of Skills; they do not imply that the underlying model has never encountered similar patterns in training.

## Evaluate actual results

After the agent writes its report outside the application:

```bash
python3 scripts/real_project_eval.py evaluate --manifest /tmp/evolution-paired-trials/manifest.json --trial 1
```

Run for each trial ID. The evaluator rejects changed acceptance checks, compares reported and observed file changes, and executes the fixed checks. Overall success requires passing behavior, a matching completed report, no unresolved decisions, and unchanged candidate source during verification. A behavioral pass is also recorded separately. It builds the frontend in a temporary validation copy and exercises its generated app through jsdom. Flaskr is checked through its HTTP test client, SQLite data, migration CLI, and the unchanged upstream tests.

Source-directory symlinks are rejected rather than silently omitted from the diff. The explicitly shared node_modules directory remains excluded. Re-evaluation uses a new temporary build copy and updates the score; preserve the first score if evaluating a subsequent implementation attempt.

The frontend DOM checks do not measure visual layout in a real browser. Evaluator wall time is recorded for reproducibility, not as a measure of agent productivity. Questions in a report are self-reported decisions, not a complete trace of every internal deliberation.

CI validates the pristine fixtures and confirms the acceptance checks reject missing new features. CI does not rerun the independent coding agents. Published trial outcomes must remain separate from these infrastructure checks.

## Replay the published v0.2.0 implementations

After preparing a new experiment directory with the documented dependencies, apply a published patch and use its report. For example, from the repository root:

```bash
git -C /tmp/evolution-paired-trials/trial-01 apply --check "$PWD/evals/results/v0.2.0/trial-01.patch"
git -C /tmp/evolution-paired-trials/trial-01 apply "$PWD/evals/results/v0.2.0/trial-01.patch"
cp evals/results/v0.2.0/trial-01.report.json /tmp/evolution-paired-trials/result-01.json
python3 scripts/real_project_eval.py evaluate --manifest /tmp/evolution-paired-trials/manifest.json --trial 1
```

Repeat with 02, 03, and 04 for the other trials. This reconstructs the recorded implementations; it does not run new coding agents. Unit tests verify each patch reconstructs the exact recorded file hashes. See [published outcomes](../results/v0.2.0/results.json), [maintainer replay](../results/v0.2.0/published-replay.json), and the [Chinese verification report](../../docs/verification.md).
