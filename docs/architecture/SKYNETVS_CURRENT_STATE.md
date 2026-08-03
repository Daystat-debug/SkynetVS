# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-03`
- Ветка: `main`
- HEAD: `4861934`
- Название HEAD: `feat: add isolated developer task repository workspace`
- `origin/main`: `4861934`
- Стабильный foundation-тег: `skynet-runtime-foundation-v1` → `09f8708`
- Рабочее дерево: чистое

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

Финальный targeted flow:

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

Полный `check` после V1D завершён успешно.

## 6. Roadmap Change 001 — VERIFIED решение

### Решение

Использовать независимый локальный clone репозитория вместо linked `git worktree`.

Этап называется:

```text
Developer Task Isolated Repository Workspace V1
```

### Причина

Linked worktree имеет отдельные `HEAD` и index, но разделяет common Git administration, refs/config/object data с основным репозиторием. Для будущего developer-task runtime это недостаточно независимая Git-граница.

### Критичное ограничение

Независимый clone обеспечивает только Git/repository isolation. Он не является OS/process sandbox и не разрешает исполнение недоверенного изменённого кода. Execution isolation должна быть утверждена до checks, которые импортируют или запускают изменённый код.

## 7. VERIFIED — Isolated Repository Workspace V1A

### Commit

```text
4861934 feat: add isolated developer task repository workspace
```

### Публичный API

```python
create_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceReport
```

### Подтверждено

- принимается только успешный полный отчёт Preflight V1;
- source repository повторно проверяется перед clone;
- `workspace_parent` должен быть внешним обычным каталогом без symlink/junction/reparse в цепочке;
- parent не может пересекаться с source repository или task root;
- parent не может находиться внутри worktree, Git administration directory или bare repository;
- создаётся уникальный workspace-контейнер;
- repository создаётся через независимый clone с `--no-local`, `--no-hardlinks`, `--no-checkout`, `--no-tags`, `--single-branch`, `--depth=1`;
- HOME, USERPROFILE, XDG, global Git config, hooks и template directory изолированы;
- workspace использует deterministic Git policy и filesystem guards;
- baseline symlink, gitlink, `.git` control paths, Windows-unsafe paths и case-collision блокируются;
- `HEAD` detached и равен verified `base_commit`;
- workspace shallow и чистый;
- remotes, обычные refs и alternate object directories отсутствуют;
- marker записывается canonical JSON;
- cleanup уже частично созданного неуспешного workspace выполняется только внутренним creation-lifecycle;
- source HEAD/status/refs/index/config не меняются;
- частично созданный workspace очищается с ограниченными Windows retries.

### Проверки

```text
repository workspace eval:      39/39
developer_task_workspace flow:  completed successfully
full check:                     completed successfully
```

Подтверждена Windows-регрессия `core.autocrlf=true`: source line-ending policy больше не создаёт ложный `source_repository_stale`.

## 8. CURRENT — Isolated Repository Workspace V1B

### Этап

```text
Workspace Cleanup and Lifecycle Audit
```

### Почему сейчас

V1A умеет безопасно создавать независимый workspace и очищать только частично созданный workspace при ошибке. Для полноценного lifecycle нужен отдельный публичный API, который удаляет уже успешно созданный workspace только по проверяемой цепочке evidence.

### Утверждённый API

```python
cleanup_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceCleanupReport
```

### Разделение ответственности

```text
modules/developer/developer_task_workspace_cleanup.py
    orchestration, evidence chain, immutable final report

modules/developer/developer_task_workspace_cleanup_fs.py
    no-follow filesystem validation, marker read, tree scan, bounded removal

modules/developer/developer_task_workspace_source.py
    read-only source Git snapshots before and after cleanup
```

### In scope

- принимать только typed manifest, полный успешный Preflight report и успешный Workspace report;
- требовать явный `workspace_parent` и сверять его с immutable evidence;
- проверять manifest fingerprint, source/task/base commit и точную workspace layout;
- требовать корректный workspace ID, содержащий task ID, fingerprint prefix и random suffix;
- расширить immutable Workspace report non-serialized 32-byte cleanup capability;
- сверять SHA-256 cleanup capability с canonical marker;
- читать marker как bounded immutable binary snapshot с TOCTOU-проверками;
- требовать точный SHA-256 и canonical UTF-8 JSON marker без неизвестных полей;
- запрещать удаление source repository, task root, workspace parent и пересекающихся путей;
- запрещать root/marker/tree symlink, junction, reparse point и special-file traversal;
- удалять только подтверждённый workspace root;
- использовать bounded Windows retries и read-only handling;
- обнаруживать подмену directory identity между retry;
- быть идемпотентным: повторный cleanup отсутствующего подтверждённого workspace возвращает `already_absent`;
- делать read-only source Git snapshots до и после cleanup;
- сохранять и доказывать неизменность source HEAD/status/refs/index/config;
- возвращать immutable structured cleanup report;
- не сериализовать cleanup capability.

### Out of scope

- применение developer patch;
- исполнение изменённого кода;
- commit, merge, push или promotion;
- удаление произвольного пути без typed report и capability;
- автоматический recovery после потери in-memory cleanup capability;
- cleanup orphan workspace после crash/restart;
- OS/process/network sandboxing;
- изменение source repository.

### Важная lifecycle-граница

Cleanup capability намеренно отсутствует в `to_dict()`. Поэтому V1B обслуживает явный cleanup в том же доверенном lifecycle, где доступен оригинальный immutable `DeveloperTaskWorkspaceReport`.

Crash recovery и orphan cleanup требуют отдельного будущего контракта и не должны незаметно ослаблять V1B.

## 9. Ожидаемые файлы V1B

```text
M  modules/developer/developer_task_workspace.py
A  modules/developer/developer_task_workspace_cleanup.py
A  modules/developer/developer_task_workspace_cleanup_fs.py
A  modules/developer/developer_task_workspace_source.py
A  tools/eval_developer_task_workspace_cleanup.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

`developer_task_workspace.py` изменяется только для выпуска non-serialized cleanup capability и записи её SHA-256 в marker. Git creation boundary `developer_task_workspace_git.py`, Preflight V1, `main.py` и пользовательские команды не изменяются.

## 10. PLANNED — targeted checks V1B

```text
python -m py_compile \
    modules/developer/developer_task_workspace.py \
    modules/developer/developer_task_workspace_cleanup.py \
    modules/developer/developer_task_workspace_cleanup_fs.py \
    modules/developer/developer_task_workspace_source.py \
    tools/eval_developer_task_workspace_cleanup.py \
    tools/eval_package_boundaries.py \
    tools/pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_preflight_composition
python -m tools.eval_developer_task_workspace
python -m tools.eval_developer_task_workspace_cleanup
python tools/pipeline.py developer_task_workspace_cleanup
python tools/pipeline.py check
```

Ожидаемые summaries:

```text
Package boundaries:             28/28
Preflight composition:          19/19
Workspace V1A:                  39/39
Workspace cleanup V1B:          41/41
```

## 11. Критерии завершения V1B

V1B завершён только если:

1. forged/raw/failed reports не могут инициировать удаление;
2. явный parent и все workspace paths совпадают с evidence;
3. cleanup capability и canonical marker совпадают;
4. marker hash, schema, fields и bytes проверены;
5. source/task/parent и sibling paths не удаляются;
6. root и descendants с reparse/symlink/special-file блокируются;
7. transient Windows cleanup failure повторяется ограниченно;
8. permanent failure возвращает structured report и не скрывается;
9. directory identity change между retries блокируется;
10. повторный cleanup после успеха идемпотентен;
11. source Git snapshot до и после совпадает;
12. pre-existing source changes сохраняются и не мешают безопасному cleanup;
13. cleanup report immutable и не содержит capability;
14. eval проходит на Windows: `41/41`;
15. package boundary и новый targeted flow подключены;
16. полный `check` проходит;
17. code-коммит содержит только семь ожидаемых файлов;
18. `origin/main` обновлён;
19. current-state обновлён после code-коммита.

## 12. DEFERRED

- Workspace crash recovery / orphan cleanup.
- Developer Task Patch Apply V1.
- Developer Task Typed Check Runner V1.
- Execution isolation policy для checks, выполняющих изменённый код.
- Developer Task Result and Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Domain Package Structure V2.
- Tools Package Structure V1.

## 13. Решения, которые нельзя пересматривать молча

- `skynet-runtime-foundation-v1` остаётся на `09f8708`.
- Gates Preflight V1 и их ответственности остаются раздельными.
- Основной worktree никогда не используется как developer-task sandbox.
- Workspace V1 использует независимый clone, а не linked worktree.
- Repository isolation нельзя описывать как sandbox произвольного кода.
- Patch не применяется без полного успешного evidence Preflight V1.
- Изменённый код не исполняется до отдельного решения по execution isolation.
- Удаление workspace требует capability + canonical marker + explicit parent.
- Отсутствие serialized cleanup capability не обходится автоматическим force-delete.
- Автоматические merge, commit, push и promotion запрещены в Developer Safety Kernel V1.
- Package migration не смешивается с этим этапом.

## 14. Следующее точное действие

1. Обновить этот current-state документ после commit `4861934`.
2. Закоммитить только architecture-документы.
3. Убедиться, что рабочее дерево чистое.
4. Проверить SHA-256 подготовленного V1B patch.
5. Выполнить `git apply --check`; использовать CRLF fallback только при контекстном несовпадении.
6. Применить V1B patch.
7. Запустить compilation, targeted eval, новый flow и полный `check`.
8. Не создавать code-коммит до успешного `41/41` и полного pipeline.

## 15. Планируемые коммиты

Документация:

```text
docs: update SkynetVS state after isolated repository workspace
```

V1B code:

```text
feat: add developer task workspace cleanup audit
```

## 16. Режим модели

До реального Windows-прогона V1B остаёмся на **Pro Standard**, потому что этап задаёт destructive filesystem boundary.

После успешного `41/41`, полного `check`, commit и обновления current-state можно вернуться на **«Очень высокий»** для механической части следующего этапа. Перед утверждением `Patch Apply V1` security-контракта снова потребуется Pro Standard.

## 17. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_workspace_cleanup.log
data/logs/pipeline/*_check.log
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
