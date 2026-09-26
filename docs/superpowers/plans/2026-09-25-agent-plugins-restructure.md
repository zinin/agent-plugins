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

✅ Done — see commit(s): `0eb00b3`, `c7b7640` (mesh-review; R5, R11)

**Interfaces:**
- Consumes: `find-mesh-exec.sh` (Task 9); `config-loader.sh config-path` (Task 2).
- Produces: каждый сниппет в `mesh-review.md` задаёт `FINDER`, `MESH_EXEC`, `LOADER="$MESH_EXEC/skills/shared/config-loader.sh"`.

---

### Task 11: mesh-review — скиллы и агенты

✅ Done — see commit(s): `f21b247`, `218c191`, `9fb52b0`, `9330a36` (mesh-review; R11, R12, R13 — fix round 1)

**Interfaces:**
- Consumes: `find-mesh-exec.sh`, свой `resolve-plugin-root.sh` (Task 9); `data-dir`, `config-path` загрузчика (Task 2).
- Produces: в каждом bash-фрагменте, где встречается `$MESH_EXEC`, он присваивается раньше (`MESH_EXEC=$(bash "$SKILL_BASE/../shared/find-mesh-exec.sh") || exit 1`); Grok читает exec-скилл из корня, который печатает `find-mesh-exec.sh`; агенты ищут прогоны в `${XDG_STATE_HOME:-$HOME/.local/state}/mesh/runs/`.

---

### Task 12: mesh-review — манифест и документация

✅ Done — see commit(s): `f08b1d4` (mesh-review; R2)

**Interfaces:**
- Produces: `plugin.json` с `"dependencies": ["mesh-exec", "session-relay"]` — Claude Code ставит их вместе с mesh-review из того же каталога.

---

### Task 13: claude-md — плагин

✅ Done — see commit(s): `9f68631` (claude-md)

**Interfaces:**
- Produces: скилл `claude-md:claude-md-writer` (голое имя `claude-md-writer` по-прежнему находится).

---

### Task 14: build-forge (был claude-forge)

✅ Done — see commit(s): `fb1995d`, `f2663f0` (claude-forge; R3, R14)

**Interfaces:**
- Produces: `/build-forge:build`, `/build-forge:deps-update`, агент `build-forge:build-runner`, скиллы `build-forge:gradle-plugin-updater`, `build-forge:google-maven-updater`.

---

### Task 15: atlassian-scout (был claude-atlassian)

✅ Done — see commit(s): `999bee7`, `5cc34de` (claude-atlassian; R1, R3, R14)

**Interfaces:**
- Produces: `/atlassian-scout:analyze-jira-ticket`, `/atlassian-scout:analyze-wiki`, `/atlassian-scout:investigate-bug`, `/atlassian-scout:investigate-feature`.

---

### Task 16: prd-flow (был claude-prd)

✅ Done — see commit(s): `be369d1`, `dc8ae62` (claude-prd; R1, R3, R14)

**Interfaces:**
- Produces: `/prd-flow:idea-to-prd`, `/prd-flow:refine-prd`, `/prd-flow:refine-tasks`.

---

### Task 17: каталог `agent-plugins`

✅ Done — see commit(s): `1476fd8` (claude-plugins)

**Interfaces:**
- Produces: каталог `zinin` из девяти плагинов по git-URL `https://github.com/zinin/<name>.git`. Эти URL заработают после Task 23–24; до того каталог проверяется локально.

---

### Task 18: ссылки снаружи

✅ Done — see commit(s): herdr-review `7d0015c` (worktree `/opt/github/zinin/.worktrees/herdr-review`), codex-base-review `8e16a61` (message reworded with the owner's consent; was `338509d`), ai-tools `67bb4f3` (worktree `/opt/gitlab/ai/.worktrees/ai-tools`), claude-private-plugins `00e4b2d`, claude-ebs `8b94e33`, wireguard-network `f51d7b0` (worktree `/opt/gitlab/ai/.worktrees/wireguard-network`)

**Interfaces:** ничего не производит для других задач; push — в Task 23.

---

### Task 19: пользователь готовит конфиги (ШАГ ПОЛЬЗОВАТЕЛЯ)

✅ Done — see commit(s): no commits — at the owner's instruction the controller created `~/.config/mesh/config.yaml` (byte-identical copy, 600) and `~/.config/session-relay/config.yaml` (`dispatch_model: opus`); Step 2 checks exact. Owner-approved additions (not in the original plan; briefs in the SDD workspace): **Task 19a** — mesh-exec `preflight-env.sh` prints the loader's move command for an old claude-mesh config, `6303808` (claude-mesh); **Task 19b** — session-relay `do-plan` Grok window warning at 85% of the window with a suggestion ≥ 150000, `50d2b22`, `9af7262` (session-relay)

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
