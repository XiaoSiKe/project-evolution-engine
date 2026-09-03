# Repeated public-project evaluation

This evaluation extends the v0.2.0 example-app pilot with two maintained public projects: HTTPX and Datasette. The fixed tasks and source commits are in [cases.json](cases.json). There are two independent runs per condition per project: eight coding runs in total.

## Conditions and boundaries

- Each project uses the same initial code, original request, dependency environment and neutral final-report schema in both conditions.
- Baseline agents must not load Skills. Skill agents receive the exact frozen project-evolution-engine package. Neither condition may load external specialist Skills or another trial's code, use the network, install dependencies, create agents, commit or publish.
- A separate real Serena and codebase-convergence integration check exercises optional tools. Its outcome is not mixed into the core-only comparison.
- Codex CLI reuses the local user's saved configuration and authentication. No model override or global configuration change is made. The manifest records the configured model name, reasoning effort and CLI version; this does not independently establish which model a custom provider actually serves.
- Cases, acceptance programs and Skill bytes are frozen before dispatch. The report schema provides a reporting format, not an expected implementation.

The Datasette preflight found an existing explicit-primary-key blob CSV defect. Repairing that integration blocker is included in the raw request for both conditions. Its cause and a reference implementation are withheld. The original CSV regression selection has one expected failure; the original HTTPX regression selection passes.

## Prepare pinned sources and runtimes

Use new temporary directories. Clone the repositories and check out the exact commits in the catalog into directories named `httpx` and `datasette`. Source snapshots include regular files and exclude Git data, dependencies, caches, build output, Serena metadata and generated egg-info.

The measured runs use Python 3.12 with separate dependency environments:

```bash
uv venv --python 3.12 /tmp/evolution-httpx-python
uv pip install --python /tmp/evolution-httpx-python/bin/python -r evals/repeated-projects/httpx-requirements.lock.txt
uv venv --python 3.12 /tmp/evolution-datasette-python
uv pip install --python /tmp/evolution-datasette-python/bin/python -r evals/repeated-projects/datasette-requirements.lock.txt
uv pip install --python /tmp/evolution-datasette-python/bin/python /tmp/evolution-sources/datasette
python3 scripts/repeated_project_eval.py prepare --output /tmp/evolution-repeated --sources /tmp/evolution-sources --httpx-python /tmp/evolution-httpx-python/bin/python --datasette-python /tmp/evolution-datasette-python/bin/python
```

Preparation initializes isolated Git repositories, captures baseline hashes and freezes the Skill and acceptance files. It refuses a nonempty output directory. Keep interpreter paths inside their virtualenv instead of resolving interpreter symlinks.

## Run local coding agents

This step uses the signed-in user's normal Codex allowance. It is an explicit local evaluation command, not a GitHub Actions step:

```bash
python3 scripts/repeated_project_eval.py run --manifest /tmp/evolution-repeated/manifest.json --trials 1 2 3 4 5 6 7 8 --workers 2
python3 scripts/repeated_project_eval.py evaluate --manifest /tmp/evolution-repeated/manifest.json --trials 1 2 3 4 5 6 7 8
```

The CLI uses an ephemeral session, the workspace-write sandbox and the supplied JSON report schema. Agent event streams remain in local artifacts. Do not upload authentication files, global configuration, system instructions or reasoning transcripts.

The evaluator compares the report with actual file changes, rejects unrelated/protected edits, requires a test change, and executes independent behavior checks. It verifies a copy of the final implementation. Unchanged upstream tests are overlaid into that copy so package-style test imports cannot accidentally test the pristine source instead of the candidate. The original candidate must remain unchanged during verification.

## Interpreting quality and cost

The protocol records per-run wall time, commands, additional tool calls, unanswered final questions and the CLI's actual `turn.completed` usage fields. Cached-input and reasoning-output subtotals are retained separately, not added again to their parent token totals.

These are coding-agent measurements. They exclude source preparation, evaluator execution, optional integration work and maintainer review; they are not a bill or a measurement of the entire release process. No unobserved dollar costs are inferred. A timeout, missing usage event or failed run remains visible.

Two runs per condition provide observations and reproducibility, not statistical significance or a universal efficiency claim. Report all runs, including unsuccessful implementations and infrastructure failures. Preserve the first outcome before any retry or repair.

CLI event behavior is documented in [OpenAI's non-interactive mode guide](https://learn.chatgpt.com/docs/non-interactive-mode). Raw source projects retain their own BSD-3-Clause and Apache-2.0 licenses; they are evaluation subjects and are not bundled in the installable Skill.
