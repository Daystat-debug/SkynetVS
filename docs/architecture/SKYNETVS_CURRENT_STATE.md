# SkynetVS Current State

**Дата обновления:** 2026-07-31  
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

## 2. VERIFIED — текущее состояние репозитория

- Ветка: `main`.
- Проверенный code HEAD до этого documentation update, сокращённый SHA: `6e2aa78`.
- Название code HEAD: `feat: add developer task repository preflight`.
- `origin/main` до этого documentation update: указывает на тот же commit `6e2aa78`.
- После коммита обновлённого current-state файла фактический HEAD станет новым documentation commit; его всегда нужно брать напрямую из Git.
- Рабочее дерево: чистое; `git status --short` ничего не выводит.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1`.
- Тег намеренно остаётся на `09f8708` как проверенная runtime-база до начала Developer Safety Kernel.
- Roadmap присутствует по каноническому пути:
  - `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
- Этот current-state файл присутствует по каноническому пути:
  - `docs/architecture/SKYNETVS_CURRENT_STATE.md`.

Полный SHA code commit `6e2aa78` не был включён в последний присланный вывод. При необходимости его нужно брать напрямую из Git. После documentation commit команда `git rev-parse HEAD` вернёт уже SHA документационного коммита, поэтому code commit следует находить через `git log --oneline --decorate`. Git остаётся источником истины.

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

## 4. VERIFIED — завершённые архитектурные этапы

- Runtime Ownership and Fault Injection Audit.
- Safe Developer Task Contract V1.
- Developer Package Structure V1.
- Core Package Structure V1.
- Runtime Package Structure V1.
- Learning Package Structure V1.
- Desktop Package Structure V1.
- Roadmap Lock V1.
- Стабильный foundation-тег `skynet-runtime-foundation-v1` на `09f8708`.

`Desktop Package Structure V1` включал только:

- `modules/desktop/screenshot.py`;
- `modules/desktop/typing_service.py`;
- `modules/desktop/window_context_service.py`.

Он не включал полный перенос audio, speech, health, reminders, commands и остальных плоских модулей.

---

## 5. VERIFIED — Developer Task Preflight V1A

### Repository Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
6e2aa78 feat: add developer task repository preflight
```

Состав commit:

```text
A  modules/developer/developer_task_preflight.py
A  tools/eval_developer_task_preflight.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Статистика commit:

```text
4 files changed, 1047 insertions(+)
```

V1A реализует read-only проверку:

- точного корня Git-репозитория;
- non-bare worktree;
- разрешения `HEAD` в commit;
- разрешения `manifest.base_commit` в commit;
- совпадения `HEAD == base_commit`;
- чистоты index и worktree;
- staged, unstaged, untracked, conflict и dirty-submodule состояний;
- безопасного поведения при Git timeout, отсутствии Git и ошибке запуска;
- нейтрализации унаследованных Git redirection/trace переменных;
- immutable структурированного отчёта и стабильных issue codes.

---

## 6. VERIFIED — проверки V1A

Targeted flow `developer_task_preflight`:

- package boundaries: `28/28`, ошибок `0`;
- developer task contract: `18/18`, ошибок `0`;
- developer task repository preflight: `22/22`, ошибок `0`;
- финал: `Flow 'developer_task_preflight' completed successfully`.

Полный flow `check`:

- завершён успешно;
- новый repository preflight включён в общий pipeline;
- регрессий в NLU, STT, TTS, audio, reminders, runtime и package boundaries не обнаружено.

Подтверждающие логи:

```text
data/logs/pipeline/20260730_133532_developer_task_preflight.log
data/logs/pipeline/20260730_133618_check.log
```

---

## 7. PLANNED — текущий программный этап

# Developer Task Preflight V1B — Patch Integrity Gate

**Статус:** архитектурная граница утверждена; патч подготовлен; в проект ещё не применён.

### Почему этот этап выполняется сейчас

V1A доказал состояние репозитория, но ещё не доказывает, что фактический patch-файл:

- находится в разрешённом task artifact directory;
- не подменён symlink, junction или reparse point;
- является обычным файлом;
- имеет допустимый размер;
- прочитан без текстовых преобразований;
- не был заменён во время чтения;
- точно соответствует `manifest.patch_sha256`.

V1B должен сформировать immutable snapshot проверенных байтов patch. Именно эти байты будут передаваться следующим preflight-слоям.

---

## 8. In scope — V1B

- Принимать уже валидированный `DeveloperTaskManifest`.
- Принимать успешный `DeveloperTaskRepositoryPreflightReport` из V1A.
- Проверять согласованность repository report и manifest fingerprint.
- Получать `task_root` явно как `pathlib.Path`.
- Требовать, чтобы `task_root` существовал и являлся каталогом.
- Отклонять symlink, junction и Windows reparse point для `task_root`.
- Требовать, чтобы `task_root` и project repository были непересекающимися деревьями.
- Разрешать только валидированное basename-имя patch с расширением `.patch`.
- Отклонять отсутствующий patch.
- Отклонять symlink/reparse point для patch-файла.
- Требовать обычный файл.
- Отклонять пустой patch.
- Ограничивать размер patch значением V1: `5 MiB`.
- Читать patch в бинарном режиме в immutable `bytes`.
- Сравнивать metadata до открытия, после открытия и после чтения.
- Обнаруживать подмену или изменение файла во время чтения.
- Вычислять SHA-256 именно от прочитанных байтов.
- Сравнивать hash с `manifest.patch_sha256`.
- Не включать patch bytes в `repr` и `to_dict()`.
- Возвращать immutable структурированный report со стабильными issue codes.

---

## 9. Out of scope — V1B

- `git apply` и `git apply --check`.
- Разбор затронутых путей.
- Проверка `manifest.allowed_files`.
- Анализ rename/copy/delete/add.
- Анализ Git file modes `120000` и `160000`.
- Создание disposable Git index.
- Изменение реального Git index или worktree.
- Создание isolated worktree.
- Запуск manifest checks.
- Установка зависимостей.
- Commit, merge, promotion или push результата developer-task.

Эти обязанности остаются V1C, V1D и последующим этапам Developer Safety Kernel.

---

## 10. Принятый API V1B

Файл:

```text
modules/developer/developer_task_patch_integrity.py
```

Публичная функция:

```python
run_developer_task_patch_integrity_preflight(
    manifest: DeveloperTaskManifest,
    *,
    repository_report: DeveloperTaskRepositoryPreflightReport,
    task_root: Path,
) -> DeveloperTaskPatchIntegrityPreflightReport
```

Публичные immutable-типы:

```python
DeveloperTaskPatchSnapshot
DeveloperTaskPatchIntegrityPreflightReport
```

Snapshot содержит:

```text
path
size_bytes
sha256
content: bytes
```

`content` исключается из `repr` и сериализованного `to_dict()`.

---

## 11. Ожидаемые файлы V1B

```text
A  modules/developer/developer_task_patch_integrity.py
A  tools/eval_developer_task_patch_integrity.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Не должны изменяться:

```text
modules/developer/developer_task_contract.py
modules/developer/developer_task_validator.py
modules/developer/developer_task_preflight.py
main.py
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
```

---

## 12. Threat model V1B

V1B обязан безопасно отклонять как минимум:

- неуспешный или внутренне противоречивый V1A-report;
- report от другого manifest;
- отсутствующий `task_root`;
- `task_root`, являющийся файлом;
- `task_root` через symlink, junction или reparse point;
- `task_root` внутри project repository;
- project repository внутри `task_root`;
- небезопасное имя patch;
- отсутствующий patch;
- patch-каталог или другой не regular file;
- patch через symlink/reparse point;
- пустой patch;
- patch больше `5 MiB`;
- ошибку чтения metadata;
- ошибку открытия;
- ошибку бинарного чтения;
- замену patch между `lstat` и `open`;
- изменение patch во время чтения;
- несовпадение SHA-256;
- случайное попадание patch bytes в JSON/report logs.

---

## 13. PLANNED — targeted checks V1B

Порядок запуска из корня проекта:

```powershell
python -m py_compile `
    .\modules\developer\developer_task_patch_integrity.py `
    .\tools\eval_developer_task_patch_integrity.py `
    .\tools\eval_package_boundaries.py `
    .\tools\pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python -m tools.eval_developer_task_patch_integrity
python tools/pipeline.py developer_task_preflight
python tools/pipeline.py check
```

Ожидаемый targeted результат нового eval:

```text
case_count: 28
fail_count: 0
```

---

## 14. Критерии завершения V1B

- Production-модуль и eval добавлены только в утверждённые пути.
- Package boundaries включают новый developer-модуль и исключают legacy-путь.
- Pipeline включает новый eval в targeted flow и полный `check`.
- Patch snapshot immutable.
- Patch bytes не выводятся через `repr` или `to_dict()`.
- Все позитивные и негативные V1B-кейсы проходят.
- Старые contract и V1A eval продолжают проходить.
- `git diff --check` пуст.
- Targeted flow проходит.
- Полный `check` проходит.
- Commit содержит только четыре файла V1B.
- После commit рабочее дерево чистое и `origin/main` синхронизирован.

Предлагаемое имя commit:

```text
feat: add developer task patch integrity preflight
```

---

## 15. Запрещённые скрытые изменения

- Нельзя расширять V1B до patch scope analysis.
- Нельзя применять patch к project worktree.
- Нельзя добавлять automatic patch installation.
- Нельзя менять manifest schema без доказанного пробела и Roadmap Change.
- Нельзя переносить несвязанные production- или tool-файлы.
- Нельзя переносить `skynet-runtime-foundation-v1` с `09f8708`.
- Нельзя считать зелёный полный pipeline доказательством поведения без targeted eval.
- Нельзя передавать будущему Git-анализатору повторно прочитанный файл вместо snapshot bytes из V1B.

---

## 16. UNVERIFIED — открытые вопросы

- Полный SHA текущего HEAD нужно брать из Git при формировании следующего handoff.
- Поведение Windows junction/reparse-point должно быть подтверждено на реальной Windows-машине targeted eval.
- Runtime-размещение task artifacts окончательно не зафиксировано; текущая безопасная модель требует `task_root` вне repository tree.
- Ограничение `5 MiB` утверждено для V1, но может быть изменено только отдельным осознанным решением и тестами.
- V1C ещё должен доказать, что проверенные байты patch затрагивают только разрешённые пути и безопасные Git file modes.

---

## 17. DEFERRED

- Developer Task Preflight V1C — Patch Scope Gate.
- Developer Task Preflight V1D — Applicability and Audit.
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

## 18. Next Exact Action

1. Заменить `docs/architecture/SKYNETVS_CURRENT_STATE.md` этим обновлённым содержимым.
2. Проверить документационный diff.
3. Создать отдельный documentation commit:

```text
docs: update SkynetVS state after repository preflight
```

4. Отправить documentation commit в `origin/main`.
5. Убедиться, что рабочее дерево чистое.
6. Проверить SHA-256 подготовленного V1B patch.
7. Выполнить `git apply --check`.
8. Применить V1B patch.
9. Запустить targeted checks.
10. Только после targeted checks запускать полный `check`.

---

## 19. Следующие действия после Next Exact Action

1. Зафиксировать V1B отдельным commit `feat: add developer task patch integrity preflight`.
2. Обновить этот current-state файл: V1B → `VERIFIED`, V1C → текущий этап.
3. Спроектировать disposable-index анализ для V1C на Pro Standard.
4. Реализовать извлечение patch scope средствами Git без самописного parser заголовков.
5. Проверить `allowed_files`, casefold collision, symlink mode `120000` и gitlink mode `160000`.

---

## 20. Рекомендованный режим модели

- Текущий V1B threat model и Windows filesystem boundary: `Pro Standard`.
- Механическое применение уже утверждённого V1B patch и обычные проверки: допустим режим `Очень высокий`.
- Проектирование V1C disposable-index scope analysis: `Pro Standard`.

---

## 21. Файлы для нового чата

Всегда прикладывать:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Для текущего этапа дополнительно прикладывать:

```text
modules/developer/developer_task_preflight.py
modules/developer/developer_task_patch_integrity.py
tools/eval_developer_task_preflight.py
tools/eval_developer_task_patch_integrity.py
tools/eval_package_boundaries.py
tools/pipeline.py
последний targeted pipeline log
последний *_check.log
```

---

## 22. Стартовый текст нового чата

```text
Продолжаем разработку SkynetVS.

Прочитай полностью приложенные SKYNETVS_ARCHITECTURE_ROADMAP_V1.md и SKYNETVS_CURRENT_STATE.md. Git, текущий код и последние проверки имеют приоритет над документами; CURRENT_STATE имеет приоритет над roadmap для текущей точки.

Не восстанавливай план по памяти, не расширяй scope без Roadmap Change и не объявляй PLANNED или UNVERIFIED завершённым.

Сначала кратко назови подтверждённую базу, текущий этап, его in scope/out of scope и Next Exact Action. Затем продолжай именно с Next Exact Action.
```
