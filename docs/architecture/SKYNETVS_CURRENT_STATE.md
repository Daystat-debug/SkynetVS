# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-03`
- Ветка: `main`
- HEAD: `1035de4b205b62109b4ea5b9e405ab651e44105f`
- Название HEAD: `feat: add complete developer task preflight composition`
- `origin/main`: `1035de4b205b62109b4ea5b9e405ab651e44105f`
- Стабильный foundation-тег: `skynet-runtime-foundation-v1` → `09f8708f67f4cf1681801ea41498815cf7df5948`
- Рабочее дерево: чистое состояние убедительно следует из handoff-архива, однако файл с пустым выводом `git status --short` не попал в ZIP; перед следующим коммитом нужно повторить проверку.

## 2. Приоритет источников истины

1. Текущее состояние Git, кода и свежих проверок.
2. Этот файл `SKYNETVS_CURRENT_STATE.md`.
3. `SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
4. Память старых чатов и предположения.

Нельзя объявлять `PLANNED` или `UNVERIFIED` завершёнными без подтверждения Git/eval.

## 3. Общая цель проекта

Создать персонального голосового ассистента, который станет сильнее обычного чат-интерфейса в среде пользователя благодаря постоянному контексту, голосу, управлению компьютером, пониманию экрана, безопасной разработке кода, воспроизводимым проверкам, контролируемому обучению и rollback.

Автономность не должна развиваться быстрее безопасности, наблюдаемости и доказательной базы.

## 4. VERIFIED — стабильный фундамент

### Runtime и сервисная база

- явное владение сервисами через composition root;
- fault boundaries и независимый shutdown;
- runtime health и мониторинг;
- lifecycle и generation guards для STT/TTS;
- регрессионное покрытие audio, reminders, timers и command runtime.

### Foundational Package Structure V1

- `modules/developer/`;
- `modules/core/`;
- `modules/runtime/`;
- `modules/learning/`;
- `modules/desktop/`.

### Roadmap Lock V1

- roadmap и оперативный handoff-документ хранятся в Git;
- скрытое расширение scope запрещено;
- изменение порядка оформляется как Roadmap Change.

## 5. VERIFIED — Developer Task Preflight V1

Последовательность code-коммитов:

```text
6e2aa78  V1A Repository Gate
cb7c6c5  V1B Patch Integrity Gate
b14486a  V1C1 Isolated Patch Index Gate
eeb50ce  V1C2 Patch Scope Policy Gate
1035de4  V1D Composition and Audit
```

Финальный публичный API:

```python
run_developer_task_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
    task_root: Path,
) -> DeveloperTaskPreflightReport
```

Подтверждено:

- canonical validation manifest;
- правильный repository root;
- `HEAD == base_commit`;
- чистые worktree и index;
- immutable snapshot точных байтов patch и SHA-256;
- применимость patch во временном изолированном Git index/object store;
- фактические changed paths и object modes;
- `allowed_files`, Windows case policy, запрет symlink и gitlink;
- фиксированный fail-closed порядок gates;
- отсутствие verified patch/changed-files evidence при частичном отказе;
- отсутствие изменений основного worktree, index и object store.

Последний targeted flow:

```text
package boundaries:             28/28
contract:                       18/18
repository preflight V1A:       22/22
patch integrity V1B:            29/29
isolated patch index V1C1:      35/35
patch scope policy V1C2:        36/36
composition and audit V1D:      19/19
developer_task_preflight flow:  completed successfully
```

Последний полный `check` после V1D завершён успешно.

## 6. Roadmap Change 001 — VERIFIED решение

### Решение

Заменить запланированный linked `git worktree` на независимый локальный clone репозитория.

Новое имя этапа:

```text
Developer Task Isolated Repository Workspace V1
```

### Причина

Linked worktree имеет отдельные `HEAD` и index, но разделяет с основным репозиторием common Git administration, refs/config/object data. Для будущего developer-task runtime это недостаточно независимая Git-граница.

### Что не меняется

```text
Preflight
  → Isolated Workspace
  → Patch Apply
  → Typed Checks
  → Result and Evidence
  → Manual Promotion
```

### Критичное ограничение

Независимый clone обеспечивает только Git/repository isolation. Он не является OS/process sandbox и не разрешает исполнение недоверенного изменённого кода. Execution isolation должна быть утверждена до checks, которые импортируют или запускают изменённый код.

## 7. CURRENT — Developer Task Isolated Repository Workspace V1A

### Этап

```text
Independent Repository Creation Gate
```

### Почему сейчас

Preflight V1 доказал безопасность постановки задачи и её patch. Теперь нужен одноразовый репозиторий, в который можно будет применить patch без общего Git-состояния с основным проектом.

### Публичный API

```python
create_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceReport
```

### In scope

- принимать только успешный полный отчёт Preflight V1;
- повторно проверять свежесть source repository перед созданием;
- требовать существующий внешний `workspace_parent`;
- запрещать symlink, junction и reparse-point в пути parent;
- запрещать пересечение с project repository и task root;
- запрещать parent внутри любого Git worktree, `.git` administration directory или bare repository;
- создавать уникальный workspace задачи;
- создавать независимый локальный clone с:
  - `--no-local`;
  - `--no-hardlinks`;
  - `--no-checkout`;
  - `--no-tags`;
  - `--single-branch`;
  - `--depth=1`;
- ограничивать Git history verified base-коммитом;
- изолировать HOME/USERPROFILE/XDG/global Git config/system attributes/hooks/template directory;
- отключать prompts, automatic maintenance, fsmonitor, untracked cache и submodule recursion;
- фиксировать deterministic Git policy: `core.autocrlf=false`, `core.eol=lf`, `core.safecrlf=true`, `core.protectNTFS=true`, `core.protectHFS=true`;
- требовать основной source worktree с обычным каталогом `.git`;
- запрещать baseline symlink (`120000`), gitlink (`160000`), неподдерживаемые modes, `.git` control paths, Windows-unsafe paths и file/directory case-collision;
- checkout точного `base_commit` в detached `HEAD`;
- удалять все remotes и branch/tag/remote refs;
- запрещать alternate object directories;
- проверять чистый workspace status;
- записывать marker с immutable evidence;
- подтверждать, что source repository не изменился;
- очищать частично созданный workspace с ограниченными Windows retries.

### Out of scope

- применение developer patch;
- запуск checks из manifest;
- импорт или выполнение изменённого кода;
- установка пакетов;
- commit, merge, push или promotion;
- публичный API удаления успешно созданного workspace;
- OS/process/network sandboxing;
- изменение основного репозитория.

### Threat model

V1A должен fail closed при:

- stale или forged Preflight evidence;
- неправильном, indirect или reparse workspace parent, а также parent внутри worktree/Git-dir/bare repository;
- source linked worktree;
- коллизии генерируемого пути;
- clone failure или timeout;
- унаследованных Git redirection/config/prompt variables;
- влиянии hooks/templates/global config;
- оставшемся remote или ref;
- shared alternates, hardlinks или local-clone optimization;
- unsafe baseline tree entries;
- изменении source repository во время clone;
- ошибке marker;
- ошибке cleanup частичного workspace.

## 8. Ожидаемые файлы V1A

```text
A  modules/developer/developer_task_workspace.py
A  modules/developer/developer_task_workspace_git.py
A  tools/eval_developer_task_workspace.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Изменения существующих модулей Preflight V1, `main.py`, runtime-сервисов и пользовательского поведения команд не планируются.

## 9. PLANNED — проверки V1A

```text
python -m py_compile \
    modules/developer/developer_task_workspace.py \
    modules/developer/developer_task_workspace_git.py \
    tools/eval_developer_task_workspace.py \
    tools/eval_package_boundaries.py \
    tools/pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python -m tools.eval_developer_task_patch_integrity
python -m tools.eval_developer_task_patch_index
python -m tools.eval_developer_task_patch_scope
python -m tools.eval_developer_task_preflight_composition
python -m tools.eval_developer_task_workspace
python tools/pipeline.py developer_task_workspace
python tools/pipeline.py check
```

Ожидаемый новый summary workspace eval:

```text
case_count: 38
fail_count: 0
```

## 10. Критерии завершения V1A

V1A завершён только если:

1. workspace использует обычный независимый каталог `.git`;
2. linked worktree-команды отсутствуют;
3. local-clone optimization, hardlinks и alternate object directories отсутствуют;
4. workspace является shallow repository с минимальной history boundary в один verified commit;
5. `HEAD` равен verified `base_commit` и находится в detached-состоянии;
6. remotes и обычные refs отсутствуют;
7. workspace status чистый;
8. baseline Git modes, `.git` control paths и Windows file/directory case-collisions безопасно блокируются;
9. source HEAD/status/refs/index/config не изменились;
10. fault injection покрывает clone, evidence, marker и cleanup failures;
11. новый eval проходит на Windows;
12. package-boundary guard и targeted flow включают V1A;
13. полный `check` проходит;
14. code-коммит содержит только пять ожидаемых файлов;
15. `origin/main` обновлён;
16. current-state обновлён после code-коммита.

## 11. DEFERRED

- Workspace V1B — cleanup успешного workspace и audit.
- Developer Task Patch Apply V1.
- Developer Task Typed Check Runner V1.
- Execution isolation policy для checks, выполняющих изменённый код.
- Developer Task Result and Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Domain Package Structure V2.
- Tools Package Structure V1.

## 12. Решения, которые нельзя пересматривать молча

- `skynet-runtime-foundation-v1` остаётся на `09f8708`.
- Gates Preflight V1 и их ответственности остаются раздельными.
- Основной worktree никогда не используется как developer-task sandbox.
- Workspace V1 использует независимый clone, а не linked worktree.
- Repository isolation нельзя описывать как sandbox произвольного кода.
- Patch не применяется без полного успешного evidence Preflight V1.
- Изменённый код не исполняется до отдельного решения по execution isolation.
- Автоматические merge, commit, push и promotion запрещены в Developer Safety Kernel V1.
- Package migration не смешивается с этим этапом.

## 13. Следующее точное действие

1. Заменить два architecture-документа версиями после `1035de4`.
2. Проверить `git status --short` и diff обоих документов.
3. Закоммитить только документы:

```text
docs: close developer task preflight and adopt isolated repository workspace
```

4. Убедиться, что рабочее дерево чистое.
5. Проверить SHA-256 подготовленного V1A patch.
6. Выполнить `git apply --check`; использовать утверждённый CRLF fallback только при необходимости.
7. Применить V1A patch.
8. Запустить targeted checks и полный `check`.
9. Не создавать V1A code-коммит до успешного завершения всех проверок.

## 14. Планируемые коммиты

Документация:

```text
docs: close developer task preflight and adopt isolated repository workspace
```

V1A code:

```text
feat: add isolated developer task repository workspace
```

## 15. Режим модели

Сейчас рекомендуется **Pro Standard**.

Причина: Roadmap Change 001 и V1A задают новую Git isolation boundary. После прохождения API и Windows fault-injection реализационные продолжения можно выполнять в режиме **«Очень высокий»** до следующего архитектурного или security-решения.

## 16. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_workspace.log
data/logs/pipeline/*_check.log
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
