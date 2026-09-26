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

✅ Done — no commits (smoke, R16); report `.superpowers/sdd/…/task-20-report.md`. Fix from it: **Task 20a** (owner-approved scope, R20/R21) — mesh-review rc=2 hint defers to the loader's move command and calls it the user's step, `0a54be7`, `aba6b5e` (mesh-review)

**Interfaces:**
- Facts for README/tables: all seven plugins load under `--plugin-dir` (39 skills/agents; mesh-review commands in `slash_commands`); a bare mesh-review load without mesh-exec/session-relay is dropped as `dependency-unsatisfied`; session-relay's hook delivers a real `ctx:…k STOP` reminder; one-shot `claude -p` kills mesh-exec's background runs at turn end (R19, pre-existing).

---

### Task 21: смоук в Grok

✅ Done — no commits (smoke, R16; model `glm-5-3-flash` — the owner's xAI subscription ended); report `…/task-21-report.md`. Fixes from it: **Task 21a** (R22, R24) — `f7b0c09`, `5591800` (claude-mesh), `1e23b30` (mesh-review), `5f42cc0`, `09c0d82` (session-relay), `1fa8385`, `b7c4080` (claude-forge)

**Interfaces:**
- Facts: a Grok snapshot is named `<source-dir-basename>-<hash>` (install mesh-exec from a directory named `mesh-exec`); `install --trust` enables; bare names resolve through an added marketplace; Grok ignores `dependencies`; `signals.json` is written when a turn ends (do-plan STOP only at turn boundaries); the old claude-atlassian works in Grok only in trusted folders whose `.mcp.json` defines mcp-atlassian.

---

### Task 22: смоук в Codex и таблица поддержки

✅ Done — see commit(s): `5e9a5ec`, `5872457`, `773c65a` (claude-plugins); `b822b60`, `a504645`, `1cbcbe2` (claude-mesh); `8bf4aae`, `9b26e55` (session-relay); `d72c206`, `6a5eded` (claude-forge); `c7dd5ff` (claude-atlassian); `0515d63`, `9f57a07` (claude-prd); `a13cf4d` (codex-base-review)

**Interfaces:**
- Produces: the support tables and Codex notes in every README; Codex-only defects (mesh-exec root lookup misses Codex's plugin cache; Codex refuses `rm -f` in ext-claude-/grok-exec pre-flight; `$$`=2 in the sandbox) are listed under "Codex follow-up" (R26).

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
  git -C "/opt/github/zinin/$r" push -u origin master
  git -C "/opt/github/zinin/$r" push -u origin feature/agent-plugins-restructure
  gh repo edit "zinin/$r" --default-branch master
  gh repo view "zinin/$r" --json defaultBranchRef -q .defaultBranchRef.name
done
```

Expected: `master` три раза — установки из каталога идут с ветки по умолчанию.

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
  cd "$dir" && git switch -q "$br" && git pull -q --ff-only || { echo "release $name: cannot update $br"; return 1; }
  grep -qF "\"name\": \"$name\"" .claude-plugin/plugin.json || { echo "release $name: $br does not carry the merged plugin"; return 1; }
  grep -q '^## \[Unreleased\]$' CHANGELOG.md || { echo "no [Unreleased] in $name"; return 1; }
  sed -i 's/"version": "[^"]*"/"version": "'"$ver"'"/' .claude-plugin/plugin.json
  sed -i "0,/^## \[Unreleased\]\$/s//## [$ver] - $today/" CHANGELOG.md
  git commit -q -m "chore(release): $ver" -- .claude-plugin/plugin.json CHANGELOG.md || return 1
  git tag -a "$name--v$ver" -m "$name $ver" || return 1
  git push -q origin "$br" --follow-tags || return 1
  notes=$(awk -v v="## [$ver]" 'index($0,v)==1{f=1;next} f&&/^## \[/{exit} f{print}' CHANGELOG.md)
  gh release create "$name--v$ver" --repo "zinin/$name" --verify-tag --title "$name $ver" --notes "$notes"
}
release /opt/github/zinin/claude-mesh      mesh-exec       0.16.0 master
release /opt/github/zinin/session-relay    session-relay   0.16.0 master
release /opt/github/zinin/mesh-review      mesh-review     0.16.0 master
release /opt/github/zinin/claude-md        claude-md       0.16.0 master
release /opt/github/zinin/claude-forge     build-forge     0.3.0  master
release /opt/github/zinin/claude-atlassian atlassian-scout 0.6.0  master
release /opt/github/zinin/claude-prd       prd-flow        0.2.0  main
```

Expected: семь релизов; в новых репозиториях `plugin.json` уже был 0.16.0 — коммит меняет только CHANGELOG. Любая ошибка внутри `release` печатает причину и возвращает 1 — остановиться и разобраться, не переходить к следующему плагину.

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
ls -d ~/.claude/plugins/cache/zinin/mesh-exec/* ~/.grok/installed-plugins/mesh-exec-* 2>/dev/null
```

Expected: `build-forge@zinin`, `claude-md@zinin`, `codex-base-review@zinin`, `herdr-review@zinin`, `mesh-exec@zinin`, `session-relay@zinin`, `atlassian-scout@zinin`, `prd-flow@zinin` (+ `mesh-review@zinin`, если ставился); ни одного `claude-mesh`, `claude-forge`, `claude-atlassian`, `claude-prd`. Grok видит те же плагины. `ls` печатает хотя бы один каталог `mesh-exec`: mesh-review и exec-скиллы ищут mesh-exec по этому имени.

- [ ] **Step 3: Codex (по желанию пользователя)** — `codex plugin marketplace add zinin/agent-plugins`, затем `codex plugin add <имя>@zinin` для нужных.

- [ ] **Step 4: Слить MR на gitlab.zinin.ru** (подтверждение пользователя) — `glab mr merge` в ai-tools, claude-private-plugins, claude-ebs, wireguard-network. В wireguard-network master ушёл вперёд после начала ветки (15 коммитов на 2026-09-26); локальное трёхстороннее слияние чистое. Если проект требует fast-forward, — `glab mr merge --rebase`.

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
