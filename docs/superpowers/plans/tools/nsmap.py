"""Namespace map claude-mesh:<component> → <new plugin>:<component>, applied in place.

    python3 nsmap.py FILE...
A quoted 2026-08-29 measurement ("the event listed 69 skills") is left verbatim.
"""
import pathlib, re, sys
EXEC = r"codex-exec|gemini-exec|grok-exec|ext-claude-exec|codex-executor|gemini-executor|grok-executor|ext-claude-executor|claude-executor"
REVIEW = (r"mesh-review|mesh-design-review|auto-decide-disputed|code-review-fresh-session|design-review-fresh-session|"
          r"review-discussion|claude-code-review|codex-code-review|gemini-code-review|grok-code-review|ext-claude-code-review|"
          r"claude-code-reviewer|codex-code-reviewer|gemini-code-reviewer|grok-code-reviewer|ext-claude-code-reviewer")
RELAY = r"do-plan|pause-after-current-task|transfer-session|exec-plan-fresh-session|continue-plan-fresh-session"
def ns_map(line):
    if "the event listed 69 skills" in line:
        return line
    line = re.sub(rf"claude-mesh:({EXEC})\b", r"mesh-exec:\1", line)
    line = re.sub(rf"claude-mesh:({REVIEW})\b", r"mesh-review:\1", line)
    line = re.sub(rf"claude-mesh:({RELAY})\b", r"session-relay:\1", line)
    return line.replace("claude-mesh:claude-md-writer", "claude-md:claude-md-writer")
for f in sys.argv[1:]:
    p = pathlib.Path(f); t = p.read_text()
    new = "".join(ns_map(l) for l in t.splitlines(keepends=True))
    if new != t:
        p.write_text(new)
