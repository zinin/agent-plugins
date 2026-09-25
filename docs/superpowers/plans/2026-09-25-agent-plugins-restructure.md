# Реструктуризация плагинов zinin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разделить `claude-mesh` на `mesh-exec`, `session-relay`, `mesh-review` и `claude-md`, переименовать `claude-forge`, `claude-atlassian`, `claude-prd` и каталог `claude-plugins`, перенести конфиг и состояние на пути XDG и выпустить всё так, чтобы плагины ставились в Claude Code, Grok и Codex.

**Architecture:** Каждый плагин — отдельный git-репозиторий с `.claude-plugin/plugin.json`; каталог `agent-plugins` перечисляет их по git-URL. Три новых репозитория извлекаются из истории `claude-mesh` через `git filter-repo`, сам `claude-mesh` становится `mesh-exec`. `mesh-exec` и `mesh-review` делят конфиг `~/.config/mesh/config.yaml`; `mesh-review` находит установленный `mesh-exec` скриптом `find-mesh-exec.sh`, а свой корень — собственной копией `resolve-plugin-root.sh`. `session-relay` читает свой конфиг из двух ключей и ни от кого не зависит. Вся работа идёт в ветках и проверяется тестами и смоуком; публикация — одним окном в конце.

**Tech Stack:** Bash 4+ и bash-тесты, Python 3 stdlib, yq/jq (загрузчик `mesh-exec`), git + git-filter-repo, gh (GitHub), glab (gitlab.zinin.ru), Claude Code 2.1.282, Grok 1.0.41, Codex 0.156.1.

**Spec:** `docs/superpowers/specs/2026-09-25-agent-plugins-restructure-design.md` (репозиторий `claude-plugins`, ветка `feature/agent-plugins-restructure`).

**Как проверялся план.** Скрипты правок и новые файлы задач 2–4 и 6–11 прогнаны 2026-09-25 на копиях репозиториев (извлечение через `git filter-repo` по командам задачи 1, затем правки по порядку задач); после каждой задачи тесты её репозитория зелёные, кроме известных провалов из Task 2 Step 1. Если скрипт падает с `PATCH FAIL`, исходник изменился после 2026-09-25: остановиться и разобраться, а не подгонять якоря.

## Global Constraints

- **Имена.** Плагины: `mesh-exec`, `session-relay`, `mesh-review`, `claude-md`, `build-forge`, `atlassian-scout`, `prd-flow`; без изменений `herdr-review`, `codex-base-review`. Каталог — репозиторий `zinin/agent-plugins`; имя маркетплейса `zinin` не меняется. Имя скилла `claude-md-writer` не меняется.
- **Версии первых релизов:** `mesh-exec`, `session-relay`, `mesh-review`, `claude-md` — 0.16.0; `build-forge` — 0.3.0; `atlassian-scout` — 0.6.0; `prd-flow` — 0.2.0. В ветках записи CHANGELOG копятся под `## [Unreleased]`; существующие `plugin.json` в ветках не трогаются по версии — их поднимает релизный коммит `chore(release): X.Y.Z` на master (Task 24). Новый `plugin.json` трёх новых плагинов создаётся сразу с `"version": "0.16.0"`: это создание манифеста, а не подъём версии.
- **Пути XDG:** конфиг `mesh` — `${MESH_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/mesh/config.yaml}`; состояние `mesh` — `${XDG_STATE_HOME:-$HOME/.local/state}/mesh`; конфиг `session-relay` — `${XDG_CONFIG_HOME:-$HOME/.config}/session-relay/config.yaml`; состояние `session-relay` — `${XDG_STATE_HOME:-$HOME/.local/state}/session-relay`.
- **Порог `session-relay`:** `stop_tokens` по умолчанию 400000, минимум 150000.
- **Манифесты** только в `.claude-plugin/`. Не создавать `.codex-plugin/`, `.grok-plugin/`, `agents/openai.yaml`, не ставить `disable-model-invocation`.
- **Внутренние переменные** `CLAUDE_MESH_PROVIDER_KIND`, `CLAUDE_MESH_DATA_DIR`, `CLAUDE_MESH_TIMEOUT_*` не переименовываются: это интерфейс между загрузчиком и exec-скиллами, а не имя плагина.
- **Историческая цитата** в `skills/grok-exec/SKILL.md` («the event listed 69 skills — `claude-mesh:mesh-review` among them») остаётся дословной. Старые записи CHANGELOG не меняются.
- **Тесты загрузчика до Task 2 Step 4 — только с `HOME` на пустой каталог.** Старый загрузчик игнорирует `MESH_CONFIG`, находит настоящий `~/.claude/plugins/data/claude-mesh-*/config.yaml` и тест экспорта печатает токены провайдеров в сообщениях о провале. Этот конфиг агент не открывает и не выводит ни при каких обстоятельствах.
- **Конфиг пользователя** агент не копирует, не создаёт и не правит; `~/.config/mesh/config.yaml` и `~/.config/session-relay/config.yaml` готовит пользователь (Task 19).
- **git add только по путям.** В репозиториях лежат неотслеживаемые файлы (`docs/session-transfer-*.md`, `docs/superpowers/**`); `git add -A`, `git add .`, `git commit -a` запрещены. Для переносов — `git mv`, для удалений — `git rm`.
- **Heredoc только с закавыченным разделителем** (`<<'EOF'`, `<<'PY'`): иначе `${CLAUDE_PLUGIN_ROOT}`, `$HOME` и `$(…)` схлопнутся при записи. После записи файла проверять, что литералы на месте.
- **`grep` на этой машине — ugrep 7.8.4.** Для строк с `$(`, кавычками и скобками использовать `grep -F`.
- **Ветка** во всех репозиториях — `feature/agent-plugins-restructure`. В `herdr-review`, `ai-tools`, `wireguard-network` идёт незавершённая работа пользователя — там ветка создаётся во временном worktree от основной ветки (Task 18), рабочая копия пользователя не трогается. Основная ветка `claude-prd` — `main`, остальных — `master`.
- **Действия наружу** — push, создание и переименование репозиториев, PR и MR, слияние, теги, релизы — только после явного «да» пользователя в момент выполнения (Tasks 23–25). До Task 23 ничего не уходит ни на GitHub, ни на gitlab.zinin.ru.
- **Коммиты** после каждой задачи, стиль как в истории репозитория: английские conventional commits в `github.com/zinin/*` и `ai-tools`; русские сообщения в `claude-ebs`, `claude-private-plugins`, `wireguard-network`.
- **Тесты** — `bash <файл>` из корня репозитория; успех — строка `=== Summary: N passed, 0 failed ===` (у `test-do-plan.sh` и `test-check-context-size.sh` — `RESULTS: N passed, 0 failed`) и код 0. У `test-command-sync.sh` допустим `1 skipped`: эталонного документа `docs/superpowers/verification/…` нет в дереве, как и на master. Правило сессии о делегировании сборок к bash-наборам не применяется: агенту build-runner `bash` не разрешён.
- **`docs/superpowers/`** в `claude-plugins` удаляется `git rm -r` последним коммитом ветки перед PR (Task 23).
- **Инструменты плана** лежат в `/opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/` (создаются в Task 1) и уходят вместе с `docs/superpowers/`.

## Review Focus

1. **Старый конфиг на месте, нового нет** (первый запуск после переезда): загрузчик `mesh-exec` завершается кодом 2 и печатает готовую команду `mkdir -p … && cp <старый> <новый> && chmod 600 …`, а обработчики кода 2 в `mesh-review` передают её пользователю. Тесты — Task 2 (Test 1b загрузчика) и Task 11 (`test-missing-config-handler.sh`: оба оркестратора печатают stderr загрузчика и называют файл через `config-path`).
2. **В кеше одновременно `claude-mesh` и новые плагины** (переходный период): `resolve-plugin-root.sh` в `mesh-exec` и в `mesh-review` и `find-mesh-exec.sh` берут новый плагин и никогда — `claude-mesh`. Тесты — Task 4 (тест 6 в `test-resolve-plugin-root.sh` `mesh-exec`: у `claude-mesh` тот же маркер `config-loader.sh`, и его путь сортируется последним) и Task 9 (`test-find-mesh-exec.sh`: только `claude-mesh` в кеше → «не найден»).
3. **`do-plan` запущен там, где нет сигнала о заполнении контекста** (Codex, голый терминал): скилл отказывается с сообщением, а не работает без STOP. Тест — Task 7 (прогон фрагмента шага 1 без `CLAUDECODE` и `GROK_SESSION_ID`).
4. **Опечатка в `~/.config/session-relay/config.yaml`** (`stop_token: 400000`, `stop_tokens: 400k`): ридер падает с именем файла и номером строки, а не берёт значение по умолчанию; шаг 1 `do-plan` останавливается. Тесты — Task 6 (`test-read-config.sh`) и Task 7.
5. **Хук и `do-plan` расходятся в пути состояния** (в том числе при заданном `XDG_STATE_HOME` и при `CLAUDE_PLUGIN_DATA`, указывающем в другое место): файл, который пишет шаг 2, читает хук, и по нему приходит STOP. Тест — Task 8 (сквозной прогон шага 2 и хука).

## Карта задач

| # | Репозиторий | Задача |
|---|-------------|--------|
| 1 | все | Ветки, извлечение трёх новых репозиториев, инструмент `nsmap.py` |
| 2–5 | `claude-mesh` → `mesh-exec` | XDG; удаление ушедшего; имена; манифест и документация |
| 6–8 | `session-relay` | ридер конфига; `do-plan`; хук, остальные скиллы, манифест |
| 9–12 | `mesh-review` | поиск `mesh-exec` и своего корня; команды; скиллы и агенты; манифест |
| 13 | `claude-md` | плагин |
| 14–16 | `build-forge`, `atlassian-scout`, `prd-flow` | переименования |
| 17 | `claude-plugins` → `agent-plugins` | каталог |
| 18 | herdr-review, codex-base-review, ai-tools, claude-private-plugins, claude-ebs, wireguard-network | ссылки снаружи |
| 19 | — | пользователь готовит конфиги |
| 20–22 | — | смоук: Claude Code, Grok, Codex |
| 23–25 | GitHub, gitlab.zinin.ru, машины | публикация веток; окно выпуска; переезд установок |

---

### Task 1: Ветки, извлечение трёх новых репозиториев, инструмент `nsmap.py`

**Репозитории:** `/opt/github/zinin/{claude-mesh,claude-forge,claude-atlassian,claude-prd,claude-plugins}`; создаются `/opt/github/zinin/{session-relay,mesh-review,claude-md}`.

**Files:**
- Create: `/opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py`
- Create (новые локальные репозитории): `/opt/github/zinin/session-relay`, `/opt/github/zinin/mesh-review`, `/opt/github/zinin/claude-md`

**Interfaces:**
- Produces: `python3 /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py FILE...` — переводит `claude-mesh:<компонент>` в `mesh-exec:` / `mesh-review:` / `session-relay:` / `claude-md:` по имени компонента, на месте, пропуская историческую цитату. Используют Tasks 7, 8, 10, 11.
- Produces: в трёх новых репозиториях master — отфильтрованная история `claude-mesh` master (без remote и тегов) и ветка `feature/agent-plugins-restructure`; в `claude-mesh`, `claude-forge`, `claude-atlassian`, `claude-prd` — ветка `feature/agent-plugins-restructure`.

- [ ] **Step 1: Проверить исходное состояние**

```bash
cd /opt/github/zinin
for d in claude-mesh claude-forge claude-atlassian claude-prd; do
  printf '%-18s %-8s dirty-tracked=%s\n' "$d" "$(git -C $d branch --show-current)" \
    "$(git -C $d status --porcelain --untracked-files=no | wc -l)"
done
git -C claude-plugins branch --show-current
for r in session-relay mesh-review claude-md; do test -e "$r" && echo "EXISTS: $r"; done; echo checked
```

Expected: `claude-mesh master dirty-tracked=0`, `claude-forge master 0`, `claude-atlassian master 0`, `claude-prd main 0`, затем `feature/agent-plugins-restructure`, затем только `checked`. Иначе — остановиться и спросить пользователя.

- [ ] **Step 2: Записать инструмент `nsmap.py`**

```bash
mkdir -p /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools
cat > /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py <<'PY'
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
PY
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py && echo syntax-ok
```

Expected: `syntax-ok`.

- [ ] **Step 3: Извлечь `session-relay`**

```bash
cd /opt/github/zinin
git clone --no-local --no-tags --single-branch --branch master /opt/github/zinin/claude-mesh session-relay
cd session-relay
git filter-repo --force \
  --path commands/do-plan.md \
  --path commands/pause-after-current-task.md \
  --path commands/transfer-session.md \
  --path commands/exec-plan-fresh-session.md \
  --path commands/continue-plan-fresh-session.md \
  --path hooks/hooks.json \
  --path hooks/check-context-size.sh \
  --path skills/shared/list-host-models.sh \
  --path skills/shared/tests/test-check-context-size.sh \
  --path skills/shared/tests/test-do-plan.sh \
  --path skills/shared/tests/test-list-host-models.sh \
  --path skills/shared/tests/fixtures/grok-models-2026-08-31.txt \
  --path LICENSE
git ls-files | wc -l
```

Expected: `13`. `filter-repo` сам удаляет remote `origin` и печатает об этом NOTICE.

- [ ] **Step 4: Извлечь `mesh-review`**

```bash
cd /opt/github/zinin
git clone --no-local --no-tags --single-branch --branch master /opt/github/zinin/claude-mesh mesh-review
cd mesh-review
git filter-repo --force \
  --path commands/mesh-review.md \
  --path commands/auto-decide-disputed.md \
  --path commands/code-review-fresh-session.md \
  --path commands/design-review-fresh-session.md \
  --path skills/mesh-design-review/SKILL.md \
  --path skills/claude-code-review/SKILL.md \
  --path skills/codex-code-review/SKILL.md \
  --path skills/gemini-code-review/SKILL.md \
  --path skills/grok-code-review/SKILL.md \
  --path skills/ext-claude-code-review/SKILL.md \
  --path agents/claude-code-reviewer.md \
  --path agents/codex-code-reviewer.md \
  --path agents/gemini-code-reviewer.md \
  --path agents/grok-code-reviewer.md \
  --path agents/ext-claude-code-reviewer.md \
  --path agents/review-discussion.md \
  --path skills/shared/code-review-prompt.md \
  --path skills/shared/render-template.py \
  --path skills/shared/resolve-plugin-root.sh \
  --path skills/shared/tests/test-command-sync.sh \
  --path skills/shared/tests/test-grok-code-review-bindings.sh \
  --path skills/shared/tests/test-render-template.sh \
  --path skills/shared/tests/test-loader-resolution.sh \
  --path skills/shared/tests/test-claude-cli-agents.sh \
  --path skills/shared/tests/test-resolve-plugin-root.sh \
  --path LICENSE
git ls-files | wc -l
```

Expected: `26`.

- [ ] **Step 5: Извлечь `claude-md`**

```bash
cd /opt/github/zinin
git clone --no-local --no-tags --single-branch --branch master /opt/github/zinin/claude-mesh claude-md
cd claude-md
git filter-repo --force --path skills/claude-md-writer/SKILL.md --path LICENSE
git ls-files
```

Expected: `LICENSE` и `skills/claude-md-writer/SKILL.md`.

- [ ] **Step 6: Проверить историю и отсутствие remote и тегов**

```bash
cd /opt/github/zinin
for r in session-relay mesh-review claude-md; do
  printf '%-14s commits=%s remotes=[%s] tags=[%s] branch=%s\n' "$r" "$(git -C $r rev-list --count HEAD)" \
    "$(git -C $r remote)" "$(git -C $r tag | tr '\n' ' ')" "$(git -C $r branch --show-current)"
done
```

Expected (2026-09-25): `session-relay commits=32`, `mesh-review commits=150`, `claude-md commits=5`; `remotes=[]`, `tags=[]`, `branch=master` у всех. Счётчики коммитов вырастут, если в `claude-mesh` master после 2026-09-25 появились коммиты по этим путям, — это нормально.

- [ ] **Step 7: Создать ветки**

```bash
cd /opt/github/zinin
for r in session-relay mesh-review claude-md claude-mesh claude-forge claude-atlassian claude-prd; do
  git -C "$r" switch -c feature/agent-plugins-restructure
done
```

Expected: семь строк `Switched to a new branch 'feature/agent-plugins-restructure'`.

- [ ] **Step 8: Commit (в `claude-plugins`)**

```bash
cd /opt/github/zinin/claude-plugins
git add docs/superpowers/plans/tools/nsmap.py
git commit -m "docs: add the namespace-map tool for the restructure plan"
```

---

### Task 2: mesh-exec — конфиг и состояние на путях XDG

**Репозиторий:** `/opt/github/zinin/claude-mesh`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Modify: `skills/shared/config-loader.sh` — шапка; `resolve_plugin_data` → фиксированные пути; `load_or_die` (подсказка для старого конфига); `validate_runtime`, `cmd_validate`; `cmd_get_flag`; `cmd_get_runtime`; диспетчер (`config-path`); имена временных файлов `mesh-*`.
- Modify: `skills/shared/preflight-env.sh` — строка конфига и подсказки через `config-path`; сообщения про неполную установку.
- Modify: `skills/shared/verify-delegation.sh` — `resolve_plugin_data` спрашивает загрузчик.
- Test: `skills/shared/tests/test-config-loader.sh`, `test-watch-runs.sh`, `test-preflight-env.sh`.

**Interfaces:**
- Produces: `config-loader.sh config-path` — печатает путь конфига (`$MESH_CONFIG`, иначе `${XDG_CONFIG_HOME:-$HOME/.config}/mesh/config.yaml`), без валидации, код 0.
- Produces: `config-loader.sh data-dir` — `${XDG_STATE_HOME:-$HOME/.local/state}/mesh`.
- Produces: нет конфига → код 2; при найденном `~/.claude/plugins/data/claude-mesh-*/config.yaml` stderr содержит `The claude-mesh config is still at <старый>. Move it:` и строку `mkdir -p "<каталог>" && cp "<старый>" "<новый>" && chmod 600 "<новый>"`.
- Produces: `get-flag do_plan_default_stop_tokens` удалён (код 1, `unknown feature`); `get-runtime` без ключа `do_plan_default_stop_tokens`; `validate` предупреждает `runtime.do_plan_default_stop_tokens is ignored: do-plan moved to the session-relay plugin …`.
- Consumes: ничего из других задач.

- [ ] **Step 1: Снять базовую линию провалов**

На этой машине master уже проваливает 5 проверок Go-yq в `test-config-loader.sh` и 2 в `test-preflight-env.sh` (двойники flavor-ов yq против установленного Go-yq v4.53.6); к этой работе они не относятся. Зафиксировать их:

```bash
cd /opt/github/zinin/claude-mesh
B=/tmp/agent-plugins-baseline; mkdir -p "$B"
for t in test-config-loader test-preflight-env; do
  bash skills/shared/tests/$t.sh 2>&1 | grep -E '^\s+FAIL' | sed -E 's/ [—(].*//' | LC_ALL=C sort > "$B/$t.fails"
  echo "$t: $(wc -l < "$B/$t.fails") baseline failures"
done
```

Expected: `test-config-loader: 5 baseline failures`, `test-preflight-env: 2 baseline failures`. Другие числа — записать фактические, дальше сравнивать с ними.

- [ ] **Step 2: Перевести тесты на новые переменные и написать новые тесты**

Скрипт заменяет 211 вызовов `CLAUDE_PLUGIN_DATA=` на `MESH_CONFIG=… XDG_STATE_HOME=…`, переписывает Test 1 и тесты 10/10b/10c загрузчика, добавляет Tests 1b и 1c, правит `test-watch-runs.sh` и `test-preflight-env.sh` (новые имена временных файлов `mesh-*`, подсказка с `mkdir -p`).

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib, sys, re
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))

T = "skills/shared/tests/test-config-loader.sh"
t = pathlib.Path(T).read_text()
n1 = t.count('CLAUDE_PLUGIN_DATA="$TDIR"'); n2 = t.count('CLAUDE_PLUGIN_DATA="$TMPD"')
if (n1, n2) != (209, 2): sys.exit(f"PATCH FAIL {T}: expected 209/2 CLAUDE_PLUGIN_DATA uses, found {n1}/{n2}")
t = t.replace('CLAUDE_PLUGIN_DATA="$TDIR"', 'MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR"')
t = t.replace('CLAUDE_PLUGIN_DATA="$TMPD"', 'MESH_CONFIG="$TMPD/config.yaml" XDG_STATE_HOME="$TMPD"')
pathlib.Path(T).write_text(t)

rep(T, '''ERR=$(mktemp)
CLAUDE_PLUGIN_DATA=/nonexistent "$LOADER" validate 2>"$ERR"
RC=$?
assert_exit "exits with rc=2 (distinct 'config not found')" "2" "$RC"
assert_stderr_contains "mentions missing config.yaml" "config.yaml not found" "$ERR"
rm -f "$ERR"
''', '''ERR=$(mktemp)
NOHOME=$(mktemp -d)   # HOME without a claude-mesh config: the machine's own must not leak in
env -u XDG_CONFIG_HOME -u XDG_STATE_HOME HOME="$NOHOME" MESH_CONFIG=/nonexistent/config.yaml "$LOADER" validate 2>"$ERR"
RC=$?
assert_exit "exits with rc=2 (distinct 'config not found')" "2" "$RC"
assert_stderr_contains "names the missing file" "config.yaml not found at /nonexistent/config.yaml" "$ERR"
assert_stderr_contains "no old config: generic advice" "Copy config.example.yaml" "$ERR"
rm -rf "$ERR" "$NOHOME"

echo "=== Test 1b: an old claude-mesh config gets the exact move command ==="
# First run after the rename: the config still sits in Claude Code's plugin-data dir.
H=$(mktemp -d)
mkdir -p "$H/.claude/plugins/data/claude-mesh-zinin"
cp "$FIXTURES/valid-minimal.yaml" "$H/.claude/plugins/data/claude-mesh-zinin/config.yaml"
ERR=$(mktemp)
env -u MESH_CONFIG -u XDG_CONFIG_HOME -u XDG_STATE_HOME HOME="$H" "$LOADER" validate 2>"$ERR"
RC=$?
assert_exit "still rc=2: nothing is copied for the user" "2" "$RC"
assert_stderr_contains "names the new path" "config.yaml not found at $H/.config/mesh/config.yaml" "$ERR"
assert_stderr_contains "names the old copy" "claude-mesh config is still at $H/.claude/plugins/data/claude-mesh-zinin/config.yaml" "$ERR"
assert_stderr_contains "prints the cp command" "cp \\"$H/.claude/plugins/data/claude-mesh-zinin/config.yaml\\" \\"$H/.config/mesh/config.yaml\\"" "$ERR"
assert_eq_str "the new file was not created" "absent" "$([ -e "$H/.config/mesh/config.yaml" ] && echo present || echo absent)"
rm -rf "$H" "$ERR"

echo "=== Test 1c: config-path and data-dir follow XDG and MESH_CONFIG ==="
H=$(mktemp -d)
assert_eq_str "config-path default" "$H/.config/mesh/config.yaml" \\
    "$(env -u MESH_CONFIG -u XDG_CONFIG_HOME HOME="$H" "$LOADER" config-path)"
assert_eq_str "config-path under XDG_CONFIG_HOME" "$H/xdg/mesh/config.yaml" \\
    "$(env -u MESH_CONFIG HOME="$H" XDG_CONFIG_HOME="$H/xdg" "$LOADER" config-path)"
assert_eq_str "MESH_CONFIG wins over XDG" "$H/other.yaml" \\
    "$(HOME="$H" XDG_CONFIG_HOME="$H/xdg" MESH_CONFIG="$H/other.yaml" "$LOADER" config-path)"
assert_eq_str "data-dir default" "$H/.local/state/mesh" \\
    "$(env -u XDG_STATE_HOME HOME="$H" "$LOADER" data-dir)"
assert_eq_str "data-dir under XDG_STATE_HOME" "$H/st/mesh" \\
    "$(HOME="$H" XDG_STATE_HOME="$H/st" "$LOADER" data-dir)"
assert_eq_str "CLAUDE_PLUGIN_DATA no longer moves anything" "$H/.local/state/mesh" \\
    "$(env -u XDG_STATE_HOME HOME="$H" CLAUDE_PLUGIN_DATA="$H/plugin-data" "$LOADER" data-dir)"
rm -rf "$H"
''')

rep(T, '''echo "=== Test 10: runtime.do_plan_default_stop_tokens below 150000 ==="
TDIR=$(mktemp -d)
cp "$FIXTURES/invalid-runtime-do-plan-tokens.yaml" "$TDIR/config.yaml"
ERR=$(mktemp)
MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR" "$LOADER" validate 2>"$ERR"
RC=$?
assert_exit "exits non-zero" "1" "$RC"
assert_stderr_contains "names do_plan_default_stop_tokens" "do_plan_default_stop_tokens" "$ERR"
assert_stderr_contains "mentions 150000 lower bound" "150000" "$ERR"
rm -rf "$TDIR" "$ERR"

# iter-2 CONCERN-11: load_or_die exits 2 (not 1) when config.yaml is missing.
echo "=== Test 10b: get-flag returns rc=2 when config.yaml missing ==="
ERR=$(mktemp)
CLAUDE_PLUGIN_DATA=/nonexistent "$LOADER" get-flag do_plan_default_stop_tokens 2>"$ERR"
RC=$?
assert_exit "get-flag exits rc=2 on missing config" "2" "$RC"
assert_stderr_contains "names missing config.yaml" "config.yaml not found" "$ERR"
rm -f "$ERR"

# iter-2 CRITICAL-2: cmd_get_flag must run validate_runtime before reading the typed scalar.
echo "=== Test 10c: get-flag do_plan_default_stop_tokens enforces ≥150000 floor ==="
TDIR=$(mktemp -d)
cp "$FIXTURES/invalid-runtime-do-plan-tokens.yaml" "$TDIR/config.yaml"
ERR=$(mktemp)
MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR" "$LOADER" get-flag do_plan_default_stop_tokens 2>"$ERR"
RC=$?
assert_exit "get-flag exits rc=1 on below-floor value" "1" "$RC"
assert_stderr_contains "mentions 150000 lower bound" "150000" "$ERR"
rm -rf "$TDIR" "$ERR"
''', '''echo "=== Test 10: runtime.do_plan_default_stop_tokens is ignored, with a warning ==="
# do-plan moved to session-relay. A config copied over from claude-mesh keeps the key, and
# must still validate — `validate` names it so it gets deleted.
TDIR=$(mktemp -d)
cp "$FIXTURES/invalid-runtime-do-plan-tokens.yaml" "$TDIR/config.yaml"
ERR=$(mktemp)
MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR" "$LOADER" validate 2>"$ERR"
RC=$?
assert_exit "a below-floor value no longer fails validate" "0" "$RC"
assert_stderr_contains "names the ignored key" "do_plan_default_stop_tokens is ignored" "$ERR"
assert_stderr_contains "points at session-relay" "session-relay" "$ERR"
rm -rf "$TDIR" "$ERR"

# iter-2 CONCERN-11: load_or_die exits 2 (not 1) when config.yaml is missing.
echo "=== Test 10b: get-flag returns rc=2 when config.yaml missing ==="
ERR=$(mktemp)
NOHOME=$(mktemp -d)
env -u XDG_CONFIG_HOME HOME="$NOHOME" MESH_CONFIG=/nonexistent/config.yaml "$LOADER" get-flag has_codex 2>"$ERR"
RC=$?
assert_exit "get-flag exits rc=2 on missing config" "2" "$RC"
assert_stderr_contains "names missing config.yaml" "config.yaml not found" "$ERR"
rm -rf "$ERR" "$NOHOME"

echo "=== Test 10c: get-flag do_plan_default_stop_tokens is gone ==="
TDIR=$(mktemp -d)
cp "$FIXTURES/valid-minimal.yaml" "$TDIR/config.yaml"
ERR=$(mktemp)
MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR" "$LOADER" get-flag do_plan_default_stop_tokens 2>"$ERR"
RC=$?
assert_exit "the removed feature is unknown (rc=1)" "1" "$RC"
assert_stderr_contains "says unknown feature" "unknown feature" "$ERR"
GOT=$(MESH_CONFIG="$TDIR/config.yaml" XDG_STATE_HOME="$TDIR" "$LOADER" get-runtime | jq -r 'has("do_plan_default_stop_tokens")')
assert_eq_str "get-runtime no longer carries the key" "false" "$GOT"
rm -rf "$TDIR" "$ERR"
''')
if pathlib.Path(T).read_text().count('CLAUDE_PLUGIN_DATA') != 2: sys.exit("PATCH FAIL: expected exactly the 2 CLAUDE_PLUGIN_DATA uses of Test 1c")

W = "skills/shared/tests/test-watch-runs.sh"
rep(W, "# fixture (same CLAUDE_PLUGIN_DATA trick as test-config-loader.sh) so the suite tests the",
       "# fixture (same MESH_CONFIG trick as test-config-loader.sh) so the suite tests the")
rep(W, 'export CLAUDE_PLUGIN_DATA="$CFGDIR"', 'export MESH_CONFIG="$CFGDIR/config.yaml"')

F = "skills/shared/tests/test-preflight-env.sh"
rep(F, 'OUT="$(env CLAUDE_PLUGIN_DATA="$CFG_DIR" TMPDIR="$CFG_DIR" \\', 'OUT="$(env MESH_CONFIG="$CFG_DIR/config.yaml" XDG_STATE_HOME="$CFG_DIR" TMPDIR="$CFG_DIR" \\')
rep(F, 'env CLAUDE_PLUGIN_DATA="$ICFG" TMPDIR="$ICFG" \\', 'env MESH_CONFIG="$ICFG/config.yaml" XDG_STATE_HOME="$ICFG" TMPDIR="$ICFG" \\')
rep(F, "claude-mesh-env-*", "mesh-env-*", count=4)
rep(F, 'assert_match "…and the one-line fix is hinted"       "hint: cp config.example.yaml" "$OUT"',
       'assert_match "…and the one-line fix is hinted"       "hint: mkdir -p" "$OUT"\nassert_match "…which copies the example into place"   "&& cp config.example.yaml" "$OUT"')
# The suites fake a failing mktemp by its template name; the loader's templates were renamed.
rep(T, 'for a in "\\$@"; do case "\\$a" in claude-mesh-yqprobe-*) exit 1 ;; esac; done',
       'for a in "\\$@"; do case "\\$a" in mesh-yqprobe-*) exit 1 ;; esac; done')
rep(F, 'for a in "\\$@"; do case "\\$a" in claude-mesh-cfg-*) exit 1 ;; esac; done',
       'for a in "\\$@"; do case "\\$a" in mesh-cfg-*) exit 1 ;; esac; done')
print("task2 tests patch applied")
PY
```

Expected: `task2 tests patch applied`.

- [ ] **Step 3: Убедиться, что новые тесты падают — только с пустым HOME**

До Step 4 загрузчик ещё старый: `MESH_CONFIG` он не знает и ищет конфиг в `~/.claude/plugins/data/claude-mesh-*` — настоящий, с токенами провайдеров, — а тест экспорта печатает значения переменных в сообщении о провале. Поэтому `HOME` подменяется пустым каталогом:

```bash
cd /opt/github/zinin/claude-mesh
EMPTY_HOME=$(mktemp -d)
HOME="$EMPTY_HOME" bash skills/shared/tests/test-config-loader.sh 2>&1 | grep -E '^\s+FAIL' | sed -E 's/ [—(].*//' \
  | LC_ALL=C sort | LC_ALL=C comm -13 /tmp/agent-plugins-baseline/test-config-loader.fails - > /tmp/agent-plugins-baseline/red.txt
rm -rf "$EMPTY_HOME"
wc -l < /tmp/agent-plugins-baseline/red.txt
grep -cE 'FAIL: (names the missing file|names the new path|config-path default|a below-floor value no longer fails validate|the removed feature is unknown)$' /tmp/agent-plugins-baseline/red.txt
grep -cE 'got .[A-Za-z0-9]{20,}' /tmp/agent-plugins-baseline/red.txt
```

Expected: `70` новых провалов (±, если master изменился), `5` — все ключевые новые проверки падают, `0` — ни одного значения, похожего на токен (код выхода блока 1: так `grep -c` сообщает о нуле совпадений).

- [ ] **Step 4: Изменить загрузчик, preflight и verify-delegation**

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))

L = "skills/shared/config-loader.sh"
rep(L, """# config-loader.sh — parses, validates, and exports claude-mesh config.
#
# Usage:
#   config-loader.sh validate           # validate only, exit 0/1
#   config-loader.sh data-dir           # print resolved plugin data dir (no validation; works pre-config)
#   config-loader.sh export <model-id>  # validate + print `export KEY=val` lines
#
# Data dir resolved by resolve_plugin_data(): $CLAUDE_PLUGIN_DATA if set (hook context),
# else the ~/.claude/plugins/data/claude-mesh-* dir with config.yaml, else claude-mesh-zinin.
# (Task 2.5, CC 2.1.156: $CLAUDE_PLUGIN_DATA is EMPTY in skill Bash-tool calls.)
# Config: $PLUGIN_DATA/config.yaml
""", """# config-loader.sh — parses, validates, and exports the mesh config (mesh-exec, mesh-review).
#
# Usage:
#   config-loader.sh validate           # validate only, exit 0/1
#   config-loader.sh config-path        # print the config file path (no validation; works pre-config)
#   config-loader.sh data-dir           # print the state dir holding runs/ and state/ (no validation)
#   config-loader.sh export <model-id>  # validate + print `export KEY=val` lines
#
# Config: $MESH_CONFIG, else ${XDG_CONFIG_HOME:-~/.config}/mesh/config.yaml.
# State:  ${XDG_STATE_HOME:-~/.local/state}/mesh.
# Both are fixed paths, the same under Claude Code, Grok and Codex. No harness plugin-data
# directory is involved, so an uninstall never deletes the config and a rename never moves it.
""")
rep(L, """resolve_plugin_data() {
    # CLAUDE_PLUGIN_DATA is set in HOOK contexts but EMPTY in skill Bash-tool calls
    # (Task 2.5, CC 2.1.156). Resolve robustly.
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then printf '%s\\n' "$CLAUDE_PLUGIN_DATA"; return; fi
    local d cand=""
    for d in "$HOME"/.claude/plugins/data/claude-mesh-*; do
        [ -d "$d" ] || continue
        if [ -f "$d/config.yaml" ]; then printf '%s\\n' "$d"; return; fi
        [ -z "$cand" ] && cand="$d"
    done
    [ -n "$cand" ] && { printf '%s\\n' "$cand"; return; }
    printf '%s\\n' "$HOME/.claude/plugins/data/claude-mesh-zinin"
}
PLUGIN_DATA="$(resolve_plugin_data)"
CONFIG_FILE="$PLUGIN_DATA/config.yaml"
""", """CONFIG_FILE="${MESH_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/mesh/config.yaml}"
PLUGIN_DATA="${XDG_STATE_HOME:-$HOME/.local/state}/mesh"
""")
rep(L, """    if [ ! -f "$CONFIG_FILE" ]; then
        echo "config.yaml not found at $CONFIG_FILE. Copy config.example.yaml from the plugin install dir." >&2
        exit 2
    fi
""", """    if [ ! -f "$CONFIG_FILE" ]; then
        echo "config.yaml not found at $CONFIG_FILE." >&2
        # Up to 0.15.0 the config lived in Claude Code's plugin-data dir. Name the move instead
        # of the generic advice when that copy is still there — the first run after the rename
        # lands here. Only the message changes: nothing is copied, the file is the user's.
        local old="" d
        for d in "$HOME"/.claude/plugins/data/claude-mesh-*/config.yaml; do
            [ -f "$d" ] && { old="$d"; break; }
        done
        if [ -n "$old" ]; then
            echo "The claude-mesh config is still at $old. Move it:" >&2
            echo "  mkdir -p \\"${CONFIG_FILE%/*}\\" && cp \\"$old\\" \\"$CONFIG_FILE\\" && chmod 600 \\"$CONFIG_FILE\\"" >&2
        else
            echo "Copy config.example.yaml from the mesh-exec plugin directory there and fill in your providers." >&2
        fi
        exit 2
    fi
""")
rep(L, 'die "yq not found. claude-mesh accepts either flavor:', 'die "yq not found. mesh-exec accepts either flavor:')
rep(L, "    # claude-mesh uses GNU-only utilities:", "    # mesh-exec uses GNU-only utilities:")
rep(L, "mktemp -d -t claude-mesh-yqprobe-XXXXXX", "mktemp -d -t mesh-yqprobe-XXXXXX")
rep(L, "mktemp -t claude-mesh-cfg-XXXXXX.json", "mktemp -t mesh-cfg-XXXXXX.json")
rep(L, "core), but this yq turned them into booleans. claude-mesh needs Python-yq", "core), but this yq turned them into booleans. mesh-exec needs Python-yq")
rep(L, "known-good document. claude-mesh accepts Python-yq", "known-good document. mesh-exec accepts Python-yq")
rep(L, 'mktemp -t "claude-mesh-env-XXXXXX.sh"', 'mktemp -t "mesh-env-XXXXXX.sh"')
rep(L, "printf '# claude-mesh env — created", "printf '# mesh env — created")
rep(L, """    local dps
    dps=$(jq -r '.runtime.do_plan_default_stop_tokens // ""' "$CONFIG_JSON")
    if [ -n "$dps" ]; then
        [[ "$dps" =~ ^[1-9][0-9]*$ ]] \\
            || die "runtime.do_plan_default_stop_tokens: must be positive integer, got \\"$dps\\""
        [ "$dps" -ge 150000 ] \\
            || die "runtime.do_plan_default_stop_tokens: must be >= 150000 (hook does not emit below 150k), got $dps"
    fi

""", "")
rep(L, """cmd_validate() {
    load_or_die
    validate_all
}
""", """cmd_validate() {
    load_or_die
    validate_all
    # do-plan left for the session-relay plugin, which has a config of its own. The key is
    # still accepted, so a config copied over from claude-mesh validates as it is; `validate`
    # names it once so it gets cleaned up — the getters stay quiet, they run many times a run.
    if [ -n "$(jq -r '.runtime.do_plan_default_stop_tokens // ""' "$CONFIG_JSON")" ]; then
        warn "runtime.do_plan_default_stop_tokens is ignored: do-plan moved to the session-relay plugin — set stop_tokens in ~/.config/session-relay/config.yaml and delete this key"
    fi
}
""")
rep(L, """    # values without bypassing the loader. Used by /mesh-review (feature gating),
    # /do-plan (default STOP threshold), etc.""", """    # values without bypassing the loader. Used by /mesh-review (feature gating) and
    # the mesh-exec wrappers.""")
rep(L, "    #         feature name AND from the four validator-backed cases\n    #         (has_claude_models, has_grok, do_plan_default_stop_tokens, dispatch_model),",
       "    #         feature name AND from the three validator-backed cases\n    #         (has_claude_models, has_grok, dispatch_model),")
rep(L, """        do_plan_default_stop_tokens)
            # Returns the configured value or "250000" as the documented default.
            # Caller (commands/do-plan.md) trusts the integer, so we MUST run the
            # validator that owns this field BEFORE reading. iter-2 CRITICAL-2:
            # load_or_die does NOT invoke validators — `cmd_get_flag` historically
            # bypassed validate_all() and silently accepted out-of-range / non-integer
            # values. Pattern mirrors cmd_get_codex/cmd_get_gemini/cmd_get_defaults
            # (each typed getter calls only the validator that owns its section,
            # NOT the full validate_all — see iter-2 CONCERN-2/3).
            # The bare-probe has_* cases above (has_codex / has_gemini / has_models /
            # has_defaults_code_review) skip validation on purpose: each is a single
            # `jq -e` probe whose rc IS the answer, so a malformed section simply reads
            # as "absent" and the validator runs later, in the typed getter that actually
            # reads field values. has_claude_models is not one of them — it VALIDATES
            # BEFORE READING, so a malformed `claude:` section fails loudly (rc=1, the
            # validator's own message) instead of jq's rc=5 being swallowed by `|| echo 0`
            # and reported as a missing catalog. (Indexing depth is not the distinction:
            # has_models probes `.models[0]`, inside its section too.)
            validate_runtime
            jq -r '.runtime.do_plan_default_stop_tokens // 250000' "$CONFIG_JSON"
            ;;
        dispatch_model)
            # Optional. Empty output = no value set → the caller omits model: on dispatch
            # and the subagent inherits the session model. validate_runtime owns the
            # field's charset check, so run it before reading (mirrors
            # do_plan_default_stop_tokens above).
""", """        dispatch_model)
            # Optional. Empty output = no value set → the caller omits model: on dispatch
            # and the subagent inherits the session model. validate_runtime owns the
            # field's charset check, so run it BEFORE reading: load_or_die does not invoke
            # validators (iter-2 CRITICAL-2), and each typed getter calls only the validator
            # that owns its section (iter-2 CONCERN-2/3). The bare-probe has_* cases above
            # skip validation on purpose: a single `jq -e` probe whose rc IS the answer.
""")
rep(L, 'die "get-flag: unknown feature \\"$feature\\" (valid: has_codex, has_gemini, has_grok, has_models, has_claude_models, has_defaults_code_review, do_plan_default_stop_tokens, dispatch_model)"',
       'die "get-flag: unknown feature \\"$feature\\" (valid: has_codex, has_gemini, has_grok, has_models, has_claude_models, has_defaults_code_review, dispatch_model)"')
rep(L, """# iter-3 CONCERN-1: typed getter for runtime UI defaults (default_run_mode) + the do-plan
# threshold, as a JSON object. /mesh-review and /do-plan read these without raw yq.""",
"""# iter-3 CONCERN-1: typed getter for runtime UI defaults (default_run_mode), as a JSON
# object. /mesh-review reads these without raw yq.""")
rep(L, """            do_plan_default_stop_tokens: (.runtime.do_plan_default_stop_tokens // 250000),
""", "")
rep(L, """    data-dir)
        # Task 2.5: print the resolved plugin data dir WITHOUT load_or_die, so skills can
        # compute their runs/ path even on a fresh install (no config.yaml yet).
        printf '%s\\n' "$PLUGIN_DATA"
        ;;
""", """    config-path)
        # WITHOUT load_or_die: callers name this path precisely when there is no config yet.
        printf '%s\\n' "$CONFIG_FILE"
        ;;
    data-dir)
        # WITHOUT load_or_die, so skills can compute their runs/ path even on a fresh
        # install (no config.yaml yet).
        printf '%s\\n' "$PLUGIN_DATA"
        ;;
""")
rep(L, 'echo "Usage: $0 {validate|data-dir|export <model-id>|', 'echo "Usage: $0 {validate|config-path|data-dir|export <model-id>|')

P = "skills/shared/preflight-env.sh"
rep(P, 'CONFIG_STATUS="OK";      CONFIG_DETAIL="$(bash "$LOADER" data-dir 2>/dev/null)/config.yaml"',
       'CONFIG_STATUS="OK";      CONFIG_DETAIL="$(bash "$LOADER" config-path 2>/dev/null)"')
rep(P, 'CONFIG_DETAIL="no config.yaml here — the review skills will not start; cp config.example.yaml into the data dir"',
       'CONFIG_DETAIL="no config.yaml here — the review skills will not start; the blocker hint below names the path"')
rep(P, """DATA_DIR="<plugin-data-dir>"
if [ "$CONFIG_STATUS" != "OK" ] || [ "$CLAUDE_CATALOG_OK" = 0 ]; then
    # Only a blocked run needs a path, and only a blocked run pays for the extra loader start.
    # Guarded because data-dir prints nothing when the loader is absent or its toolchain dead,
    # and a hint whose path starts at the filesystem root points at a file nobody has.
    DD="$(bash "$LOADER" data-dir 2>/dev/null)"
    [ -z "$DD" ] || DATA_DIR="$DD"
fi""", """CONFIG_PATH="<config-path>"
if [ "$CONFIG_STATUS" != "OK" ] || [ "$CLAUDE_CATALOG_OK" = 0 ]; then
    # Only a blocked run needs a path, and only a blocked run pays for the extra loader start.
    # Guarded because config-path prints nothing when the loader is absent, and a hint whose
    # path is empty points at a file nobody has.
    CP="$(bash "$LOADER" config-path 2>/dev/null)"
    [ -z "$CP" ] || CONFIG_PATH="$CP"
fi""")
rep(P, 'BLOCKER="claude-mesh install is incomplete"', 'BLOCKER="mesh-exec install is incomplete"')
rep(P, 'BLOCKER_HINT="reinstall or update the claude-mesh plugin — config-loader.sh is missing',
       'BLOCKER_HINT="reinstall or update the mesh-exec plugin — config-loader.sh is missing')
rep(P, 'BLOCKER_HINT="cp config.example.yaml $DATA_DIR/config.yaml — the review skills need it even for the built-in claude reviewer" ;;',
       'BLOCKER_HINT="mkdir -p ${CONFIG_PATH%/*} && cp config.example.yaml $CONFIG_PATH — the review skills need it even for the built-in claude reviewer" ;;')
rep(P, 'BLOCKER_HINT="edit $DATA_DIR/config.yaml to fix what the config row reports',
       'BLOCKER_HINT="edit $CONFIG_PATH to fix what the config row reports')

rep(P, 'then re-run; $DATA_DIR/config.yaml was never read, so nothing above says anything about its contents',
       'then re-run; $CONFIG_PATH was never read, so nothing above says anything about its contents')
rep(P, 'fix the claude: section of $DATA_DIR/config.yaml (the claude-models row above',
       'fix the claude: section of $CONFIG_PATH (the claude-models row above')

V = "skills/shared/verify-delegation.sh"
rep(V, "#     data-dir    optional; defaults to config-loader resolve_plugin_data()",
       "#     data-dir    optional; defaults to `config-loader.sh data-dir` (~/.local/state/mesh)")
rep(V, """resolve_plugin_data() {
    if [ -n "${CLAUDE_PLUGIN_DATA:-}" ]; then printf '%s\\n' "$CLAUDE_PLUGIN_DATA"; return; fi
    local d
    for d in "$HOME"/.claude/plugins/data/claude-mesh-*; do
        [ -d "$d" ] && [ -f "$d/config.yaml" ] && { printf '%s\\n' "$d"; return; }
    done
    printf '%s\\n' "$HOME/.claude/plugins/data/claude-mesh-zinin"
}""", """resolve_plugin_data() {
    # One source of truth for where runs live: the loader's data-dir. The XDG default is the
    # fallback for a loader that cannot start, so a broken install still yields a real path.
    local d
    d="$(bash "$(cd "$(dirname "$0")" && pwd)/config-loader.sh" data-dir 2>/dev/null)" || d=""
    printf '%s\\n' "${d:-${XDG_STATE_HOME:-$HOME/.local/state}/mesh}"
}""")
print("task2 code patch applied")
PY
bash -n skills/shared/config-loader.sh && bash -n skills/shared/preflight-env.sh && bash -n skills/shared/verify-delegation.sh && echo syntax-ok
```

Expected: `task2 code patch applied`, `syntax-ok`.

- [ ] **Step 5: Прогнать затронутые наборы и сравнить с базовой линией**

```bash
cd /opt/github/zinin/claude-mesh
for t in test-config-loader test-preflight-env; do
  bash skills/shared/tests/$t.sh 2>&1 | grep -E '^\s+FAIL' | sed -E 's/ [—(].*//' | LC_ALL=C sort > /tmp/agent-plugins-baseline/$t.after
  echo "$t: new=[$(LC_ALL=C comm -13 /tmp/agent-plugins-baseline/$t.fails /tmp/agent-plugins-baseline/$t.after | tr '\n' ';')]"
done
for t in test-watch-runs test-verify-delegation; do bash skills/shared/tests/$t.sh 2>&1 | tail -1; done
```

Expected: `test-config-loader: new=[]`, `test-preflight-env: new=[]`, затем `=== Summary: 110 passed, 0 failed ===` и `=== Summary: 233 passed, 0 failed ===`. На 2026-09-25 набор загрузчика давал `424 passed, 5 failed` (было 411/5).

- [ ] **Step 6: Commit**

```bash
cd /opt/github/zinin/claude-mesh
git add skills/shared/config-loader.sh skills/shared/preflight-env.sh skills/shared/verify-delegation.sh \
  skills/shared/tests/test-config-loader.sh skills/shared/tests/test-watch-runs.sh skills/shared/tests/test-preflight-env.sh
git commit -m "feat: read the config and keep runs at fixed XDG paths"
```

---

### Task 3: mesh-exec — удалить ушедшие части и разделить смешанный тест

**Репозиторий:** `/opt/github/zinin/claude-mesh`.

**Files:**
- Delete: `commands/`, `hooks/`, `skills/{mesh-design-review,claude-code-review,codex-code-review,gemini-code-review,grok-code-review,ext-claude-code-review,claude-md-writer}/`, `agents/{claude,codex,gemini,grok,ext-claude}-code-reviewer.md`, `agents/review-discussion.md`, `skills/shared/code-review-prompt.md`, `skills/shared/render-template.py`, `scripts/backup-config.sh`, `skills/shared/tests/{test-command-sync,test-grok-code-review-bindings,test-render-template,test-check-context-size,test-do-plan,test-loader-resolution}.sh`
- Modify: `skills/shared/tests/test-claude-cli-agents.sh` — остаётся половина про исполнителей и exec-скиллы.

**Interfaces:**
- Consumes: Task 1 (ветка). Produces: дерево `mesh-exec` без чужих файлов; Task 4 переименовывает то, что осталось.

- [ ] **Step 1: Удалить файлы, которые ушли в другие плагины**

```bash
cd /opt/github/zinin/claude-mesh
git rm -q -r commands hooks skills/mesh-design-review skills/claude-code-review skills/codex-code-review \
  skills/gemini-code-review skills/grok-code-review skills/ext-claude-code-review skills/claude-md-writer
git rm -q agents/claude-code-reviewer.md agents/codex-code-reviewer.md agents/gemini-code-reviewer.md \
  agents/grok-code-reviewer.md agents/ext-claude-code-reviewer.md agents/review-discussion.md \
  skills/shared/code-review-prompt.md skills/shared/render-template.py scripts/backup-config.sh \
  skills/shared/tests/test-command-sync.sh skills/shared/tests/test-grok-code-review-bindings.sh \
  skills/shared/tests/test-render-template.sh skills/shared/tests/test-check-context-size.sh \
  skills/shared/tests/test-do-plan.sh skills/shared/tests/test-loader-resolution.sh
git ls-files | grep -vc '^skills/shared/tests/fixtures/'
```

Expected: `45`.

- [ ] **Step 2: Оставить в `test-claude-cli-agents.sh` половину про исполнителей**

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
def cut(path, start, end):
    """Remove from the line holding `start` through the line holding `end`, both once."""
    p = pathlib.Path(path); t = p.read_text()
    if t.count(start) != 1 or t.count(end) != 1:
        sys.exit(f"CUT FAIL {path}: markers {t.count(start)}/{t.count(end)}")
    a = t.rfind("\n", 0, t.index(start)) + 1
    b = t.index("\n", t.index(end)) + 1
    p.write_text(t[:a] + t[b:])

X = "skills/shared/tests/test-claude-cli-agents.sh"
rep(X, """# Presence contract for the Grok-host Claude CLI wrappers (spec §4).
#
# claude-code-reviewer / claude-executor dispatch official `claude -p` via
# ext-claude-exec HOST_CLAUDE=1. Catalog aliases (opus, fable), no tooling
# constraint, run dirs under runs/claude/. Task 6 appends dual-path asserts
# for all ten wrappers; this file starts with the three new paths only so
# Test 6 in test-command-sync.sh stays grok-specific.
""", """# Contract for the mesh-exec wrapper agents and exec skills.
#
# claude-executor dispatches official `claude -p` via ext-claude-exec HOST_CLAUDE=1:
# catalog aliases (opus, fable), run dirs under runs/claude/. The reviewer half of
# this file moved to the mesh-review plugin together with the reviewers.
""")
rep(X, """echo "=== Test: claude CLI reviewer, executor, review skill ==="
assert_eq "reviewer agent exists" "1" "$([ -f "$REPO/agents/claude-code-reviewer.md" ] && echo 1 || echo 0)"
assert_eq "executor agent exists" "1" "$([ -f "$REPO/agents/claude-executor.md" ] && echo 1 || echo 0)"
assert_eq "review skill exists" "1" "$([ -f "$REPO/skills/claude-code-review/SKILL.md" ] && echo 1 || echo 0)"
assert_eq "reviewer does not STOP when MODEL is omitted" "0" \\
    "$(grep -c 'ERROR: MODEL parameter is required on first line' "$REPO/agents/claude-code-reviewer.md")"
assert_eq "executor does not STOP when MODEL is omitted" "0" \\
    "$(grep -c 'ERROR: MODEL parameter is required on first line' "$REPO/agents/claude-executor.md")"
assert_ge "reviewer still invokes skill when MODEL omitted" "1" \\
    "$(grep -c 'If the first line is not `MODEL=`, still invoke the skill' "$REPO/agents/claude-code-reviewer.md")"
assert_ge "executor still invokes skill when MODEL omitted" "1" \\
    "$(grep -c 'If the first line is not `MODEL=`, still invoke the skill' "$REPO/agents/claude-executor.md")"
assert_ge "reviewer names HOST_CLAUDE" "1" \\
    "$(grep -c 'HOST_CLAUDE=1' "$REPO/skills/claude-code-review/SKILL.md")"
assert_eq "review skill has no tooling-constraint section" "0" \\
    "$(grep -c '## Tooling constraint' "$REPO/skills/claude-code-review/SKILL.md")"
""", """echo "=== Test: claude CLI executor ==="
assert_eq "executor agent exists" "1" "$([ -f "$REPO/agents/claude-executor.md" ] && echo 1 || echo 0)"
assert_eq "executor does not STOP when MODEL is omitted" "0" \\
    "$(grep -c 'ERROR: MODEL parameter is required on first line' "$REPO/agents/claude-executor.md")"
assert_ge "executor still invokes skill when MODEL omitted" "1" \\
    "$(grep -c 'If the first line is not `MODEL=`, still invoke the skill' "$REPO/agents/claude-executor.md")"
""")
rep(X, """# 8 pre-existing wrappers; claude-* already have the paragraph from Task 5.
WRAPPERS="codex-code-reviewer.md codex-executor.md gemini-code-reviewer.md gemini-executor.md grok-code-reviewer.md grok-executor.md ext-claude-code-reviewer.md ext-claude-executor.md claude-code-reviewer.md claude-executor.md\"""",
"""# The five executor wrappers; the reviewer wrappers are checked in mesh-review.
WRAPPERS="codex-executor.md gemini-executor.md grok-executor.md ext-claude-executor.md claude-executor.md\"""")
rep(X, 'SKILLS_WITH_RESOLVER="claude-code-review ext-claude-exec ext-claude-code-review codex-exec codex-code-review gemini-exec gemini-code-review grok-exec grok-code-review mesh-design-review"',
       'SKILLS_WITH_RESOLVER="ext-claude-exec codex-exec gemini-exec grok-exec"')
cut(X, 'echo ""\necho "=== Test: Grok Read of *-exec searches installed-plugins first ==="',
       'assert_eq "every review→exec Read searches installed-plugins before .claude/plugins" "0" "$read_stale"')
rep(X, """    "$REPO"/skills/*/SKILL.md "$REPO"/commands/*.md \\
    "$REPO"/skills/shared/resolve-plugin-root.sh || true)""", """    "$REPO"/skills/*/SKILL.md \\
    "$REPO"/skills/shared/resolve-plugin-root.sh || true)""")
print("task3 split applied")
PY
bash skills/shared/tests/test-claude-cli-agents.sh 2>&1 | tail -1
```

Expected: `task3 split applied`, `=== Summary: 17 passed, 0 failed ===`.

- [ ] **Step 3: Прогнать оставшиеся наборы**

```bash
cd /opt/github/zinin/claude-mesh
for f in skills/shared/tests/test-*.sh; do printf '%-36s %s\n' "$(basename $f)" "$(bash $f 2>&1 | grep -E 'Summary|RESULTS' | tail -1)"; done
```

Expected: 0 failed везде, кроме `test-config-loader.sh` (5) и `test-preflight-env.sh` (у него итоговой строки нет — проверить сравнением из Task 2 Step 5).

- [ ] **Step 4: Commit**

```bash
cd /opt/github/zinin/claude-mesh
git add skills/shared/tests/test-claude-cli-agents.sh
git commit -m "refactor: drop the parts that moved to session-relay, mesh-review and claude-md"
```

(`git rm` уже поставил удаления в индекс.)

---

### Task 4: mesh-exec — имена и поиск своего корня

**Репозиторий:** `/opt/github/zinin/claude-mesh`.

**Files:**
- Modify: все файлы в `skills/` и `agents/` (карта имён, шаблоны `*mesh-exec*`, сообщения), `skills/shared/resolve-plugin-root.sh`, `skills/shared/config-loader.sh` (комментарий `load_or_die`), `agents/{claude,grok,codex,gemini,ext-claude}-executor.md` (пути прогонов), `skills/ext-claude-exec/SKILL.md`, `skills/codex-exec/SKILL.md`.
- Test: `skills/shared/tests/test-resolve-plugin-root.sh`, `skills/shared/tests/test-claude-cli-agents.sh` (поддельные каталоги `claude-mesh` → `mesh-exec`).

**Interfaces:**
- Produces: `resolve-plugin-root.sh` и блоки поиска в exec-скиллах ищут `*mesh-exec*/skills/shared/config-loader.sh`; каталог `claude-mesh` в кеше им не подходит (Review Focus 2).

- [ ] **Step 1: Применить переименования**

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib, re, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))

EXEC = r"codex-exec|gemini-exec|grok-exec|ext-claude-exec|codex-executor|gemini-executor|grok-executor|ext-claude-executor|claude-executor"
REVIEW = (r"mesh-review|mesh-design-review|auto-decide-disputed|code-review-fresh-session|design-review-fresh-session|"
          r"review-discussion|claude-code-review|codex-code-review|gemini-code-review|grok-code-review|ext-claude-code-review|"
          r"claude-code-reviewer|codex-code-reviewer|gemini-code-reviewer|grok-code-reviewer|ext-claude-code-reviewer")
RELAY = r"do-plan|pause-after-current-task|transfer-session|exec-plan-fresh-session|continue-plan-fresh-session"
HISTORICAL = "the event listed 69 skills"   # a quoted 2026-08-29 measurement: stays verbatim

def ns_map(line):
    if HISTORICAL in line:
        return line
    line = re.sub(rf"claude-mesh:({EXEC})\b", r"mesh-exec:\1", line)
    line = re.sub(rf"claude-mesh:({REVIEW})\b", r"mesh-review:\1", line)
    line = re.sub(rf"claude-mesh:({RELAY})\b", r"session-relay:\1", line)
    return line.replace("claude-mesh:claude-md-writer", "claude-md:claude-md-writer")

code = [p for p in pathlib.Path(".").rglob("*") if p.is_file() and p.parts[0] in ("skills", "agents")
        and "fixtures" not in p.parts and p.suffix in (".md", ".sh", ".py")]
for p in code:
    t = p.read_text()
    new = "".join(ns_map(l) for l in t.splitlines(keepends=True))
    new = new.replace("'*claude-mesh*/", "'*mesh-exec*/")
    new = new.replace("claude-mesh plugin root not found", "mesh-exec plugin root not found")
    new = new.replace("Grok loads a marketplace claude-mesh from the Claude cache",
                      "Grok loads a marketplace mesh-exec from the Claude cache")
    new = new.replace("(the loader self-discovers `~/.claude/plugins/data/claude-mesh-*`)",
                      "(`~/.local/state/mesh`, or `$XDG_STATE_HOME/mesh` when that is set)")
    # a comment citing a file that now lives in another plugin keeps the path, with the plugin in front
    new = re.sub(r"(?<![\w/-])(commands/mesh-review\.md|skills/(?:claude|grok)-code-review/SKILL\.md)", r"mesh-review/\1", new)
    if new != t:
        p.write_text(new)

rep("skills/shared/resolve-plugin-root.sh",
    "# ~/.grok/installed-plugins/claude-mesh-<hash>. That path is what `grok inspect`",
    "# ~/.grok/installed-plugins/mesh-exec-<hash>. That path is what `grok inspect`")
rep("skills/shared/config-loader.sh", """    # iter-2 CONCERN-11: "config not found" gets a DISTINCT exit code (2) so
    # user-invoked commands like /do-plan can tolerate the genuinely-tolerable
    # "no config yet" case during first-run, while every other class of error
    # (yaml malformed, env binaries missing, validator die) still fast-fails
    # via the canonical `die` (rc=1). See `commands/do-plan.md` Step 1 for the
    # consumer side. Do NOT fold this into `die` — it must stay distinguishable.""",
"""    # iter-2 CONCERN-11: "config not found" gets a DISTINCT exit code (2) so
    # callers can tell the genuinely-tolerable "no config yet" case during first-run
    # from every other class of error (yaml malformed, env binaries missing, validator
    # die), which still fast-fails via the canonical `die` (rc=1). The mesh-review
    # orchestrators branch on it (mesh-review/commands/mesh-review.md Step 1). Do NOT
    # fold this into `die` — it must stay distinguishable.""")
for agent, engine in (("claude-executor", "claude/<alias>"), ("grok-executor", "grok/<model>")):
    eng = engine.split("/")[0]; leaf = engine.split("/")[1]
    rep(f"agents/{agent}.md", f"""- Work directory path: `${{CLAUDE_PLUGIN_DATA}}/runs/{engine}/YYYY-MM-DD-HH-MM-SS-<pid>-taskname/`
  — that is the SHAPE of the path, not a string to paste into a shell. `${{CLAUDE_PLUGIN_DATA}}`
  is EMPTY in a Bash call (Task 2.5), so expanding it there searches `/runs/{eng}` and finds
  nothing — reporting a run that happened as one that did not. Name the path the skill printed,
  or glob the data dir (run dirs are depth 2, `{leaf}/<run>`):
  `find "$HOME"/.claude/plugins/data/claude-mesh-*/runs/{eng} -mindepth 2 -maxdepth 2 -type d`""",
    f"""- Work directory path: `~/.local/state/mesh/runs/{engine}/YYYY-MM-DD-HH-MM-SS-<pid>-taskname/`
  (`$XDG_STATE_HOME/mesh/runs/…` when `XDG_STATE_HOME` is set). Name the path the skill printed,
  or list the run dirs (depth 2, `{leaf}/<run>`):
  `find "${{XDG_STATE_HOME:-$HOME/.local/state}}"/mesh/runs/{eng} -mindepth 2 -maxdepth 2 -type d`""")
for agent, eng in (("codex-executor", "codex"), ("gemini-executor", "gemini")):
    rep(f"agents/{agent}.md", f"- Work directory path: `${{CLAUDE_PLUGIN_DATA}}/runs/{eng}/YYYY-MM-DD-HH-MM-SS-taskname/`",
        f"- Work directory path: `~/.local/state/mesh/runs/{eng}/YYYY-MM-DD-HH-MM-SS-taskname/`")
rep("agents/ext-claude-executor.md", "- WORK_DIR path (under `${CLAUDE_PLUGIN_DATA}/runs/ext-claude/<provider>/<short>/...`)",
    "- WORK_DIR path (under `~/.local/state/mesh/runs/ext-claude/<provider>/<short>/...`)")
rep("skills/ext-claude-exec/SKILL.md", "Execute arbitrary prompts via `claude -p` with provider/model env taken from\n`${CLAUDE_PLUGIN_DATA}/config.yaml`.",
    "Execute arbitrary prompts via `claude -p` with provider/model env taken from\n`~/.config/mesh/config.yaml`.")
rep("skills/codex-exec/SKILL.md", "(where `$WORK_DIR` is under `${CLAUDE_PLUGIN_DATA}/runs/codex/...`)",
    "(where `$WORK_DIR` is under `~/.local/state/mesh/runs/codex/...`)")
for t in ("skills/shared/tests/test-resolve-plugin-root.sh", "skills/shared/tests/test-claude-cli-agents.sh"):
    p = pathlib.Path(t); p.write_text(p.read_text().replace("claude-mesh", "mesh-exec"))
print("task4 names applied")
PY
```

Expected: `task4 names applied`.

- [ ] **Step 2: Проверить, что осталось от старого имени**

```bash
cd /opt/github/zinin/claude-mesh
grep -rn 'claude-mesh' skills agents | awk -F: '{print $1}' | sort | uniq -c
grep -rnF 'CLAUDE_PLUGIN_DATA}/runs' skills agents; grep -rnF 'CLAUDE_PLUGIN_DATA}/config' skills agents; echo "---"
```

Expected ровно:
```
      1 skills/grok-exec/SKILL.md
      3 skills/shared/config-loader.sh
      7 skills/shared/tests/test-config-loader.sh
      2 skills/shared/tests/test-verify-delegation.sh
---
```
(историческая цитата; три строки о переезде старого конфига и их тесты; фикстура «a complete review of claude-mesh» — произвольный текст для проверки распознавания отказа).

- [ ] **Step 3: Тест: оставшийся в кеше `claude-mesh` — не этот плагин**

У `claude-mesh` тот же маркер `skills/shared/config-loader.sh`, так что от ложного выбора защищает только шаблон `*mesh-exec*`. В тесте путь старого плагина сортируется последним — ослабленный шаблон выбрал бы его.

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib
ins = r'''# 6. A claude-mesh cache left from before the rename is not this plugin. It carries the same
#    config-loader.sh marker, so only the *mesh-exec* pattern keeps it out — and its path is
#    made to sort LAST, so a loosened pattern would pick it and fail here.
OLD_HOME="$(mktemp -d)"
mkdir -p "$OLD_HOME/.claude/plugins/cache/zz-old/claude-mesh/9.9.9/skills/shared" \
         "$OLD_HOME/.claude/plugins/cache/zinin/mesh-exec/0.16.0/skills/shared"
touch "$OLD_HOME/.claude/plugins/cache/zz-old/claude-mesh/9.9.9/skills/shared/config-loader.sh" \
      "$OLD_HOME/.claude/plugins/cache/zinin/mesh-exec/0.16.0/skills/shared/config-loader.sh"
GOT=$(HOME="$OLD_HOME" GROK_PLUGIN_ROOT= CLAUDE_PLUGIN_ROOT= SKILL_BASE= "$SCRIPT")
assert_eq "claude-mesh in the cache is ignored, even sorting last" "$OLD_HOME/.claude/plugins/cache/zinin/mesh-exec/0.16.0" "$GOT"
rm -rf "$OLD_HOME"'''
p = pathlib.Path("skills/shared/tests/test-resolve-plugin-root.sh"); t = p.read_text()
anchor = '\necho "=== Summary:'
assert t.count(anchor) == 1, "anchor"
p.write_text(t.replace(anchor, "\n" + ins + anchor))
print("test 6 added")
PY
bash skills/shared/tests/test-resolve-plugin-root.sh 2>&1 | tail -1
cp skills/shared/resolve-plugin-root.sh /tmp/agent-plugins-resolver.bak
sed -i "s|'\*mesh-exec\*/skills/shared/config-loader.sh'|'*mesh*/skills/shared/config-loader.sh'|g" skills/shared/resolve-plugin-root.sh
bash skills/shared/tests/test-resolve-plugin-root.sh 2>&1 | grep -E 'sorting last|Summary'
cp /tmp/agent-plugins-resolver.bak skills/shared/resolve-plugin-root.sh && echo restored
```

Expected: `test 6 added`; `=== Summary: 14 passed, 0 failed ===`; с ослабленным шаблоном — `FAIL: claude-mesh in the cache is ignored, even sorting last …` и `=== Summary: 13 passed, 1 failed ===`; затем `restored`.

- [ ] **Step 4: Прогнать все наборы**

```bash
cd /opt/github/zinin/claude-mesh
for f in skills/shared/tests/test-*.sh; do printf '%-36s %s\n' "$(basename $f)" "$(bash $f 2>&1 | grep -E 'Summary|RESULTS' | tail -1)"; done
for t in test-config-loader test-preflight-env; do
  bash skills/shared/tests/$t.sh 2>&1 | grep -E '^\s+FAIL' | sed -E 's/ [—(].*//' | LC_ALL=C sort | LC_ALL=C comm -13 /tmp/agent-plugins-baseline/$t.fails - | sed "s/^/NEW $t: /"
done; echo done
```

Expected: 0 failed во всех наборах, кроме базовых провалов (`test-resolve-plugin-root.sh` — 14 passed); перед `done` — ни одной строки `NEW`.

- [ ] **Step 5: Commit**

```bash
cd /opt/github/zinin/claude-mesh
git add skills agents
git commit -m "refactor: rename the plugin to mesh-exec in skills, agents and scripts"
```

---

### Task 5: mesh-exec — манифест, конфиг-пример и документация

**Репозиторий:** `/opt/github/zinin/claude-mesh`.

**Files:**
- Modify: `.claude-plugin/plugin.json`, `config.example.yaml`, `README.md`, `AGENTS.md`, `CHANGELOG.md`

**Interfaces:**
- Consumes: Tasks 2–4. Produces: плагин с именем `mesh-exec` для смоука (Tasks 20–22).

- [ ] **Step 1: Манифест**

Заменить `.claude-plugin/plugin.json` целиком (версия остаётся 0.15.0 — её поднимет релиз):

```json
{
  "name": "mesh-exec",
  "version": "0.15.0",
  "displayName": "Mesh Exec",
  "description": "Run a prompt through another model's CLI — Codex, Gemini, Grok, Claude Code, or alt-provider models via claude -p — with logging, a watchdog and run directories",
  "author": {
    "name": "Alexander V. Zinin",
    "email": "azinin@gmail.com",
    "url": "https://github.com/zinin"
  },
  "repository": "https://github.com/zinin/mesh-exec",
  "license": "MIT",
  "keywords": ["agent-skills", "multi-model", "codex", "gemini", "grok", "claude-code", "delegation"]
}
```

- [ ] **Step 2: `config.example.yaml`**

Путь копирования, указатель на session-relay вместо `do_plan_default_stop_tokens`, имена команд ревью, `claude-mesh` → `mesh-exec` в прозе; абзац о том, как `/do-plan` проверяет `dispatch_model` в Grok, удаляется — do-plan уехал.

```bash
cd /opt/github/zinin/claude-mesh
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
E = "config.example.yaml"
rep(E, "# claude-mesh — example configuration", "# mesh — example configuration (mesh-exec and mesh-review read this one file)")
rep(E, "# Copy this file to  ~/.claude/plugins/data/claude-mesh-zinin/config.yaml  and edit.",
       "# Copy this file to  ~/.config/mesh/config.yaml  and edit; chmod 600 — it will hold tokens.\n"
       "# ($XDG_CONFIG_HOME/mesh/config.yaml when XDG_CONFIG_HOME is set; MESH_CONFIG overrides the path.)")
rep(E, "external models is nine reviewers for one /mesh-review.", "external models is nine reviewers for one /mesh-review:mesh-review.")
rep(E, "claude-mesh does not police the", "mesh-exec does not police the")
rep(E, "claude-mesh cannot tell that a grok", "mesh-exec cannot tell that a grok")
rep(E, "# Consumed when you run `/mesh-review default` / `/mesh-design-review default`.",
       "# Consumed by the mesh-review plugin: `/mesh-review:mesh-review default` / `/mesh-review:mesh-design-review default`.")
rep(E, "# used by: /mesh-review default", "# used by: /mesh-review:mesh-review default")
rep(E, "# used by: /mesh-design-review default", "# used by: /mesh-review:mesh-design-review default")
rep(E, "Pre-selects the run-mode choice in the /mesh-review UI.", "Pre-selects the run-mode choice in the /mesh-review:mesh-review UI.")
rep(E, """  # /do-plan with no argument uses this as its STOP threshold (in tokens).
  do_plan_default_stop_tokens: 250000          # [optional] positive integer, must be >= 150000
                                               #   (the check-context-size.sh hook emits nothing below the
                                               #   150k milestone, so a lower STOP could never fire).
                                               #   `/do-plan <N>` overrides this for a single invocation.
""", """  # do-plan's STOP threshold moved to the session-relay plugin: stop_tokens in
  # ~/.config/session-relay/config.yaml. A do_plan_default_stop_tokens key left here is ignored.
""")
rep(E, "  # /mesh-review Step 6.0 delegation guard:", "  # /mesh-review:mesh-review Step 6.0 delegation guard:")
rep(E, "  # Model for subagents dispatched by /do-plan, /mesh-review, /mesh-design-review.",
       "  # Model for subagents dispatched by mesh-exec's wrapper agents and by mesh-review\n"
       "  # (/mesh-review:mesh-review, /mesh-review:mesh-design-review). do-plan has its own, in session-relay.")
rep(E, """  # On Grok, /do-plan additionally checks the live `grok models` catalog: a slug that is
  # not a host model (typical: opus) is dropped and subagents inherit the session
  # (model and reasoning effort — spawn_subagent has no effort field).
""", "")
rep(E, "#   the /mesh-review and /mesh-design-review watcher", "#   the mesh-review watcher")
print("task5 config example patch applied")
PY
grep -nE 'claude-mesh|do-plan|do_plan' config.example.yaml
MESH_CONFIG="$PWD/config.example.yaml" XDG_STATE_HOME="$(mktemp -d)" bash skills/shared/config-loader.sh validate; echo "validate rc=$?"
```

Expected: `task5 config example patch applied`; grep печатает три строки-указателя на session-relay (351, 352, 363); `validate rc=0`.

- [ ] **Step 3: README**

Переписать `README.md`. Разделы от начала файла до конца раздела `### Grok Build` включительно заменить текстом:

````markdown
# mesh-exec

Run a prompt through another model's CLI and keep a record of the run: Codex, Gemini, Grok,
the Claude Code CLI itself, and Anthropic-compatible alt providers (z.ai, Alibaba DashScope,
DeepSeek, LiteLLM, an Ollama daemon) through `claude -p`. Each run gets a directory with the
prompt, the raw stream, the answer and a readable report; a watchdog restarts a stalled CLI.

An [Agent Skills](https://agentskills.io) plugin for Claude Code, Grok and Codex. Split out of
claude-mesh 0.15.0: multi-model review moved to [mesh-review](https://github.com/zinin/mesh-review),
plan execution and session hand-off to [session-relay](https://github.com/zinin/session-relay),
the CLAUDE.md skill to [claude-md](https://github.com/zinin/claude-md).

## Skills and agents

- **`/mesh-exec:codex-exec`, `/mesh-exec:gemini-exec`, `/mesh-exec:grok-exec`** — run a prompt
  through that CLI with full logging and progress display.
- **`/mesh-exec:ext-claude-exec`** — run a prompt through `claude -p` against an alt provider
  from `config.yaml`, or, with `HOST_CLAUDE=1`, through the Claude Code CLI under your own
  `claude login`.
- **Agents `mesh-exec:codex-executor`, `gemini-executor`, `grok-executor`, `ext-claude-executor`,
  `claude-executor`** — the same runs as subagents, for Claude Code and Grok. mesh-review
  dispatches them.
- **`skills/shared/`** — the config loader, environment preflight, run watcher, delegation
  guard and watchdog that the skills and mesh-review share.

## Install

### Claude Code

```
/plugin marketplace add zinin/agent-plugins
/plugin install mesh-exec@zinin
```

### Grok

Nothing to do when Claude Code has it: Grok loads the plugins Claude Code installed. Without
Claude Code: `grok plugin marketplace add zinin/agent-plugins`, then
`grok plugin install mesh-exec --trust`.

### Codex

```
codex plugin marketplace add zinin/agent-plugins
codex plugin add mesh-exec@zinin
```

Codex has no plugin agents, so the `*-executor` agents do not exist there; the skills do. A
run writes under `~/.local/state/mesh/`, outside the workspace: approve the write Codex asks
about, or start it with `--add-dir ~/.local/state/mesh`.

## Configure

The config is `~/.config/mesh/config.yaml` (`$XDG_CONFIG_HOME/mesh/config.yaml` when that is
set; `MESH_CONFIG` overrides the path). Runs live under `~/.local/state/mesh/runs/`
(`$XDG_STATE_HOME/mesh`). Both paths are the same under every harness, and neither is deleted
when you uninstall the plugin.

```bash
cd /opt/github/zinin/claude-mesh
mkdir -p ~/.config/mesh
cp <plugin dir>/config.example.yaml ~/.config/mesh/config.yaml
chmod 600 ~/.config/mesh/config.yaml
```

The plugin dir is the checkout, or `~/.claude/plugins/cache/zinin/mesh-exec/<version>/` after
a marketplace install. Then edit the file:
- providers (URL + token) under `providers:`, models under `models:` with id `<provider>/<short>`;
- the optional `claude:` / `codex:` / `gemini:` / `grok:` sections (`grok:` needs a non-empty
  `models:` catalog — see the schema table below);
- `defaults:` — review presets for the mesh-review plugin, which reads this same file.

Check it: `bash <plugin dir>/skills/shared/config-loader.sh validate`.

### Moving from claude-mesh

claude-mesh kept the config in Claude Code's plugin-data directory. Copy it once:

```bash
cd /opt/github/zinin/claude-mesh
mkdir -p ~/.config/mesh
cp ~/.claude/plugins/data/claude-mesh-zinin/config.yaml ~/.config/mesh/config.yaml
chmod 600 ~/.config/mesh/config.yaml
```

Until you do, every skill stops with `config.yaml not found` and prints that command.
`runtime.do_plan_default_stop_tokens` is ignored now (`validate` says so): do-plan moved to
session-relay, which has `stop_tokens` in `~/.config/session-relay/config.yaml`. Old runs stay
in the old directory; nothing reads them.

### Grok Build

- `builtin: native` in a mesh-review preset runs `spawn_subagent` with slugs from `grok models`;
  `builtin: claude` runs `claude -p` (Claude Code CLI) under `HOST_CLAUDE=1`: the CLI's own
  `claude login` credentials, no provider `export` from `config.yaml`. That run unsets
  `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and the Bedrock / Vertex routing variables, so log
  the CLI in first. Run dirs: `runs/claude/<alias>/`.
- The `grok models` probe that builds the native page waits `GROK_MODELS_TIMEOUT` seconds, else
  `PREFLIGHT_CLI_TIMEOUT`, else 30; a non-numeric value falls back to 30 with a warning.
````

Остальные разделы оставить с такими правками:
1. `## Claude Code settings (not plugin config)` — без изменений.
2. `## Dependencies` — первый пункт (`claude` CLI …, со всеми вложенными абзацами про `runtime.dispatch_model` и `claude.models`) заменить на:
```markdown
- A harness that loads Agent Skills: Claude Code, Grok or Codex. The `claude` CLI is needed only
  for `ext-claude-exec` (alt providers and `HOST_CLAUDE=1`).
  - `runtime.dispatch_model` governs the plumbing: the codex / gemini / grok / ext-claude wrapper
    agents and mesh-review's `review-discussion` agent. Empty = the subagent inherits the session
    model. do-plan's subagents take `dispatch_model` from session-relay's own config instead.
  - `claude.models` is the catalog mesh-review offers for the built-in `claude` reviewer; each
    selected entry is one more full review, so cost scales with it.
```
   В пункте про `python3` убрать упоминание review-скиллов (`shared/render-template.py … in ALL review skills`) — теперь это mesh-review; оставить `ext-claude-exec` и `shared/extract-result.py`. В пункте про `grok` CLI заменить `every installed claude-* plugin` на `every installed plugin`.
3. `## Config schema reference` — в строке таблицы `defaults:` дописать `(read by the mesh-review plugin)`; в `### The grok: section…` без изменений.
4. `## WARNING: Uninstall wipes config` — удалить раздел целиком.
5. `## Troubleshooting` — строку `config.yaml not found at ...` заменить на `| config.yaml not found at … | See "Configure" and "Moving from claude-mesh" — the message prints the cp command when the old config is still there |`; строку про `backup-config.sh` удалить; в строке про рост `runs/` путь `~/.claude/plugins/data/claude-mesh*/runs` заменить на `~/.local/state/mesh/runs`; `/mesh-review` в строке про KILLED заменить на `/mesh-review:mesh-review`.
6. `## Credits` — удалить раздел (переезжает в claude-md).
7. `## License` — без изменений.

Проверка: `grep -n 'claude-mesh' README.md` печатает только строки раздела `### Moving from claude-mesh` и вводную фразу «Split out of claude-mesh 0.15.0».

- [ ] **Step 4: AGENTS.md**

В `AGENTS.md`: заголовок `# claude-mesh (plugin source)` → `# mesh-exec (plugin source)`; заменить во всём файле `claude-mesh@zinin` → `mesh-exec@zinin`, `claude plugin disable claude-mesh` → `claude plugin disable mesh-exec`, `claude-mesh-<hash>` и `claude-mesh-*` → `mesh-exec-<hash>` и `mesh-exec-*`, `/absolute/path/to/claude-mesh` → `/absolute/path/to/mesh-exec`, `grok plugin uninstall claude-mesh` / `grok plugin enable claude-mesh` / `grok plugin update claude-mesh` → `mesh-exec`, `p["name"]=="claude-mesh"` → `p["name"]=="mesh-exec"`, `~/.claude/plugins/cache/zinin/claude-mesh/` → `~/.claude/plugins/cache/zinin/mesh-exec/`, `commands/mesh-review.md` в примере `cmp` → `skills/shared/config-loader.sh`. Строку `Do not edit the user's ~/.claude/plugins/data/claude-mesh-*/config.yaml or` заменить на `Do not edit the user's ~/.config/mesh/config.yaml or`. В раздел `## While working in this repo` добавить пункты:

```markdown
- mesh-review calls these scripts across the plugin boundary: `config-loader.sh` (subcommands
  `data-dir`, `config-path`, `get-flag`, `get-defaults`, `get-runtime`, `list-models`,
  `list-claude-models`, `list-grok-models`, `get-codex`, `get-gemini`), `preflight-env.sh`,
  `watch-runs.sh`, `verify-delegation.sh`, `watchdog.sh`, `list-host-models.sh`. A change to
  their interface ships in the same release as the matching mesh-review change.
- Tests: `for f in skills/shared/tests/test-*.sh; do bash "$f"; done`.
```

Проверка: `grep -n 'claude-mesh' AGENTS.md` пусто.

- [ ] **Step 5: CHANGELOG**

После строки `All notable changes to claude-mesh will be documented here.` заменить её на `All notable changes to mesh-exec (claude-mesh up to 0.15.0) will be documented here.` и вставить перед `## [0.15.0] - 2026-09-05`:

```markdown
## [Unreleased]

### Changed
- **Renamed from claude-mesh to mesh-exec** and cut down to one job: running prompts through
  other models' CLIs. `/mesh-review` and `/mesh-design-review` with their reviewers moved to the
  mesh-review plugin; `/do-plan`, `/pause-after-current-task` and the fresh-session prompt
  generators to session-relay; `claude-md-writer` to claude-md. Skill and agent names change
  accordingly: `/claude-mesh:codex-exec` is `/mesh-exec:codex-exec`.
- **The config lives at `~/.config/mesh/config.yaml`, runs under `~/.local/state/mesh/`**
  (XDG; `MESH_CONFIG` overrides the config path). No harness plugin-data directory is involved:
  an uninstall no longer deletes the config, and Codex finds it too. When the old
  `~/.claude/plugins/data/claude-mesh-*/config.yaml` is still there and the new one is not,
  the loader prints the command that copies it. New `config-loader.sh config-path`.
- **`runtime.do_plan_default_stop_tokens` is ignored with a warning** and `get-flag
  do_plan_default_stop_tokens` is gone: do-plan has its own config in session-relay.

### Removed
- `scripts/backup-config.sh`: the config no longer sits where an uninstall deletes it.
```

- [ ] **Step 6: Проверить и закоммитить**

```bash
cd /opt/github/zinin/claude-mesh
python3 -c 'import json; print(json.load(open(".claude-plugin/plugin.json"))["name"])'
claude plugin validate . 2>&1 | tail -3
git add .claude-plugin/plugin.json config.example.yaml README.md AGENTS.md CHANGELOG.md
git commit -m "docs: describe mesh-exec — manifest, config example, README, AGENTS, changelog"
```

Expected: `mesh-exec`; `claude plugin validate` без ошибок (предупреждения допустимы — записать их).

---
### Task 6: session-relay — раскладка скиллов и ридер конфига

**Репозиторий:** `/opt/github/zinin/session-relay`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Move: `commands/<имя>.md` → `skills/<имя>/SKILL.md` для `do-plan`, `pause-after-current-task`, `transfer-session`, `exec-plan-fresh-session`, `continue-plan-fresh-session`; `skills/shared/list-host-models.sh` → `skills/do-plan/list-host-models.sh`; `skills/shared/tests/*` → `tests/`
- Create: `skills/do-plan/read-config.py`, `tests/test-read-config.sh`, `config.example.yaml`
- Modify: `tests/test-do-plan.sh`, `tests/test-check-context-size.sh`, `tests/test-list-host-models.sh` (пути после переноса)

**Interfaces:**
- Produces: `python3 skills/do-plan/read-config.py [--file PATH] get stop_tokens|dispatch_model` → значение (по умолчанию 400000 и пустая строка), код 0; ошибка конфига → код 1 и `<file>:<line>: <reason>` на stderr; ошибка вызова → код 64. `read-config.py [--file PATH] path` → путь, который читается. Без `--file` — `${XDG_CONFIG_HOME:-$HOME/.config}/session-relay/config.yaml`. Используют Task 7 (шаг 1 `do-plan`) и Task 8.

- [ ] **Step 1: Перенести команды в скиллы и тесты в `tests/`**

```bash
cd /opt/github/zinin/session-relay
for c in do-plan pause-after-current-task transfer-session exec-plan-fresh-session continue-plan-fresh-session; do
  mkdir -p "skills/$c" && git mv "commands/$c.md" "skills/$c/SKILL.md"
done
git mv skills/shared/list-host-models.sh skills/do-plan/list-host-models.sh
mkdir -p tests/fixtures
git mv skills/shared/tests/test-check-context-size.sh skills/shared/tests/test-do-plan.sh skills/shared/tests/test-list-host-models.sh tests/
git mv skills/shared/tests/fixtures/grok-models-2026-08-31.txt tests/fixtures/
sed -i 's|REPO="$(cd "$TESTS_DIR/../../.." \&\& pwd)"|REPO="$(cd "$TESTS_DIR/.." \&\& pwd)"|; s|CMD="$REPO/commands/do-plan.md"|CMD="$REPO/skills/do-plan/SKILL.md"|' tests/test-do-plan.sh
sed -i 's|HOOK="$TESTS_DIR/../../../hooks/check-context-size.sh"|HOOK="$TESTS_DIR/../hooks/check-context-size.sh"|' tests/test-check-context-size.sh
sed -i 's|SCRIPT="$TESTS_DIR/../list-host-models.sh"|SCRIPT="$TESTS_DIR/../skills/do-plan/list-host-models.sh"|' tests/test-list-host-models.sh
for f in tests/test-*.sh; do printf '%-28s %s\n' "$(basename $f)" "$(bash $f 2>&1 | tail -1)"; done
```

Expected: `test-check-context-size.sh RESULTS: 22 passed, 0 failed`, `test-do-plan.sh RESULTS: 15 passed, 0 failed`, `test-list-host-models.sh === Summary: 11 passed, 0 failed ===`. Каталоги `commands/` и `skills/shared/` пусты и исчезают.

- [ ] **Step 2: Commit раскладки**

```bash
cd /opt/github/zinin/session-relay
git add tests/test-do-plan.sh tests/test-check-context-size.sh tests/test-list-host-models.sh
git commit -m "refactor: turn the commands into skills and move the tests to tests/"
```

- [ ] **Step 3: Написать тест ридера конфига**

```bash
cd /opt/github/zinin/session-relay
cat > tests/test-read-config.sh <<'EOF'
#!/usr/bin/env bash
# Tests for skills/do-plan/read-config.py — session-relay's two-key config.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
READ="$TESTS_DIR/../skills/do-plan/read-config.py"
FAIL=0
PASS=0
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then PASS=$((PASS+1)); echo "  PASS: $desc"
    else FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected '$expected', got '$actual')"; fi
}
assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    case "$haystack" in
        *"$needle"*) PASS=$((PASS+1)); echo "  PASS: $desc" ;;
        *) FAIL=$((FAIL+1)); echo "  FAIL: $desc (no '$needle' in '$haystack')" ;;
    esac
}
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
run() {   # $1 = config body or "-" for no file; rest = read-config.py args. Sets OUT ERR RC.
    local body="$1"; shift
    rm -f "$T/config.yaml"
    [ "$body" = "-" ] || printf '%s' "$body" > "$T/config.yaml"
    OUT="$(python3 "$READ" --file "$T/config.yaml" "$@" 2>"$T/err")"; RC=$?
    ERR="$(cat "$T/err")"
}

echo "=== no file: defaults ==="
run - get stop_tokens;    assert_eq "stop_tokens defaults to 400000" "400000" "$OUT"; assert_eq "rc 0" "0" "$RC"
run - get dispatch_model; assert_eq "dispatch_model defaults to empty" "" "$OUT"; assert_eq "rc 0" "0" "$RC"

echo "=== both keys, comments, blank lines, quotes ==="
CFG=$'# session-relay\n\nstop_tokens: 300000   # pause earlier\ndispatch_model: "opus"\n'
run "$CFG" get stop_tokens;    assert_eq "stop_tokens read" "300000" "$OUT"
run "$CFG" get dispatch_model; assert_eq "quotes stripped" "opus" "$OUT"
run $'dispatch_model:\n' get dispatch_model; assert_eq "an empty value means unset" "" "$OUT"; assert_eq "…rc 0" "0" "$RC"
run $'dispatch_model: us.anthropic.claude-opus-4-v2:0\n' get dispatch_model
assert_eq "provider ids with . : pass" "us.anthropic.claude-opus-4-v2:0" "$OUT"

echo "=== errors name the file and the line ==="
run $'stop_tokens: 149999\n' get stop_tokens
assert_eq "below the floor → rc 1" "1" "$RC"
assert_contains "…names the file and line" "$T/config.yaml:1" "$ERR"
assert_contains "…and the floor" "150000" "$ERR"
run $'\nstop_tokens: 400k\n' get stop_tokens
assert_eq "400k is not an integer → rc 1" "1" "$RC"
assert_contains "…names line 2" "$T/config.yaml:2" "$ERR"
run $'stop_token: 400000\n' get stop_tokens
assert_eq "a typo'd key → rc 1" "1" "$RC"
assert_contains "…says unknown key" "unknown key 'stop_token'" "$ERR"
run $'stop_tokens: 400000\nstop_tokens: 300000\n' get stop_tokens
assert_eq "a duplicate key → rc 1" "1" "$RC"
assert_contains "…says duplicate" "duplicate key 'stop_tokens'" "$ERR"
run $'just text\n' get stop_tokens
assert_eq "a line without a colon → rc 1" "1" "$RC"
run $'dispatch_model: -rf\n' get dispatch_model
assert_eq "a flag-looking model → rc 1" "1" "$RC"
run $'stop_tokens:\n' get stop_tokens
assert_eq "an empty stop_tokens → rc 1" "1" "$RC"

echo "=== default path follows XDG_CONFIG_HOME ==="
mkdir -p "$T/xdg/session-relay"
printf 'stop_tokens: 250000\n' > "$T/xdg/session-relay/config.yaml"
OUT="$(XDG_CONFIG_HOME="$T/xdg" python3 "$READ" get stop_tokens)"
assert_eq "reads \$XDG_CONFIG_HOME/session-relay/config.yaml" "250000" "$OUT"
OUT="$(env -u XDG_CONFIG_HOME HOME="$T/nohome" python3 "$READ" get stop_tokens)"
assert_eq "no XDG, no file under HOME → default" "400000" "$OUT"
OUT="$(XDG_CONFIG_HOME="$T/xdg" python3 "$READ" path)"
assert_eq "path prints the file it reads" "$T/xdg/session-relay/config.yaml" "$OUT"

echo "=== the shipped example parses ==="
EXAMPLE="$TESTS_DIR/../config.example.yaml"
OUT="$(python3 "$READ" --file "$EXAMPLE" get stop_tokens)"; assert_eq "config.example.yaml: stop_tokens" "400000" "$OUT"
OUT="$(python3 "$READ" --file "$EXAMPLE" get dispatch_model)"; assert_eq "config.example.yaml: dispatch_model left out" "" "$OUT"

echo "=== usage ==="
python3 "$READ" get nothing >/dev/null 2>&1; assert_eq "unknown key to get → rc 64" "64" "$?"
python3 "$READ" >/dev/null 2>&1; assert_eq "no command → rc 64" "64" "$?"

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" = "0" ]
EOF
bash tests/test-read-config.sh 2>&1 | tail -1
```

Expected: `=== Summary: 3 passed, 25 failed ===` (скрипта ещё нет; три «прохода» — совпадение пустого вывода с ожидаемой пустой строкой).

- [ ] **Step 4: Написать ридер и пример конфига**

```bash
cd /opt/github/zinin/session-relay
cat > skills/do-plan/read-config.py <<'EOF'
#!/usr/bin/env python3
"""Read session-relay's config: two flat keys, Python standard library only.

    read-config.py [--file PATH] get stop_tokens|dispatch_model
    read-config.py [--file PATH] path

The file is PATH, else ${XDG_CONFIG_HOME:-~/.config}/session-relay/config.yaml. A missing
file means the defaults: stop_tokens 400000, dispatch_model unset (printed as an empty line).

The format is a strict subset of YAML: one `key: value` per line, `#` comments, blank lines,
optional quotes around a value. A mistake — an unknown or repeated key, a value that is not
what the key takes — exits 1 with `<file>:<line>: <reason>` on stderr instead of falling back
to a default: a typo must not quietly move the STOP threshold. Usage errors exit 64.
"""
import os
import re
import sys

DEFAULTS = {"stop_tokens": "400000", "dispatch_model": ""}
MIN_STOP = 150000  # the context hook emits nothing below 150k, so a lower threshold never fires
# Same charset as mesh's runtime.dispatch_model: a leading letter/digit keeps flags out.
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]*$")
LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")


def default_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "session-relay", "config.yaml")


def fail(where, reason):
    print(f"{where}: {reason}", file=sys.stderr)
    sys.exit(1)


def parse(path):
    values = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return values
    seen = set()
    for number, raw in enumerate(lines, 1):
        where = f"{path}:{number}"
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if not line:
            continue
        match = LINE_RE.match(line)
        if not match:
            fail(where, "expected `key: value`")
        key, value = match.group(1), match.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key not in DEFAULTS:
            fail(where, f"unknown key '{key}' (valid: {', '.join(DEFAULTS)})")
        if key in seen:
            fail(where, f"duplicate key '{key}'")
        seen.add(key)
        if key == "stop_tokens":
            if not re.fullmatch(r"[1-9][0-9]*", value):
                fail(where, f"stop_tokens must be a whole number of tokens, got '{value}'")
            if int(value) < MIN_STOP:
                fail(where, f"stop_tokens must be >= {MIN_STOP} (the context hook emits nothing below 150k), got {value}")
        elif value and not MODEL_RE.match(value):
            fail(where, f"dispatch_model must start with a letter or digit and use only [A-Za-z0-9._:@-], got '{value}'")
        values[key] = value
    return values


def main(argv):
    args = list(argv)
    path = None
    if args[:1] == ["--file"]:
        if len(args) < 2 or not args[1]:
            print("usage: read-config.py [--file PATH] get <key> | path", file=sys.stderr)
            return 64
        path, args = args[1], args[2:]
    path = path or default_path()
    if args == ["path"]:
        print(path)
        return 0
    if len(args) != 2 or args[0] != "get" or args[1] not in DEFAULTS:
        print("usage: read-config.py [--file PATH] get stop_tokens|dispatch_model | path", file=sys.stderr)
        return 64
    print(parse(path)[args[1]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF
chmod +x skills/do-plan/read-config.py
cat > config.example.yaml <<'EOF'
# session-relay config — copy to ~/.config/session-relay/config.yaml
# ($XDG_CONFIG_HOME/session-relay/config.yaml when XDG_CONFIG_HOME is set).
# Every key is optional, and a missing file means the defaults shown here.
# Plain `key: value` lines only: no nesting, no lists. A mistake stops do-plan with
# <file>:<line> rather than falling back to a default.

# STOP threshold for /session-relay:do-plan, in tokens: a whole number, at least 150000
# (the context hook emits nothing below 150k). An argument — /session-relay:do-plan 300k —
# overrides it for one run. Keep it below your model's context window; on Grok, do-plan
# warns when it is not.
stop_tokens: 400000

# Model for do-plan's subagents. Leave it out to inherit the session model. On Grok the
# value is used only when it is a live slug from `grok models`.
# dispatch_model: opus
EOF
bash tests/test-read-config.sh 2>&1 | grep -E 'FAIL|Summary'
```

Expected: `=== Summary: 28 passed, 0 failed ===`.

- [ ] **Step 5: Commit**

```bash
cd /opt/github/zinin/session-relay
git add skills/do-plan/read-config.py tests/test-read-config.sh config.example.yaml
git commit -m "feat: read session-relay's own two-key config"
```

---

### Task 7: session-relay — скилл `do-plan`

**Репозиторий:** `/opt/github/zinin/session-relay`.

**Files:**
- Modify: `skills/do-plan/SKILL.md`
- Test: `tests/test-do-plan.sh` (заменяется)

**Interfaces:**
- Consumes: `read-config.py` (Task 6); `nsmap.py` (Task 1).
- Produces: шаг 1 `do-plan` печатает `DEFAULT_STOP=<n>` и `DISPATCH_MODEL=<m>`, в Grok ещё `CONTEXT_SIGNALS=` и `CONTEXT_WINDOW=`; без `CLAUDECODE` и `GROK_SESSION_ID` — код 1 и `do-plan здесь не поддерживается`. Шаг 2 пишет `${XDG_STATE_HOME:-$HOME/.local/state}/session-relay/do-plan-config-<cwd-encoded>-<session>.json` с `{"stop_threshold":N}` — этот путь читает хук после Task 8.

- [ ] **Step 1: Заменить тест контрактом и поведением нового шага 1 и шага 2**

```bash
cd /opt/github/zinin/session-relay
cat > tests/test-do-plan.sh <<'EOF'
#!/usr/bin/env bash
# Contract and behaviour tests for skills/do-plan/SKILL.md.
# The skill is prose the controller follows plus bash fences it runs. The greps lock the
# sentences that would silently regress; the fence runs lock what Step 1 and Step 2 do.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$TESTS_DIR/.." && pwd)"
CMD="$REPO/skills/do-plan/SKILL.md"
HOOK="$REPO/hooks/check-context-size.sh"
HOOKS="$REPO/hooks/hooks.json"

FAIL=0
PASS=0

assert_ge() {
    local desc="$1" min="$2" actual="$3"
    case "$actual" in
        ''|*[!0-9]*)
            FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected a count >= $min, got '$actual')"
            return ;;
    esac
    if [ "$actual" -ge "$min" ]; then
        PASS=$((PASS+1)); echo "  PASS: $desc ($actual >= $min)"
    else
        FAIL=$((FAIL+1)); echo "  FAIL: $desc ($actual < $min)"
    fi
}
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then PASS=$((PASS+1)); echo "  PASS: $desc"
    else FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected '$expected', got '$actual')"; fi
}
assert_contains() {
    local desc="$1" needle="$2" file="$3"
    if grep -Fq -- "$needle" "$file"; then
        PASS=$((PASS+1)); echo "  PASS: $desc"
    else
        FAIL=$((FAIL+1)); echo "  FAIL: $desc (missing in $file: '$needle')"
    fi
}
assert_has() {
    local desc="$1" needle="$2" haystack="$3"
    case "$haystack" in
        *"$needle"*) PASS=$((PASS+1)); echo "  PASS: $desc" ;;
        *) FAIL=$((FAIL+1)); echo "  FAIL: $desc (no '$needle' in: $haystack)" ;;
    esac
}
# The n-th ```bash fence after the heading that starts with $1.
fence() {
    awk -v h="$1" -v want="${2:-1}" '
        index($0, h) == 1 { in_sec = 1; next }
        in_sec && /^## / { exit }
        in_sec && /^```bash$/ { n++; if (n == want) { on = 1; next } }
        on && /^```$/ { exit }
        on { print }' "$CMD"
}

echo "== /do-plan: Grok session id =="
assert_contains "SID falls back to GROK_SESSION_ID" \
    'SID="${CLAUDE_CODE_SESSION_ID:-${GROK_SESSION_ID:-}}"' "$CMD"
assert_ge "abort copy names both session id vars" "1" \
    "$(grep -c 'CLAUDE_CODE_SESSION_ID and GROK_SESSION_ID' "$CMD" || true)"

echo "== /do-plan: host catalog filter =="
assert_contains "probes the live host catalog via list-host-models.sh" 'list-host-models.sh' "$CMD"
assert_contains "membership is exact-line grep -Fxq" 'grep -Fxq' "$CMD"
assert_ge "clears DISPATCH_MODEL when the slug is not a host model" "2" \
    "$(grep -c 'DISPATCH_MODEL=""' "$CMD" || true)"
assert_ge "says inherit when the slug is missing from the host catalog" "1" \
    "$(grep -c 'наследуем модель сессии' "$CMD" || true)"

echo "== /do-plan: effort is not a spawn field =="
assert_ge "tells the controller spawn_subagent has no effort field" "1" \
    "$(grep -ci 'spawn_subagent has no' "$CMD" || true)"

echo "== /do-plan: Grok reads context from signals.json, not the hook =="
assert_contains "Step 1 echoes CONTEXT_SIGNALS path" 'CONTEXT_SIGNALS=' "$CMD"
assert_contains "Grok primary usage is contextTokensUsed" 'contextTokensUsed' "$CMD"
assert_ge "says the Grok hook is not the primary STOP channel" "1" \
    "$(grep -ci 'not the primary' "$CMD" || true)"
assert_contains "poll snippet prints CONTEXT_USED= even when the file is missing" 'echo "CONTEXT_USED="' "$CMD"
assert_contains "poll snippet WARNs when signals.json is missing" 'signals.json не найден' "$CMD"
assert_contains "missing list-host-models.sh is a distinct warning" 'list-host-models.sh не найден' "$CMD"
assert_contains "Step 1 reads the Grok context window" 'contextWindowTokens' "$CMD"
assert_contains "the window warning says STOP will not fire" 'STOP не сработает' "$CMD"

echo "== /do-plan: session-relay owns its config and state =="
assert_eq "no mesh config-loader anywhere" "0" "$(grep -c 'config-loader' "$CMD" || true)"
assert_eq "no claude-mesh name left" "0" "$(grep -c 'claude-mesh' "$CMD" || true)"
assert_contains "default threshold is 400000" 'default 400000' "$CMD"
assert_contains "state lives under XDG" 'STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/session-relay"' "$CMD"

echo "== /do-plan: Step 1 behaviour =="
STEP1="$(fence '### Resolve the config-driven default')"
assert_ge "Step 1 fence extracted" "20" "$(printf '%s\n' "$STEP1" | grep -c .)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
OUT="$(cd "$T" && env -u CLAUDECODE -u GROK_SESSION_ID CLAUDE_PLUGIN_ROOT="$REPO" bash -c "$STEP1" 2>&1)"; RC=$?
assert_eq "no Claude Code, no Grok → refuses (rc 1)" "1" "$RC"
assert_has "…with the no-signal message" "do-plan здесь не поддерживается" "$OUT"
mkdir -p "$T/xdg/session-relay"
printf 'stop_tokens: 300000\ndispatch_model: opus\n' > "$T/xdg/session-relay/config.yaml"
OUT="$(cd "$T" && env -u GROK_SESSION_ID CLAUDECODE=1 CLAUDE_PLUGIN_ROOT="$REPO" XDG_CONFIG_HOME="$T/xdg" bash -c "$STEP1" 2>&1)"; RC=$?
assert_eq "Claude Code with a config → rc 0" "0" "$RC"
assert_has "reads stop_tokens" "DEFAULT_STOP=300000" "$OUT"
assert_has "reads dispatch_model" "DISPATCH_MODEL=opus" "$OUT"
printf 'stop_tokens: 400k\n' > "$T/xdg/session-relay/config.yaml"
OUT="$(cd "$T" && env -u GROK_SESSION_ID CLAUDECODE=1 CLAUDE_PLUGIN_ROOT="$REPO" XDG_CONFIG_HOME="$T/xdg" bash -c "$STEP1" 2>&1)"; RC=$?
assert_eq "a config typo stops Step 1 (rc 1)" "1" "$RC"
assert_has "…naming file and line" "$T/xdg/session-relay/config.yaml:1" "$OUT"
rm -f "$T/xdg/session-relay/config.yaml"
OUT="$(cd "$T" && env -u GROK_SESSION_ID CLAUDECODE=1 CLAUDE_PLUGIN_ROOT="$REPO" XDG_CONFIG_HOME="$T/xdg" bash -c "$STEP1" 2>&1)"; RC=$?
assert_eq "no config file → defaults, rc 0" "0" "$RC"
assert_has "…threshold 400000" "DEFAULT_STOP=400000" "$OUT"

echo "== /do-plan Step 2 writes the per-session file under XDG_STATE_HOME =="
STEP2="$(fence '## Step 2' | sed 's/<THRESHOLD>/400000/')"
assert_ge "Step 2 fence extracted" "10" "$(printf '%s\n' "$STEP2" | grep -c .)"
mkdir -p "$T/proj"
( cd "$T/proj" && env -u GROK_SESSION_ID XDG_STATE_HOME="$T/st" CLAUDE_CODE_SESSION_ID=sid-42 bash -c "$STEP2" ); RC=$?
assert_eq "Step 2 ran" "0" "$RC"
CWD_ENC="$(printf '%s' "$T/proj" | sed 's|/|-|g')"
WROTE="$T/st/session-relay/do-plan-config-${CWD_ENC}-sid-42.json"
assert_eq "Step 2 wrote the per-session file under XDG_STATE_HOME" "400000" "$(jq -r '.stop_threshold' "$WROTE" 2>/dev/null)"

echo "== hooks.json: Claude Code path unchanged =="
assert_ge "still registers PostToolUse" "1" "$(grep -c '"PostToolUse"' "$HOOKS" || true)"
if grep -Fq '"PreToolUse"' "$HOOKS"; then
    FAIL=$((FAIL+1)); echo "  FAIL: hooks.json must not register PreToolUse (Claude Code uses PostToolUse; Grok STOP is signals.json)"
else
    PASS=$((PASS+1)); echo "  PASS: hooks.json has no PreToolUse"
fi

echo
echo "RESULTS: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
EOF
bash tests/test-do-plan.sh 2>&1 | tail -1
```

Expected: `RESULTS: … passed, N failed` с N > 0 (среди провалов — `no mesh config-loader anywhere`, `no Claude Code, no Grok → refuses (rc 1)`, `default threshold is 400000`).

- [ ] **Step 2: Карта имён и правки `do-plan`**

Скрипт сам содержит строки ```` ``` ```` (новый текст шага 1 с bash-фрагментом), поэтому блок ниже огорожен четырьмя обратными кавычками. Шаг 1 получает защиту по харнесу, поиск `read-config.py` вместо загрузчика, печать `DEFAULT_STOP=` и окна Grok; шаг 2 — каталог состояния XDG; добавляется подраздел про окно Grok; аргумент описан словами; шаг 7 предлагает herdr-review или mesh-review.

````bash
cd /opt/github/zinin/session-relay
python3 /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py skills/do-plan/SKILL.md
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
def between(path, start, end, new):
    """Replace the text from `start` (inclusive) up to `end` (exclusive); both must occur once."""
    p = pathlib.Path(path); t = p.read_text()
    if t.count(start) != 1 or t.count(end) != 1:
        sys.exit(f"BETWEEN FAIL {path}: {t.count(start)}/{t.count(end)}: {start[:80]!r}")
    a = t.index(start); b = t.index(end)
    if b < a: sys.exit(f"BETWEEN FAIL {path}: end before start")
    p.write_text(t[:a] + new + t[b:])

D = "skills/do-plan/SKILL.md"
rep(D, "description: Execute the loaded plan via superpowers:subagent-driven-development with automatic pause at a context-size threshold. Optional argument is the STOP threshold in tokens; the default comes from runtime.do_plan_default_stop_tokens in config.yaml (default 250000). Examples — /session-relay:do-plan, /session-relay:do-plan 300k, /session-relay:do-plan 400000.",
       "description: Execute the loaded plan via superpowers:subagent-driven-development with automatic pause at a context-size threshold. Optional argument is the STOP threshold in tokens; the default comes from stop_tokens in ~/.config/session-relay/config.yaml (default 400000). Examples — /session-relay:do-plan, /session-relay:do-plan 300k, /session-relay:do-plan 400000.")
rep(D, "- Session context size crosses the configured STOP threshold (default = `runtime.do_plan_default_stop_tokens` from config.yaml, 250 000 if unset).",
       "- Session context size crosses the configured STOP threshold (default = `stop_tokens` from `~/.config/session-relay/config.yaml`, 400 000 if unset).")
rep(D, "- **Grok:** that hook is **not the primary** STOP channel.",
       "- **Anywhere else** (Codex, a bare terminal): nothing reports the context size, so a run would never pause. Step 1 refuses to start there.\n- **Grok:** that hook is **not the primary** STOP channel.")
between(D, "### Resolve the config-driven default", "The `2)` arm tolerates exactly one case", """### Resolve the config-driven default

When no argument is given, the STOP threshold is `stop_tokens` from `~/.config/session-relay/config.yaml` (`$XDG_CONFIG_HOME/session-relay/config.yaml` when that is set), read by `read-config.py` next to this file. Claude Code substitutes the plugin root into this file's text; Grok and Codex do not, hence the version-sorted globs as fallback — installed-plugins first, and only inside a Grok session:

```bash
# A STOP needs a signal: the PostToolUse hook on Claude Code (CLAUDECODE is set in its Bash
# calls), signals.json on Grok (GROK_SESSION_ID). Anywhere else — Codex, for one — nothing tells
# this session how full its context is, and a run that cannot pause must not start.
if [ -z "${CLAUDECODE:-}" ] && [ -z "${GROK_SESSION_ID:-}" ]; then
    echo "/session-relay:do-plan: do-plan здесь не поддерживается: нет сигнала о заполнении контекста (нужен Claude Code или Grok)." >&2
    exit 1
fi
SR_READ="${CLAUDE_PLUGIN_ROOT}/skills/do-plan/read-config.py"
[ -f "$SR_READ" ] || [ -z "${GROK_SESSION_ID:-}" ] || SR_READ="$(find "$HOME"/.grok/installed-plugins -path '*session-relay*/skills/do-plan/read-config.py' 2>/dev/null | sort -V | tail -1)" || true
[ -f "$SR_READ" ] || SR_READ="$(find "$HOME"/.claude/plugins -path '*session-relay*/skills/do-plan/read-config.py' 2>/dev/null | sort -V | tail -1)" || true
[ -f "$SR_READ" ] || SR_READ="$(find "$HOME"/.grok/plugins -path '*session-relay*/skills/do-plan/read-config.py' 2>/dev/null | sort -V | tail -1)" || true
[ -f "$SR_READ" ] || { echo "/session-relay:do-plan: read-config.py not found (is session-relay installed?)" >&2; exit 1; }
GM=""
trap 'rm -f "$GM"' EXIT

# read-config.py prints the default for a missing file and exits 1 with <file>:<line> on a
# config mistake — a typo must never quietly move the threshold, so both reads fail fast.
DEFAULT_STOP=$(python3 "$SR_READ" get stop_tokens) || exit 1
# Dispatch model for subagents. Empty = inherit the session model.
DISPATCH_MODEL=$(python3 "$SR_READ" get dispatch_model) || exit 1
# On Grok, pass dispatch_model only if it is a live host slug. opus is not.
# Probe failure / empty catalog / missing timeout(1) → inherit (fail closed):
# better than a spawn_subagent rejected for an unknown model.
if [ -n "${GROK_SESSION_ID:-}" ] && [ -n "$DISPATCH_MODEL" ]; then
    HOST_MODELS=""
    if ! command -v timeout >/dev/null 2>&1; then
        echo "ВНИМАНИЕ: timeout(1) отсутствует — grok models не запускался; dispatch_model=$DISPATCH_MODEL не проверялся, наследуем модель сессии" >&2
        DISPATCH_MODEL=""
    else
        GM=$(mktemp -t do-plan-host-models-XXXXXX) \\
            || { echo "/session-relay:do-plan: mktemp failed for host catalog" >&2; exit 1; }
        GMT="${GROK_MODELS_TIMEOUT:-${PREFLIGHT_CLI_TIMEOUT:-30}}"
        case "$GMT" in
            ''|*[!0-9]*|0) echo "ВНИМАНИЕ: GROK_MODELS_TIMEOUT='$GMT' не число — использую 30" >&2; GMT=30 ;;
        esac
        LIST_HM="$(dirname "$SR_READ")/list-host-models.sh"
        if [ ! -f "$LIST_HM" ]; then
            echo "ВНИМАНИЕ: list-host-models.sh не найден — dispatch_model=$DISPATCH_MODEL не проверялся, наследуем модель сессии" >&2
            DISPATCH_MODEL=""
        elif timeout "$GMT" grok models >"$GM" 2>/dev/null; then
            HOST_MODELS=$(bash "$LIST_HM" --from-file "$GM")
        fi
        rm -f "$GM"
        GM=""
        if [ -z "$DISPATCH_MODEL" ]; then
            : # already inherit (missing list-host-models.sh)
        elif [ -z "$HOST_MODELS" ]; then
            echo "ВНИМАНИЕ: каталог хоста пуст или grok models не удался — dispatch_model=$DISPATCH_MODEL не передаём, наследуем модель сессии" >&2
            DISPATCH_MODEL=""
        elif ! printf '%s\\n' "$HOST_MODELS" | grep -Fxq -- "$DISPATCH_MODEL"; then
            echo "ВНИМАНИЕ: dispatch_model=$DISPATCH_MODEL нет в каталоге хоста — наследуем модель сессии" >&2
            DISPATCH_MODEL=""
        fi
    fi
    echo "HOST_MODELS=[$(printf '%s' "$HOST_MODELS" | tr '\\n' ' ')]"
fi
echo "DEFAULT_STOP=$DEFAULT_STOP"       # the threshold when no argument was given
echo "DISPATCH_MODEL=$DISPATCH_MODEL"   # surface to the controller (empty = inherit session)
# Grok: the controller polls this file for STOP (Step 6). Same glob the hook uses.
if [ -n "${GROK_SESSION_ID:-}" ]; then
    grok_home="${GROK_HOME:-$HOME/.grok}"
    CONTEXT_SIGNALS=""
    for f in "$grok_home"/sessions/*/"$GROK_SESSION_ID"/signals.json; do
        [ -f "$f" ] && CONTEXT_SIGNALS="$f" && break
    done
    echo "CONTEXT_SIGNALS=$CONTEXT_SIGNALS"
    # The window this session's model has; checked against the threshold below.
    CONTEXT_WINDOW=""
    [ -z "$CONTEXT_SIGNALS" ] || CONTEXT_WINDOW=$(jq -r '.contextWindowTokens // empty' "$CONTEXT_SIGNALS" 2>/dev/null)
    echo "CONTEXT_WINDOW=$CONTEXT_WINDOW"
fi
```

""")
between(D, "The `2)` arm tolerates exactly one case", "### Parse the argument", """A missing config file is not an error — the defaults apply. Any mistake in an existing file (an unknown or repeated key, `stop_tokens` that is not a whole number or is below 150000, a `dispatch_model` outside `[A-Za-z0-9._:@-]`) stops here with `<file>:<line>: <reason>`. Do NOT regress this to a silent default: a typo would move the STOP threshold without anyone noticing.

""")
rep(D, """`$ARGUMENTS` (if any) is the STOP threshold in tokens. Accepted formats:

| Input | Resolved tokens |
|---|---|
| (empty) | value of `$DEFAULT_STOP` (`runtime.do_plan_default_stop_tokens`, default `250000`) |""", """The argument is the text after the skill name in the invocation (Claude Code appends it as `ARGUMENTS:`; Grok and Codex pass it in the message). It is the STOP threshold in tokens. Accepted formats:

| Input | Resolved tokens |
|---|---|
| (empty) | the `DEFAULT_STOP=` value printed in Step 1 (`stop_tokens`, default `400000`) |""")
rep(D, "This floor applies to both an explicit `$ARGUMENTS` value and the config-driven `$DEFAULT_STOP`. The config side is already enforced earlier by `validate_runtime` (Task 7), so by the time `/session-relay:do-plan` reads `$DEFAULT_STOP` it is known to satisfy the floor — this check primarily guards an explicit too-low argument.",
       "This floor applies to both an explicit argument and the config-driven `DEFAULT_STOP`. `read-config.py` already enforces it for the config, so this check primarily guards an explicit too-low argument.")
rep(D, """Do not invoke any skill, do not write the config file, do not start execution.

## Step 2""", """Do not invoke any skill, do not write the config file, do not start execution.

### On Grok: compare the threshold with the context window

When Step 1 printed a number after `CONTEXT_WINDOW=` and the resolved threshold is **not below** it, the threshold can never be reached: Grok compacts the conversation before the count gets there, so STOP would never fire. Output this one line, then continue:

```
ВНИМАНИЕ: порог <THRESHOLD> не меньше окна контекста модели <CONTEXT_WINDOW> — STOP не сработает. Задайте порог меньше окна, например /session-relay:do-plan <CONTEXT_WINDOW × 0.7, rounded down to thousands>.
```

An empty `CONTEXT_WINDOW=` (no `signals.json` yet, or no such field) means the window is unknown: say nothing. Claude Code prints no window at all; skip this check there.

## Step 2""")
between(D, "The hook reads `<plugin-data>/state/do-plan-config-<cwd-encoded>-<session>.json`", "# Bind the hook to THIS session via a PER-SESSION config file", """The hook reads `~/.local/state/session-relay/do-plan-config-<cwd-encoded>-<session>.json` (`$XDG_STATE_HOME/session-relay/…` when that is set) to know the STOP threshold, where `<cwd-encoded>` is the absolute `pwd` with every `/` replaced by `-` and `<session>` is the current session id. The hook (`check-context-size.sh`) computes `<cwd-encoded>` from the same `pwd` encoding and the directory from the same `XDG_STATE_HOME` rule, so both sides land on one path under a marketplace install and under a `--plugin-dir` dev load alike. Session id: Claude Code uses the transcript filename stem; Grok uses `sessionId` / `$GROK_SESSION_ID` — this file's `SID` must be byte-equal to that key. Per-session keying lets two concurrent `/do-plan` runs in one cwd coexist without clobbering each other's threshold.

Use Bash:

```bash
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/session-relay"
mkdir -p "$STATE_DIR"
CWD_ENC=$(pwd | sed 's|/|-|g')

""")
rep(D, """CONFIG_PATH="$PLUGIN_DATA/state/do-plan-config-${CWD_ENC}-${SID}.json"
CONFIG_TMP="$(mktemp "$PLUGIN_DATA/state/.do-plan-config-${CWD_ENC}-${SID}.XXXXXX")" \\""",
"""CONFIG_PATH="$STATE_DIR/do-plan-config-${CWD_ENC}-${SID}.json"
CONFIG_TMP="$(mktemp "$STATE_DIR/.do-plan-config-${CWD_ENC}-${SID}.XXXXXX")" \\""")
rep(D, "/session-relay:do-plan: STOP threshold = 250000 tokens. Dispatch model = <DISPATCH_MODEL>, full review rigor. Starting subagent-driven-development.",
       "/session-relay:do-plan: STOP threshold = 400000 tokens. Dispatch model = <DISPATCH_MODEL>, full review rigor. Starting subagent-driven-development.")
rep(D, "- The dispatch model is `$DISPATCH_MODEL`, resolved in Step 1 from config `runtime.dispatch_model`, then (on Grok) dropped unless it is a live host slug.",
       "- The dispatch model is `$DISPATCH_MODEL`, resolved in Step 1 from `dispatch_model` in the session-relay config, then (on Grok) dropped unless it is a live host slug.")
rep(D, "  - **Empty** (no config value, no config.yaml, or the configured slug is not a host model)",
       "  - **Empty** (no `dispatch_model` in the config, no config file, or the configured slug is not a host model)")
rep(D, "check that the hook's STOP-marker file (`<plugin-data>/state/context-stop-<session>.txt`) exists",
       "check that the hook's STOP-marker file (`~/.local/state/session-relay/context-stop-<session>.txt`) exists")
rep(D, """`/mesh-review:code-review-fresh-session` generates the prompt, carrying the git range and what
only this session knows — deviations from the plan, what was left unfinished, known weak spots.""",
"""Which external review to offer depends on what is installed. Inside herdr (`HERDR_ENV=1`),
`/herdr-review:review` launches it right here. With the mesh-review plugin installed,
`/mesh-review:code-review-fresh-session` writes the prompt for a fresh session, carrying the git
range and what only this session knows — deviations from the plan, what was left unfinished,
known weak spots. With neither, say so and offer the user's own review before finishing.""")
rep(D, "verdict; `skills/shared/preflight-env.sh` has a dedicated branch for exactly this, and calls",
       "verdict; mesh-exec's `skills/shared/preflight-env.sh` has a dedicated branch for exactly this, and calls")
rep(D, "- `/session-relay:do-plan` — threshold = `runtime.do_plan_default_stop_tokens` from config.yaml (default 250 000)",
       "- `/session-relay:do-plan` — threshold = `stop_tokens` from `~/.config/session-relay/config.yaml` (default 400 000)")
print("task7 do-plan patch applied")
PY
sed -i 's|^# Claude Code slash-command Bash has CLAUDE_CODE_SESSION_ID; Grok has GROK_SESSION_ID$|# Claude Code'"'"'s Bash calls have CLAUDE_CODE_SESSION_ID; Grok has GROK_SESSION_ID|' skills/do-plan/SKILL.md
grep -nE 'claude-mesh|config-loader|PLUGIN_DATA|slash-command' skills/do-plan/SKILL.md; echo "---"
````

Expected: `task7 do-plan patch applied`, затем только `---`.

- [ ] **Step 3: Прогнать тесты**

```bash
cd /opt/github/zinin/session-relay
for f in tests/test-*.sh; do printf '%-28s %s\n' "$(basename $f)" "$(bash $f 2>&1 | tail -1)"; done
```

Expected: `test-do-plan.sh RESULTS: 34 passed, 0 failed`; остальные как в Task 6.

- [ ] **Step 4: Commit**

```bash
cd /opt/github/zinin/session-relay
git add skills/do-plan/SKILL.md tests/test-do-plan.sh
git commit -m "feat: do-plan reads its own config, keeps state under XDG and refuses hosts without a context signal"
```

---

### Task 8: session-relay — хук, остальные скиллы, манифест и документация

**Репозиторий:** `/opt/github/zinin/session-relay`.

**Files:**
- Modify: `hooks/check-context-size.sh`, `skills/{pause-after-current-task,transfer-session,exec-plan-fresh-session,continue-plan-fresh-session}/SKILL.md`
- Test: `tests/test-check-context-size.sh`, `tests/test-do-plan.sh` (добавляется сквозная проверка хука)
- Create: `.claude-plugin/plugin.json`, `README.md`, `AGENTS.md`, `CHANGELOG.md`, `.gitignore`

**Interfaces:**
- Consumes: путь шага 2 из Task 7.
- Produces: хук читает `${XDG_STATE_HOME:-$HOME/.local/state}/session-relay/`, игнорируя `CLAUDE_PLUGIN_DATA` и `GROK_PLUGIN_DATA`; плагин `session-relay` 0.16.0 для смоука.

- [ ] **Step 1: Добавить сквозную проверку «шаг 2 → хук»**

```bash
cd /opt/github/zinin/session-relay
python3 - <<'PY'
import pathlib
ins = r'''echo "== the hook reads the directory Step 2 wrote =="
HOOK_DIR_LINE="$(grep -E '^STATE_DIR=' "$HOOK")"
HOOK_DIR="$(XDG_STATE_HOME="$T/st" bash -c "$HOOK_DIR_LINE"$'\n''printf %s "$STATE_DIR"')"
assert_eq "the hook reads the same directory" "$T/st/session-relay" "$HOOK_DIR"
# End to end: a transcript over the threshold makes the hook say STOP for this session.
TRANSCRIPT="$T/sid-42.jsonl"
jq -nc '{type:"assistant",message:{usage:{input_tokens:410000,cache_creation_input_tokens:0,cache_read_input_tokens:0}}}' > "$TRANSCRIPT"
STDIN="$(jq -nc --arg t "$TRANSCRIPT" --arg c "$T/proj" '{transcript_path:$t,cwd:$c,hook_event_name:"PostToolUse",session_id:"sid-42"}')"
HOUT="$(printf '%s' "$STDIN" | env -u CLAUDE_PLUGIN_DATA -u GROK_PLUGIN_DATA XDG_STATE_HOME="$T/st" bash "$HOOK" 2>/dev/null)"
assert_has "the hook fires STOP from the file Step 2 wrote" "STOP threshold=400k" "$HOUT"'''
p = pathlib.Path("tests/test-do-plan.sh"); t = p.read_text()
anchor = 'echo "== hooks.json: Claude Code path unchanged =="'
assert t.count(anchor) == 1, "anchor"
p.write_text(t.replace(anchor, ins + anchor))
print("hook check inserted")
PY
bash tests/test-do-plan.sh 2>&1 | grep -E '^\s+FAIL|RESULTS'
```

Expected: `FAIL: the hook reads the same directory …`, `FAIL: the hook fires STOP from the file Step 2 wrote …`, `RESULTS: 34 passed, 2 failed`.

- [ ] **Step 2: Хук на пути XDG, карта имён в хуке и остальных скиллах**

```bash
cd /opt/github/zinin/session-relay
python3 /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py \
  skills/pause-after-current-task/SKILL.md skills/transfer-session/SKILL.md \
  skills/exec-plan-fresh-session/SKILL.md skills/continue-plan-fresh-session/SKILL.md hooks/check-context-size.sh
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
H = "hooks/check-context-size.sh"
rep(H, "#      ${CLAUDE_PLUGIN_DATA}/state/do-plan-config-<cwd-encoded>-<session>.json):",
       "#      ${XDG_STATE_HOME:-~/.local/state}/session-relay/do-plan-config-<cwd-encoded>-<session>.json):")
rep(H, """# Source of truth: github.com/zinin/claude-mesh/hooks/check-context-size.sh
# Wired in:        github.com/zinin/claude-mesh/hooks/hooks.json
# Reads state from: ${CLAUDE_PLUGIN_DATA:-$GROK_PLUGIN_DATA}/state/""",
"""# Source of truth: github.com/zinin/session-relay/hooks/check-context-size.sh
# Wired in:        github.com/zinin/session-relay/hooks/hooks.json
# Reads state from: ${XDG_STATE_HOME:-~/.local/state}/session-relay/ — the directory do-plan
# writes, computed the same way on every harness. The plugin-data variables Claude Code and
# Grok export into hooks are ignored: under a --plugin-dir load they named a different
# directory from the one do-plan wrote, and the STOP threshold silently never fired.""")
rep(H, 'STATE_DIR="${CLAUDE_PLUGIN_DATA:-${GROK_PLUGIN_DATA:-$HOME/.claude/plugins/data/claude-mesh-zinin}}/state"',
       'STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/session-relay"')

T = "tests/test-check-context-size.sh"
t = pathlib.Path(T).read_text()
t = t.replace('$tmp/state', '$tmp/session-relay').replace('CLAUDE_PLUGIN_DATA="$tmp"', 'XDG_STATE_HOME="$tmp"')
pathlib.Path(T).write_text(t)
rep(T, """#   data_via: "claude" (default) sets CLAUDE_PLUGIN_DATA; "grok" sets only GROK_PLUGIN_DATA
#   so the hook must honour the Grok alias when the Claude one is unset.""",
"""#   data_via: "claude" (default) also exports CLAUDE_PLUGIN_DATA, "grok" GROK_PLUGIN_DATA — both
#   pointing elsewhere: the hook must read $XDG_STATE_HOME/session-relay and nothing else.""")
rep(T, """    env_args=(GROK_HOME="$tmp/grok" GROK_SESSION_ID="$session")
    if [ "$data_via" = grok ]; then
        env_args+=(GROK_PLUGIN_DATA="$tmp")
        out="$(printf '%s' "$stdin" | env -u CLAUDE_PLUGIN_DATA "${env_args[@]}" bash "$HOOK" 2>/dev/null)"; rc=$?
    else
        env_args+=(XDG_STATE_HOME="$tmp")
        out="$(printf '%s' "$stdin" | env "${env_args[@]}" bash "$HOOK" 2>/dev/null)"; rc=$?
    fi""", """    env_args=(GROK_HOME="$tmp/grok" GROK_SESSION_ID="$session" XDG_STATE_HOME="$tmp")
    if [ "$data_via" = grok ]; then
        env_args+=(GROK_PLUGIN_DATA="$tmp/elsewhere")
        out="$(printf '%s' "$stdin" | env -u CLAUDE_PLUGIN_DATA "${env_args[@]}" bash "$HOOK" 2>/dev/null)"; rc=$?
    else
        env_args+=(CLAUDE_PLUGIN_DATA="$tmp/elsewhere")
        out="$(printf '%s' "$stdin" | env "${env_args[@]}" bash "$HOOK" 2>/dev/null)"; rc=$?
    fi""")
rep(T, 'assert_contains "Grok: GROK_PLUGIN_DATA (no CLAUDE_PLUGIN_DATA) + 200k → ctx:200k"',
       'assert_contains "Grok: GROK_PLUGIN_DATA ignored, XDG state read + 200k → ctx:200k"')
print("task8 hook patch applied")
PY
sed -i 's/fresh Claude Code session/fresh agent session/g; s/new, clean Claude Code session/new, clean agent session/g' \
  skills/transfer-session/SKILL.md skills/exec-plan-fresh-session/SKILL.md skills/continue-plan-fresh-session/SKILL.md
sed -i 's/The whole point of this command is to stop/The whole point of this skill is to stop/' skills/pause-after-current-task/SKILL.md
grep -rnE 'claude-mesh|Claude Code session|this command' skills hooks; echo "---"
for f in tests/test-*.sh; do printf '%-28s %s\n' "$(basename $f)" "$(bash $f 2>&1 | tail -1)"; done
```

Expected: `task8 hook patch applied`; до `---` ничего; `test-check-context-size.sh RESULTS: 22 passed, 0 failed`, `test-do-plan.sh RESULTS: 36 passed, 0 failed`, `test-list-host-models.sh … 11 passed`, `test-read-config.sh … 28 passed`.

- [ ] **Step 3: Commit кода**

```bash
cd /opt/github/zinin/session-relay
git add hooks/check-context-size.sh skills tests/test-check-context-size.sh tests/test-do-plan.sh
git commit -m "feat: the context hook reads the state do-plan writes under XDG, whatever the harness"
```

- [ ] **Step 4: Манифест, `.gitignore`, README, AGENTS.md, CHANGELOG**

```bash
cd /opt/github/zinin/session-relay
mkdir -p .claude-plugin
cat > .claude-plugin/plugin.json <<'EOF'
{
  "name": "session-relay",
  "version": "0.16.0",
  "displayName": "Session Relay",
  "description": "Run a plan until the context fills up, pause at a clean checkpoint, and hand the work to a fresh session",
  "author": {
    "name": "Alexander V. Zinin",
    "email": "azinin@gmail.com",
    "url": "https://github.com/zinin"
  },
  "repository": "https://github.com/zinin/session-relay",
  "license": "MIT",
  "keywords": ["agent-skills", "plan-execution", "context", "session-handoff", "subagent-driven-development"]
}
EOF
cp /opt/github/zinin/claude-mesh/.gitignore .gitignore
```

`README.md`:

````markdown
# session-relay

Run an implementation plan until the context fills up, pause at a clean checkpoint, and hand
the work to a fresh session. An [Agent Skills](https://agentskills.io) plugin for Claude Code
and Grok, installable in Codex. Split out of claude-mesh 0.15.0.

## Skills

- **`/session-relay:do-plan [threshold]`** — run the loaded plan through
  `superpowers:subagent-driven-development` and pause at a clean checkpoint once the session
  context crosses the STOP threshold: `stop_tokens` from the config (default 400000), or the
  argument for one run (`300k`, `400000`). Claude Code gets the signal from this plugin's
  `PostToolUse` hook, Grok from the session's `signals.json`; on Grok, do-plan also warns when
  the threshold is not below the model's context window. Where neither signal exists — Codex,
  a bare terminal — do-plan refuses to start.
- **`/session-relay:pause-after-current-task`** — finish the current task in full (spec review,
  code review, fixes), then stop before the next one.
- **`/session-relay:continue-plan-fresh-session`**, **`/session-relay:exec-plan-fresh-session`**,
  **`/session-relay:transfer-session`** — write a prompt that resumes the plan, starts it, or
  carries any work over, in a fresh session. The prompt goes to a file under `docs/`; the chat
  gets only its path.

`do-plan` needs the [superpowers](https://github.com/obra/superpowers) plugin.

## Install

### Claude Code

```
/plugin marketplace add zinin/agent-plugins
/plugin install session-relay@zinin
```

### Grok

Nothing to do when Claude Code has it: Grok loads the plugins Claude Code installed. Without
Claude Code: `grok plugin marketplace add zinin/agent-plugins`, then
`grok plugin install session-relay --trust`.

### Codex

```
codex plugin marketplace add zinin/agent-plugins
codex plugin add session-relay@zinin
```

Codex gets the prompt generators and `pause-after-current-task`. `do-plan` refuses to start
there: Codex tells a session nothing about how full its context is.

## Configure

Optional. `~/.config/session-relay/config.yaml` (`$XDG_CONFIG_HOME/session-relay/config.yaml`
when that is set); `config.example.yaml` is a starting point:

```yaml
stop_tokens: 400000    # STOP threshold in tokens, at least 150000
dispatch_model: opus   # model for do-plan's subagents; leave it out to inherit the session model
```

A mistake in the file stops do-plan with `<file>:<line>` instead of quietly using a default.
The state — the per-session threshold do-plan writes and the hook's markers — lives in
`~/.local/state/session-relay/` (`$XDG_STATE_HOME/session-relay`).

### Moving from claude-mesh

`runtime.do_plan_default_stop_tokens` and `runtime.dispatch_model` in the claude-mesh config are
not read here. The default threshold was 250000 there and is 400000 here; set `stop_tokens`
for the old value, and `dispatch_model` if you had one.

## Tests

`for f in tests/test-*.sh; do bash "$f"; done`

## License

MIT — see [LICENSE](LICENSE).
````

`AGENTS.md`:

````markdown
# session-relay (plugin source)

This file is for work inside this repository. It is not a plugin component.

## Load the working tree

- **Claude Code**, this session only: disable a marketplace copy first
  (`claude plugin disable session-relay@zinin`), then `claude --plugin-dir "$PWD"`; re-enable it
  afterwards.
- **Grok** has no `--plugin-dir` in interactive mode: `grok plugin install "$PWD" --trust`
  copies a snapshot to `~/.grok/installed-plugins/session-relay-<hash>`. After a change,
  `grok plugin uninstall session-relay --confirm` and install again, then start a new session.
  Keep exactly one snapshot: `ls -d ~/.grok/installed-plugins/session-relay-*` lists one entry.

## While working in this repo

- Agents never edit the user's `~/.config/session-relay/config.yaml`.
- Do not bump `.claude-plugin/plugin.json` on a feature branch; a release is a separate
  `chore(release): X.Y.Z` commit on master with an annotated tag `session-relay--vX.Y.Z`.
- Before a PR: `git rm -r docs/superpowers/` when it exists, and commit.
- Tests: `for f in tests/test-*.sh; do bash "$f"; done`.
````

`CHANGELOG.md`:

````markdown
# Changelog

All notable changes to session-relay will be documented here.

## [Unreleased]

### Changed
- **Split out of claude-mesh 0.15.0.** `do-plan`, `pause-after-current-task`, `transfer-session`,
  `exec-plan-fresh-session` and `continue-plan-fresh-session` moved here with their history and
  became skills — `/session-relay:do-plan` and so on — because Codex loads skills, not commands.
- **A config of its own: `~/.config/session-relay/config.yaml`** with `stop_tokens` (default
  400000; claude-mesh's `runtime.do_plan_default_stop_tokens` defaulted to 250000) and
  `dispatch_model`. `read-config.py` reads it without `yq`; a mistake stops do-plan with
  `<file>:<line>`.
- **State under `~/.local/state/session-relay/`**, one path for the hook and do-plan under
  every harness. Under a `--plugin-dir` load the hook used to read another plugin-data
  directory than the one do-plan wrote, and STOP never fired.
- **do-plan refuses to start without a context signal** (Codex, a bare terminal), and on Grok
  warns when the threshold is not below the model's context window.
- **do-plan's end-of-plan review offer** names `/herdr-review:review` or the mesh-review plugin,
  whichever is there, instead of `/claude-mesh:code-review-fresh-session`.
````

- [ ] **Step 5: Проверить манифест и закоммитить**

```bash
cd /opt/github/zinin/session-relay
claude plugin validate . 2>&1 | tail -3
git add .claude-plugin/plugin.json .gitignore README.md AGENTS.md CHANGELOG.md
git commit -m "docs: session-relay manifest, README, AGENTS and changelog"
```

Expected: `✔ Validation passed with warnings` с одним предупреждением: в `hooks/hooks.json` `${CLAUDE_PLUGIN_ROOT}` не в кавычках. Оно унаследовано от claude-mesh; пути установки пробелов не содержат, связка хука в этой работе не меняется.

---

### Task 9: mesh-review — поиск `mesh-exec` и своего корня

**Репозиторий:** `/opt/github/zinin/mesh-review`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Create: `skills/shared/find-mesh-exec.sh`, `skills/shared/tests/test-find-mesh-exec.sh`
- Modify: `skills/shared/resolve-plugin-root.sh` (маркер `find-mesh-exec.sh`, шаблон `*mesh-review*`), `skills/shared/tests/test-resolve-plugin-root.sh` (порт + тест 6)

**Interfaces:**
- Produces: `bash skills/shared/find-mesh-exec.sh` → корень `mesh-exec` на stdout, код 0; не найден → код 1 и `mesh-exec не найден: поставьте mesh-exec@zinin …`; `MESH_EXEC_ROOT` без `skills/shared/config-loader.sh` → код 1 и сообщение с именем переменной. Используют Tasks 10 и 11.
- Produces: `resolve-plugin-root.sh` печатает корень mesh-review (маркер `skills/shared/find-mesh-exec.sh`), `claude-mesh` в кеше ему не подходит.

`test-claude-cli-agents.sh` после извлечения описывает весь claude-mesh и в этом репозитории падает; он заменяется в Task 11 — до тех пор его не запускать.

- [ ] **Step 1: Написать тест поиска `mesh-exec`**

```bash
cd /opt/github/zinin/mesh-review
cat > skills/shared/tests/test-find-mesh-exec.sh <<'EOF'
#!/usr/bin/env bash
# Tests for skills/shared/find-mesh-exec.sh — how mesh-review reaches the mesh-exec plugin.
#
# Order under test: MESH_EXEC_ROOT (a --plugin-dir working tree) → ~/.grok/installed-plugins
# (only inside a Grok session) → ~/.claude/plugins → ~/.grok/plugins, each root on its own and
# version-sorted. A claude-mesh cache left over from before the split must never be taken
# for mesh-exec.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$TESTS_DIR/../find-mesh-exec.sh"
FAIL=0
PASS=0
assert_eq() {
    if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "  PASS: $1"
    else FAIL=$((FAIL+1)); echo "  FAIL: $1 (expected '$2', got '$3')"; fi
}
assert_has() {
    case "$3" in *"$2"*) PASS=$((PASS+1)); echo "  PASS: $1" ;;
    *) FAIL=$((FAIL+1)); echo "  FAIL: $1 (no '$2' in '$3')" ;; esac
}
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
plant() {   # plant <dir>: a fake mesh-exec root
    mkdir -p "$1/skills/shared" && : > "$1/skills/shared/config-loader.sh"
}
run() {     # run <HOME> [GROK_SESSION_ID] [MESH_EXEC_ROOT] → OUT ERR RC
    OUT="$(env -u MESH_EXEC_ROOT -u GROK_SESSION_ID HOME="$1" ${2:+GROK_SESSION_ID="$2"} ${3:+MESH_EXEC_ROOT="$3"} \
        bash -c 'set -euo pipefail; bash "$0"' "$SCRIPT" 2>"$T/err")"; RC=$?
    ERR="$(cat "$T/err")"
}

echo "=== MESH_EXEC_ROOT: a working tree wins over anything installed ==="
H="$T/h1"; plant "$H/.claude/plugins/cache/zinin/mesh-exec/9.9.9"; plant "$T/dev"
run "$H" "" "$T/dev"
assert_eq "rc 0" "0" "$RC"; assert_eq "prints the dev tree" "$T/dev" "$OUT"
run "$H" "" "$T/nowhere"
assert_eq "a MESH_EXEC_ROOT without mesh-exec fails loudly (rc 1)" "1" "$RC"
assert_has "…naming the variable" "MESH_EXEC_ROOT=$T/nowhere" "$ERR"

echo "=== the Claude cache: highest version, and never claude-mesh ==="
H="$T/h2"
plant "$H/.claude/plugins/cache/zinin/mesh-exec/0.9.0"; plant "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0"
plant "$H/.claude/plugins/cache/zinin/claude-mesh/0.15.0"
run "$H"
assert_eq "rc 0" "0" "$RC"
assert_eq "0.16.0 over 0.9.0, the old claude-mesh ignored" "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0" "$OUT"
H="$T/h3"; plant "$H/.claude/plugins/cache/zinin/claude-mesh/0.15.0"
run "$H"
assert_eq "only claude-mesh installed → not found (rc 1)" "1" "$RC"
assert_has "…telling what to install" "mesh-exec@zinin" "$ERR"

echo "=== installed-plugins wins only inside a Grok session ==="
H="$T/h4"
plant "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0"; plant "$H/.grok/installed-plugins/mesh-exec-aabbccdd"
run "$H" "grok-session-1"
assert_eq "Grok session: the snapshot" "$H/.grok/installed-plugins/mesh-exec-aabbccdd" "$OUT"
run "$H"
assert_eq "no Grok session: the Claude cache" "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0" "$OUT"

echo "=== set -euo pipefail: a missing installed-plugins dir falls through ==="
H="$T/h5"; plant "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0"
run "$H" "grok-session-1"
assert_eq "rc 0 under strict mode" "0" "$RC"
assert_eq "…and the Claude cache is found" "$H/.claude/plugins/cache/zinin/mesh-exec/0.16.0" "$OUT"

echo "=== ~/.grok/plugins is the last root ==="
H="$T/h6"; plant "$H/.grok/plugins/cache/z/mesh-exec/1.0.0"
run "$H"
assert_eq "found under .grok/plugins" "$H/.grok/plugins/cache/z/mesh-exec/1.0.0" "$OUT"

echo "=== nothing installed ==="
run "$T/empty"
assert_eq "rc 1" "1" "$RC"
assert_eq "nothing on stdout" "" "$OUT"
assert_has "the message says what to do" "mesh-exec не найден: поставьте mesh-exec@zinin" "$ERR"

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" = "0" ]
EOF
bash skills/shared/tests/test-find-mesh-exec.sh 2>&1 | tail -1
```

Expected: `=== Summary: 1 passed, 15 failed ===`.

- [ ] **Step 2: Написать `find-mesh-exec.sh`**

```bash
cd /opt/github/zinin/mesh-review
cat > skills/shared/find-mesh-exec.sh <<'EOF'
#!/usr/bin/env bash
# find-mesh-exec.sh — print the root of the mesh-exec plugin that mesh-review should use.
#
# mesh-review runs mesh-exec's scripts (config-loader.sh, preflight-env.sh, watch-runs.sh,
# verify-delegation.sh, watchdog.sh, list-host-models.sh) and reads its exec skills. They live
# in another plugin, so no path relative to this file reaches them.
#
# Search order, first hit wins:
#   1. $MESH_EXEC_ROOT — a working tree loaded with --plugin-dir. Set but wrong is an error,
#      not a reason to fall back: a dev run must not quietly test the installed copy.
#   2. ~/.grok/installed-plugins — only inside a Grok session (GROK_SESSION_ID set): an
#      unpublished `grok plugin install <tree>` snapshot, the copy `grok inspect` loads.
#   3. ~/.claude/plugins — the marketplace copy; Grok loads it from here too.
#   4. ~/.grok/plugins.
# Each root is searched on its own and version-sorted: one find over several roots would let
# `sort -V` compare whole paths, and `.claude` < `.grok` would decide instead of the version.
# The pattern names mesh-exec only, so a claude-mesh cache left from before the split is
# never taken for it.
set -u
marker="skills/shared/config-loader.sh"
if [ -n "${MESH_EXEC_ROOT:-}" ]; then
    if [ -f "$MESH_EXEC_ROOT/$marker" ]; then
        (cd "$MESH_EXEC_ROOT" && pwd)
        exit 0
    fi
    echo "find-mesh-exec: MESH_EXEC_ROOT=$MESH_EXEC_ROOT has no $marker" >&2
    exit 1
fi
found=""
[ -z "${GROK_SESSION_ID:-}" ] || found="$(find "$HOME"/.grok/installed-plugins -path "*mesh-exec*/$marker" 2>/dev/null | sort -V | tail -1)" || true
[ -n "$found" ] || found="$(find "$HOME"/.claude/plugins -path "*mesh-exec*/$marker" 2>/dev/null | sort -V | tail -1)" || true
[ -n "$found" ] || found="$(find "$HOME"/.grok/plugins -path "*mesh-exec*/$marker" 2>/dev/null | sort -V | tail -1)" || true
if [ -n "$found" ]; then
    (cd "$(dirname "$found")/../.." && pwd)
    exit 0
fi
echo "mesh-exec не найден: поставьте mesh-exec@zinin (mesh-review работает через него)" >&2
exit 1
EOF
chmod +x skills/shared/find-mesh-exec.sh
bash skills/shared/tests/test-find-mesh-exec.sh 2>&1 | grep -E 'FAIL|Summary'
```

Expected: `=== Summary: 16 passed, 0 failed ===`.

- [ ] **Step 3: Свой `resolve-plugin-root.sh` и порт его теста**

```bash
cd /opt/github/zinin/mesh-review
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
R = "skills/shared/resolve-plugin-root.sh"
t = pathlib.Path(R).read_text()
for old, new, n in (("loader_at", "root_at", 5), ("skills/shared/config-loader.sh", "skills/shared/find-mesh-exec.sh", 4),
                    ("claude-mesh", "mesh-review", 5)):
    if t.count(old) != n: sys.exit(f"PATCH FAIL {R}: {old!r} x{t.count(old)} (expected {n})")
    t = t.replace(old, new)
pathlib.Path(R).write_text(t)
rep(R, "#!/usr/bin/env bash\nset -u\n", """#!/usr/bin/env bash
# resolve-plugin-root.sh — print the root of THIS plugin (mesh-review): the directory whose
# skills/shared/ holds find-mesh-exec.sh, code-review-prompt.md and render-template.py.
# mesh-exec, which holds the loader and the run scripts, is found by find-mesh-exec.sh.
set -u
""")
T = "skills/shared/tests/test-resolve-plugin-root.sh"
t = pathlib.Path(T).read_text()
t = t.replace("skills/shared/config-loader.sh", "skills/shared/find-mesh-exec.sh").replace("claude-mesh", "mesh-review")
t = t.replace('SKILL_BASE="$REPO/skills/ext-claude-exec"', 'SKILL_BASE="$REPO/skills/codex-code-review"')
pathlib.Path(T).write_text(t)
rep(T, '\necho "=== Summary:', '''
# 6. A claude-mesh cache left from before the split is not this plugin, even with a higher version.
OLD_HOME="$(mktemp -d)"
mkdir -p "$OLD_HOME/.claude/plugins/cache/zinin/claude-mesh/9.9.9/skills/shared" \\
         "$OLD_HOME/.claude/plugins/cache/zinin/mesh-review/0.16.0/skills/shared"
touch "$OLD_HOME/.claude/plugins/cache/zinin/claude-mesh/9.9.9/skills/shared/config-loader.sh" \\
      "$OLD_HOME/.claude/plugins/cache/zinin/mesh-review/0.16.0/skills/shared/find-mesh-exec.sh"
GOT=$(HOME="$OLD_HOME" GROK_PLUGIN_ROOT= CLAUDE_PLUGIN_ROOT= SKILL_BASE= "$SCRIPT")
assert_eq "claude-mesh 9.9.9 in the cache is ignored" "$OLD_HOME/.claude/plugins/cache/zinin/mesh-review/0.16.0" "$GOT"
rm -rf "$OLD_HOME"
echo "=== Summary:''')
print("task9 root patch applied")
PY
bash skills/shared/tests/test-resolve-plugin-root.sh 2>&1 | grep -E 'FAIL|Summary'
```

Expected: `task9 root patch applied`, `=== Summary: 14 passed, 0 failed ===`.

- [ ] **Step 4: Commit**

```bash
cd /opt/github/zinin/mesh-review
git add skills/shared/find-mesh-exec.sh skills/shared/tests/test-find-mesh-exec.sh \
  skills/shared/resolve-plugin-root.sh skills/shared/tests/test-resolve-plugin-root.sh
git commit -m "feat: find the mesh-exec plugin and this plugin's own root"
```

---

### Task 10: mesh-review — команды

**Репозиторий:** `/opt/github/zinin/mesh-review`.

**Files:**
- Modify: все `commands/*.md`, `skills/*/SKILL.md`, `agents/*.md`, `skills/shared/tests/*.sh` (карта имён); `commands/mesh-review.md` (5 сниппетов поиска → `FINDER`, обработчик кода 2, строка прозы); `commands/{code,design}-review-fresh-session.md` (PREFLIGHT ищет `*mesh-exec*`)
- Test: `skills/shared/tests/test-loader-resolution.sh` (порт), `skills/shared/tests/test-command-sync.sh` (`config-path` в словаре подкоманд)

**Interfaces:**
- Consumes: `find-mesh-exec.sh` (Task 9); `config-loader.sh config-path` (Task 2).
- Produces: каждый сниппет в `mesh-review.md` задаёт `FINDER`, `MESH_EXEC`, `LOADER="$MESH_EXEC/skills/shared/config-loader.sh"`.

- [ ] **Step 1: Карта имён по всему дереву**

```bash
cd /opt/github/zinin/mesh-review
python3 /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py \
  $(git ls-files 'commands/*.md' 'skills/*/SKILL.md' 'agents/*.md' 'skills/shared/tests/*.sh')
grep -rnoE 'claude-mesh:[a-z-]+' commands skills agents | awk -F: '{print $NF}' | sort | uniq -c
```

Expected: пусто (все `claude-mesh:<компонент>` переведены).

- [ ] **Step 2: Сниппеты, обработчик кода 2, PREFLIGHT, тесты**

```bash
cd /opt/github/zinin/mesh-review
python3 - <<'PY'
import pathlib, re, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))

M = "commands/mesh-review.md"
# The five loader snippets. mesh-review's commands reach mesh-exec's loader through
# find-mesh-exec.sh, which they locate in their own plugin exactly as they used to locate
# the loader: the substituted plugin root first, then the version-sorted globs.
glob = "'*claude-mesh*/skills/shared/config-loader.sh'"
lines = [
    'LOADER="${CLAUDE_PLUGIN_ROOT}/skills/shared/config-loader.sh"',
    '[ -f "$LOADER" ] || [ -z "${GROK_SESSION_ID:-}" ] || LOADER="$(find "$HOME"/.grok/installed-plugins -path ' + glob + ' 2>/dev/null | sort -V | tail -1)" || true',
    '[ -f "$LOADER" ] || LOADER="$(find "$HOME"/.claude/plugins -path ' + glob + ' 2>/dev/null | sort -V | tail -1)" || true',
    '[ -f "$LOADER" ] || LOADER="$(find "$HOME"/.grok/plugins -path ' + glob + ' 2>/dev/null | sort -V | tail -1)" || true',
]
pat = re.compile(r"^(?P<ind>[ \t]*)" + re.escape(lines[0]) + r"\n"
                 + "".join(r"(?P=ind)" + re.escape(l) + r"\n" for l in lines[1:])
                 + r'(?P=ind)\[ -f "\$LOADER" \] \|\| \{ echo "[^"\n]*" >&2; exit 1; \}\n', re.M)
fglob = "'*mesh-review*/skills/shared/find-mesh-exec.sh'"
def block(m):
    i = m.group("ind")
    return "".join(i + l + "\n" for l in (
        'FINDER="${CLAUDE_PLUGIN_ROOT}/skills/shared/find-mesh-exec.sh"',
        '[ -f "$FINDER" ] || [ -z "${GROK_SESSION_ID:-}" ] || FINDER="$(find "$HOME"/.grok/installed-plugins -path ' + fglob + ' 2>/dev/null | sort -V | tail -1)" || true',
        '[ -f "$FINDER" ] || FINDER="$(find "$HOME"/.claude/plugins -path ' + fglob + ' 2>/dev/null | sort -V | tail -1)" || true',
        '[ -f "$FINDER" ] || FINDER="$(find "$HOME"/.grok/plugins -path ' + fglob + ' 2>/dev/null | sort -V | tail -1)" || true',
        '[ -f "$FINDER" ] || { echo "find-mesh-exec.sh not found (is mesh-review installed?)" >&2; exit 1; }',
        'MESH_EXEC="$(bash "$FINDER")" || exit 1',
        'LOADER="$MESH_EXEC/skills/shared/config-loader.sh"'))
t = pathlib.Path(M).read_text()
t, n = pat.subn(block, t)
if n != 5: sys.exit(f"PATCH FAIL {M}: expected 5 loader snippets, replaced {n}")
pathlib.Path(M).write_text(t)
rep(M, """  # Name the dir the loader actually reads — a literal placeholder here would be substituted
  # by the harness and, under a --plugin-dir load, would point at the wrong data dir.
  2) echo "config.yaml ещё не создан. Скопируйте config.example.yaml в $("$LOADER" data-dir)/config.yaml, заполните токены и повторите /mesh-review:mesh-review."; rm -f "$LOADER_ERR"; exit 0 ;;""",
"""  # Name the file the loader actually reads, and pass its stderr on: when the old claude-mesh
  # config is still in place, the loader prints the exact command that moves it.
  2) cat "$LOADER_ERR" >&2; echo "config.yaml ещё не создан. Скопируйте config.example.yaml в $("$LOADER" config-path), заполните токены и повторите /mesh-review:mesh-review."; rm -f "$LOADER_ERR"; exit 0 ;;""")
rep(M, "(matches the convention used in other claude-mesh AskUserQuestion sites)",
       "(matches the convention used in other mesh-review AskUserQuestion sites)")

for C in ("commands/code-review-fresh-session.md", "commands/design-review-fresh-session.md"):
    rep(C, "'*claude-mesh*/skills/shared/preflight-env.sh'", "'*mesh-exec*/skills/shared/preflight-env.sh'", count=3)
    rep(C, 'echo "preflight-env.sh not found — older claude-mesh here; expected degradation, NOT a broken environment"',
           'echo "preflight-env.sh not found — no mesh-exec here; expected degradation, NOT a broken environment"')

S_ = "skills/shared/tests/test-command-sync.sh"
rep(S_, "# Keep it equal to the case arms at the bottom of config-loader.sh.",
        "# Keep it equal to the case arms at the bottom of mesh-exec's config-loader.sh.")
rep(S_, "LOADER_SUBCMDS='validate|data-dir|export|",
        "LOADER_SUBCMDS='validate|config-path|data-dir|export|")

L = "skills/shared/tests/test-loader-resolution.sh"
t = pathlib.Path(L).read_text()
t = (t.replace("skills/shared/config-loader.sh", "skills/shared/find-mesh-exec.sh")
      .replace("claude-mesh", "mesh-review").replace('"$LOADER"', '"$FINDER"').replace("LOADER=", "FINDER="))
pathlib.Path(L).write_text(t)
rep(L, """# Regression tests for the config-loader resolution snippet that the slash commands
# duplicate (commands/mesh-review.md x2, commands/do-plan.md x2).""",
"""# Regression tests for the find-mesh-exec.sh resolution snippet that the slash commands
# duplicate (commands/mesh-review.md x5). The snippet locates this plugin's own finder; the
# finder then locates mesh-exec, whose loader the command runs.""")
rep(L, 'assert_eq "7 primary lines across commands/" "7" "$n_primary"', 'assert_eq "5 primary lines across commands/" "5" "$n_primary"')
rep(L, 'assert_eq "7 .claude fallback lines across commands/" "7" "$n_fallback"', 'assert_eq "5 .claude fallback lines across commands/" "5" "$n_fallback"')
rep(L, 'assert_eq "7 .grok fallback lines across commands/" "7" "$n_fallback2"', 'assert_eq "5 .grok fallback lines across commands/" "5" "$n_fallback2"')
rep(L, 'assert_eq "7 installed-plugins fallback lines across commands/" "7" "$n_fallback_inst"', 'assert_eq "5 installed-plugins fallback lines across commands/" "5" "$n_fallback_inst"')
rep(L, 'assert_eq "do-plan.md carries 2" "2" "$(grep -Fxc "$PRIMARY" "$CMD_DIR/do-plan.md")"\n', '')
print("task10 commands patch applied")
PY
grep -nE 'claude-mesh' commands/*.md
for t in test-loader-resolution test-command-sync; do bash skills/shared/tests/$t.sh 2>&1 | tail -1; done
```

Expected: `task10 commands patch applied`; grep — одна строка, `commands/mesh-review.md:108` (комментарий про старый конфиг); `=== Summary: 21 passed, 0 failed ===` и `=== Summary: 95 passed, 0 failed, 1 skipped ===`.

- [ ] **Step 3: Commit**

```bash
cd /opt/github/zinin/mesh-review
git add commands skills agents
git commit -m "refactor: mesh-review commands reach mesh-exec's loader through find-mesh-exec.sh"
```

---

### Task 11: mesh-review — скиллы и агенты

**Репозиторий:** `/opt/github/zinin/mesh-review`.

**Files:**
- Modify: `skills/{claude,codex,gemini,grok,ext-claude}-code-review/SKILL.md`, `skills/mesh-design-review/SKILL.md`, `agents/{claude,codex,gemini,grok,ext-claude}-code-reviewer.md`
- Test (replace): `skills/shared/tests/test-claude-cli-agents.sh`; Create: `skills/shared/tests/test-mesh-exec-fences.sh`

**Interfaces:**
- Consumes: `find-mesh-exec.sh`, свой `resolve-plugin-root.sh` (Task 9); `data-dir`, `config-path` загрузчика (Task 2).
- Produces: в каждом bash-фрагменте, где встречается `$MESH_EXEC`, он присваивается раньше (`MESH_EXEC=$(bash "$SKILL_BASE/../shared/find-mesh-exec.sh") || exit 1`); Grok читает exec-скилл из корня, который печатает `find-mesh-exec.sh`; агенты ищут прогоны в `${XDG_STATE_HOME:-$HOME/.local/state}/mesh/runs/`.

- [ ] **Step 1: Написать контрактные тесты: фрагменты и обработчики кода 2**

```bash
cd /opt/github/zinin/mesh-review
cat > skills/shared/tests/test-mesh-exec-fences.sh <<'EOF'
#!/usr/bin/env bash
# Every bash fence that uses $MESH_EXEC must assign it first.
#
# mesh-review reaches mesh-exec's loader and run scripts through $MESH_EXEC, printed by
# find-mesh-exec.sh. Each fence runs in a fresh shell, so a fence that uses the variable
# without assigning it runs `/skills/shared/config-loader.sh` — a path that does not exist —
# and fails far from the cause. The fences are extracted and checked one by one.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$TESTS_DIR/../../.." && pwd)"
FAIL=0
PASS=0
USES=0
bad=0
for f in "$REPO"/skills/*/SKILL.md "$REPO"/commands/*.md; do
    report="$(awk -v file="${f#"$REPO"/}" '
        /^[ \t]*```bash[ \t]*$/ { in_f = 1; start = NR; assigned = 0; next }
        in_f && /^[ \t]*```[ \t]*$/ { in_f = 0; next }
        in_f {
            line = $0
            if (line ~ /MESH_EXEC=/) assigned = 1
            tmp = line; gsub(/MESH_EXEC=/, "", tmp)
            if (tmp ~ /\$MESH_EXEC/ || tmp ~ /\$\{MESH_EXEC/) {
                uses++
                if (!assigned) printf "BAD %s:%d (fence from line %d)\n", file, NR, start
            }
        }
        END { printf "USES %d\n", uses }' "$f")"
    USES=$((USES + $(printf '%s\n' "$report" | awk '/^USES/ {print $2}')))
    while IFS= read -r l; do
        [ -n "$l" ] || continue
        bad=$((bad+1)); echo "    $l"
    done < <(printf '%s\n' "$report" | grep '^BAD' || true)
done
if [ "$bad" = 0 ]; then PASS=$((PASS+1)); echo "  PASS: every \$MESH_EXEC use follows its assignment in the same fence"
else FAIL=$((FAIL+1)); echo "  FAIL: $bad use(s) of \$MESH_EXEC before assignment"; fi
if [ "$USES" -ge 10 ]; then PASS=$((PASS+1)); echo "  PASS: the check saw $USES uses (non-vacuous)"
else FAIL=$((FAIL+1)); echo "  FAIL: only $USES uses of \$MESH_EXEC seen — did the fences move?"; fi
echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" = "0" ]
EOF
cat > skills/shared/tests/test-missing-config-handler.sh <<'EOF'
#!/usr/bin/env bash
# With no config yet, both orchestrators must hand the loader's own message to the user.
#
# The first run after the rename finds the old claude-mesh config in Claude Code's plugin-data
# dir and no ~/.config/mesh/config.yaml. The loader exits 2 and prints the exact cp command on
# stderr; an rc=2 arm that swallows stderr leaves the user with a generic "copy the example"
# and a config they already have. The arm must also name the file through `config-path` —
# `data-dir` is the state dir now, not where the config lives.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$TESTS_DIR/../../.." && pwd)"
FAIL=0
PASS=0
check() {   # check <desc> <file>
    local desc="$1" f="$2" arm
    arm="$(grep -E '^[[:space:]]*2\) ' "$f" | grep -F 'config.yaml ещё не создан')"
    if [ "$(printf '%s\n' "$arm" | grep -c .)" != 1 ]; then
        FAIL=$((FAIL+1)); echo "  FAIL: $desc: expected exactly one rc=2 arm, found $(printf '%s\n' "$arm" | grep -c .)"; return
    fi
    case "$arm" in
        *'cat "$LOADER_ERR" >&2'*) PASS=$((PASS+1)); echo "  PASS: $desc passes the loader's stderr on" ;;
        *) FAIL=$((FAIL+1)); echo "  FAIL: $desc swallows the loader's stderr" ;;
    esac
    case "$arm" in
        *'"$LOADER" config-path'*) PASS=$((PASS+1)); echo "  PASS: $desc names the file via config-path" ;;
        *) FAIL=$((FAIL+1)); echo "  FAIL: $desc does not name the file via config-path" ;;
    esac
    case "$arm" in
        *'data-dir)/config.yaml'*) FAIL=$((FAIL+1)); echo "  FAIL: $desc still points at the data dir" ;;
        *) PASS=$((PASS+1)); echo "  PASS: $desc no longer points at the data dir" ;;
    esac
}
check "mesh-review" "$REPO/commands/mesh-review.md"
check "mesh-design-review" "$REPO/skills/mesh-design-review/SKILL.md"
echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" = "0" ]
EOF
bash skills/shared/tests/test-mesh-exec-fences.sh 2>&1 | tail -3
bash skills/shared/tests/test-missing-config-handler.sh 2>&1 | grep -E 'FAIL|Summary'
```

Expected: `FAIL: only 5 uses of $MESH_EXEC seen — did the fences move?` (пока их используют только сниппеты команд из Task 10), `=== Summary: 1 passed, 1 failed ===`; обработчик `mesh-design-review` ещё старый — `FAIL: mesh-design-review swallows the loader's stderr`, `… does not name the file via config-path`, `… still points at the data dir`, `=== Summary: 3 passed, 3 failed ===`.

- [ ] **Step 2: Правки скиллов и агентов**

```bash
cd /opt/github/zinin/mesh-review
python3 - <<'PY'
import pathlib, re, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:300]}")
    p.write_text(t.replace(old, new))
def sub(path, pattern, repl, count, flags=0):
    p = pathlib.Path(path); t, n = re.subn(pattern, repl, p.read_text(), flags=flags)
    if n != count:
        sys.exit(f"SUB FAIL {path}: expected {count}, replaced {n}: {pattern[:120]}")
    p.write_text(t)

REVIEW_SKILLS = ["claude-code-review", "codex-code-review", "gemini-code-review", "grok-code-review", "ext-claude-code-review"]
SKILLS = [f"skills/{s}/SKILL.md" for s in REVIEW_SKILLS + ["mesh-design-review"]]
FIND_MX = 'MESH_EXEC=$(bash "$SKILL_BASE/../shared/find-mesh-exec.sh") || exit 1'
for f in SKILLS:
    p = pathlib.Path(f); t = p.read_text()
    # The locator blocks now look for THIS plugin by its own marker, find-mesh-exec.sh.
    t = t.replace('[ -f "$_R/skills/shared/config-loader.sh" ] && { _LOADER="$_R/skills/shared/config-loader.sh"; break; }',
                  '[ -f "$_R/skills/shared/find-mesh-exec.sh" ] && { _LOADER="$_R/skills/shared/find-mesh-exec.sh"; break; }')
    t = t.replace("'*claude-mesh*/skills/shared/config-loader.sh'", "'*mesh-review*/skills/shared/find-mesh-exec.sh'")
    t = re.sub(r"\b_LOADER\b", "_MARKER", t)
    t = t.replace("claude-mesh plugin root not found", "mesh-review plugin root not found")
    t = t.replace("Grok loads a marketplace claude-mesh from the Claude cache", "Grok loads a marketplace mesh-review from the Claude cache")
    # mesh-exec's loader, reached through the finder.
    t = re.sub(r'^([ \t]*)LOADER="\$SKILL_BASE/\.\./shared/config-loader\.sh"$',
               lambda m: f'{m.group(1)}{FIND_MX}\n{m.group(1)}LOADER="$MESH_EXEC/skills/shared/config-loader.sh"', t, flags=re.M)
    t = t.replace("Shared scripts live at `$SKILL_BASE/../shared/<x>` (e.g. `code-review-prompt.md`); the loader is `$SKILL_BASE/../shared/config-loader.sh`.",
                  "This plugin's own shared files live at `$SKILL_BASE/../shared/<x>` (e.g. `code-review-prompt.md`); the loader and the run scripts are mesh-exec's, at `$MESH_EXEC/skills/shared/<x>` with `MESH_EXEC=$(bash \"$SKILL_BASE/../shared/find-mesh-exec.sh\")`.")
    # Grok, no Skill tool: read the exec skill from mesh-exec's root, found by the finder.
    t = re.sub(r"^\*\*If this host has no Skill tool\*\* \(Grok Build\): `Read` the plugin's `skills/([a-z-]+-exec)/SKILL\.md` and follow every step\. "
               r"Plugin root: `\$CLAUDE_PLUGIN_ROOT` or `\$GROK_PLUGIN_ROOT` if set to an existing directory; otherwise\n`find [^\n]*'\*claude-mesh\*/skills/\1/SKILL\.md'[^\n]*\n",
               r"**If this host has no Skill tool** (Grok Build): `Read` mesh-exec's `skills/\1/SKILL.md` and follow every step. mesh-exec's root is what "
               r"`bash \"$SKILL_BASE/../shared/find-mesh-exec.sh\"` prints — `$MESH_EXEC_ROOT` when set, else `$HOME/.grok/installed-plugins` (inside a Grok session only), "
               r"then `$HOME/.claude/plugins`, then `$HOME/.grok/plugins`, each version-sorted.\n", t, flags=re.M)
    t = t.replace("${CLAUDE_PLUGIN_DATA}/runs/", "~/.local/state/mesh/runs/")
    t = t.replace("claude-mesh never substitutes a model of its own.", "mesh-review never substitutes a model of its own.")
    t = t.replace("(the loader self-discovers `~/.claude/plugins/data/claude-mesh-*`)", "(`~/.local/state/mesh`, or `$XDG_STATE_HOME/mesh` when that is set)")
    p.write_text(t)

rep("skills/ext-claude-code-review/SKILL.md",
    "Shared scripts live at `$SKILL_BASE/../shared/<x>`; get the data dir via `\"$LOADER\" data-dir` where `LOADER=\"$SKILL_BASE/../shared/config-loader.sh\"`.",
    "This plugin's own shared files live at `$SKILL_BASE/../shared/<x>`; mesh-exec's at `$MESH_EXEC/skills/shared/<x>`, with `MESH_EXEC=$(bash \"$SKILL_BASE/../shared/find-mesh-exec.sh\")`. Get the data dir via `\"$LOADER\" data-dir` where `LOADER=\"$MESH_EXEC/skills/shared/config-loader.sh\"`.")

D = "skills/mesh-design-review/SKILL.md"
rep(D, "- loader = `$SKILL_BASE/../shared/config-loader.sh`\n- sibling shared scripts = `$SKILL_BASE/../shared/<x>`",
       "- loader = `$MESH_EXEC/skills/shared/config-loader.sh`, where `MESH_EXEC=$(bash \"$SKILL_BASE/../shared/find-mesh-exec.sh\")` — the loader and the run scripts belong to the mesh-exec plugin\n- this plugin's own shared files = `$SKILL_BASE/../shared/<x>`; mesh-exec's run scripts = `$MESH_EXEC/skills/shared/<x>`")
rep(D, '   WATCH="$SKILL_BASE/../shared/watch-runs.sh"', f'   {FIND_MX}\n   WATCH="$MESH_EXEC/skills/shared/watch-runs.sh"')
rep(D, '   VERIFY="$SKILL_BASE/../shared/verify-delegation.sh"\n   DATA_DIR="$("$SKILL_BASE/../shared/config-loader.sh" data-dir)"',
       f'   {FIND_MX}\n   VERIFY="$MESH_EXEC/skills/shared/verify-delegation.sh"\n   DATA_DIR="$("$MESH_EXEC/skills/shared/config-loader.sh" data-dir)"')
rep(D, """  # Name the dir the loader actually reads — a literal placeholder here would be substituted
  # by the harness and, under a --plugin-dir load, would point at the wrong data dir.
  2) echo "config.yaml ещё не создан. Скопируйте config.example.yaml в $("$LOADER" data-dir)/config.yaml, заполните токены и повторите /mesh-review:mesh-design-review."; rm -f "$LOADER_ERR"; exit 0 ;;""",
"""  # Name the file the loader actually reads, and pass its stderr on: when the old claude-mesh
  # config is still in place, the loader prints the exact command that moves it.
  2) cat "$LOADER_ERR" >&2; echo "config.yaml ещё не создан. Скопируйте config.example.yaml в $("$LOADER" config-path), заполните токены и повторите /mesh-review:mesh-design-review."; rm -f "$LOADER_ERR"; exit 0 ;;""")
rep(D, "(plugin `subagent_type`s are `claude-mesh:`-namespaced — verified on CC 2.1.156; bare names do not",
       "(plugin `subagent_type`s are plugin-namespaced — `mesh-exec:` for the executors, `mesh-review:` for review-discussion — verified on CC 2.1.156; bare names do not")
rep(D, "Plugin types stay `claude-mesh:`-namespaced.", "Plugin types stay plugin-namespaced (`mesh-exec:` executors, `mesh-review:` review-discussion).")
rep(D, "# built-in agent type — NOT claude-mesh:-namespaced", "# built-in agent type — NOT plugin-namespaced")
rep(D, "subagent_type: [claude-mesh:<executor>]", "subagent_type: [mesh-exec:<executor>]")
rep(D, "never prefix it with `claude-mesh:`.", "never prefix it with a plugin namespace.")

AGENTS = [f"agents/{a}-code-reviewer.md" for a in ("claude", "codex", "gemini", "grok", "ext-claude")]
for f in AGENTS:
    p = pathlib.Path(f); t = p.read_text()
    t = t.replace("'*claude-mesh*/skills/", "'*mesh-review*/skills/")
    t = t.replace('for d in "$HOME"/.claude/plugins/data/claude-mesh-*/runs/', 'for d in "${XDG_STATE_HOME:-$HOME/.local/state}"/mesh/runs/')
    t = re.sub(r"Do NOT expand `\$\{CLAUDE_PLUGIN_DATA\}` in a Bash call: it is EMPTY there\s+\(Task 2\.5\), so a literal `\$\{CLAUDE_PLUGIN_DATA\}/runs/(\w+)/\.\.\.` searches `/runs/\1` and finds\s+nothing — which would report a review that ran as one that did not\. Glob the data dir instead\.",
               r"Run dirs live under\n`~/.local/state/mesh/runs/\1/` (`$XDG_STATE_HOME/mesh/runs/\1/` when `XDG_STATE_HOME` is set).", t)
    t = re.sub(r"\(Task 2\.5: `\$\{CLAUDE_PLUGIN_DATA\}` is empty in agent Bash calls — glob the data dir(, newest run dirs by mtime)?\)",
               r"(run dirs live under `~/.local/state/mesh/runs/`\1)", t)
    t = t.replace("${CLAUDE_PLUGIN_DATA}/runs/", "~/.local/state/mesh/runs/")
    p.write_text(t)
print("task11 skills/agents patch applied")
PY
grep -rnE "claude-mesh|CLAUDE_PLUGIN_DATA\}/runs|plugins/data/|_LOADER\b" skills/*/SKILL.md agents/*.md
grep -rnE '\$SKILL_BASE/\.\./shared/(config-loader|watch-runs|verify-delegation|preflight-env|watchdog|list-host-models)' skills; echo "---"
```

Expected: `task11 skills/agents patch applied`; первый grep — одна строка, `skills/mesh-design-review/SKILL.md:302` (комментарий про старый конфиг); до `---` больше ничего.

- [ ] **Step 3: Заменить `test-claude-cli-agents.sh` половиной про ревьюеров**

```bash
cd /opt/github/zinin/mesh-review
cat > skills/shared/tests/test-claude-cli-agents.sh <<'EOF'
#!/usr/bin/env bash
# Contract for the mesh-review wrapper agents and review skills.
#
# claude-code-reviewer dispatches official `claude -p` through mesh-exec's ext-claude-exec
# (HOST_CLAUDE=1): catalog aliases (opus, fable), no tooling constraint, run dirs under
# runs/claude/. The executor half of this file stayed in mesh-exec with the executors.
set -u
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$TESTS_DIR/../../.." && pwd)"

FAIL=0
PASS=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS+1)); echo "  PASS: $desc"
    else
        FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_ge() {
    local desc="$1" min="$2" actual="$3"
    case "$actual" in
        ''|*[!0-9]*)
            FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected a count >= $min, got '$actual' — did the file move?)"
            return ;;
    esac
    if [ "$actual" -ge "$min" ]; then
        PASS=$((PASS+1)); echo "  PASS: $desc ($actual >= $min)"
    else
        FAIL=$((FAIL+1)); echo "  FAIL: $desc (expected >= $min, got $actual)"
    fi
}

echo "=== Test: claude CLI reviewer and review skill ==="
assert_eq "reviewer agent exists" "1" "$([ -f "$REPO/agents/claude-code-reviewer.md" ] && echo 1 || echo 0)"
assert_eq "review skill exists" "1" "$([ -f "$REPO/skills/claude-code-review/SKILL.md" ] && echo 1 || echo 0)"
assert_eq "reviewer does not STOP when MODEL is omitted" "0" \
    "$(grep -c 'ERROR: MODEL parameter is required on first line' "$REPO/agents/claude-code-reviewer.md")"
assert_ge "reviewer still invokes skill when MODEL omitted" "1" \
    "$(grep -c 'If the first line is not `MODEL=`, still invoke the skill' "$REPO/agents/claude-code-reviewer.md")"
assert_ge "reviewer names HOST_CLAUDE" "1" \
    "$(grep -c 'HOST_CLAUDE=1' "$REPO/skills/claude-code-review/SKILL.md")"
assert_eq "review skill has no tooling-constraint section" "0" \
    "$(grep -c '## Tooling constraint' "$REPO/skills/claude-code-review/SKILL.md")"

echo ""
echo "=== Test: wrapper dual-path invoke + Grok wait ==="
AGENTS="$REPO/agents"
WRAPPERS="codex-code-reviewer.md gemini-code-reviewer.md grok-code-reviewer.md ext-claude-code-reviewer.md claude-code-reviewer.md"
forbid=0
for f in $WRAPPERS; do
    grep -q 'Do NOT read SKILL.md' "$AGENTS/$f" && forbid=$((forbid+1))
done
assert_eq "no wrapper still forbids reading SKILL.md" "0" "$forbid"
missing=0
for f in $WRAPPERS; do
    grep -q 'If this host has no Skill tool' "$AGENTS/$f" || missing=$((missing+1))
    grep -q 'do not end the turn while the CLI is alive' "$AGENTS/$f" || missing=$((missing+1))
done
assert_eq "every wrapper has dual invoke + Grok wait" "0" "$missing"

echo ""
echo "=== Test: empty-SKILL_BASE else-branch is in the fence ==="
# Prose telling the LLM to rewrite is not enough: the executable fence must contain the find
# fallback. Every resolve-plugin-root.sh call via $SKILL_BASE must sit in `if [ -n "$SKILL_BASE" ]`,
# and the else-branch finds THIS plugin by its own marker, find-mesh-exec.sh.
SKILLS_WITH_RESOLVER="claude-code-review ext-claude-code-review codex-code-review gemini-code-review grok-code-review mesh-design-review"
mismatch=0
for s in $SKILLS_WITH_RESOLVER; do
    f="$REPO/skills/$s/SKILL.md"
    n_resolve="$(grep -c 'bash "$SKILL_BASE/../shared/resolve-plugin-root.sh"' "$f" || true)"
    n_if="$(grep -c 'if \[ -n "\$SKILL_BASE" \]; then' "$f" || true)"
    n_find="$(grep -c 'mesh-review\*/skills/shared/find-mesh-exec.sh' "$f" || true)"
    n_installed="$(grep -c 'installed-plugins' "$f" || true)"
    if [ "$n_resolve" != "$n_if" ] || [ "$n_find" -lt "$n_if" ]; then
        mismatch=$((mismatch+1))
        echo "    mismatch $s: resolve=$n_resolve if=$n_if find=$n_find"
    fi
    if [ "$n_installed" -lt "$n_if" ]; then
        mismatch=$((mismatch+1))
        echo "    mismatch $s: installed-plugins=$n_installed if=$n_if"
    fi
done
assert_eq "every resolver fence has empty-SKILL_BASE else-branch" "0" "$mismatch"

echo ""
echo "=== Test: Grok reads each exec skill from mesh-exec, through find-mesh-exec.sh ==="
# The review skill → exec SKILL.md hop crosses into another plugin. The no-Skill-tool paragraph
# must hand the path to find-mesh-exec.sh (MESH_EXEC_ROOT, then installed-plugins inside a Grok
# session, then .claude, then .grok) and must not name the old plugin.
REVIEW_SKILLS="claude-code-review ext-claude-code-review codex-code-review gemini-code-review grok-code-review"
read_bad=0
for s in $REVIEW_SKILLS; do
    para="$(awk '/If this host has no Skill tool/,/Following the skill/' "$REPO/skills/$s/SKILL.md")"
    printf '%s' "$para" | grep -q 'find-mesh-exec.sh' || { read_bad=$((read_bad+1)); echo "    $s: no find-mesh-exec.sh"; }
    if printf '%s' "$para" | grep -q 'claude-mesh'; then read_bad=$((read_bad+1)); echo "    $s: still names claude-mesh"; fi
done
assert_eq "every review→exec Read goes through find-mesh-exec.sh" "0" "$read_bad"

echo ""
echo "=== Test: resolver fences keep the ROOT ORDER, and the prose agrees ==="
# Every fence holds exactly one find per root, so pairing the i-th line of each root by position
# checks every fence: the installed-plugins line must precede the .claude line, which must
# precede the .grok line.
order_bad=0
for s in $SKILLS_WITH_RESOLVER; do
    f="$REPO/skills/$s/SKILL.md"
    inst="$(grep -boF 'find "$HOME"/.grok/installed-plugins -path' "$f" | cut -d: -f1)"
    cc="$(grep -boF 'find "$HOME"/.claude/plugins -path' "$f" | cut -d: -f1)"
    gp="$(grep -boF 'find "$HOME"/.grok/plugins -path' "$f" | cut -d: -f1)"
    n_i="$(printf '%s\n' "$inst" | grep -c .)"; n_c="$(printf '%s\n' "$cc" | grep -c .)"; n_g="$(printf '%s\n' "$gp" | grep -c .)"
    if [ "$n_i" -eq 0 ] || [ "$n_i" != "$n_c" ] || [ "$n_c" != "$n_g" ]; then
        order_bad=$((order_bad+1)); echo "    $s: find counts installed=$n_i claude=$n_c grok=$n_g"; continue
    fi
    if ! paste <(printf '%s\n' "$inst") <(printf '%s\n' "$cc") <(printf '%s\n' "$gp") | while IFS=$'\t' read -r a b c; do
            [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ] || { echo "    $s: fence order wrong at byte offsets $a/$b/$c"; exit 1; }
        done; then
        order_bad=$((order_bad+1))
    fi
    [ "$(grep -cF 'searches `$HOME/.grok/installed-plugins` first' "$f")" = 1 ] \
        || { order_bad=$((order_bad+1)); echo "    $s: prose does not say installed-plugins first (exactly once)"; }
    [ "$(grep -cF 'searches `$HOME/.claude/plugins` first' "$f")" = 0 ] \
        || { order_bad=$((order_bad+1)); echo "    $s: stale prose says .claude first"; }
done
assert_eq "every skill fence searches installed-plugins, .claude, .grok in that order, and the prose says so" "0" "$order_bad"

echo ""
echo "=== Test: every root-find assignment is guarded against find rc=1 ==="
# The three roots are each a `find | sort | tail` assignment. Any one of them on a missing
# directory is a set -e hole; `|| true` after the assignment is the contract.
unprotected=0
while IFS= read -r line; do
    printf '%s\n' "$line" | grep -q '|| true[[:space:]]*$' && continue
    unprotected=$((unprotected+1))
    echo "    unguarded: $line"
done < <(grep -h 'find "$HOME"/.*/find-mesh-exec.sh' \
    "$REPO"/skills/*/SKILL.md "$REPO"/commands/*.md \
    "$REPO"/skills/shared/resolve-plugin-root.sh || true)
assert_ge "the guard check saw the finds" "20" \
    "$(grep -h 'find "$HOME"/.*/find-mesh-exec.sh' "$REPO"/skills/*/SKILL.md "$REPO"/commands/*.md "$REPO"/skills/shared/resolve-plugin-root.sh | grep -c .)"
assert_eq "every root find assignment ends with || true" "0" "$unprotected"

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" = "0" ]
EOF
for f in skills/shared/tests/test-*.sh; do printf '%-36s %s\n' "$(basename $f)" "$(bash $f 2>&1 | grep -E Summary | tail -1)"; done
```

Expected: все девять наборов с `0 failed`: `test-claude-cli-agents` 13, `test-command-sync` 95 (+1 skipped), `test-find-mesh-exec` 16, `test-grok-code-review-bindings` 8, `test-loader-resolution` 21, `test-mesh-exec-fences` 2, `test-missing-config-handler` 6, `test-render-template` 44, `test-resolve-plugin-root` 14.

- [ ] **Step 4: Проверить, что контрактный тест действительно ловит нарушение**

```bash
cd /opt/github/zinin/mesh-review
cp skills/codex-code-review/SKILL.md /tmp/agent-plugins-codex-skill.bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/codex-code-review/SKILL.md")
p.write_text(p.read_text().replace('MESH_EXEC=$(bash "$SKILL_BASE/../shared/find-mesh-exec.sh") || exit 1\n', '', 1))
PY
bash skills/shared/tests/test-mesh-exec-fences.sh 2>&1 | grep -E 'FAIL|Summary'
cp /tmp/agent-plugins-codex-skill.bak skills/codex-code-review/SKILL.md && git diff --stat -- skills/codex-code-review/SKILL.md | tail -1
```

Expected: `FAIL: 1 use(s) of $MESH_EXEC before assignment`, `=== Summary: 1 passed, 1 failed ===`; после восстановления файл совпадает с состоянием после Step 2.

- [ ] **Step 5: Commit**

```bash
cd /opt/github/zinin/mesh-review
git add skills agents skills/shared/tests/test-claude-cli-agents.sh skills/shared/tests/test-mesh-exec-fences.sh skills/shared/tests/test-missing-config-handler.sh
git commit -m "refactor: review skills and agents run mesh-exec's scripts and read runs under XDG"
```

---

### Task 12: mesh-review — манифест и документация

**Репозиторий:** `/opt/github/zinin/mesh-review`.

**Files:**
- Create: `.claude-plugin/plugin.json`, `README.md`, `AGENTS.md`, `CHANGELOG.md`, `.gitignore`

**Interfaces:**
- Produces: `plugin.json` с `"dependencies": ["mesh-exec", "session-relay"]` — Claude Code ставит их вместе с mesh-review из того же каталога.

- [ ] **Step 1: Манифест и `.gitignore`**

```bash
cd /opt/github/zinin/mesh-review
mkdir -p .claude-plugin
cat > .claude-plugin/plugin.json <<'EOF'
{
  "name": "mesh-review",
  "version": "0.16.0",
  "displayName": "Mesh Review",
  "description": "Multi-model code and design review from inside the session: parallel reviewers on Claude, Codex, Gemini, Grok and alt-provider models, merged findings, auto-fixes and a guided walk through the disputed ones",
  "author": {
    "name": "Alexander V. Zinin",
    "email": "azinin@gmail.com",
    "url": "https://github.com/zinin"
  },
  "repository": "https://github.com/zinin/mesh-review",
  "license": "MIT",
  "keywords": ["agent-skills", "code-review", "design-review", "multi-model", "claude-code", "grok"],
  "dependencies": ["mesh-exec", "session-relay"]
}
EOF
cp /opt/github/zinin/claude-mesh/.gitignore .gitignore
```

- [ ] **Step 2: README**

Пункты раздела «Commands and skills» переписаны из раздела Features README claude-mesh с новыми именами. Файл целиком:

````markdown
# mesh-review

Multi-model review orchestrated from inside the agent session: `/mesh-review:mesh-review` for
code, `/mesh-review:mesh-design-review` for a design document and its plan. Reviewers run in
parallel — the session's own model, Codex, Gemini, Grok and alt-provider models — and the
orchestrator merges their findings, fixes the clear ones and walks you through the disputed
ones. For Claude Code and Grok. Split out of claude-mesh 0.15.0.

For everyday code review consider [herdr-review](https://github.com/zinin/herdr-review): it runs
under any harness and keeps every reviewer in a visible tab. mesh-review stays for sessions
without herdr and for design review, which herdr-review does not do.

## Commands and skills

- **`/mesh-review:mesh-review`** — orchestrate code review across multiple models in parallel;
  add `autodecide` to have the disputed issues decided for you — same full analysis, an explicit
  self-check, one commit per decision. `default` runs the `defaults.code_review` preset,
  `BASE_BRANCH=<branch>` sets the base.
- **`/mesh-review:mesh-design-review`** — iterative design-doc review with discussion of issues;
  remembers earlier answers and filters duplicates; takes the same `autodecide` argument.
- **`/mesh-review:auto-decide-disputed`** — invoke mid-review to hand the remaining disputed
  issues to the agent itself: it writes the same structured analysis, rebuts its own
  recommendation in a `Проверка решения` section, marks each decision `уверенно` /
  `под вопросом`, and commits them one by one — `git log --grep=auto-decide-disputed` lists the
  run, `git revert` undoes any single decision.
- **`/mesh-review:code-review-fresh-session`, `/mesh-review:design-review-fresh-session`** —
  sandbox-aware prompts for a fresh session that reviews rather than implements. They never
  name a model: the session runs mesh-exec's `skills/shared/preflight-env.sh` where it actually
  lives and picks reviewers from what that reports — for a review in another machine, VM or
  sandbox with its own `config.yaml`.
- **Reviewer agents `mesh-review:codex-code-reviewer`, `gemini-code-reviewer`,
  `grok-code-reviewer`, `ext-claude-code-reviewer`, `claude-code-reviewer`** and the matching
  `/mesh-review:<engine>-code-review` skills — one external reviewer each, run through
  mesh-exec's exec skills. The grok reviewer takes a `MODEL` from the `grok.models` catalog, so
  one review can run several grok models; `claude-code-reviewer` is how `builtin: claude`
  resolves on Grok, where there is no in-process Claude.
- **Grok Build** — both orchestrators detect Grok by the presence of `spawn_subagent` and
  dispatch native `general-purpose` reviewers (`builtin: native`, slugs from `grok models`)
  alongside the CLI wrappers.

## Requires

- **mesh-exec** — the config loader, the run scripts, the exec skills and the executor agents.
  Claude Code installs it together with mesh-review (`dependencies` in `plugin.json`).
  `skills/shared/find-mesh-exec.sh` finds it: `$MESH_EXEC_ROOT`, then
  `~/.grok/installed-plugins` inside a Grok session, then `~/.claude/plugins`, then
  `~/.grok/plugins`.
- **session-relay** — design review ends by handing over to
  `/session-relay:continue-plan-fresh-session`.
- **The config** is mesh-exec's `~/.config/mesh/config.yaml`; review presets live in its
  `defaults:` section, runs under `~/.local/state/mesh/runs/`. See mesh-exec's README.

## Install

### Claude Code

```
/plugin marketplace add zinin/agent-plugins
/plugin install mesh-review@zinin
```

### Grok

Loaded from the Claude Code install. Without Claude Code: `grok plugin marketplace add
zinin/agent-plugins`, then `grok plugin install <name> --trust` for mesh-exec, session-relay
and mesh-review.

### Codex

Not supported: the orchestrators dispatch plugin agents, and Codex has none.

## Tests

`for f in skills/shared/tests/test-*.sh; do bash "$f"; done`

## License

MIT — see [LICENSE](LICENSE).
````

- [ ] **Step 3: AGENTS.md и CHANGELOG**

`AGENTS.md`:

````markdown
# mesh-review (plugin source)

This file is for work inside this repository. It is not a plugin component.

## Load the working tree

mesh-review needs mesh-exec and session-relay. Load all three working trees and point the
finder at mesh-exec's:

```bash
cd /opt/github/zinin/mesh-review
MESH_EXEC_ROOT=/path/to/mesh-exec claude --plugin-dir /path/to/mesh-exec \
  --plugin-dir /path/to/session-relay --plugin-dir "$PWD"
```

Disable marketplace copies of the three first (`claude plugin disable <name>@zinin`) and
re-enable them afterwards. In Grok install a snapshot of each (`grok plugin install <path>
--trust`), one snapshot per plugin; `MESH_EXEC_ROOT` is not needed there — the finder takes
the `installed-plugins` snapshot inside a Grok session.

## Cross-plugin contract

mesh-review runs mesh-exec's `config-loader.sh` (subcommands `data-dir`, `config-path`,
`get-flag`, `get-defaults`, `get-runtime`, `list-models`, `list-claude-models`,
`list-grok-models`, `get-codex`, `get-gemini`), `preflight-env.sh`, `watch-runs.sh`,
`verify-delegation.sh`, `watchdog.sh` and `list-host-models.sh`, and invokes its exec skills and
executor agents by name. A change to that interface ships in the same release on both sides.

## While working in this repo

- Agents never edit the user's `~/.config/mesh/config.yaml`.
- Do not bump `.claude-plugin/plugin.json` on a feature branch; a release is a separate
  `chore(release): X.Y.Z` commit on master with an annotated tag `mesh-review--vX.Y.Z`.
- Before a PR: `git rm -r docs/superpowers/` when it exists, and commit.
- Tests: `for f in skills/shared/tests/test-*.sh; do bash "$f"; done`.
````

`CHANGELOG.md`:

````markdown
# Changelog

All notable changes to mesh-review will be documented here.

## [Unreleased]

### Changed
- **Split out of claude-mesh 0.15.0.** `/mesh-review`, `/mesh-design-review`,
  `auto-decide-disputed`, the two review prompt generators, the five `*-code-review` skills and
  `*-code-reviewer` agents, and `review-discussion` moved here with their history. Names
  change: `/claude-mesh:mesh-review` is `/mesh-review:mesh-review`.
- **Depends on mesh-exec and session-relay** (`dependencies` in `plugin.json`). The loader and
  the run scripts are mesh-exec's; `skills/shared/find-mesh-exec.sh` finds its root.
- **The config is mesh-exec's `~/.config/mesh/config.yaml`**, runs live under
  `~/.local/state/mesh/runs/`. With no config yet, the orchestrators pass on the loader's
  message, which names the command that copies an old claude-mesh config into place.
````

- [ ] **Step 4: Проверить и закоммитить**

```bash
cd /opt/github/zinin/mesh-review
claude plugin validate . 2>&1 | tail -3
git add .claude-plugin/plugin.json .gitignore README.md AGENTS.md CHANGELOG.md
git commit -m "docs: mesh-review manifest with its dependencies, README, AGENTS and changelog"
```

Expected: validate без ошибок.

---

### Task 13: claude-md — плагин

**Репозиторий:** `/opt/github/zinin/claude-md`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Create: `.claude-plugin/plugin.json`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `.gitignore`
- `skills/claude-md-writer/SKILL.md` не меняется: `claude-ebs` вызывает скилл по имени `claude-md-writer`.

**Interfaces:**
- Produces: скилл `claude-md:claude-md-writer` (голое имя `claude-md-writer` по-прежнему находится).

- [ ] **Step 1: Манифест, `.gitignore`, CHANGELOG, AGENTS.md**

```bash
cd /opt/github/zinin/claude-md
mkdir -p .claude-plugin
cat > .claude-plugin/plugin.json <<'EOF'
{
  "name": "claude-md",
  "version": "0.16.0",
  "displayName": "CLAUDE.md Writer",
  "description": "Write and refactor CLAUDE.md files: size budgets, the CLAUDE.md → .claude/rules/ → co-located layout, paths: frontmatter for conditional loading, a quality checklist",
  "author": {
    "name": "Alexander V. Zinin",
    "email": "azinin@gmail.com",
    "url": "https://github.com/zinin"
  },
  "repository": "https://github.com/zinin/claude-md",
  "license": "MIT",
  "keywords": ["agent-skills", "claude-md", "documentation", "rules", "memory"]
}
EOF
cp /opt/github/zinin/claude-mesh/.gitignore .gitignore
cat > CHANGELOG.md <<'EOF'
# Changelog

All notable changes to claude-md will be documented here.

## [Unreleased]

### Changed
- **Split out of claude-mesh 0.15.0.** The `claude-md-writer` skill moved here with its history.
  The skill keeps its name; the command is `/claude-md:claude-md-writer`.
EOF
cat > AGENTS.md <<'EOF'
# claude-md (plugin source)

This file is for work inside this repository. It is not a plugin component.

- Load the working tree in Claude Code with `claude --plugin-dir "$PWD"` (disable a marketplace
  copy first); in Grok with `grok plugin install "$PWD" --trust`, one snapshot at a time.
- The skill is vendored: see Credits in README.md before editing it.
- Do not bump `.claude-plugin/plugin.json` on a feature branch; a release is a separate
  `chore(release): X.Y.Z` commit on master with an annotated tag `claude-md--vX.Y.Z`.
EOF
```

- [ ] **Step 2: README**

Раздел Credits перенесён дословно из README claude-mesh. Файл целиком:

````markdown
# claude-md

Best practices for writing and refactoring `CLAUDE.md` files: size budgets, the three-tier
`CLAUDE.md` → `.claude/rules/` → co-located layout, `paths:` frontmatter for conditional
loading, a quality checklist. One skill, `/claude-md:claude-md-writer`. Split out of
claude-mesh 0.15.0.

The skill is about Claude Code's memory files; Grok reads `CLAUDE.md` too. Codex reads
`AGENTS.md`, so the plugin installs there but has little to do.

## Install

- **Claude Code:** `/plugin marketplace add zinin/agent-plugins`, then
  `/plugin install claude-md@zinin`.
- **Grok:** loaded from the Claude Code install; without Claude Code,
  `grok plugin marketplace add zinin/agent-plugins` and `grok plugin install claude-md --trust`.
- **Codex:** `codex plugin marketplace add zinin/agent-plugins`, then
  `codex plugin add claude-md@zinin`.

## Credits

`skills/claude-md-writer/` is vendored from
[serejaris/personal-corp-os](https://github.com/serejaris/personal-corp-os/tree/main/skills/claude-md-writer)
(MIT), then corrected against the current Claude Code docs — the upstream copy had drifted
since it was written. The skill's own footer lists every change. Upstream still maintains it;
to see what has moved there, diff against
`https://raw.githubusercontent.com/serejaris/personal-corp-os/main/skills/claude-md-writer/SKILL.md`,
expecting our corrections to show up as differences.

## License

MIT — see [LICENSE](LICENSE).
````

- [ ] **Step 3: Проверить и закоммитить**

```bash
cd /opt/github/zinin/claude-md
claude plugin validate . 2>&1 | tail -3
grep -c 'serejaris/personal-corp-os' README.md
git add .claude-plugin/plugin.json .gitignore README.md CHANGELOG.md AGENTS.md
git commit -m "docs: claude-md manifest, README with credits, AGENTS and changelog"
```

Expected: validate без ошибок; `2` (две строки со ссылками на upstream в разделе Credits).

---
### Task 14: build-forge (был claude-forge)

**Репозиторий:** `/opt/github/zinin/claude-forge`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Modify: все текстовые файлы кроме `CHANGELOG.md` (`claude-forge` → `build-forge`), `.claude-plugin/plugin.json` (`displayName`, `keywords`)
- Move: `commands/deps-update.md` → `skills/deps-update/SKILL.md`
- Modify: `CHANGELOG.md` (запись `[Unreleased]`)

**Interfaces:**
- Produces: `/build-forge:build`, `/build-forge:deps-update`, агент `build-forge:build-runner`, скиллы `build-forge:gradle-plugin-updater`, `build-forge:google-maven-updater`.

- [ ] **Step 1: Переименовать и превратить `deps-update` в скилл**

```bash
cd /opt/github/zinin/claude-forge
git ls-files | grep -v '^CHANGELOG.md$' | xargs grep -l 'claude-forge' | xargs sed -i 's/claude-forge/build-forge/g'
sed -i 's|zinin/claude-plugins|zinin/agent-plugins|g' README.md
mkdir -p skills/deps-update && git mv commands/deps-update.md skills/deps-update/SKILL.md
sed -i 's/"displayName": "Claude Forge"/"displayName": "Build Forge"/; s/"claude-code"/"agent-skills"/' .claude-plugin/plugin.json
git ls-files | grep -v '^CHANGELOG.md$' | xargs grep -n 'claude-forge\|claude-plugins'; echo "---"; cat .claude-plugin/plugin.json
```

Expected: до `---` пусто; `"name": "build-forge"`, `"displayName": "Build Forge"`, `"version": "0.2.0"`, `"repository": "https://github.com/zinin/build-forge"`.

- [ ] **Step 2: CHANGELOG**

Вставить перед первым заголовком версии (`## [0.2.0] …`):

```markdown
## [Unreleased]

### Changed
- **Renamed from claude-forge to build-forge.** `/claude-forge:build` is `/build-forge:build`,
  the agent is `build-forge:build-runner`, the updater skills are `build-forge:*`. Permission
  rules that name the old skills (`Skill(claude-forge:…)`) need the new name.
- **`deps-update` is a skill now** (`skills/deps-update/`): Codex loads skills, not commands.
  The invocation stays `/build-forge:deps-update`.
```

Если в файле нет строки `## [Unreleased]`, её не было и раньше — вставляемый блок её создаёт.

- [ ] **Step 3: Проверить и закоммитить**

```bash
cd /opt/github/zinin/claude-forge
claude plugin validate . 2>&1 | tail -3
git add -u && git add skills/deps-update/SKILL.md
git status --short
git commit -m "refactor: rename the plugin to build-forge and make deps-update a skill"
```

Expected: validate без ошибок; `git status --short` показывает только изменённые и перенесённые файлы плагина (`git add -u` берёт только отслеживаемые).

---

### Task 15: atlassian-scout (был claude-atlassian)

**Репозиторий:** `/opt/github/zinin/claude-atlassian`.

**Files:**
- Modify: все текстовые файлы кроме `CHANGELOG.md` и `docs/` (`claude-atlassian` → `atlassian-scout`), `.claude-plugin/plugin.json` (`displayName`, `keywords`), `CHANGELOG.md`

**Interfaces:**
- Produces: `/atlassian-scout:analyze-jira-ticket`, `/atlassian-scout:analyze-wiki`, `/atlassian-scout:investigate-bug`, `/atlassian-scout:investigate-feature`.

- [ ] **Step 1: Переименовать**

```bash
cd /opt/github/zinin/claude-atlassian
git ls-files | grep -vE '^(CHANGELOG\.md|docs/)' | xargs grep -l 'claude-atlassian' | xargs sed -i 's/claude-atlassian/atlassian-scout/g'
sed -i 's|zinin/claude-plugins|zinin/agent-plugins|g' README.md
sed -i 's/"displayName": "Claude Atlassian"/"displayName": "Atlassian Scout"/; s/"claude-code"/"agent-skills"/' .claude-plugin/plugin.json
git ls-files | grep -vE '^(CHANGELOG\.md|docs/)' | xargs grep -n 'claude-atlassian\|claude-plugins'; echo "---"
python3 -m unittest discover -s tests -t . 2>&1 | tail -2
```

Expected: до `---` пусто; `Ran 172 tests …`, `OK`.

- [ ] **Step 2: CHANGELOG** — вставить перед первым заголовком версии:

```markdown
## [Unreleased]

### Changed
- **Renamed from claude-atlassian to atlassian-scout.** The skills keep their names:
  `/claude-atlassian:analyze-jira-ticket` is `/atlassian-scout:analyze-jira-ticket`, and so on.
```

- [ ] **Step 3: Проверить и закоммитить**

```bash
cd /opt/github/zinin/claude-atlassian
claude plugin validate . 2>&1 | tail -3
git add -u && git status --short
git commit -m "refactor: rename the plugin to atlassian-scout"
```

---

### Task 16: prd-flow (был claude-prd)

**Репозиторий:** `/opt/github/zinin/claude-prd` (основная ветка `main`).

**Files:**
- Modify: все текстовые файлы кроме `CHANGELOG.md` (`claude-prd` → `prd-flow`), `.claude-plugin/plugin.json`, `CHANGELOG.md`

**Interfaces:**
- Produces: `/prd-flow:idea-to-prd`, `/prd-flow:refine-prd`, `/prd-flow:refine-tasks`.

- [ ] **Step 1: Переименовать**

```bash
cd /opt/github/zinin/claude-prd
git ls-files | grep -v '^CHANGELOG.md$' | xargs grep -l 'claude-prd' | xargs sed -i 's/claude-prd/prd-flow/g'
sed -i 's|zinin/claude-plugins|zinin/agent-plugins|g' README.md
sed -i 's/"displayName": "Claude PRD"/"displayName": "PRD Flow"/; s/"claude-code"/"agent-skills"/' .claude-plugin/plugin.json
git ls-files | grep -v '^CHANGELOG.md$' | xargs grep -n 'claude-prd\|claude-plugins'; echo "---"
```

Expected: до `---` пусто.

- [ ] **Step 2: CHANGELOG** — вставить перед первым заголовком версии:

```markdown
## [Unreleased]

### Changed
- **Renamed from claude-prd to prd-flow.** The skills keep their names: `/claude-prd:refine-prd`
  is `/prd-flow:refine-prd`, and so on.
```

- [ ] **Step 3: Проверить и закоммитить**

```bash
cd /opt/github/zinin/claude-prd
claude plugin validate . 2>&1 | tail -3
git add -u && git status --short
git commit -m "refactor: rename the plugin to prd-flow"
```

---

### Task 17: каталог `agent-plugins`

**Репозиторий:** `/opt/github/zinin/claude-plugins`, ветка `feature/agent-plugins-restructure`.

**Files:**
- Modify: `.claude-plugin/marketplace.json`, `README.md`

**Interfaces:**
- Produces: каталог `zinin` из девяти плагинов по git-URL `https://github.com/zinin/<name>.git`. Эти URL заработают после Task 23–24; до того каталог проверяется локально.

- [ ] **Step 1: `marketplace.json`**

```bash
cd /opt/github/zinin/claude-plugins
cat > .claude-plugin/marketplace.json <<'EOF'
{
  "name": "zinin",
  "owner": {
    "name": "Alexander V. Zinin",
    "url": "https://github.com/zinin"
  },
  "description": "Agent plugins by zinin for Claude Code, Grok and Codex",
  "plugins": [
    {
      "name": "mesh-exec",
      "source": { "source": "url", "url": "https://github.com/zinin/mesh-exec.git" },
      "description": "Run a prompt through another model's CLI — Codex, Gemini, Grok, Claude Code, alt-provider models — with logging, a watchdog and run directories"
    },
    {
      "name": "session-relay",
      "source": { "source": "url", "url": "https://github.com/zinin/session-relay.git" },
      "description": "Run a plan until the context fills up, pause at a clean checkpoint, and hand the work to a fresh session"
    },
    {
      "name": "mesh-review",
      "source": { "source": "url", "url": "https://github.com/zinin/mesh-review.git" },
      "description": "Multi-model code and design review from inside the session, for Claude Code and Grok; installs mesh-exec and session-relay with it"
    },
    {
      "name": "claude-md",
      "source": { "source": "url", "url": "https://github.com/zinin/claude-md.git" },
      "description": "Write and refactor CLAUDE.md files: size budgets, the three-tier layout, paths: frontmatter, a quality checklist"
    },
    {
      "name": "build-forge",
      "source": { "source": "url", "url": "https://github.com/zinin/build-forge.git" },
      "description": "Build/test/lint delegation and JVM/Android dependency updates (Gradle plugins, Google Maven)"
    },
    {
      "name": "atlassian-scout",
      "source": { "source": "url", "url": "https://github.com/zinin/atlassian-scout.git" },
      "description": "Jira ticket analysis, Confluence page reading, and cross-repository investigation of bugs and of new work via context-protecting subagents"
    },
    {
      "name": "prd-flow",
      "source": { "source": "url", "url": "https://github.com/zinin/prd-flow.git" },
      "description": "Idea to PRD to tasks: collaborative PRD authoring plus autonomous refinement of PRD and tasks.json"
    },
    {
      "name": "herdr-review",
      "source": { "source": "url", "url": "https://github.com/zinin/herdr-review.git" },
      "description": "Multi-agent code review inside herdr: reviewers, an orchestrator and a fixer as visible, interactive agents in their own tabs"
    },
    {
      "name": "codex-base-review",
      "source": { "source": "url", "url": "https://github.com/zinin/codex-base-review.git" },
      "description": "Codex-style PR review against the branch this one was cut from"
    }
  ]
}
EOF
python3 -c 'import json; d=json.load(open(".claude-plugin/marketplace.json")); print(d["name"], len(d["plugins"]))'
claude plugin validate . 2>&1 | tail -3
```

Expected: `zinin 9`; validate без ошибок (предупреждения о недоступных пока URL допустимы — записать).

- [ ] **Step 2: README**

Файл целиком (таблицу «Где что работает» Task 22 уточнит по итогам смоука):

````markdown
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
````

- [ ] **Step 3: Проверить, что Codex читает каталог**

```bash
cd /opt/github/zinin/claude-plugins
CX=$(mktemp -d /tmp/agent-plugins-codex-cat-XXXXXX)
CODEX_HOME="$CX" codex plugin marketplace add /opt/github/zinin/claude-plugins 2>&1 | grep -v 'PATH aliases' | tail -2
CODEX_HOME="$CX" codex plugin list 2>&1 | grep -E '@zinin' | awk '{print $1}'
rm -rf "$CX"
```

Expected: девять строк `mesh-exec@zinin` … `codex-base-review@zinin`.

- [ ] **Step 4: Commit**

```bash
cd /opt/github/zinin/claude-plugins
git add .claude-plugin/marketplace.json README.md
git commit -m "feat: the catalog lists the split and renamed plugins for Claude Code, Grok and Codex"
```

---

### Task 18: ссылки снаружи

**Репозитории и способ:**
- `herdr-review` — worktree `/opt/github/zinin/.worktrees/herdr-review` от `master` (в рабочей копии идёт `feat/build-queue`);
- `codex-base-review` — `git switch -c` в рабочей копии (только неотслеживаемые файлы);
- `ai-tools` — worktree `/opt/gitlab/ai/.worktrees/ai-tools` от `master` (32 незакоммиченных изменения в рабочей копии);
- `claude-private-plugins`, `claude-ebs` — `git switch -c` (рабочие копии чистые);
- `wireguard-network` — worktree `/opt/gitlab/ai/.worktrees/wireguard-network` от `master` (рабочая копия на `wg-overlay-plan-d`).

**Files:** `README.md` в herdr-review и codex-base-review; `claude-tools/settings.json`, `claude-tools/settings-telegram-hook.json`, `cli-proxy/gemini-settings.json` в ai-tools; `README.md` в claude-private-plugins и claude-ebs; `CLAUDE.md` в wireguard-network.

**Interfaces:** ничего не производит для других задач; push — в Task 23.

- [ ] **Step 1: Проверить состояние и создать ветки**

```bash
git -C /opt/github/zinin/codex-base-review status --porcelain --untracked-files=no | wc -l
git -C /opt/gitlab/ai/claude-private-plugins status --porcelain | wc -l
git -C /opt/gitlab/ai/claude-ebs status --porcelain | wc -l
mkdir -p /opt/github/zinin/.worktrees /opt/gitlab/ai/.worktrees
git -C /opt/github/zinin/herdr-review worktree add /opt/github/zinin/.worktrees/herdr-review -b feature/agent-plugins-restructure master
git -C /opt/gitlab/ai/ai-tools worktree add /opt/gitlab/ai/.worktrees/ai-tools -b feature/agent-plugins-restructure master
git -C /opt/gitlab/ai/wireguard-network worktree add /opt/gitlab/ai/.worktrees/wireguard-network -b feature/agent-plugins-restructure master
git -C /opt/github/zinin/codex-base-review switch -c feature/agent-plugins-restructure master
git -C /opt/gitlab/ai/claude-private-plugins switch -c feature/agent-plugins-restructure master
git -C /opt/gitlab/ai/claude-ebs switch -c feature/agent-plugins-restructure master
```

Expected: три нуля; три `Preparing worktree …`; три `Switched to a new branch …`. Ненулевое число — остановиться и спросить пользователя.

- [ ] **Step 2: Правки**

```bash
python3 - <<'PY'
import pathlib, sys
def rep(path, old, new, count=1):
    p = pathlib.Path(path); t = p.read_text(); n = t.count(old)
    if n != count:
        sys.exit(f"PATCH FAIL {path}: expected {count}, found {n}:\n{old[:200]}")
    p.write_text(t.replace(old, new))
rep("/opt/github/zinin/.worktrees/herdr-review/README.md", "/plugin marketplace add zinin/claude-plugins", "/plugin marketplace add zinin/agent-plugins")
rep("/opt/github/zinin/codex-base-review/README.md", "/plugin marketplace add zinin/claude-plugins", "/plugin marketplace add zinin/agent-plugins")
for f in ("claude-tools/settings.json", "claude-tools/settings-telegram-hook.json", "cli-proxy/gemini-settings.json"):
    rep(f"/opt/gitlab/ai/.worktrees/ai-tools/{f}", "Skill(claude-forge:gradle-plugin-updater)", "Skill(build-forge:gradle-plugin-updater)")
rep("/opt/gitlab/ai/claude-private-plugins/README.md",
    "Публичные плагины — в [zinin/claude-plugins](https://github.com/zinin/claude-plugins).",
    "Публичные плагины — в [zinin/agent-plugins](https://github.com/zinin/agent-plugins).")
rep("/opt/gitlab/ai/claude-ebs/README.md",
    "В плагин он не входит и должен быть доступен отдельно — локально в `~/.claude/skills/claude-md-writer`.",
    "В плагин он не входит и ставится отдельно — плагином `claude-md` из каталога `zinin` (`/plugin install claude-md@zinin`).")
rep("/opt/gitlab/ai/.worktrees/wireguard-network/CLAUDE.md",
    "Не отправлять репозиторий на внешнее ревью (claude-mesh и подобные).",
    "Не отправлять репозиторий на внешнее ревью (mesh-review, herdr-review и подобные).")
print("external references updated")
PY
for f in /opt/gitlab/ai/.worktrees/ai-tools/claude-tools/settings.json /opt/gitlab/ai/.worktrees/ai-tools/claude-tools/settings-telegram-hook.json /opt/gitlab/ai/.worktrees/ai-tools/cli-proxy/gemini-settings.json; do python3 -m json.tool "$f" >/dev/null && echo "json ok: $f"; done
```

Expected: `external references updated`; три `json ok`.

- [ ] **Step 3: Коммиты**

```bash
git -C /opt/github/zinin/.worktrees/herdr-review commit -m "docs: the catalog moved to zinin/agent-plugins" -- README.md
git -C /opt/github/zinin/codex-base-review commit -m "docs: the catalog moved to zinin/agent-plugins" -- README.md
git -C /opt/gitlab/ai/.worktrees/ai-tools commit -m "chore: allow build-forge:gradle-plugin-updater (claude-forge was renamed)" -- claude-tools/settings.json claude-tools/settings-telegram-hook.json cli-proxy/gemini-settings.json
git -C /opt/gitlab/ai/claude-private-plugins commit -m "Витрина: публичный каталог переехал в zinin/agent-plugins" -- README.md
git -C /opt/gitlab/ai/claude-ebs commit -m "README: claude-md-writer ставится плагином claude-md" -- README.md
git -C /opt/gitlab/ai/.worktrees/wireguard-network commit -m "CLAUDE.md: внешнее ревью — mesh-review, herdr-review" -- CLAUDE.md
```

Expected: шесть коммитов, в каждом по одному файлу (в ai-tools — три).

---

### Task 19: пользователь готовит конфиги (ШАГ ПОЛЬЗОВАТЕЛЯ)

Агент не копирует и не создаёт конфиги пользователя — он просит пользователя выполнить команды и ждёт подтверждения.

- [ ] **Step 1: Попросить пользователя выполнить**

```bash
mkdir -p ~/.config/mesh
cp ~/.claude/plugins/data/claude-mesh-zinin/config.yaml ~/.config/mesh/config.yaml
chmod 600 ~/.config/mesh/config.yaml
mkdir -p ~/.config/session-relay
printf 'dispatch_model: opus\n' > ~/.config/session-relay/config.yaml
```

(`dispatch_model: opus` — нынешнее значение `runtime.dispatch_model`; `stop_tokens` не пишется: новый порог по умолчанию 400000.)

- [ ] **Step 2: Проверить после подтверждения**

```bash
bash /opt/github/zinin/claude-mesh/skills/shared/config-loader.sh validate; echo "mesh validate rc=$?"
python3 /opt/github/zinin/session-relay/skills/do-plan/read-config.py get stop_tokens
python3 /opt/github/zinin/session-relay/skills/do-plan/read-config.py get dispatch_model
stat -c '%a %n' ~/.config/mesh/config.yaml
```

Expected: WARN `runtime.do_plan_default_stop_tokens is ignored …` и `mesh validate rc=0`; `400000`; `opus`; `600 …/config.yaml`.

---

### Task 20: смоук в Claude Code

**Где:** рабочие деревья всех семи плагинов через `--plugin-dir`, песочный репозиторий. Опубликованные `claude-*@zinin` остаются установленными — имена не пересекаются.

- [ ] **Step 1: Песочный репозиторий**

```bash
SMOKE=/tmp/agent-plugins-smoke; rm -rf "$SMOKE"; mkdir -p "$SMOKE" && cd "$SMOKE"
git init -q -b master
printf 'def add(a, b):\n    return a + b\n' > calc.py
printf 'from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n' > test_calc.py
git add calc.py test_calc.py && git commit -qm "init"
git switch -qc feature/smoke
printf 'def add(a, b):\n    return a - b\n' > calc.py && git commit -qam "change add"
PD=(--plugin-dir /opt/github/zinin/claude-mesh --plugin-dir /opt/github/zinin/session-relay --plugin-dir /opt/github/zinin/mesh-review \
    --plugin-dir /opt/github/zinin/claude-md --plugin-dir /opt/github/zinin/claude-forge --plugin-dir /opt/github/zinin/claude-atlassian \
    --plugin-dir /opt/github/zinin/claude-prd)
declare -p PD > /tmp/agent-plugins-smoke.pd
```

- [ ] **Step 2: Что видит сессия**

```bash
cd /tmp/agent-plugins-smoke && source /tmp/agent-plugins-smoke.pd
claude -p "${PD[@]}" --output-format stream-json --verbose "Reply OK" < /dev/null 2>/dev/null \
  | jq -r 'select(.type=="system" and .subtype=="init") | (.skills[]?, .agents[]?)' \
  | grep -E '^(mesh-exec|session-relay|mesh-review|claude-md|build-forge|atlassian-scout|prd-flow):' | sort
```

Expected (порядок сортировки): `atlassian-scout:analyze-jira-ticket`, `…:analyze-wiki`, `…:investigate-bug`, `…:investigate-feature`; `build-forge:build`, `build-forge:build-runner`, `build-forge:deps-update`, `build-forge:google-maven-updater`, `build-forge:gradle-plugin-updater`; `claude-md:claude-md-writer`; `mesh-exec:claude-executor`, `mesh-exec:codex-exec`, `mesh-exec:codex-executor`, `mesh-exec:ext-claude-exec`, `mesh-exec:ext-claude-executor`, `mesh-exec:gemini-exec`, `mesh-exec:gemini-executor`, `mesh-exec:grok-exec`, `mesh-exec:grok-executor`; `mesh-review:` — пять `*-code-review`, пять `*-code-reviewer`, `mesh-design-review`, `review-discussion` и четыре команды (`mesh-review`, `auto-decide-disputed`, `code-review-fresh-session`, `design-review-fresh-session`), если Claude Code перечисляет команды в `skills`; `prd-flow:idea-to-prd`, `prd-flow:refine-prd`, `prd-flow:refine-tasks`; `session-relay:` — пять скиллов. Команды `mesh-review:*`, которых нет в `skills`, проверить в `.slash_commands[]` тем же `jq` с `.slash_commands[]?`. Записать фактический список в отчёт задачи.

- [ ] **Step 3: mesh-exec — прогон через исполнителя**

```bash
cd /tmp/agent-plugins-smoke && source /tmp/agent-plugins-smoke.pd
BEFORE=$(date +%s)
claude -p "${PD[@]}" "Use the mesh-exec:codex-executor agent: have Codex reply with the single word PONG. Then print the run directory it created." < /dev/null | tail -5
find "${XDG_STATE_HOME:-$HOME/.local/state}/mesh/runs/codex" -mindepth 1 -maxdepth 1 -type d -newermt "@$BEFORE" | head -3
```

Expected: новый каталог прогона под `~/.local/state/mesh/runs/codex/`, в его `output.txt` есть `PONG`.

- [ ] **Step 4: session-relay — генератор и шаги 1–3 `do-plan`**

```bash
cd /tmp/agent-plugins-smoke && source /tmp/agent-plugins-smoke.pd
claude -p "${PD[@]}" "/session-relay:transfer-session" < /dev/null | tail -3; ls docs/session-transfer-*.md
claude -p "${PD[@]}" "/session-relay:do-plan 300k — smoke test: run Steps 1 to 3 only, then stop before Step 4. There is no plan to execute." < /dev/null | tail -6
ls -t "${XDG_STATE_HOME:-$HOME/.local/state}"/session-relay/do-plan-config-*agent-plugins-smoke* | head -1 | xargs cat
```

Expected: файл `docs/session-transfer-<дата>-<время>.md`; строка `/session-relay:do-plan: STOP threshold = 300000 tokens. Dispatch model = opus …`; `{"stop_threshold":300000}`. Если модель не остановилась после шага 3 — это поведение модели, не плагина: записать и продолжить.

- [ ] **Step 5: mesh-review — один ревьюер через mesh-exec**

```bash
cd /tmp/agent-plugins-smoke && source /tmp/agent-plugins-smoke.pd
BEFORE=$(date +%s)
MESH_EXEC_ROOT=/opt/github/zinin/claude-mesh claude -p "${PD[@]}" "/mesh-review:codex-code-review BASE_BRANCH=master — review the change on this branch" < /dev/null | tail -15
find "${XDG_STATE_HOME:-$HOME/.local/state}/mesh/runs/codex" -mindepth 1 -maxdepth 1 -type d -newermt "@$BEFORE" | head -3
```

Expected: новый каталог прогона; отзыв находит, что `add` вычитает вместо сложения.

- [ ] **Step 6: build-forge — агент под новым именем**

```bash
cd /tmp/agent-plugins-smoke && source /tmp/agent-plugins-smoke.pd
claude -p "${PD[@]}" "/build-forge:build run the Python tests with pytest" < /dev/null | tail -8
```

Expected: отчёт build-runner о прогоне pytest с одним проваленным тестом (`test_add`) — ветка специально сломана.

- [ ] **Step 7: Итог**

Записать в отчёт задачи результаты шагов 2–6. Каталоги данных вида `~/.claude/plugins/data/*-inline`, если Claude Code их создал для `--plugin-dir`, удалить, только если они пусты (`rmdir`).

---

### Task 21: смоук в Grok

- [ ] **Step 1: Поставить снимки рабочих деревьев**

```bash
for p in claude-mesh session-relay mesh-review claude-md claude-forge claude-atlassian claude-prd; do
  grok plugin install "/opt/github/zinin/$p" --trust 2>&1 | tail -1
done
grok inspect --json | python3 -c 'import json,sys
d=json.load(sys.stdin)
for p in d["plugins"]:
    if p["name"] in ("mesh-exec","session-relay","mesh-review","claude-md","build-forge","atlassian-scout","prd-flow"):
        print(p["name"], p["path"])'
```

Expected: семь строк, пути под `~/.grok/installed-plugins/<имя>-<hash>`.

- [ ] **Step 2: Скиллы в сессии**

```bash
cd /tmp/agent-plugins-smoke
grok -p "Reply OK" --output-format streaming-messages-json 2>/dev/null | head -1 \
  | jq -r '.skills[]?' | grep -E '^(mesh-exec|session-relay|mesh-review|claude-md|build-forge|atlassian-scout|prd-flow):' | sort
```

Expected: те же скиллы, что в Task 20 Step 2 (без агентов).

- [ ] **Step 3: Шаг 1 `do-plan` внутри настоящей сессии Grok**

```bash
cd /tmp/agent-plugins-smoke
STEP1="$(awk 'index($0,"### Resolve the config-driven default")==1{s=1;next} s&&/^## /{exit} s&&/^```bash$/{f=1;next} f&&/^```$/{exit} f{print}' /opt/github/zinin/session-relay/skills/do-plan/SKILL.md)"
grok -p "Run the following bash block exactly as written in one shell call and print its output verbatim, nothing else:
$STEP1" --permission-mode bypassPermissions 2>/dev/null | tail -8
```

Expected: `DEFAULT_STOP=400000`, `DISPATCH_MODEL=` (пусто, если `opus` не слаг хоста, с предупреждением «наследуем модель сессии») или слаг, `CONTEXT_SIGNALS=<путь к signals.json>`, `CONTEXT_WINDOW=<число>`. Так проверяются поиск `read-config.py` через `installed-plugins` и чтение окна.

- [ ] **Step 4: Генератор и ревью через mesh-exec**

```bash
cd /tmp/agent-plugins-smoke
grok -p "/session-relay:transfer-session" --permission-mode bypassPermissions 2>/dev/null | tail -3; ls docs/session-transfer-*.md
BEFORE=$(date +%s)
grok -p "/mesh-review:codex-code-review BASE_BRANCH=master" --permission-mode bypassPermissions 2>/dev/null | tail -10
find "${XDG_STATE_HOME:-$HOME/.local/state}/mesh/runs/codex" -mindepth 1 -maxdepth 1 -type d -newermt "@$BEFORE" | head -3
```

Expected: второй файл `docs/session-transfer-*.md`; новый каталог прогона codex.

- [ ] **Step 5: Убрать снимки**

```bash
for n in mesh-exec session-relay mesh-review claude-md build-forge atlassian-scout prd-flow; do grok plugin uninstall "$n" --confirm 2>&1 | tail -1; done
ls ~/.grok/installed-plugins | grep -E '^(mesh-exec|session-relay|mesh-review|claude-md|build-forge|atlassian-scout|prd-flow)-'; echo "---"
```

Expected: до `---` пусто.

---

### Task 22: смоук в Codex и таблица поддержки

- [ ] **Step 1: Изолированный Codex и локальный каталог из веток**

```bash
CX=/tmp/agent-plugins-codex; rm -rf "$CX"; mkdir -p "$CX/home" "$CX/mp/.claude-plugin"
ln -s ~/.codex/auth.json "$CX/home/auth.json"
python3 - "$CX/mp" <<'PY'
import json, pathlib, subprocess, sys
mp = pathlib.Path(sys.argv[1]); plugins = []
for src, name in (("claude-mesh","mesh-exec"),("session-relay","session-relay"),("mesh-review","mesh-review"),("claude-md","claude-md"),
                  ("claude-forge","build-forge"),("claude-atlassian","atlassian-scout"),("claude-prd","prd-flow")):
    dest = mp / "plugins" / name; dest.mkdir(parents=True)
    tar = subprocess.run(["git","-C",f"/opt/github/zinin/{src}","archive","HEAD"], check=True, capture_output=True).stdout
    subprocess.run(["tar","-x","-C",str(dest)], input=tar, check=True)
    plugins.append({"name": name, "source": f"./plugins/{name}", "description": name})
(mp/".claude-plugin"/"marketplace.json").write_text(json.dumps({"name":"zinin-smoke","owner":{"name":"smoke"},"plugins":plugins}, indent=2))
PY
git -C "$CX/mp" init -q && git -C "$CX/mp" add -A && git -C "$CX/mp" -c user.name=smoke -c user.email=smoke@local commit -qm mp
export CODEX_HOME="$CX/home"
codex plugin marketplace add "$CX/mp" 2>&1 | grep -v 'PATH aliases' | tail -1
for n in mesh-exec session-relay mesh-review claude-md build-forge atlassian-scout prd-flow; do codex plugin add "$n@zinin-smoke" 2>&1 | grep -v 'PATH aliases' | tail -1; done
cd /tmp/agent-plugins-smoke && codex debug prompt-input 2>/dev/null > "$CX/prompt.json"
grep -oE '(mesh-exec|session-relay|mesh-review|claude-md|build-forge|atlassian-scout|prd-flow):[a-z-]+' "$CX/prompt.json" | sort -u
```

Expected: семь `Added plugin …`; список скиллов всех семи плагинов (команды `mesh-review` — если Codex их сконвертировал; записать, какие из них появились).

- [ ] **Step 2: Вызовы в `codex exec`**

```bash
export CODEX_HOME=/tmp/agent-plugins-codex/home; cd /tmp/agent-plugins-smoke
codex exec '$session-relay:transfer-session' 2>&1 | tail -3; ls docs/session-transfer-*.md
codex exec '$session-relay:do-plan' 2>&1 | grep -F 'do-plan здесь не поддерживается' | head -1
codex exec --add-dir "${XDG_STATE_HOME:-$HOME/.local/state}/mesh" '$mesh-exec:grok-exec — have Grok reply with the single word PONG' 2>&1 | tail -5
codex exec '$build-forge:gradle-plugin-updater — what is the latest version of the org.jetbrains.kotlin.jvm plugin?' 2>&1 | tail -5
```

Expected: третий файл `docs/session-transfer-*.md`; строка отказа `do-plan здесь не поддерживается`; для `grok-exec` и `gradle-plugin-updater` — записать фактический исход (успех или причина: песочница, сеть, фоновый запуск).

- [ ] **Step 3: Обновить таблицы поддержки**

По итогам Tasks 20–22 заменить в `/opt/github/zinin/claude-plugins/README.md` каждое «smoke» в таблице «Where each plugin works» на `✓` или на `—` с причиной в одну строку (например, `grok-exec: sandbox blocks the background run`). Непрошедшее перенести в раздел «Codex follow-up» в конце README:

```markdown
## Codex follow-up

What does not work in Codex yet is tracked for a separate change: <список пунктов из смоука>.
```

Те же итоги — одной строкой в разделе Install/Codex README каждого затронутого плагина (`mesh-exec`, `session-relay`, `build-forge`, `atlassian-scout`, `prd-flow`) в их репозиториях.

- [ ] **Step 4: Убрать изолированный Codex и закоммитить таблицы**

```bash
rm -rf /tmp/agent-plugins-codex /tmp/agent-plugins-smoke /tmp/agent-plugins-smoke.pd
cd /opt/github/zinin/claude-plugins && git add README.md && git commit -m "docs: record where each plugin works after the smoke runs"
```

И по коммиту `docs: note the Codex smoke result` в каждом плагине, где README менялся (`git add README.md`).

---

### Task 23: публикация веток — GitHub и gitlab.zinin.ru (ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЯ)

Каждый шаг этой задачи — действие наружу. Перед Step 2 показать пользователю сводку (репозитории, ветки, что будет создано) и получить явное «да».

- [ ] **Step 1: Убрать `docs/superpowers` из ветки каталога**

```bash
cd /opt/github/zinin/claude-plugins
git rm -r -q docs/superpowers && git commit -m "docs: drop the design and plan before the PR"
```

- [ ] **Step 2: Создать репозитории новых плагинов и отправить их**

```bash
for r in session-relay mesh-review claude-md; do
  desc=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["description"])' "/opt/github/zinin/$r/.claude-plugin/plugin.json")
  gh repo create "zinin/$r" --public --description "$desc"
  git -C "/opt/github/zinin/$r" remote add origin "git@github.com:zinin/$r.git"
  git -C "/opt/github/zinin/$r" push -u origin master feature/agent-plugins-restructure
done
```

- [ ] **Step 3: Отправить ветки существующих репозиториев**

```bash
for d in claude-mesh claude-forge claude-atlassian claude-prd claude-plugins codex-base-review; do
  git -C "/opt/github/zinin/$d" push -u origin feature/agent-plugins-restructure
done
git -C /opt/github/zinin/.worktrees/herdr-review push -u origin feature/agent-plugins-restructure
for d in /opt/gitlab/ai/.worktrees/ai-tools /opt/gitlab/ai/claude-private-plugins /opt/gitlab/ai/claude-ebs /opt/gitlab/ai/.worktrees/wireguard-network; do
  git -C "$d" push -u origin feature/agent-plugins-restructure
done
```

- [ ] **Step 4: PR на GitHub**

```bash
body='Part of the agent-plugins restructure: claude-mesh splits into mesh-exec, session-relay, mesh-review and claude-md; claude-forge, claude-atlassian and claude-prd become build-forge, atlassian-scout and prd-flow; the catalog becomes zinin/agent-plugins. Merge only in the release window — see the plan in the claude-plugins branch history.'
for r in claude-mesh session-relay mesh-review claude-md claude-forge claude-atlassian claude-plugins codex-base-review herdr-review; do
  gh pr create --repo "zinin/$r" --base master --head feature/agent-plugins-restructure --title "Agent-plugins restructure" --body "$body"
done
gh pr create --repo zinin/claude-prd --base main --head feature/agent-plugins-restructure --title "Agent-plugins restructure" --body "$body"
```

- [ ] **Step 5: MR на gitlab.zinin.ru**

```bash
for d in /opt/gitlab/ai/.worktrees/ai-tools /opt/gitlab/ai/claude-private-plugins /opt/gitlab/ai/claude-ebs /opt/gitlab/ai/.worktrees/wireguard-network; do
  (cd "$d" && glab mr create --source-branch feature/agent-plugins-restructure --target-branch master --fill --yes)
done
```

- [ ] **Step 6: Остановиться**

Показать пользователю ссылки на 10 PR и 4 MR. Не сливать: слияние — Task 24, после ревью пользователя.

---

### Task 24: окно выпуска (ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЯ)

Перед Step 1: пользователь одобрил PR; в окне он не запускает новых сессий Claude Code и Grok (автообновление при старте подтянет чужой плагин под старым именем, пока каталог не обновлён — спецификация, «Ловушка редиректа»). Выполнять шаги подряд, без пауз.

- [ ] **Step 1: Переименовать репозитории на GitHub**

```bash
gh repo rename mesh-exec       -R zinin/claude-mesh      --yes
gh repo rename build-forge     -R zinin/claude-forge     --yes
gh repo rename atlassian-scout -R zinin/claude-atlassian --yes
gh repo rename prd-flow        -R zinin/claude-prd       --yes
gh repo rename agent-plugins   -R zinin/claude-plugins   --yes
git ls-remote https://github.com/zinin/claude-mesh.git HEAD | head -1
```

Expected: пять подтверждений; `git ls-remote` по старому адресу отвечает (редирект).

- [ ] **Step 2: Слить PR плагинов**

```bash
for r in mesh-exec session-relay mesh-review claude-md build-forge atlassian-scout prd-flow; do
  gh pr merge --repo "zinin/$r" --merge feature/agent-plugins-restructure
done
```

- [ ] **Step 3: Релизные коммиты, теги, GitHub releases**

```bash
release() {  # release <local dir> <plugin name> <version> <default branch>
  local dir="$1" name="$2" ver="$3" br="$4" today; today=$(date +%F)
  cd "$dir" && git switch -q "$br" && git pull -q --ff-only
  sed -i 's/"version": "[^"]*"/"version": "'"$ver"'"/' .claude-plugin/plugin.json
  grep -q '^## \[Unreleased\]$' CHANGELOG.md || { echo "no [Unreleased] in $name"; return 1; }
  sed -i "0,/^## \[Unreleased\]\$/s//## [$ver] - $today/" CHANGELOG.md
  git commit -q -m "chore(release): $ver" -- .claude-plugin/plugin.json CHANGELOG.md
  git tag -a "$name--v$ver" -m "$name $ver"
  git push -q origin "$br" --follow-tags
  notes=$(awk -v v="## [$ver]" 'index($0,v)==1{f=1;next} f&&/^## \[/{exit} f{print}' CHANGELOG.md)
  gh release create "$name--v$ver" --repo "zinin/$name" --title "$name $ver" --notes "$notes"
}
release /opt/github/zinin/claude-mesh      mesh-exec       0.16.0 master
release /opt/github/zinin/session-relay    session-relay   0.16.0 master
release /opt/github/zinin/mesh-review      mesh-review     0.16.0 master
release /opt/github/zinin/claude-md        claude-md       0.16.0 master
release /opt/github/zinin/claude-forge     build-forge     0.3.0  master
release /opt/github/zinin/claude-atlassian atlassian-scout 0.6.0  master
release /opt/github/zinin/claude-prd       prd-flow        0.2.0  main
```

Expected: семь релизов; в новых репозиториях `plugin.json` уже был 0.16.0 — коммит меняет только CHANGELOG.

- [ ] **Step 4: Выпустить каталог**

```bash
gh pr merge --repo zinin/agent-plugins --merge feature/agent-plugins-restructure
gh pr merge --repo zinin/herdr-review --merge feature/agent-plugins-restructure
gh pr merge --repo zinin/codex-base-review --merge feature/agent-plugins-restructure
```

Окно закрыто: каталог перечисляет новые плагины, старые записи удалены.

- [ ] **Step 5: Проверить каталог**

```bash
claude plugin marketplace update zinin 2>&1 | tail -1
python3 -c 'import json,os; d=json.load(open(os.path.expanduser("~/.claude/plugins/marketplaces/zinin/.claude-plugin/marketplace.json"))); print([p["name"] for p in d["plugins"]])'
```

Expected: девять новых имён.

---

### Task 25: переезд установок и уборка (ШАГИ ПОЛЬЗОВАТЕЛЯ + проверка)

- [ ] **Step 1: Пользователь переустанавливает плагины** — команды из README каталога, раздел «Moving from the claude-* plugins» (на каждой машине; конфиги — Task 19, если на этой машине ещё не сделано). `prd-flow` выключить (`claude plugin disable prd-flow@zinin`), если он не нужен: `claude-prd` был выключен.

- [ ] **Step 2: Проверка после переустановки**

```bash
python3 -c 'import json,os; d=json.load(open(os.path.expanduser("~/.claude/plugins/installed_plugins.json"))); print(sorted(k for k in d["plugins"] if k.endswith("@zinin")))'
grok inspect --json | python3 -c 'import json,sys; print(sorted(p["name"] for p in json.load(sys.stdin)["plugins"]))'
```

Expected: `build-forge@zinin`, `claude-md@zinin`, `codex-base-review@zinin`, `herdr-review@zinin`, `mesh-exec@zinin`, `session-relay@zinin`, `atlassian-scout@zinin`, `prd-flow@zinin` (+ `mesh-review@zinin`, если ставился); ни одного `claude-mesh`, `claude-forge`, `claude-atlassian`, `claude-prd`. Grok видит те же плагины.

- [ ] **Step 3: Codex (по желанию пользователя)** — `codex plugin marketplace add zinin/agent-plugins`, затем `codex plugin add <имя>@zinin` для нужных.

- [ ] **Step 4: Слить MR на gitlab.zinin.ru** (подтверждение пользователя) — `glab mr merge` в ai-tools, claude-private-plugins, claude-ebs, wireguard-network.

- [ ] **Step 5: Уборка**

```bash
git -C /opt/github/zinin/herdr-review worktree remove /opt/github/zinin/.worktrees/herdr-review
git -C /opt/gitlab/ai/ai-tools worktree remove /opt/gitlab/ai/.worktrees/ai-tools
git -C /opt/gitlab/ai/wireguard-network worktree remove /opt/gitlab/ai/.worktrees/wireguard-network
rmdir /opt/github/zinin/.worktrees /opt/gitlab/ai/.worktrees 2>/dev/null; true
```

По желанию пользователя — переименовать локальные клоны и обновить remote:

```bash
cd /opt/github/zinin
for pair in claude-mesh:mesh-exec claude-forge:build-forge claude-atlassian:atlassian-scout claude-prd:prd-flow claude-plugins:agent-plugins; do
  old=${pair%%:*}; new=${pair##*:}
  mv "$old" "$new" && git -C "$new" remote set-url origin "git@github.com:zinin/$new.git"
done
```

Старый каталог данных `~/.claude/plugins/data/claude-mesh-zinin/` (сохранён `--keep-data`) пользователь удаляет сам, когда убедится, что новый конфиг работает.
