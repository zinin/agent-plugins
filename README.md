# zinin/agent-plugins

Agent plugins by [zinin](https://github.com/zinin) for Claude Code, Grok and Codex.

## Add the catalog

| Harness | Command |
|---|---|
| Claude Code | `/plugin marketplace add zinin/agent-plugins`, then `/plugin install <name>@zinin` |
| Grok | nothing when Claude Code has the plugins — Grok loads what Claude Code installed; otherwise `grok plugin marketplace add zinin/agent-plugins`, then `grok plugin install <name> --trust` |
| Codex | `codex plugin marketplace add zinin/agent-plugins`, then `codex plugin add <name>@zinin` |

## Plugins

| Plugin | What it does |
|---|---|
| [mesh-exec](https://github.com/zinin/mesh-exec) | Run a prompt through another model's CLI — Codex, Gemini, Grok, Claude Code, alt-provider models — with logging and a watchdog |
| [session-relay](https://github.com/zinin/session-relay) | Run a plan until the context fills up, pause at a clean checkpoint, hand the work to a fresh session |
| [mesh-review](https://github.com/zinin/mesh-review) | Multi-model code and design review from inside the session; installs mesh-exec and session-relay with it |
| [claude-md](https://github.com/zinin/claude-md) | Write and refactor CLAUDE.md files |
| [build-forge](https://github.com/zinin/build-forge) | Build/test/lint delegation and JVM/Android dependency updates |
| [atlassian-scout](https://github.com/zinin/atlassian-scout) | Jira and Confluence analysis, bug and feature investigation in code |
| [prd-flow](https://github.com/zinin/prd-flow) | Idea to PRD to tasks |
| [herdr-review](https://github.com/zinin/herdr-review) | Multi-agent code review inside herdr |
| [codex-base-review](https://github.com/zinin/codex-base-review) | Codex-style review against the base branch |

## Where each plugin works

| Plugin | Claude Code | Grok | Codex |
|---|---|---|---|
| mesh-exec | ✓ | ✓ | skills: smoke; no executor agents — Codex has no plugin agents |
| session-relay | ✓ | ✓ | prompt generators and pause: smoke; do-plan refuses — no context signal |
| mesh-review | ✓ | ✓ | not supported — dispatches plugin agents |
| claude-md | ✓ | ✓ | installs; Codex reads AGENTS.md, not CLAUDE.md |
| build-forge | ✓ | ✓ | deps-update and the updaters: smoke; build needs the build-runner agent |
| atlassian-scout | ✓ | ✓ | smoke |
| prd-flow | ✓ | ✓ | smoke |
| herdr-review | ✓ | ✓ | ✓ (see its README) |
| codex-base-review | ✓ | ✓ | ✓ |

## Moving from the claude-* plugins

claude-mesh became mesh-exec, session-relay, mesh-review and claude-md; claude-forge is
build-forge, claude-atlassian is atlassian-scout, claude-prd is prd-flow. In Claude Code:

```
claude plugin uninstall claude-mesh@zinin --keep-data
claude plugin uninstall claude-forge@zinin
claude plugin uninstall claude-atlassian@zinin
claude plugin uninstall claude-prd@zinin
claude plugin marketplace update zinin
claude plugin install mesh-exec@zinin
claude plugin install session-relay@zinin
claude plugin install claude-md@zinin
claude plugin install build-forge@zinin
claude plugin install atlassian-scout@zinin
claude plugin install prd-flow@zinin
claude plugin install mesh-review@zinin    # optional
```

Then copy the mesh config to its new place — mesh-exec's README, "Moving from claude-mesh".
The catalog was `zinin/claude-plugins`; GitHub redirects that address, so an existing
`zinin` catalog keeps working and needs no re-adding.
