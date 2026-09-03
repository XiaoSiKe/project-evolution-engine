# Sources and adaptation

Reference snapshot: 2026-09-03. This package contains rewritten workflow guidance and user-authorized tool adaptations. Source documents are research material, not additional runtime instructions.

## User-owned predecessor

[XiaoSiKe/codebase-convergence](https://github.com/XiaoSiKe/codebase-convergence/tree/4d413b3184b9c91e122b093384d67bcf0d89a92f) at `4d413b3184b9c91e122b093384d67bcf0d89a92f` supplied the two core disciplines, collector, safe installer, fixture materialization, diff reconciliation, and reusable tool tests. This reuse was explicitly authorized by the owner. The predecessor does not declare a separate open-source license; this project does not label it MIT retroactively.

The update workflow replaces defect-only admission with an authorized behavior delta. Optional repair remains evidence-driven. No existing project files are modified by installing this Skill.

## External references

| Source at fixed commit | Adaptation boundary |
| --- | --- |
| [Fission-AI/OpenSpec @ e062b9572be9](https://github.com/Fission-AI/OpenSpec/blob/e062b9572be933564ba3899d059377dfa1393e32/docs/existing-projects.md) | Incremental behavior deltas and scoped adoption; adapted prose, no upstream runtime. |
| [gotalab/cc-sdd @ 29aee950f4ad](https://github.com/gotalab/cc-sdd/blob/29aee950f4addc36f9aeecb9881c46540e71ecc9/tools/cc-sdd/templates/shared/settings/rules/gap-analysis.md) | Requirement-to-code mapping and extend/new/combined options; adapted to avoid a mandatory spec pipeline. |
| [gsd-build/get-shit-done @ bdcaab2c752d](https://github.com/gsd-build/get-shit-done/blob/bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815/commands/gsd/map-codebase.md) | Project context dimensions and refresh discipline; no mandatory seven-document or multi-agent mapping step. |
| [buildermethods/agent-os @ 475b0cac4c7c](https://github.com/buildermethods/agent-os/blob/475b0cac4c7c5cf2336ad5a663b691a6d3415e05/README.md) | Discover and selectively load project-specific conventions; adapted without a required standards store. |
| [EveryInc/compound-engineering-plugin @ d3c6f12d4b64](https://github.com/EveryInc/compound-engineering-plugin/blob/d3c6f12d4b64d36ec9924bb8cf4ad6bb8e97ce5e/skills/ce-compound/SKILL.md) | Preserve only useful, verified project reasoning; no upstream execution or shipping workflow is bundled. |
| [obra/superpowers @ b36e0829c6d0](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/writing-plans/SKILL.md) | File responsibilities and verifiable increments, paired with verification-before-completion; proportionate checks replace universal ceremony. |
| [oraios/serena @ 813fd98f4fd3](https://github.com/oraios/serena/blob/813fd98f4fd32e0606cb52281467fc055e45a356/README.md) | Optional symbol-navigation guidance and an independent stdio client for an installed official runtime. No upstream server or parser is bundled; observed integration coverage is recorded separately. |
| [LB623/no-negative-echo @ eba9f1d2b4c1](https://github.com/LB623/no-negative-echo/blob/eba9f1d2b4c19e699786a49427189988ad6d8d65/no-negative-echo/SKILL.md) | Generate delivery surfaces from the accepted final state while retaining required compatibility, diagnostic, audit and baseline facts; integrated without its scanner or optional high-assurance process. |
| [Square-Q/subconscious-skill @ 06f8cf2a777c](https://github.com/Square-Q/subconscious-skill/blob/06f8cf2a777cf7e5a4de86a766d08e58c044503c/README.md) | README layout inspiration only: centered hero, icon navigation, badges, section rhythm. No memory features or claims are adopted. |

Licenses are reproduced in [third-party notices](../THIRD_PARTY_NOTICES.md). The examples, eval oracles, and public README claims in this package are its own verification surface.

## Scope of reuse

OpenSpec, cc-sdd, GSD, Agent OS, Compound Engineering, Superpowers, and no-negative-echo are method sources, not hard dependencies. Only actually available optional tools or specialists are invoked. GitNexus and Anthropic feature-dev are not copied into this package.
