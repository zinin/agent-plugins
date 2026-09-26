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
| [mesh-review](https://github.com/zinin/mesh-review) | Multi-model code and design review from inside the session; Claude Code installs mesh-exec and session-relay with it |
| [claude-md](https://github.com/zinin/claude-md) | Write and refactor CLAUDE.md files |
| [build-forge](https://github.com/zinin/build-forge) | Build/test/lint delegation and JVM/Android dependency updates |
| [atlassian-scout](https://github.com/zinin/atlassian-scout) | Jira and Confluence analysis, bug and feature investigation in code |
| [prd-flow](https://github.com/zinin/prd-flow) | Idea to PRD to tasks |
| [herdr-review](https://github.com/zinin/herdr-review) | Multi-agent code review inside herdr |
| [codex-base-review](https://github.com/zinin/codex-base-review) | Codex-style review against the base branch |

## Where each plugin works

| Plugin | Claude Code | Grok | Codex |
|---|---|---|---|
| mesh-exec | ✓ | ✓ | codex-exec, grok-exec: ✓ in a trusted folder or with `-s workspace-write`, plus `--add-dir ~/.local/state/mesh`, the CLI's home writable and network on (see its README); ext-claude-exec: — in `codex exec`, Codex refuses its `rm -f` step; gemini-exec: not verified — no Gemini credentials on the test machine (the Codex side — skill, loader, run dir — worked); no executor agents — Codex has no plugin agents |
| session-relay | ✓ | ✓; do-plan's STOP fires only when a turn ends | prompt generators and pause: ✓ in a writable workspace (a trusted folder or `-s workspace-write`); do-plan refuses — no context signal |
| mesh-review | ✓ | ✓ | not supported — dispatches plugin agents |
| claude-md | ✓ | ✓ | installs; Codex reads AGENTS.md, not CLAUDE.md |
| build-forge | ✓ | ✓ | deps-update and the updaters: ✓ in a trusted folder or with `-s workspace-write`, with network on (`-c sandbox_workspace_write.network_access=true`); build needs the build-runner agent |
| atlassian-scout | ✓ | ✓ | ✓ with `[mcp_servers.mcp-atlassian]` in Codex's `config.toml` |
| prd-flow | ✓ | ✓ | ✓ — the interview starts (`codex exec` stops at its first question) |
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

If claude-prd was disabled, disable prd-flow the same way: `claude plugin disable prd-flow@zinin`.

Then move the configs: copy the mesh config to `~/.config/mesh/config.yaml` (mode 600) —
mesh-exec's README, "Moving from claude-mesh"; if it set `runtime.dispatch_model`, write
`dispatch_model: <model>` to `~/.config/session-relay/config.yaml` — session-relay's README,
"Moving from claude-mesh". `--keep-data` above keeps the old config until you have copied it.

Grok needs no step of its own: it loads what Claude Code installed, and `grok inspect` lists the
new names. In Codex: `codex plugin marketplace add zinin/agent-plugins`, then
`codex plugin add <name>@zinin` for each plugin you use there.

The catalog was `zinin/claude-plugins`; GitHub redirects that address, so an existing
`zinin` catalog keeps working and needs no re-adding.

## Codex follow-up

What does not work in Codex yet is tracked for a separate change:

- mesh-exec looks for its own root only in Claude Code's and Grok's plugin directories, not in
  Codex's plugin cache: its skills' fences stop with "mesh-exec plugin root not found" unless the
  model fills in the path Codex shows for the skill.
- `codex exec` refuses commands that contain `rm -f`, and the preflights of ext-claude-exec and
  grok-exec do: ext-claude-exec never starts, and grok-exec got through only because the model
  rewrote the command.
- A mesh-exec run has to stay in the foreground: a background job does not outlive the
  `codex exec` turn.
- Inside Codex's sandbox `$$` is always 2, so every mesh-exec run directory gets the same `-2-`
  suffix; two runs of one task in the same second would share a directory.
- Codex does not substitute `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_SKILL_DIR}` in skill text: the
  model has to find the plugin's path itself (it did for build-forge's helpers; atlassian-scout's
  attachment download was not exercised).
- build-forge's Google Maven helper reports a network failure as "Group not found" — what Codex's
  default sandbox, which has no network, produces.
