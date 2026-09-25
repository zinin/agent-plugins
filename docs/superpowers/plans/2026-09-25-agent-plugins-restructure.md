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

✅ Done — see commit(s): `930b019` (claude-plugins); new local repos session-relay, mesh-review, claude-md; branch feature/agent-plugins-restructure in 7 repos

**Interfaces:**
- Produces: `python3 /opt/github/zinin/claude-plugins/docs/superpowers/plans/tools/nsmap.py FILE...` — переводит `claude-mesh:<компонент>` в `mesh-exec:` / `mesh-review:` / `session-relay:` / `claude-md:` по имени компонента, на месте, пропуская историческую цитату. Используют Tasks 7, 8, 10, 11.
- Produces: в трёх новых репозиториях master — отфильтрованная история `claude-mesh` master (без remote и тегов) и ветка `feature/agent-plugins-restructure`; в `claude-mesh`, `claude-forge`, `claude-atlassian`, `claude-prd` — ветка `feature/agent-plugins-restructure`.

---

### Task 2: mesh-exec — конфиг и состояние на путях XDG

✅ Done — see commit(s): `5a532de` (claude-mesh)

**Interfaces:**
- Produces: `config-loader.sh config-path` — печатает путь конфига (`$MESH_CONFIG`, иначе `${XDG_CONFIG_HOME:-$HOME/.config}/mesh/config.yaml`), без валидации, код 0.
- Produces: `config-loader.sh data-dir` — `${XDG_STATE_HOME:-$HOME/.local/state}/mesh`.
- Produces: нет конфига → код 2; при найденном `~/.claude/plugins/data/claude-mesh-*/config.yaml` stderr содержит `The claude-mesh config is still at <старый>. Move it:` и строку `mkdir -p "<каталог>" && cp "<старый>" "<новый>" && chmod 600 "<новый>"`.
- Produces: `get-flag do_plan_default_stop_tokens` удалён (код 1, `unknown feature`); `get-runtime` без ключа `do_plan_default_stop_tokens`; `validate` предупреждает `runtime.do_plan_default_stop_tokens is ignored: do-plan moved to the session-relay plugin …`.
- Consumes: ничего из других задач.

---

### Task 3: mesh-exec — удалить ушедшие части и разделить смешанный тест

✅ Done — see commit(s): `2cfa0de` (claude-mesh)

**Interfaces:**
- Consumes: Task 1 (ветка). Produces: дерево `mesh-exec` без чужих файлов; Task 4 переименовывает то, что осталось.

---

### Task 4: mesh-exec — имена и поиск своего корня

✅ Done — see commit(s): `40e2250` (claude-mesh)

**Interfaces:**
- Produces: `resolve-plugin-root.sh` и блоки поиска в exec-скиллах ищут `*mesh-exec*/skills/shared/config-loader.sh`; каталог `claude-mesh` в кеше им не подходит (Review Focus 2).

---

### Task 5: mesh-exec — манифест, конфиг-пример и документация

✅ Done — see commit(s): `3bf5cc8`, `3415b58`, `b291a62` (claude-mesh)

**Interfaces:**
- Consumes: Tasks 2–4. Produces: плагин с именем `mesh-exec` для смоука (Tasks 20–22).

---

### Task 6: session-relay — раскладка скиллов и ридер конфига

✅ Done — see commit(s): `68bf73f`, `9dce898` (session-relay)

**Interfaces:**
- Produces: `python3 skills/do-plan/read-config.py [--file PATH] get stop_tokens|dispatch_model` → значение (по умолчанию 400000 и пустая строка), код 0; ошибка конфига → код 1 и `<file>:<line>: <reason>` на stderr; ошибка вызова → код 64. `read-config.py [--file PATH] path` → путь, который читается. Без `--file` — `${XDG_CONFIG_HOME:-$HOME/.config}/session-relay/config.yaml`. Используют Task 7 (шаг 1 `do-plan`) и Task 8.

---

### Task 7: session-relay — скилл `do-plan`

✅ Done — see commit(s): `2623f82` (session-relay)

**Interfaces:**
- Consumes: `read-config.py` (Task 6); `nsmap.py` (Task 1).
- Produces: шаг 1 `do-plan` печатает `DEFAULT_STOP=<n>` и `DISPATCH_MODEL=<m>`, в Grok ещё `CONTEXT_SIGNALS=` и `CONTEXT_WINDOW=`; без `CLAUDECODE` и `GROK_SESSION_ID` — код 1 и `do-plan здесь не поддерживается`. Шаг 2 пишет `${XDG_STATE_HOME:-$HOME/.local/state}/session-relay/do-plan-config-<cwd-encoded>-<session>.json` с `{"stop_threshold":N}` — этот путь читает хук после Task 8.

---

### Task 8: session-relay — хук, остальные скиллы, манифест и документация

✅ Done — see commit(s): `f61fb49`, `67768eb`, `929b759` (session-relay)

**Interfaces:**
- Consumes: путь шага 2 из Task 7.
- Produces: хук читает `${XDG_STATE_HOME:-$HOME/.local/state}/session-relay/`, игнорируя `CLAUDE_PLUGIN_DATA` и `GROK_PLUGIN_DATA`; плагин `session-relay` 0.16.0 для смоука.

---

### Task 9: mesh-review — поиск `mesh-exec` и своего корня

✅ Done — see commit(s): `454ddfb`, `69d1f79` (mesh-review)

**Interfaces:**
- Produces: `bash skills/shared/find-mesh-exec.sh` → корень `mesh-exec` на stdout, код 0; не найден → код 1 и `mesh-exec не найден: поставьте mesh-exec@zinin …`; `MESH_EXEC_ROOT` без `skills/shared/config-loader.sh` → код 1 и сообщение с именем переменной. Используют Tasks 10 и 11.
- Produces: `resolve-plugin-root.sh` печатает корень mesh-review (маркер `skills/shared/find-mesh-exec.sh`), `claude-mesh` в кеше ему не подходит.

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
