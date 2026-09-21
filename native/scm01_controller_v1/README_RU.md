# SCM01 Controller V1 — source/build-only

Основание: согласие сообщения #82 на контракт SCM01 из #81. Этот компонент —
**внешний Python-клиент Win32 SCM**, а не новая служба и не новая AOT-сборка Guard.
C++ используется только для /c-проверки ABI по установленному изолированному SDK.
Отдельный Controller.exe не создаётся. Исходные Guard V3, harness и R05 не изменяются.

## Реализовано

- `scm01_contract.py`: фиксированные имя SkynetVSGuard, virtual account
  NT SERVICE\SkynetVSGuard, pinned Guard V3 и строгий terminal tuple.
- `scm01_engine.py`: однократная последовательность absence → create → config/status
  → start → status polling → owned-handle config/status recheck → delete → close → absence.
- `scm01_native.py`: 10 explicit Win32 bindings с QUERY/CREATE/START/DELETE/READ_CONTROL;
  без ControlService, ChangeServiceConfig, token changes, taskkill и поиска процессов.
  Служба, существовавшая до create, никогда не принимается под управление. Race=1073
  также не разрешает adopt. Ошибка/неизвестный RPC outcome не разрешает повтор.
- `scm01_journal.py`: create-exclusive once marker и append/fsync записи намерения перед
  каждым изменением. Ошибка журнала запрещает дальнейшие изменения. Общий cleanup
  пытается закрыть все известные handles; неизвестный RPC outcome остаётся неизвестным.
- Native API errors хранятся отдельно от результата службы. QueryServiceStatusEx
  возвращает ожидаемый `16/1/0/1066/78/0/0`; RUNNING не подходит. Начальный pending
  не обязателен. PID из status нигде не используется для остановки/атрибуции процесса.
- Native config queries сохраняют raw buffers и pcbBytesNeeded. По Microsoft это поле
  при ERROR_INSUFFICIENT_BUFFER означает требуемый размер; на успехе оно не используется
  как число достоверно возвращённых байтов. Успех с pcbBytesNeeded=0 не отбрасывается.
- Recovery actions/triggers/delayed-autostart проверяются, но не исправляются; defaults
  SID/privileges и raw security descriptor только записываются/сравниваются. Это не
  проверка эффективного token и не доказательство безопасного ACL.

## Runtime закрыт

`controller_main.py` всегда возвращает 92 до импорта native backend.
`runtime_gate.require_runtime_authority` всегда выбрасывает RuntimeClosed, даже для
JSON с approved=true. Обычный конструктор WinScmApi вызывает gate до WinDLL.
Подстановка функции для offline-тестов не является runtime-entrypoint или разрешением.
Это fail-closed поведение текущих исходников, не обещание защиты от их ручной правки.

Намеренно НЕ выданы: runtime capsule/issuer, host-side consumption разрешения,
подготовка конкретной VM, путь и проверка наследованных ACL/доступа service account,
наблюдатель вне гостя и останов/reset. Ни LabCapsule dataclass, ни наличие исходника
CreateService не разрешают выполнение. Build-пакет не импортирует и не запускает
контроллер: только py_compile и cl /c.

## Бюджеты, ещё требующие runtime-согласования для конкретного стенда

CreateServiceW/StartServiceW/DeleteService — по одной попытке, без resume/retry.
Status: 30 с, максимум 301 polling-запрос; отсутствие службы: 10 с, максимум 101 probe;
пауза 0,1 с. Query config/security: фиксированный буфер 8192 байта, без auto-grow/retry.
Индивидуально блокирующий SCM RPC не считается жёстко отменяемым.

Delete разрешён только через retained handle, полученный собственным успешным create,
после повторного config-match и STOPPED. Ошибка первоначальной конфигурации, её drift,
зависшая служба или недоступный журнал оставляют запись для внешнего восстановления
одноразового гостя, а не приводят к удалению по имени. После DeleteService успех
подтверждается только ERROR_SERVICE_DOES_NOT_EXIST=1060 после закрытия service handles.
1072, отказ доступа или timeout — не подтверждение удаления.

Даже чистый будущий terminal/absence результат называется
SCM01_REFUSAL_OBSERVED_PENDING_GUEST_RETIREMENT_NOT_PRODUCTION.
Он не подтверждает natural process exit, выполнение Handler, полную историю переходов,
production origin или восстановление всей VM. Внешнее retirement гостя обязательно.

## Сохранённые границы

R01 ERROR; R02/R03 REVIEW_REQUIRED; R04 DIAGNOSTIC_ONLY;
R05 18/18 SYNTHETIC_PROVIDER_ONLY. B02/P00 NOT_ACCEPTED; P01 NOT_IMPLEMENTED;
acquisition BLOCKED; native factory CLOSED. Исторические suites не повторяются.

При build ERROR сохранить report, Review.zip, once marker, workspace и частичные
исходники. Никакого reset/repair/rerun или ручного запуска controller_main/SCM API.

## Учёт частичных исходов

`mutation_budget_claims` — расход одноразового допуска, не утверждение, что RPC
обязательно выполнился. Факт вызова/результат читается из отдельной записи журнала.
`all_known_scm_handles_closed` относится только к зарегистрированным handles;
неопределённый исход RPC не позволяет объявить все объекты ОС отсутствующими.
Успешный build не разрешает запуск даже closed-entrypoint для runtime-тестирования.
