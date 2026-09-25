# Реструктуризация плагинов zinin — дизайн

Дата: 2026-09-25. Репозиторий: `claude-plugins` (станет `agent-plugins`). Ветка:
`feature/agent-plugins-restructure`.

Затрагивает также публичные `claude-mesh`, `claude-forge`, `claude-atlassian`, `claude-prd`,
`herdr-review`, `codex-base-review` (github.com/zinin) и приватные `ai-tools`,
`claude-private-plugins`, `claude-ebs`, `wireguard-network` (gitlab.zinin.ru/ai). В приватных
меняются только ссылки на старые имена.

## Задача

Плагины писались под Claude Code. Теперь основная работа идёт в Grok, иногда в Codex. Grok сам
загружает плагины, установленные Claude Code. Codex читает каталог формата Claude без изменений:
`codex plugin marketplace add zinin/claude-plugins` поставил `claude-mesh@zinin` (проверено
2026-09-24 на Codex 0.156.1 в изолированном `CODEX_HOME`).

Проблем три.

1. Имена `claude-*` обещают «только для Claude», хотя плагины от харнеса почти не зависят.
2. `claude-mesh` смешивает четыре задачи: вызов чужих CLI, выполнение плана с передачей работы
   между сессиями, CLAUDE.md и мультимодельное ревью. Поставить часть нельзя. Ревью
   (`mesh-review`, `mesh-design-review`) в ежедневной работе заменил `/herdr-review:review`, но
   снять его отдельно нельзя.
3. Конфиг `claude-mesh` с токенами лежит в каталоге данных Claude Code, и загрузчик ищет его
   шаблоном `~/.claude/plugins/data/claude-mesh-*`. Шаблон ломается при переименовании, Codex о
   таком каталоге не знает, а `uninstall` без `--keep-data` стирает конфиг.

Цель: у каждого плагина одна задача и имя без харнеса; любой плагин ставится отдельно в Claude
Code, Grok и Codex; ревью живёт в отдельном необязательном плагине.

## Границы

Входит:

- деление `claude-mesh` на четыре плагина;
- переименование `claude-forge`, `claude-atlassian`, `claude-prd` и каталога `claude-plugins`;
- перенос конфига и состояния на пути XDG;
- упаковка под три харнеса: команды становятся скиллами там, где плагин идёт в Codex; таблица
  поддержки;
- ссылки на старые имена во всех репозиториях, включая приватные;
- переезд установленных копий.

Не входит:

- доводка под Codex того, что опирается на агентов Claude или на хук контекста: это второй
  проект (см. последний раздел);
- переименование приватных плагинов (`claude-ebs`, `claude-operator`) и приватного каталога;
- изменение поведения скиллов сверх того, что требует переезд;
- монорепозиторий: его можно сделать позже, имена и границы от этого не меняются.

Допущение: пользователь один. У всех публичных репозиториев 0 звёзд, 0 форков и 0 наблюдателей
(2026-09-24). Поэтому переезд разовый, без переходного периода и без псевдонимов старых имён.

## Закреплённые решения

| Решение | Выбор | Почему |
|---------|-------|--------|
| Деление `claude-mesh` | Четыре плагина: `mesh-exec`, `session-relay`, `mesh-review`, `claude-md` | Одна задача на плагин: ставится любое подмножество, а имя точно называет содержимое |
| Хранение | Отдельный репозиторий на плагин, как сейчас | Процесс (PR, релизы, AGENTS.md) не меняется; монорепозиторий возможен позже без смены имён и границ |
| Схема имён | «Объект-роль», как у `herdr-review` и `codex-base-review` | Одиночные слова (`mesh`, `forge`, `prd`) слишком общие; `atlassian` занят официальным плагином в `claude-plugins-official` |
| `claude` в `claude-md` | Остаётся | Слово называет файл CLAUDE.md, а не харнес; скилл описывает возможности Claude Code (`.claude/rules/`, фронтматтер `paths:`). По той же логике `claude-operator` сохраняет имя |
| Команды `mesh-review` | Не переименовываются: `/mesh-review:mesh-review`, `/mesh-review:mesh-design-review` | Плагин стал запасным; меньше правок — меньше риска |
| Конфиг и состояние | `~/.config/<имя>/` и `~/.local/state/<имя>/` (XDG), как у herdr-review | Не зависят от харнеса, переживают `uninstall`, убирают поиск шаблоном и расхождение хука с `do-plan` при `--plugin-dir` |
| Конфиг `session-relay` | Свой файл из двух ключей; порог по умолчанию 400000 | `do-plan` не тянет ради двух значений загрузчик `mesh-exec` на 1606 строк и `yq` |
| Зависимости | `mesh-review` зависит от `mesh-exec` и `session-relay` через `dependencies` в `plugin.json`, без ограничений версий | Claude Code ставит зависимости сам; обе стороны выпускает один человек |
| Манифесты | Только `.claude-plugin/plugin.json` и `.claude-plugin/marketplace.json` | Codex читает формат Claude (проверено), Grok — тоже (так сказано в его документации) |
| Команды → скиллы | В плагинах, которые идут в Codex | Автоконвертация Codex взяла 1 команду `claude-mesh` из 9 |
| Кто вызывает скилл | Как сейчас: пользователь и модель; `disable-model-invocation` не ставится | Скиллы вызывают друг друга; Codex это поле игнорирует (проверено) |
| Цель для Codex | Плагин ставится, скиллы видны модели, простые скиллы проходят смоук; остальное — во втором проекте | Каждая доводка под Codex требует своего смоука; вместе с переездом объём вырос бы вдвое |
| Репозиторий `claude-mesh` | Переименовывается в `mesh-exec`; три новых репозитория извлекаются с историей через `git filter-repo` | В `mesh-exec` остаются общая инфраструктура и большинство тестов; старые ссылки на них работают через редирект GitHub |
| Версии | Первая версия под новым именем — следующий minor старого плагина: `mesh-exec`, `session-relay`, `mesh-review` и `claude-md` — 0.16.0 (после `claude-mesh` 0.15.0), `build-forge` — 0.3.0, `atlassian-scout` — 0.6.0, `prd-flow` — 0.2.0 | Видна преемственность со старым плагином |

## Карта плагинов

Каталог — `zinin/agent-plugins`. Имя маркетплейса `zinin` не меняется, поэтому ID установки
остаётся вида `<плагин>@zinin`.

| Плагин | Было | Задача | Зависит от |
|--------|------|--------|------------|
| `mesh-exec` | часть `claude-mesh` | Вызов чужих CLI: Codex, Gemini, Grok, Claude Code и alt-провайдеры через `claude -p` | — |
| `session-relay` | часть `claude-mesh` | Выполнение плана с паузой по порогу контекста и передача работы между сессиями | — |
| `mesh-review` | часть `claude-mesh` | Мультимодельное ревью кода и дизайна | `mesh-exec`, `session-relay` |
| `claude-md` | часть `claude-mesh` | Написание и рефакторинг CLAUDE.md | — |
| `build-forge` | `claude-forge` | Делегирование сборки, тестов и линта; обновление зависимостей JVM и Android | — |
| `atlassian-scout` | `claude-atlassian` | Разбор тикетов Jira и страниц Confluence, расследование багов и задач в коде | — |
| `prd-flow` | `claude-prd` | От идеи к PRD и задачам | — |
| `herdr-review` | — | Без изменений; правится README | — |
| `codex-base-review` | — | Без изменений; правится README | — |

Новые имена свободны в каталогах `claude-plugins-official`, `openai-curated` и `xai-official`
(проверено 2026-09-24).

### Состав плагинов из `claude-mesh`

Каждый файл `claude-mesh` уходит ровно в один плагин.

**`mesh-exec`** — репозиторий `claude-mesh` после переименования:

- `skills/codex-exec/`, `skills/gemini-exec/`, `skills/grok-exec/`, `skills/ext-claude-exec/` со
  всеми вспомогательными скриптами;
- `agents/codex-executor.md`, `gemini-executor.md`, `grok-executor.md`, `ext-claude-executor.md`,
  `claude-executor.md`;
- `skills/shared/`: `config-loader.sh`, `resolve-plugin-root.sh`, `preflight-env.sh`,
  `list-host-models.sh`, `watch-runs.sh`, `verify-delegation.sh`, `watchdog.sh`,
  `stream-json-report.sh`, `extract-result.py`;
- тесты по таблице из раздела «Проверка»;
- `config.example.yaml` без `runtime.do_plan_default_stop_tokens`;
- `scripts/backup-config.sh` удаляется: конфиг больше не лежит в каталоге, который стирает
  `uninstall`.

**`session-relay`** — новый репозиторий:

- `skills/do-plan/`, `skills/pause-after-current-task/`, `skills/transfer-session/`,
  `skills/exec-plan-fresh-session/`, `skills/continue-plan-fresh-session/` — из одноимённых команд;
- `skills/do-plan/read-config.py` (новый) и `skills/do-plan/list-host-models.sh` (копия из
  `mesh-exec`, 51 строка);
- `hooks/hooks.json`, `hooks/check-context-size.sh`;
- `config.example.yaml` из двух ключей;
- тесты в `tests/`.

**`mesh-review`** — новый репозиторий:

- команды `mesh-review`, `auto-decide-disputed`, `code-review-fresh-session`,
  `design-review-fresh-session` остаются командами;
- `skills/mesh-design-review/` и пять скиллов `skills/<движок>-code-review/`;
- пять агентов `agents/<движок>-code-reviewer.md` и `agents/review-discussion.md`;
- `skills/shared/code-review-prompt.md`, `skills/shared/render-template.py`,
  `skills/shared/find-mesh-exec.sh` (новый);
- `skills/shared/resolve-plugin-root.sh` — своя копия: ищет корень `mesh-review` по маркеру
  `skills/shared/find-mesh-exec.sh` и шаблону `*mesh-review*`. С ней блоки поиска в скиллах ревью
  сохраняют прежнее устройство, меняются только маркер и шаблон;
- в `plugin.json`: `"dependencies": ["mesh-exec", "session-relay"]`.

**`claude-md`** — новый репозиторий:

- `skills/claude-md-writer/SKILL.md`. Имя скилла не меняется: `claude-ebs` вызывает его по имени
  `claude-md-writer`;
- раздел Credits из README `claude-mesh` (upstream `serejaris/personal-corp-os`, MIT) переезжает в
  README `claude-md`.

Каждый новый репозиторий получает README, CHANGELOG, LICENSE (MIT) и AGENTS.md. AGENTS.md
описывает загрузку рабочего дерева в Claude Code и Grok по образцу нынешнего AGENTS.md
`claude-mesh`. Для `mesh-review` там сказано, что `mesh-exec` и `session-relay` загружаются рядом
(`--plugin-dir` на каждый), а `MESH_EXEC_ROOT` указывает на рабочее дерево `mesh-exec`.

### Переименования без смены состава

В `build-forge`, `atlassian-scout` и `prd-flow` меняются `name`, `displayName` и `repository` в
`plugin.json`, README и ссылки на себя (`/claude-forge:build`,
`subagent_type: "claude-forge:build-runner"` и подобные). В `build-forge` команда `deps-update`
становится скиллом.

Каталог `agent-plugins`: новый `marketplace.json` перечисляет девять плагинов. Описание каталога
и README больше не говорят «for Claude Code». README объясняет установку в трёх харнесах и
приводит таблицу поддержки из раздела «Упаковка под харнесы».

## Конфиг и состояние

| Плагин | Конфиг | Состояние |
|--------|--------|-----------|
| `mesh-exec` и `mesh-review` (общий) | `~/.config/mesh/config.yaml` | `~/.local/state/mesh/runs/<движок>/…` и `~/.local/state/mesh/state/` |
| `session-relay` | `~/.config/session-relay/config.yaml` | `~/.local/state/session-relay/` |
| остальные | — | — |

Пути учитывают `$XDG_CONFIG_HOME` и `$XDG_STATE_HOME`. `MESH_CONFIG` переопределяет путь конфига
`mesh` целиком, по образцу `HERDR_REVIEW_CONFIG`. Права на файлы конфига — 600, как сейчас.

### `mesh`: загрузчик в `mesh-exec`

- Секции нынешнего конфига остаются все: `providers`, `models`, `claude`, `codex`, `gemini`, `grok`,
  `defaults` (пресеты ревью) и `runtime`.
- `config-loader.sh data-dir` возвращает `~/.local/state/mesh`. Новая подкоманда
  `config-loader.sh config-path` печатает путь конфига: его называют сообщения о том, что конфига
  ещё нет, и подсказки `preflight-env.sh` — `data-dir` теперь каталог состояния, а не конфига.
- Поиск каталога данных шаблоном уходит отовсюду: из `resolve_plugin_data` в загрузчике, из
  `verify-delegation.sh`, из хука, из агентов `claude-code-reviewer`, `codex-code-reviewer`,
  `ext-claude-code-reviewer`, `gemini-code-reviewer`, `grok-code-reviewer`, `claude-executor`,
  `grok-executor` и из exec-скиллов. Сейчас шаблон `plugins/data/claude-mesh` зашит в 19 файлов.
- Нового конфига нет, а старый (`~/.claude/plugins/data/claude-mesh-*/config.yaml`) есть — загрузчик
  завершается ошибкой и печатает готовую команду `cp`. Сам он ничего не копирует: правило «агент не
  трогает конфиг пользователя» остаётся в силе.
- `runtime.do_plan_default_stop_tokens` в конфиге `mesh` вызывает предупреждение «переехало в
  session-relay», а не ошибку. Так старый конфиг проходит валидацию после простого копирования.
- `runtime.dispatch_model` остаётся: его читают агенты-исполнители и `review-discussion`.
- Внутренние переменные `CLAUDE_MESH_PROVIDER_KIND`, `CLAUDE_MESH_DATA_DIR`,
  `CLAUDE_MESH_TIMEOUT_*` не переименовываются: это интерфейс между загрузчиком и exec-скиллами,
  а не имя плагина.
- В Codex запись в `~/.local/state/mesh` из песочницы требует `--add-dir` или подтверждения.
  README говорит об этом так же, как README herdr-review.

### `session-relay`: свой конфиг

```yaml
stop_tokens: 400000      # порог STOP для do-plan: целое число, не меньше 150000
dispatch_model: opus     # модель субагентов do-plan; без ключа — модель сессии
```

- Файл читает `skills/do-plan/read-config.py`: python3 со стандартной библиотекой, без `yq` и
  PyYAML. Формат — плоские строки `ключ: значение` с необязательным комментарием.
- Нет файла — действуют значения по умолчанию: `stop_tokens` 400000, `dispatch_model` не задан.
- Неизвестный ключ, нецелый порог или порог меньше 150000 — ошибка с именем файла и номером строки.
  Минимум 150000 сохраняется, потому что ниже него хук молчит.
- Аргумент `/session-relay:do-plan 300k` по-прежнему важнее конфига.
- В Grok правило для `dispatch_model` прежнее: значение уходит в `spawn_subagent`, только если это
  живой слаг из `grok models`.
- Новое: в Grok `do-plan` сравнивает порог с `contextWindowTokens` из `signals.json` и
  предупреждает, если порог не меньше окна, потому что такой порог никогда не сработает. Пример —
  модель DKS-Ultra с окном 204800.
- Хук и `do-plan` работают с состоянием в `~/.local/state/session-relay/` и вычисляют путь
  одинаково. Это закрывает расхождение при загрузке через `--plugin-dir`, которое `do-plan.md`
  сейчас описывает как «Known divergence, fixed separately».

## Связи между плагинами

### `mesh-review` → `mesh-exec`

`mesh-review` вызывает скрипты `mesh-exec`, его exec-скиллы и агентов-исполнителей.

`skills/shared/find-mesh-exec.sh` печатает корень `mesh-exec`. Порядок поиска повторяет нынешний
`resolve-plugin-root.sh` с новым именем:

1. `MESH_EXEC_ROOT`, если там есть `skills/shared/config-loader.sh` — для разработки через
   `--plugin-dir`;
2. в сессии Grok (задан `GROK_SESSION_ID`) — `~/.grok/installed-plugins/mesh-exec-*`;
3. `~/.claude/plugins/cache/*/mesh-exec/*/`, самая новая версия по `sort -V`;
4. `~/.grok/plugins/`, каталог с `mesh-exec` в имени.

Если ничего не найдено, скрипт завершается с кодом 1 и сообщением «mesh-exec не найден:
поставьте mesh-exec@zinin».

Скрипты `mesh-exec` берутся как `$MESH_EXEC/skills/shared/<скрипт>` вместо нынешнего
`$SKILL_BASE/../shared/<скрипт>`. Свои файлы (`code-review-prompt.md`, `render-template.py`,
`find-mesh-exec.sh`) `mesh-review` берёт из своей папки, как раньше: скиллы — относительно
`SKILL_BASE`, команды — через подстановку `${CLAUDE_PLUGIN_ROOT}` с поиском по шаблону
`*mesh-review*` как запасным путём, так же как команды сейчас находят загрузчик.

Ссылки идут через пространства имён:

- агент `mesh-review:<движок>-code-reviewer` вызывает скилл `mesh-review:<движок>-code-review`;
- скилл ревью вызывает `mesh-exec:<движок>-exec`: в Claude Code через Skill tool, в Grok — читая
  `SKILL.md` из найденного корня `mesh-exec`, как сейчас;
- `mesh-design-review` вызывает агентов `mesh-exec:<движок>-executor`.

Контракт записывается в AGENTS.md обоих репозиториев. `mesh-review` вызывает:

- `config-loader.sh` с подкомандами `data-dir`, `get-flag`, `get-defaults`, `get-runtime`,
  `list-models`, `list-claude-models`, `list-grok-models`, `get-codex`, `get-gemini`;
- `preflight-env.sh`, `watch-runs.sh`, `verify-delegation.sh`, `watchdog.sh`,
  `list-host-models.sh`.

Изменение их интерфейса выходит в релиз одновременно с правкой `mesh-review`.

### `mesh-review` → `session-relay`

Последний шаг `mesh-design-review` предлагает «остановиться и начать работу» через
`/session-relay:continue-plan-fresh-session`. Зависимость объявлена, поэтому скилл всегда на месте.

### `session-relay` ни от кого не зависит

- Загрузчик `mesh-exec` не нужен: у `session-relay` свой ридер конфига и своя копия
  `list-host-models.sh`.
- Шаг 7 `do-plan` сейчас предлагает `/claude-mesh:code-review-fresh-session`. Новая формулировка:
  предложить внешнее ревью — `/herdr-review:review` внутри herdr или
  `/mesh-review:code-review-fresh-session`, если `mesh-review` установлен. Порядок «сначала ревью,
  потом `superpowers:finishing-a-development-branch`» сохраняется.
- Упоминание `skills/shared/preflight-env.sh` в шаге 7 указывает на этот файл в `mesh-exec`.

### Правило для ссылок на старые имена

- Живой текст меняется на новые имена: инструкции, примеры вызова, пути, сообщения об ошибках.
  В `claude-mesh` это около 170 ссылок `claude-mesh:` в 26 файлах и шаблоны путей в 32 файлах.
- Цитаты прошлых замеров остаются дословными: это запись того, что было. Пример — «the event listed
  69 skills — `claude-mesh:mesh-review`…» в `grok-exec`.
- Старые записи CHANGELOG не меняются. Новая запись в каждом плагине объясняет переименование и
  откуда пришли файлы.

### Ссылки снаружи

| Где | Что меняется | Зачем |
|-----|--------------|-------|
| `herdr-review/README.md`, `codex-base-review/README.md` | `marketplace add zinin/claude-plugins` → `zinin/agent-plugins` | Установка по новому адресу |
| `ai-tools`: `claude-tools/settings.json`, `claude-tools/settings-telegram-hook.json`, `cli-proxy/gemini-settings.json` | `Skill(claude-forge:gradle-plugin-updater)` → `Skill(build-forge:gradle-plugin-updater)` | Иначе правило разрешения молча перестанет срабатывать |
| `claude-private-plugins/README.md` | ссылка на `zinin/claude-plugins` → `zinin/agent-plugins` | Ссылка на публичный каталог |
| `claude-ebs/README.md` | «claude-md-writer — локально в `~/.claude/skills/`» → «плагин `claude-md@zinin`» | Строка устарела ещё до переезда |
| `wireguard-network/CLAUDE.md` | «claude-mesh и подобные» → «mesh-review, herdr-review и подобные» | Правило о внешнем ревью называет старый плагин |

Не меняются: `session-transfer-*.md` и `docs/superpowers/` в проектах — это история.
`~/.claude/settings.json` обновится при удалении и установке плагинов.

## Упаковка под харнесы

- Манифесты: `.claude-plugin/plugin.json` в каждом плагине и `.claude-plugin/marketplace.json` в
  каталоге. Папки `.codex-plugin/` и `.grok-plugin/` не создаются.
- Скиллами становятся пять команд `session-relay` и команда `deps-update` из `build-forge`.
  `mesh-review` оставляет команды: он не для Codex.
- Скиллы остаются доступны и пользователю, и модели, как команды сейчас. Причина — цепочки вызовов:
  `do-plan` при STOP вызывает `pause-after-current-task`; `mesh-design-review` вызывает
  `auto-decide-disputed`, `design-review-fresh-session` и `continue-plan-fresh-session`;
  `mesh-review` вызывает `auto-decide-disputed`. Пометка `disable-model-invocation: true` запретила
  бы эти вызовы в Claude Code и Grok, а Codex её игнорирует: проверено, что скилл с пометкой виден
  модели, а скрывает его только `agents/openai.yaml` с `policy.allow_implicit_invocation: false`.
  От случайного вызова защищает описание скилла, как сейчас.
- Свои скрипты скилл вызывает по пути относительно своей папки. Так советует документация Grok, и
  так сделано в herdr-review. Подстановку `${CLAUDE_PLUGIN_ROOT}` делает только Claude Code.
- Аргументы скилл описывает словами — «текст после имени скилла», как в herdr-review. `$ARGUMENTS`
  остаётся для Claude Code.
- `do-plan` работает только там, где есть сигнал о заполнении контекста: в Claude Code (задан
  `CLAUDECODE`, сигнал даёт хук) и в Grok (задан `GROK_SESSION_ID`, сигнал даёт `signals.json`).
  В остальных харнесах он сообщает «do-plan здесь не поддерживается: нет сигнала о заполнении
  контекста» и останавливается.

### Таблица поддержки

| Плагин | Claude Code | Grok | Codex |
|--------|-------------|------|-------|
| `mesh-exec` | ✓ | ✓ | скиллы — смоук; агентов-исполнителей нет, у Codex только универсальный `spawn_agent` |
| `session-relay` | ✓ | ✓ | `transfer-session`, `exec-plan-fresh-session`, `continue-plan-fresh-session`, `pause-after-current-task` — смоук; `do-plan` — нет |
| `claude-md` | ✓ | ✓ | ставится; CLAUDE.md Codex не читает |
| `mesh-review` | ✓ | ✓ | не цель |
| `build-forge` | ✓ | ✓ | `deps-update`, `gradle-plugin-updater`, `google-maven-updater` — смоук; `build` — нет, ему нужен агент `build-runner` |
| `atlassian-scout` | ✓ | ✓ | смоук |
| `prd-flow` | ✓ | ✓ | смоук |

«Смоук» означает, что работоспособность проверяется во время реализации. Что смоук не пройдёт,
уходит во второй проект и помечается в README как неподдерживаемое.

Критерий для Codex в этом проекте: каждый плагин ставится командой `codex plugin add <имя>@zinin`,
все его скиллы видны в `codex debug prompt-input`, смоук-скиллы работают, а README называет то, что
не поддерживается.

## Переезд

### Репозитории

| Было | Стало | Как |
|------|-------|-----|
| `claude-mesh` | `mesh-exec` | Переименование на GitHub; из дерева удаляется всё, что уходит в другие плагины |
| — | `session-relay`, `mesh-review`, `claude-md` | Новые репозитории. Файлы и их история извлекаются из `claude-mesh` через `git filter-repo --path` по спискам из раздела «Состав плагинов из `claude-mesh`»; перенос в новые пути (`commands/do-plan.md` → `skills/do-plan/SKILL.md`) — обычным коммитом, `git log --follow` ведёт историю дальше |
| `claude-forge` | `build-forge` | Переименование на GitHub |
| `claude-atlassian` | `atlassian-scout` | Переименование на GitHub |
| `claude-prd` | `prd-flow` | Переименование на GitHub |
| `claude-plugins` | `agent-plugins` | Переименование на GitHub |

GitHub сохраняет редиректы со старых адресов, пока никто не создаст репозиторий со старым именем.

### Ловушка редиректа и окно выпуска

После переименования старая запись каталога `claude-mesh` → `github.com/zinin/claude-mesh` через
редирект попадёт в `mesh-exec`. Пока на master там старое содержимое, всё работает. Когда туда
вольётся ветка с новым именем в `plugin.json`, автообновление подтянет под именем
`claude-mesh@zinin` другой плагин. То же относится к `claude-forge`, `claude-atlassian` и
`claude-prd`.

Поэтому слияние веток в плагинах и выпуск нового каталога идут подряд, в одном окне в несколько
минут. Всё это время Claude Code и Grok не запущены: их автообновление срабатывает при старте.

### Шаги

1. Ветки во всех затронутых репозиториях: тесты и смоук по локальным путям в трёх харнесах
   (раздел «Проверка»). Опубликованные плагины не затрагиваются.
2. Пользователь копирует `~/.claude/plugins/data/claude-mesh-zinin/config.yaml` в
   `~/.config/mesh/config.yaml` (права 600) и создаёт `~/.config/session-relay/config.yaml` со
   строкой `dispatch_model: opus`. Старый `claude-mesh` продолжает работать со старым каталогом
   данных.
3. GitHub: переименования и три новых репозитория. На master переименованных репозиториев пока
   старое содержимое, поэтому старые записи каталога работают.
4. Окно выпуска: слияние веток и релизные коммиты во всех плагинах, затем новый
   `marketplace.json` в `agent-plugins`, где старые записи удалены, а новые добавлены.
5. На каждой машине, в Claude Code:

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
   claude plugin install mesh-review@zinin    # по желанию
   ```

   `claude-prd` сейчас выключен в `enabledPlugins`; `prd-flow` выключается так же, если он не
   нужен. Grok берёт установку Claude Code сам, проверка — `grok inspect`. В Codex:
   `codex plugin marketplace add zinin/agent-plugins`, затем `codex plugin add <имя>@zinin` для
   нужных плагинов.
6. Правка ссылок снаружи по таблице из раздела «Связи между плагинами».
7. По желанию: локальные клоны в `/opt/github/zinin/` получают новые имена и
   `git remote set-url`.

Каталог `zinin` на машинах остаётся подключённым как `zinin/claude-plugins` и работает через
редирект. Команды `marketplace remove` и `add` для смены адреса не нужны: `remove` снимает все
плагины каталога.

### Откат

Если после шага 4 новые плагины не работают, в `marketplace.json` возвращаются старые записи,
закреплённые на последних коммитах до слияния (поле `sha` источника `url`). Старые плагины
ставятся обратно. Старый каталог данных `claude-mesh` сохранён флагом `--keep-data`.

## Проверка

### Наборы тестов

Сейчас все наборы лежат в `claude-mesh/skills/shared/tests/`. Они делятся по владельцам.

| Набор | Куда | Что меняется |
|-------|------|--------------|
| `test-config-loader.sh`, `lib-yq-doubles.sh`, `fixtures/` | `mesh-exec` | Пути XDG; предупреждение про `do_plan_default_stop_tokens`; ошибка с командой `cp` при найденном старом конфиге |
| `test-resolve-plugin-root.sh` | `mesh-exec`; порт — в `mesh-review` | Имя плагина в шаблонах поиска; в обоих — тест, что `claude-mesh` в кеше не принимается за свой корень |
| `test-preflight-env.sh`, `test-watch-runs.sh`, `test-verify-delegation.sh`, `test-extract-result.sh`, `test-stream-json-report.sh` | `mesh-exec` | Пути прогонов |
| `test-grok-effort-resolution.sh`, `test-grok-run-discovery.sh`, `test-grok-exec-smoke.sh`, `test-host-claude-env.sh`, `test-list-host-models.sh` | `mesh-exec` | Имена в сообщениях |
| `test-claude-cli-agents.sh` | делится | Часть про `claude-executor` уходит в `mesh-exec`, часть про `claude-code-reviewer` и `claude-code-review` — в `mesh-review` |
| `test-command-sync.sh`, `test-grok-code-review-bindings.sh`, `test-render-template.sh` | `mesh-review` | Имена в синхронизируемых фрагментах |
| `test-loader-resolution.sh` | `mesh-review`, переписывается | Проверяет, что фрагмент поиска `mesh-exec` дословно одинаков во всех местах `mesh-review`; часть про `do-plan.md` уходит |
| `test-find-mesh-exec.sh` (новый) | `mesh-review` | Порядок поиска, `MESH_EXEC_ROOT`, ошибка при отсутствии `mesh-exec` |
| `test-mesh-exec-fences.sh` (новый) | `mesh-review` | Каждый bash-фрагмент, где встречается `$MESH_EXEC`, присваивает его раньше |
| `test-missing-config-handler.sh` (новый) | `mesh-review` | Оба оркестратора при коде 2 печатают stderr загрузчика и называют файл через `config-path` |
| `test-check-context-size.sh` | `session-relay` | Путь состояния XDG |
| `test-do-plan.sh` | `session-relay` | Ридер конфига вместо загрузчика; проверка окна в Grok; отказ без сигнала о заполнении контекста |
| `test-list-host-models.sh` и его фикстура (копии) | `session-relay` | — |
| `test-read-config.sh` (новый) | `session-relay` | Значения по умолчанию, порог 400000, минимум 150000, неизвестный ключ |

Каждый репозиторий проходит свои наборы до слияния.

### Смоук по харнесам

**Claude Code.** Старые `claude-mesh@zinin`, `claude-forge@zinin`, `claude-atlassian@zinin` и
`claude-prd@zinin` выключены. Сессия запускается с `--plugin-dir` на рабочее дерево каждого из
семи плагинов (`mesh-exec`, `session-relay`, `mesh-review`, `claude-md`, `build-forge`,
`atlassian-scout`, `prd-flow`) и с `MESH_EXEC_ROOT` на рабочее дерево `mesh-exec`. Проверяется:

- `config-loader.sh validate` на `~/.config/mesh/config.yaml`;
- `/mesh-exec:codex-exec` с коротким промптом кладёт прогон в `~/.local/state/mesh/runs/codex/`;
- `/session-relay:do-plan` пишет состояние в `~/.local/state/session-relay/`, и хук его видит;
- `/session-relay:transfer-session` пишет промпт в файл;
- `/mesh-review:mesh-review` с одним ревьюером на маленькой ветке находит `mesh-exec` и доводит
  ревью до отчёта;
- по одному вызову из `build-forge`, `atlassian-scout`, `prd-flow` и `claude-md`.

**Grok.** Каждый плагин ставится командой `grok plugin install <путь> --trust`, по одному снимку на
плагин. `grok inspect` показывает все плагины и их скиллы. Повторяются те же вызовы, что в Claude
Code. `do-plan` на модели с окном меньше порога печатает предупреждение.

**Codex.** Изолированный `CODEX_HOME` и временный каталог во временной папке: копии плагинов в
`plugins/<имя>` и относительные пути `./plugins/<имя>` в `.claude-plugin/marketplace.json` — такой
каталог Codex принимает, проверено. Затем `codex plugin add` для каждого плагина. `codex debug prompt-input` показывает
ожидаемые скиллы. Каждый смоук-скилл из таблицы поддержки вызывается через `codex exec`.

После выпуска (шаг 5) короткая повторная проверка идёт в каждом харнесе уже из настоящего каталога.

## Второй проект: доводка под Codex

Вне этого проекта, со своей спецификацией:

- `build-forge:build` — `spawn_agent` с текстом `agents/build-runner.md` в роли промпта вместо
  агента `build-runner`;
- сигнал STOP для `do-plan` — через хуки Codex (`PostToolUse`), если они сообщают размер контекста;
- `atlassian-scout` — раздача задач разведчикам через `spawn_agent`, если смоук этого проекта
  покажет, что без неё не обойтись;
- агенты-исполнители `mesh-exec` — решение по итогам смоука: если exec-скиллы в Codex работают
  напрямую, агенты там не нужны.
