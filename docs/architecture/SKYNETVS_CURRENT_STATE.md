# SkynetVS Current State

## 1. Метаданные

- Дата обновления: `2026-08-04`
- Ветка: `main`
- Проверенный code baseline перед этим documentation commit: `892e175`
- Название code baseline: `feat: add developer task workspace cleanup audit`
- `origin/main` на проверенной code-точке: `892e175`
- Documentation HEAD после сохранения этого файла определяется фактическим `git log -1`; self-referential commit SHA в содержимом не фиксируется.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1` → `09f8708`
- Рабочее дерево после documentation commit должно быть чистым.

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

## 8. VERIFIED — Isolated Repository Workspace V1B

### Commit

```text
892e175 feat: add developer task workspace cleanup audit
```

### Публичный API

```python
cleanup_developer_task_workspace(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskWorkspaceCleanupReport
```

### Подтверждено

- cleanup принимает только typed manifest, успешный полный Preflight report и успешный Workspace report;
- explicit `workspace_parent`, fixed layout, workspace ID и marker evidence сверяются до удаления;
- non-serialized cleanup capability связана с canonical marker через SHA-256;
- marker читается как bounded immutable binary snapshot с TOCTOU-проверками;
- source repository, task root, workspace parent, sibling paths и пересекающиеся пути не удаляются;
- root/marker/descendants с symlink, junction, reparse point или special-file блокируются;
- transient Windows filesystem failures повторяются ограниченно;
- permanent failure и directory identity change возвращаются структурированно;
- повторный cleanup после успеха идемпотентен;
- source HEAD/status/refs/index/config до и после cleanup совпадают;
- уже существовавшие source changes сохраняются;
- cleanup capability отсутствует в `repr()` и `to_dict()`;
- applied или staged workspace может быть удалён тем же verified cleanup lifecycle.

### Проверки

```text
Workspace V1A:                     39/39
Workspace Cleanup V1B:             41/41
developer_task_workspace_cleanup:  completed successfully
full check:                        completed successfully
```

## 9. CURRENT — Developer Task Patch Apply V1

### Назначение

Применить точные verified patch bytes только внутри независимого repository workspace, повторно доказать итоговое Git-состояние и не допустить частичного или неподтверждённого результата.

### Утверждённый API

```python
apply_developer_task_patch(
    manifest: DeveloperTaskManifest,
    *,
    preflight_report: DeveloperTaskPreflightReport,
    workspace_report: DeveloperTaskWorkspaceReport,
    workspace_parent: Path,
) -> DeveloperTaskPatchApplyReport
```

### Разделение ответственности

```text
modules/developer/developer_task_patch_apply.py
    evidence orchestration, filesystem/marker boundary, source snapshots, final report

modules/developer/developer_task_patch_apply_git.py
    hardened Git apply, staged-state audit, rollback to clean base
```

### In scope

- повторно проверить manifest fingerprint, полный Preflight report и Workspace report;
- требовать явный `workspace_parent` и fixed workspace layout;
- проверить workspace marker, cleanup capability, tree safety и directory identity;
- снять read-only source Git snapshot до mutation;
- использовать только immutable patch bytes из Preflight V1;
- применять patch через stdin с `git apply --index`;
- не использовать `--3way`, `--reject` или `--unsafe-paths`;
- оставить `HEAD` detached на `base_commit`;
- требовать staged-only state без unstaged/untracked/conflict;
- повторно извлечь raw diff, modes и result-index paths;
- точно сравнить их с Preflight V1C1/V1C2 evidence;
- вычислить result tree и SHA-256 canonical staged diff;
- принудительно привязать каждую mutating Git-команду к ожидаемым `--git-dir` и `--work-tree`;
- проверить local Git config без includes, запретить `core.worktree`, external filters и другие execution/redirection keys;
- повторно проверить remotes, refs, alternates, shallow state, hooks path и config fingerprint;
- повторно проверить workspace marker и source snapshot после apply;
- при любом failure после начала mutation восстановить workspace через bounded reset/clean;
- различать `applied`, `rejected_clean` и `failed_dirty`;
- записать canonical `control/patch_apply.json`;
- создать non-serialized 32-byte check capability для следующего Typed Check Runner;
- сохранить совместимость verified cleanup после успешного apply.

### Out of scope

- запуск `py_compile`, Python modules или pipeline внутри изменённого workspace;
- произвольный shell;
- установка зависимостей;
- commit, branch, merge, push или promotion;
- изменение основного repository;
- OS/process/network sandbox;
- автоматический перенос результата в `main`;
- orphan recovery после потери in-memory capabilities.

## 10. Ожидаемые файлы Patch Apply V1

```text
A  modules/developer/developer_task_patch_apply.py
A  modules/developer/developer_task_patch_apply_git.py
M  modules/developer/developer_task_patch_index.py
M  modules/developer/developer_task_workspace_git.py
A  tools/eval_developer_task_patch_apply.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Стабильные Preflight/Workspace APIs, `main.py` и пользовательские голосовые команды не изменяются.

## 11. PLANNED — targeted checks Patch Apply V1

```text
python -m py_compile \
    modules/developer/developer_task_patch_apply.py \
    modules/developer/developer_task_patch_apply_git.py \
    modules/developer/developer_task_patch_index.py \
    modules/developer/developer_task_workspace_git.py \
    tools/eval_developer_task_patch_apply.py \
    tools/eval_package_boundaries.py \
    tools/pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_preflight_composition
python -m tools.eval_developer_task_workspace
python -m tools.eval_developer_task_workspace_cleanup
python -m tools.eval_developer_task_patch_apply
python tools/pipeline.py developer_task_patch_apply
python tools/pipeline.py check
```

Ожидаемые summaries:

```text
Package boundaries:             28/28
Preflight composition:          19/19
Workspace V1A:                  39/39
Workspace cleanup V1B:          41/41
Patch Apply V1:                 30/30
```

## 12. Критерии завершения Patch Apply V1

1. raw/failed/forged reports не могут инициировать mutation;
2. source/task/workspace paths и canonical marker совпадают с evidence;
3. dirty, attached, linked или повторно applied workspace блокируется до mutation;
4. exact patch bytes передаются Git только через stdin;
5. apply использует index + worktree и не использует unsafe recovery options;
6. фактические changes/modes/result-index paths точно совпадают с Preflight facts;
7. staged state не содержит unstaged/untracked/conflict/submodule changes;
8. `HEAD`, refs, remotes, alternates, hooks и shallow boundary не меняются;
9. Git root/git-dir/common-dir явно совпадают с isolated workspace evidence;
10. local config не содержит includes, worktree redirection или external filter commands и сохраняет isolated policy fingerprint;
11. source Git snapshot до и после совпадает;
12. apply marker canonical и связан с result tree/diff/config/check capability;
13. capability отсутствует в serialization и repr;
14. apply/fact/marker/source/postcondition failure откатывает workspace к чистому base;
15. rollback failure возвращает `failed_dirty` и запрещает reuse;
16. patch, удаляющий последний tracked file, корректно поддерживает пустой resulting index;
17. successful applied workspace удаляется verified cleanup API;
18. eval проходит на Windows: `30/30`;
19. новый targeted flow и полный `check` проходят;
20. code-коммит содержит только семь ожидаемых файлов;
21. `origin/main` обновлён;
22. current-state обновлён после code-коммита.

## 13. DEFERRED

- Developer Task Typed Check Runner V1.
- Execution isolation policy для checks, выполняющих изменённый код.
- Developer Task Result and Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Workspace crash recovery / orphan cleanup.
- Domain Package Structure V2.
- Tools Package Structure V1.

## 14. Решения, которые нельзя пересматривать молча

- `skynet-runtime-foundation-v1` остаётся на `09f8708`.
- Основной worktree никогда не используется как developer-task sandbox.
- Patch применяется только после полного Preflight V1 и Workspace V1 evidence.
- Применяются immutable bytes, а не повторно прочитанный patch-файл.
- Partial apply или post-apply mismatch не разрешает продолжение.
- Rollback failure делает workspace непригодным для checks.
- Изменённый код не исполняется до отдельного execution isolation решения.
- Apply marker/check capability не сериализуются как секрет для восстановления.
- Автоматические commit/merge/push/promotion запрещены.
- Package migration не смешивается с Developer Safety Kernel.

## 15. Следующее точное действие

1. Закоммитить это обновление architecture-документов отдельно.
2. Убедиться, что working tree чистый.
3. Проверить SHA-256 Patch Apply V1 patch.
4. Выполнить `git apply --check`; CRLF fallback применять только при контекстном несовпадении.
5. Применить code patch.
6. Запустить compilation и targeted eval.
7. Запустить `developer_task_patch_apply` flow.
8. Запустить полный `check`.
9. Не создавать code-коммит до успешного `30/30`, targeted flow и полного pipeline.

## 16. Планируемые коммиты

Документация:

```text
docs: close workspace lifecycle and start developer task patch apply
```

Code:

```text
feat: add verified developer task patch apply
```

## 17. Режим модели

До реального Windows-прогона Patch Apply V1 остаёмся на **Pro Standard**, потому что это первая изменяющая Git-граница Developer Safety Kernel.

После успешного `30/30`, полного `check`, commit и обновления current-state можно вернуться на **«Очень высокий»** для механической реализации уже утверждённого Typed Check Runner. Перед утверждением process/OS execution isolation снова потребуется Pro Standard.

## 18. Файлы для будущего handoff

Обязательно:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Дополнительно приложить последние:

```text
data/logs/pipeline/*_developer_task_patch_apply.log
data/logs/pipeline/*_check.log
```

Новый чат должен продолжать с раздела **«Следующее точное действие»**, а не восстанавливать roadmap по памяти.
