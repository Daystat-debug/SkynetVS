# SkynetVS Current State

**Дата обновления:** 2026-07-30, снимок на 03:08 по локальному времени рабочей машины  
**Модель статусов:** `VERIFIED`, `PLANNED`, `DEFERRED`, `UNVERIFIED`

---

## 1. Источники истины

Использовать источники в следующем порядке:

1. Текущее состояние Git и текущий код проекта.
2. Последние успешно завершённые targeted checks и полные pipeline-логи.
3. Этот файл: `docs/architecture/SKYNETVS_CURRENT_STATE.md`.
4. `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
5. История чата и предположения.

Если источники противоречат друг другу, нельзя молча объединять их. Нужно зафиксировать противоречие и отдать приоритет Git, коду и проверкам.

---

## 2. VERIFIED — снимок репозитория

Следующие значения получены из `SkynetVS_Preflight_Context_20260730_030824.zip` до документационного коммита:

- Ветка: `main`.
- Проверенный code baseline HEAD: `09f8708f67f4cf1681801ea41498815cf7df5948`.
- Название HEAD: `refactor: move desktop interaction services into package`.
- `origin/main`: `09f8708f67f4cf1681801ea41498815cf7df5948`.
- Стабильный тег на code baseline: `skynet-runtime-foundation-v1`.
- Тег намеренно остаётся на `09f8708` как точка до появления developer-task runtime.
- В снимке не было unstaged-изменений отслеживаемых файлов.
- Staged-изменение на момент снимка:
  - `A  docs/architecture/SkynetVS_ARCHITECTURE_ROADMAP_V1.md`.
- `docs/architecture/SKYNETVS_CURRENT_STATE.md` на момент снимка отсутствовал.

### Проблема регистра имени roadmap

Канонический путь:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
```

В Git index снимка записан путь со смешанным регистром:

```text
docs/architecture/SkynetVS_ARCHITECTURE_ROADMAP_V1.md
```

Перед документационным коммитом необходимо выполнить двухшаговый `git mv`, чтобы Windows и Git зафиксировали каноническое имя в верхнем регистре.

---

## 3. Общая цель проекта

Создать SkynetVS как персонального голосового ассистента, который со временем сможет превзойти обычный чат-ассистент в персональной среде пользователя за счёт сочетания:

- постоянного персонального и проектного контекста;
- естественного голосового взаимодействия;
- безопасного управления компьютером и приложениями;
- понимания экрана и текущей рабочей ситуации;
- контролируемой разработки и саморевью собственного кода;
- обучения на обратной связи с защитой от регрессий;
- наблюдаемости, воспроизводимости, доказательств и rollback;
- будущего мультимодального восприятия физического мира.

Автономность не должна развиваться быстрее безопасности, диагностики, изоляции, проверки и возможности отката.

---

## 4. VERIFIED — завершённые этапы

- Runtime Ownership and Fault Injection Audit.
- Safe Developer Task Contract V1.
- Developer Package Structure V1.
- Core Package Structure V1.
- Runtime Package Structure V1.
- Learning Package Structure V1.
- Desktop Package Structure V1.
- Стабильный foundation-тег `skynet-runtime-foundation-v1` на `09f8708`.

`Desktop Package Structure V1` включал только:

- `modules/desktop/screenshot.py`;
- `modules/desktop/typing_service.py`;
- `modules/desktop/window_context_service.py`.

Он не включал полный перенос audio, speech, health, reminders, commands и остальных плоских модулей.

---

## 5. VERIFIED — последний полный pipeline

Последний приложенный лог:

```text
data/logs/pipeline/20260730_015314_check.log
```

Результат:

- flow: `check`;
- pipeline-этапов: `65`;
- записей `[OK]`: `866`;
- записей `[FAIL]`: `0`;
- финал: `Flow 'check' completed successfully`.

Ключевые подтверждённые секции:

- package boundaries: `28` кейсов, `0` ошибок;
- developer task contract: `18` кейсов, `0` ошибок;
- runtime architecture audit: `9` кейсов, `0` ошибок.

---

## 6. Текущий организационный gate

### Roadmap Lock V1

**Статус:** готов к документационному коммиту.

Содержимое roadmap подготовлено и добавлено в index, но приложенный Git-снимок доказывает, что оно ещё не было закоммичено и отправлено в `origin`.

Roadmap Lock V1 считается завершённым только когда:

1. roadmap имеет каноническое имя в верхнем регистре;
2. этот current-state файл присутствует;
3. оба файла закоммичены;
4. commit отправлен в `origin/main`;
5. после этого `git status --short` пуст.

---

## 7. PLANNED — текущий программный этап

# Developer Task Preflight V1

**Статус:** архитектура проаудирована; реализация не начата.

### Почему этот этап выполняется сейчас

Существующий manifest validator доказывает корректность схемы задачи и полей политики. Он ещё не доказывает, что реальный репозиторий, commit, worktree, байты patch, scope patch и применимость patch соответствуют manifest.

`Developer Task Preflight V1` закрывает этот разрыв до того, как patch сможет попасть даже в изолированное рабочее окружение.

---

## 8. In scope — Developer Task Preflight V1

- Убедиться, что `project_root` является точным корнем non-bare Git worktree.
- Разрешить `HEAD` до commit-объекта.
- Разрешить `manifest.base_commit` до commit-объекта.
- Потребовать `resolved HEAD == resolved base_commit`.
- Потребовать чистый index и worktree, включая staged, unstaged, untracked, conflict и dirty-submodule состояния.
- Получать task artifact directory явно и отдельно от `project_root`.
- Проверить, что patch — обычный файл, а не symlink.
- Ограничить максимальный размер patch.
- Прочитать байты patch один раз и вычислить SHA-256 именно от этих байтов.
- Сравнить вычисленный hash с `manifest.patch_sha256`.
- Проверить применимость patch без изменения реального index и worktree.
- Получить точные изменяемые пути и file modes средствами Git через временный disposable index.
- Сравнить каждый затронутый путь с `manifest.allowed_files` с точной и case-insensitive проверкой.
- Отклонять case-collision и неоднозначность регистра.
- Отклонять symlink, gitlink/submodule, небезопасные типы файлов и пути вне разрешённого scope.
- Вернуть immutable структурированный report со стабильными issue codes.

---

## 9. Out of scope — Developer Task Preflight V1

- Применение patch к реальному worktree.
- Изменение реального Git index.
- `git reset`, `git clean`, `git stash`, checkout, merge, commit или push.
- Создание isolated worktree для реального выполнения.
- Запуск manifest checks: `py_compile`, `python_module`, pipeline flow.
- Установка зависимостей.
- Автоматическое исправление manifest.
- Автоматическое расширение `allowed_files`.
- Автоматический promotion или merge.
- Проверка `source_sha256`, поскольку текущий manifest не содержит локального пути к source artifact, который preflight мог бы прочитать.

---

## 10. Принятые архитектурные решения

- `DeveloperTaskManifest` остаётся валидированным входным контрактом.
- Preflight принимает уже валидированный `DeveloperTaskManifest`, а не raw JSON object.
- Manifest schema validation и runtime preflight остаются разными ответственностями.
- Первый preflight-патч не изменяет `developer_task_contract.py` и `developer_task_validator.py`, если тест не докажет реальный пробел контракта.
- Публичный API preflight:

```python
run_developer_task_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
    task_root: Path,
) -> DeveloperTaskPreflightReport
```

- Ожидаемые операционные ошибки возвращаются как структурированные issues, а не как одна общая exception.
- Ошибки использования API разработчиком могут оставаться `TypeError` или `ValueError`.
- Реальный project index и worktree всегда остаются нетронутыми.
- Нельзя заново реализовывать parser Git patch через хрупкий разбор строк.
- После вычисления hash те же байты patch передаются Git через standard input, чтобы проверялись именно верифицированные байты.
- Симуляция patch выполняется с disposable `GIT_INDEX_FILE` во временном каталоге и сравнивается с разрешённым base commit.
- Rename detection отключается при извлечении scope: rename консервативно представляется как deletion плюс addition, поэтому оба пути обязаны быть разрешены.
- `modules/developer/` и `tools/eval_developer_*` остаются protected.
- В `modules/developer/__init__.py` не добавляются reexports.

---

## 11. PLANNED — публичные типы

Файл:

```text
modules/developer/developer_task_preflight.py
```

Планируемые immutable-типы:

```python
@dataclass(frozen=True)
class DeveloperTaskPreflightIssue:
    code: str
    check: str
    message: str
    expected: str = ""
    actual: str = ""


@dataclass(frozen=True)
class DeveloperTaskPreflightReport:
    manifest_fingerprint: str
    project_root: str
    repository_root: str
    task_root: str
    patch_path: str
    head_commit: str
    resolved_base_commit: str
    actual_patch_sha256: str
    changed_files: tuple[str, ...]
    issues: tuple[DeveloperTaskPreflightIssue, ...]
```

Report должен предоставлять:

- `ok`;
- `issue_codes`;
- `to_dict()`.

Точные имена полей можно изменить только до первого implementation commit preflight; после этого интерфейс фиксируется eval.

---

## 12. Threat model

Preflight обязан безопасно отклонять как минимум:

- неправильный каталог или неправильный репозиторий;
- bare repository;
- `project_root`, указывающий на подкаталог репозитория;
- отсутствующий или невалидный `HEAD`;
- отсутствующий, неоднозначный или не являющийся commit-объектом `base_commit`;
- несовпадение `HEAD` и base commit;
- staged, unstaged, untracked, conflict или dirty-submodule состояние;
- отсутствующий task directory;
- task directory или patch path через symlink/reparse point;
- отсутствующий patch;
- patch, не являющийся обычным файлом;
- oversized patch;
- несовпадение patch hash;
- подмену patch после вычисления hash;
- malformed, empty или неприменимый patch;
- path traversal или unsafe Git path;
- путь вне `allowed_files`;
- case-only mismatch или duplicate casefold path;
- создание или изменение symbolic link;
- создание или изменение gitlink/submodule;
- patch, изменяющий больше путей, чем объявлено;
- Git command timeout или неожиданную ошибку Git;
- ошибку очистки временных analysis artifacts.

---

## 13. Первый implementation slice

### Developer Task Preflight V1A — Repository Gate

Ожидаемые файлы:

```text
modules/developer/developer_task_preflight.py
tools/eval_developer_task_preflight.py
tools/eval_package_boundaries.py
tools/pipeline.py
```

Первый slice реализует и проверяет:

- immutable report и issue types;
- exact Git root validation;
- non-bare worktree validation;
- разрешение `HEAD`;
- разрешение base commit;
- `HEAD == base_commit`;
- clean status через machine-readable porcelain;
- структурированные Git failures и timeouts;
- pipeline flow `developer_task_preflight`;
- регистрацию нового protected-модуля в package-boundary eval.

Patch integrity и disposable-index simulation выполняются следующими slices внутри того же этапа `Developer Task Preflight V1`.

---

## 14. PLANNED — targeted checks для V1A

Планируемый порядок:

```powershell
python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python tools/pipeline.py developer_task_preflight
python tools/pipeline.py check
```

Инструменты запускаются из корня проекта.

---

## 15. Критерии завершения полного Developer Task Preflight V1

- Реализованы repository, base, cleanliness, artifact, hash, scope, mode и applicability checks.
- Каждая ожидаемая ошибка имеет стабильный issue code и eval-case.
- Реальный project index и worktree одинаковы до и после каждого eval-case.
- Новые developer-файлы защищены существующей safety policy.
- Package-boundary eval проходит.
- Targeted preflight flow проходит.
- Полный flow `check` проходит.
- Этап имеет отдельный commit, после чего обновлён этот файл.

---

## 16. Запрещённые скрытые изменения

- Нельзя расширять Preflight V1 до isolated worktree execution.
- Нельзя добавлять automatic patch installation.
- Нельзя переносить несвязанные production- или tool-файлы.
- Нельзя менять manifest schema без доказанного пробела и явного Roadmap Change.
- Нельзя добавлять произвольные shell-команды.
- Нельзя вручную парсить Git patch headers, если Git может выдать machine-readable результат.
- Нельзя переносить `skynet-runtime-foundation-v1` с `09f8708`.
- Нельзя считать зелёный полный pipeline доказательством поведения, для которого нет targeted eval.

---

## 17. UNVERIFIED — открытые решения

Следующее должно быть подтверждено реализацией, а не принято на веру:

- Финальное runtime-место task artifacts: вне репозитория или в отдельном ignored task inbox.
- Точная стратегия обнаружения Windows reparse points для task directory и patch file.
- Финальный предел размера patch; предлагаемое значение V1: `5 MiB`.
- Точные Git timeouts; предлагаемое значение V1: `10 секунд` на команду.
- Нужно ли дополнительно нейтрализовать local repository config сверх явных Git flags и безопасных environment variables.

Эти решения не должны молча менять manifest schema.

---

## 18. DEFERRED

- Developer Task Isolated Workspace V1.
- Developer Task Patch Apply V1.
- Developer Task Typed Check Runner V1.
- Developer Task Result & Evidence V1.
- Developer Task Manual Promotion V1.
- Developer Safety Kernel Audit V1.
- Domain Package Structure V2.
- Tools Package Structure V1.
- Дополнительные package migrations для audio, speech, health, reminders, understanding и commands.

---

## 19. Next Exact Action

До изменения production-кода:

1. Исправить регистр имени roadmap в Git.
2. Добавить этот файл в `docs/architecture/`.
3. Проверить staged documentation diff.
4. Создать документационный commit roadmap и current-state protocol.
5. Отправить commit в `origin`.
6. Подтвердить чистое рабочее дерево.
7. Начать Developer Task Preflight V1A.

---

## 20. Планируемые commits

Документационный gate:

```text
docs: lock SkynetVS architecture roadmap and current state
```

Первый программный slice:

```text
feat: add developer task repository preflight
```

---

## 21. Рекомендованный режим модели

- Текущий threat-model и API: `Pro Standard`.
- Механическая реализация после фиксации интерфейса V1A: `Очень высокий`.
- Disposable-index scope analysis и финальный security audit: снова `Pro Standard`.

---

## 22. Файлы для нового чата

Всегда прикладывать:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Для архитектурной работы или закрытия этапа дополнительно прикладывать:

```text
последний data/logs/pipeline/*_check.log
```

Для активной разработки Developer Task Preflight дополнительно прикладывать текущие изменённые developer/preflight-файлы и targeted eval.

---

## 23. Стартовый текст нового чата

```text
Продолжаем разработку SkynetVS.

Прочитай полностью приложенные SKYNETVS_ARCHITECTURE_ROADMAP_V1.md и SKYNETVS_CURRENT_STATE.md. Git, текущий код и последние проверки имеют приоритет над документами; CURRENT_STATE имеет приоритет над roadmap для текущей точки.

Не восстанавливай план по памяти, не расширяй scope без Roadmap Change и не объявляй PLANNED или UNVERIFIED завершённым.

Сначала кратко назови подтверждённую базу, текущий этап, его in scope/out of scope и Next Exact Action. Затем продолжай именно с Next Exact Action.
```
