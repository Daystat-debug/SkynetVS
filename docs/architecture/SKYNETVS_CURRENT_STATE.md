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

Если источники противоречат друг другу, нельзя молча объединять их. Нужно явно зафиксировать противоречие и отдать приоритет Git, коду и проверкам.

---

## 2. VERIFIED — текущее состояние репозитория

- Ветка: `main`.
- Проверенный code HEAD до следующего documentation update: `cb7c6c5`.
- Название code HEAD: `feat: add developer task patch integrity preflight`.
- `origin/main`: указывает на тот же commit `cb7c6c5`.
- Рабочее дерево после commit и push: чистое; `git status --short` ничего не выводит.
- Стабильный foundation-тег: `skynet-runtime-foundation-v1`.
- Foundation-тег намеренно остаётся на `09f8708` как проверенная runtime-база до завершения Developer Safety Kernel.
- Roadmap находится по каноническому пути:
  - `docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md`.
- Current-state находится по каноническому пути:
  - `docs/architecture/SKYNETVS_CURRENT_STATE.md`.

После коммита этой обновлённой версии файла фактический `HEAD` станет новым documentation commit. Проверенный code commit `cb7c6c5` при этом останется в истории непосредственно под documentation commit. Git остаётся источником истины.

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

Полная доменная раскладка audio, speech, health, reminders, commands и остальных плоских модулей отложена до Domain Package Structure V2.

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

V1A реализует read-only проверку:

- точного корня Git-репозитория;
- non-bare worktree;
- разрешения `HEAD` и `manifest.base_commit` в commit;
- совпадения `HEAD == base_commit`;
- чистоты index и worktree;
- staged, unstaged, untracked, conflict и dirty-submodule состояний;
- нейтрализации унаследованных Git redirection/trace переменных;
- Git timeout, отсутствия Git и ошибки запуска;
- immutable структурированного отчёта со стабильными issue codes.

---

## 6. VERIFIED — Developer Task Preflight V1B

### Patch Integrity Gate

**Статус:** завершён, проверен, закоммичен и отправлен в `origin/main`.

Commit:

```text
cb7c6c5 feat: add developer task patch integrity preflight
```

Предшествующий documentation commit:

```text
fc23db4 docs: update SkynetVS state after repository preflight
```

Состав V1B commit:

```text
A  modules/developer/developer_task_patch_integrity.py
A  tools/eval_developer_task_patch_integrity.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

V1B реализует:

- обязательный успешный V1A-report;
- согласованность manifest fingerprint и repository root;
- отдельный `task_root`, не пересекающийся с project repository;
- запрет symlink, junction и Windows reparse point для `task_root` и patch;
- regular-file validation;
- ограничение patch размером `5 MiB`;
- точное бинарное чтение в immutable `bytes`;
- защиту от подмены между metadata check, `open`, чтением и финальным `fstat`;
- SHA-256 именно прочитанных байтов;
- immutable `DeveloperTaskPatchSnapshot`;
- исключение patch bytes из `repr` и `to_dict()`;
- переносимую file-version проверку без Windows `st_ctime`.

---

## 7. VERIFIED — проверки V1A + V1B

Targeted flow `developer_task_preflight`:

- package boundaries: `28/28`, ошибок `0`;
- developer task contract: `18/18`, ошибок `0`;
- repository preflight V1A: `22/22`, ошибок `0`;
- patch integrity preflight V1B: `29/29`, ошибок `0`;
- финал: `Flow 'developer_task_preflight' completed successfully`.

Полный flow `check`:

- завершён успешно;
- V1A и V1B включены в общий pipeline;
- регрессий в NLU, STT, TTS, audio, reminders, runtime и package boundaries не обнаружено.

Подтверждающие логи:

```text
data/logs/pipeline/20260731_131205_developer_task_preflight.log
data/logs/pipeline/20260731_131222_check.log
```

---

## 8. PLANNED — текущий программный этап

# Developer Task Preflight V1C1 — Isolated Patch Index Gate

**Статус:** архитектурная граница утверждена; патч подготовлен; в проект ещё не применён.

### Уточнение реализации V1C

Изначально V1C рассматривался как один Patch Scope Gate. Прототип успешно прошёл проверки, но получался новым security-монолитом: Git isolation, parsing и allowlist policy находились в одном крупном модуле.

Поэтому утверждённый V1C делится на два последовательных среза без изменения долгосрочного roadmap:

```text
V1C1 — Isolated Patch Index Gate
V1C2 — Patch Scope Policy Gate
```

Это implementation refinement, а не Roadmap Change:

- V1C1 отвечает за безопасное получение фактов средствами Git;
- V1C2 отвечает за применение security policy к уже полученным фактам.

### Почему V1C1 выполняется сейчас

V1B доказал неизменность и SHA-256 patch bytes, но ещё не доказал:

- что эти байты можно безопасно применить к `base_commit`;
- какие пути и Git file modes они меняют;
- что Git-анализ не затронет настоящий index;
- что Git не запишет новые blob-объекты в настоящий object store;
- что rename нормализован до двух write-scope операций;
- что explicit copy не используется как скрытая read-scope операция.

---

## 9. In scope — V1C1

- Принимать уже валидированный `DeveloperTaskManifest`.
- Принимать успешный `DeveloperTaskRepositoryPreflightReport` из V1A.
- Принимать успешный `DeveloperTaskPatchIntegrityPreflightReport` из V1B.
- Повторно проверять fingerprints, repository root и целостность snapshot bytes.
- Получать настоящий Git object directory только read-only командой.
- Создавать отдельный временный каталог вне project repository.
- Отклонять временный каталог, если он является symlink/reparse point или пересекается с project repository.
- Создавать отдельный `GIT_INDEX_FILE`.
- Создавать отдельный `GIT_OBJECT_DIRECTORY`.
- Давать временному object store read-only доступ к baseline objects через `GIT_ALTERNATE_OBJECT_DIRECTORIES`.
- Загружать `base_commit` во временный index через `git read-tree` без обновления worktree.
- Передавать Git только immutable bytes из V1B snapshot через stdin.
- Отклонять explicit Git copy operation.
- Применять patch только к временному index через `git apply --cached`.
- Получать machine-readable raw diff через NUL-delimited Git output.
- Отключать rename detection в итоговом scope-факте, чтобы rename представлялся как `D old + A new`.
- Получать полный resulting index path list через machine-readable `git ls-files --stage -z`.
- Поддерживать SHA-1 и SHA-256 object IDs.
- Поддерживать file modes `100644`, `100755`, `120000`, `160000` как факты для следующего policy gate.
- Отклонять небезопасные repository-relative paths, Windows reserved names и неоднозначный Git output.
- Отклонять patch без resulting changes.
- Структурировать Git timeout, missing Git, launch failure, output failure и cleanup failure.
- Гарантировать, что настоящий worktree, index и object store не изменяются.
- Возвращать immutable report и immutable change records.

---

## 10. Out of scope — V1C1

- Сравнение фактических путей с `manifest.allowed_files`.
- Финальное решение о допустимости rename source/destination.
- Windows case-collision policy для changed paths и resulting index.
- Финальный запрет mode `120000`.
- Финальный запрет mode `160000`.
- Применение patch к настоящему worktree или настоящему index.
- Создание isolated worktree.
- Запуск checks из manifest.
- Установка зависимостей.
- Commit, merge, promotion или push результата developer-task.

Allowlist, case-collision и mode policy входят в V1C2. Финальная applicability/audit boundary остаётся V1D.

---

## 11. Принятый API V1C1

Файл:

```text
modules/developer/developer_task_patch_index.py
```

Публичная функция:

```python
run_developer_task_patch_index_preflight(
    manifest: DeveloperTaskManifest,
    *,
    repository_report: DeveloperTaskRepositoryPreflightReport,
    patch_integrity_report: DeveloperTaskPatchIntegrityPreflightReport,
) -> DeveloperTaskPatchIndexPreflightReport
```

Публичные immutable-типы:

```python
DeveloperTaskPatchIndexChange
DeveloperTaskPatchIndexPreflightReport
```

Report содержит:

```text
manifest_fingerprint
repository_root
base_commit
changed_files
changes
result_index_paths
issues
```

`DeveloperTaskPatchIndexChange` содержит:

```text
path
status
old_mode
new_mode
```

---

## 12. Ожидаемые файлы V1C1

```text
A  modules/developer/developer_task_patch_index.py
A  tools/eval_developer_task_patch_index.py
M  tools/eval_package_boundaries.py
M  tools/pipeline.py
```

Не должны изменяться:

```text
modules/developer/developer_task_contract.py
modules/developer/developer_task_validator.py
modules/developer/developer_task_preflight.py
modules/developer/developer_task_patch_integrity.py
main.py
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
```

---

## 13. Threat model V1C1

V1C1 обязан безопасно отклонять или изолировать как минимум:

- неуспешный или внутренне противоречивый V1A/V1B-report;
- report от другого manifest;
- повреждённый immutable patch snapshot;
- poisoned `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, Git trace и external diff environment;
- Git timeout, отсутствие Git и ошибку запуска;
- неверный object-directory output;
- временный каталог через symlink/reparse point;
- временный каталог внутри repository, равный repository или являющийся его родителем;
- запись новых blobs в настоящий object store;
- изменение настоящего index;
- изменение настоящего worktree;
- explicit copy metadata;
- malformed machine-readable raw diff;
- unsafe Windows path, reserved name, control character и path traversal;
- unsupported Git status или file mode;
- patch без resulting changes;
- failure удаления временного Git state.

---

## 14. PLANNED — targeted checks V1C1

Порядок запуска из корня проекта:

```powershell
python -m py_compile `
    .\modules\developer\developer_task_patch_index.py `
    .\tools\eval_developer_task_patch_index.py `
    .\tools\eval_package_boundaries.py `
    .\tools\pipeline.py

python -m tools.eval_package_boundaries
python -m tools.eval_developer_task_contract
python -m tools.eval_developer_task_preflight
python -m tools.eval_developer_task_patch_integrity
python -m tools.eval_developer_task_patch_index
python tools/pipeline.py developer_task_preflight
python tools/pipeline.py check
```

Ожидаемый результат нового eval:

```text
case_count: 34
fail_count: 0
```

Targeted eval покрывает:

- полную изоляцию index/worktree/object store;
- immutable report/change;
- prerequisite failures;
- manifest fingerprint mismatch;
- snapshot corruption;
- rename как `D + A`;
- explicit copy rejection;
- add/delete;
- executable mode;
- symlink/gitlink mode exposure для V1C2;
- no-op/non-patch payload;
- invalid Git output;
- temp creation/preparation/overlap/cleanup failures;
- Git timeout/missing/launch failures;
- SHA-1/SHA-256 raw records;
- Windows-safe path semantics без опасного Unicode `casefold` expansion.

---

## 15. Критерии завершения V1C1

- Production-модуль и eval добавлены только в утверждённые пути.
- Package boundaries включают новый developer-модуль и исключают legacy-путь.
- Pipeline включает V1C1 в targeted flow и полный `check`.
- V1A/V1B prerequisites повторно проверяются.
- Используются только immutable V1B patch bytes.
- Настоящий index, worktree и object store не изменяются.
- Rename нормализуется до `D + A`.
- Explicit copy отклоняется.
- Git modes и resulting index paths представлены в immutable report.
- `git diff --check` пуст.
- Новый eval проходит `34/34`.
- Старые contract, V1A и V1B eval продолжают проходить.
- Targeted flow проходит.
- Полный `check` проходит.
- Commit содержит только четыре файла V1C1.
- После commit рабочее дерево чистое и `origin/main` синхронизирован.

Предлагаемое имя commit:

```text
feat: add isolated developer task patch index preflight
```

---

## 16. PLANNED — следующий срез V1C2

# Developer Task Preflight V1C2 — Patch Scope Policy Gate

V1C2 будет принимать проверенный V1C1-report и выполнять только policy:

- case-insensitive allowlist comparison с Windows-compatible normalization;
- запрет Unicode `casefold` expansion как способа ошибочно отождествить разные имена;
- обязательное разрешение обеих сторон rename;
- changed-path case collision;
- resulting-index case collision;
- запрет symlink mode `120000`;
- запрет gitlink/submodule mode `160000`;
- immutable scope report;
- отсутствие любых Git write operations.

---

## 17. Запрещённые скрытые изменения

- Нельзя объединять V1C1 и V1C2 обратно в один security-монолит без отдельного решения.
- Нельзя применять patch к project worktree или настоящему index.
- Нельзя разрешать Git писать новые objects в настоящий object store.
- Нельзя повторно читать patch-файл вместо использования snapshot bytes из V1B.
- Нельзя молча разрешать explicit copy.
- Нельзя использовать Python `str.casefold()` как эквивалент Windows filename comparison в V1C2.
- Нельзя менять manifest schema без доказанного пробела и Roadmap Change.
- Нельзя переносить несвязанные production- или tool-файлы.
- Нельзя переносить `skynet-runtime-foundation-v1` с `09f8708`.
- Нельзя считать зелёный полный pipeline доказательством V1C1 без targeted eval.

---

## 18. UNVERIFIED — открытые вопросы

- Фактический SHA нового documentation commit нужно брать напрямую из Git после обновления этого файла.
- V1C1 ещё должен пройти targeted и полный pipeline на реальной Windows-машине пользователя.
- Windows Git должен подтвердить `GIT_ALTERNATE_OBJECT_DIRECTORIES` с путём, содержащим пробелы и Unicode; eval использует task/scratch paths с пробелами и poisoned environment.
- V1C2 policy ещё не реализован.
- V1D ещё должен завершить итоговую applicability и evidence boundary.

---

## 19. DEFERRED

- Developer Task Preflight V1C2 — Patch Scope Policy Gate.
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

## 20. Next Exact Action

1. Заменить `docs/architecture/SKYNETVS_CURRENT_STATE.md` этим обновлённым содержимым.
2. Проверить, что documentation diff затрагивает только current-state файл.
3. Создать отдельный documentation commit:

```text
docs: update SkynetVS state after patch integrity preflight
```

4. Отправить documentation commit в `origin/main`.
5. Убедиться, что рабочее дерево чистое.
6. Проверить SHA-256 подготовленного V1C1 patch.
7. Выполнить `git apply --check`.
8. Применить V1C1 patch.
9. Запустить targeted checks.
10. Только после targeted checks запускать полный `check`.
11. Не создавать V1C1 commit до анализа обоих логов.

---

## 21. Следующие действия после Next Exact Action

1. Зафиксировать V1C1 отдельным commit `feat: add isolated developer task patch index preflight`.
2. Обновить этот current-state файл: V1C1 → `VERIFIED`, V1C2 → текущий этап.
3. Реализовать небольшой pure-policy V1C2 без Git mutation.
4. Провести V1D applicability/evidence audit.
5. Только затем переходить к Developer Task Isolated Workspace V1.

---

## 22. Рекомендованный режим модели

- Проектирование и аудит V1C1/V1C2 Git security boundary: `Pro Standard`.
- Механическое применение уже утверждённого patch и обычные проверки: допустим режим `Очень высокий`.
- До завершения V1C2 пользователь решил остаться на `Pro Standard`.

---

## 23. Файлы для нового чата

Всегда прикладывать:

```text
docs/architecture/SKYNETVS_ARCHITECTURE_ROADMAP_V1.md
docs/architecture/SKYNETVS_CURRENT_STATE.md
```

Для текущего этапа дополнительно прикладывать:

```text
modules/developer/developer_task_preflight.py
modules/developer/developer_task_patch_integrity.py
modules/developer/developer_task_patch_index.py
tools/eval_developer_task_preflight.py
tools/eval_developer_task_patch_integrity.py
tools/eval_developer_task_patch_index.py
tools/eval_package_boundaries.py
tools/pipeline.py
последний targeted pipeline log
последний *_check.log
```

---

## 24. Стартовый текст нового чата

```text
Продолжаем разработку SkynetVS.

Прочитай полностью приложенные SKYNETVS_ARCHITECTURE_ROADMAP_V1.md и SKYNETVS_CURRENT_STATE.md. Git, текущий код и последние проверки имеют приоритет над документами; CURRENT_STATE имеет приоритет над roadmap для текущей точки.

Не восстанавливай план по памяти, не расширяй scope без Roadmap Change и не объявляй PLANNED или UNVERIFIED завершённым.

Сначала кратко назови подтверждённую базу, текущий этап, его in scope/out of scope и Next Exact Action. Затем продолжай именно с Next Exact Action.
```
