# Source119 V4 — focused review, новый основной чат C02 / сообщение #3

Номер поставки 119 продолжает Source118; это НЕ сообщение #119 нового чата.
Последняя ревизия: Source119 V4, 32 source-файла, source-only / NOT APPLIED.

Исправлены три конкретных source-стыка. Guest byte-loader явно импортирует
benign_capsule и benign_layout до возврата entry, через уже установленный проверенный
finder. Pure _parse_initial_worker_frame проверяет initial run_id до worker byte-loader
и native process observation; прежний последующий recheck сохраняется. Лимит одного
source-файла в NativeContextSpec теперь 262144, как в ingress/first-loader; лимит
интерпретатора отдельный и не менялся.

Состав suite: 64 baseline + REG01–REG92 = 156 методов. Все прежние 140 методов
сохранены по AST, добавлены 16. Итоговые результаты и exact-source diff находятся во
внешнем Review119. Новая eager-import проверка анализирует только AST: наличие файла
в capsule больше не подменяется утверждением, что модуль уже находится в sys.modules.
Actual guest/byte-loader/PowerShell не исполняются, native API не вызываются.

Внешний offline harness требует `-I -S -B`: без site initialization и записи pyc.
Это условия доверенной test phase, не OS sandbox и не Windows/runtime acceptance.
Public gates и оба process-local issuer остаются always-deny. Нового issuer здесь нет.
Git apply/commit/push, Windows native smoke, Sandbox, guest, SCM/Guard/install/ACL и
enrollment не разрешены. Scope acceptance остаётся OPEN по native/local admission.

Далее дословно сохранены предыдущие README-разделы Source118/117 как история;
указанные там старые номера тестов относятся к тем ревизиям, не к V4.

---

# SCM01-WSB01-BEN01 — Source118 V3 (source-only)

**Статус:** подготовленный кандидат; 32 файла; public gates CLOSED / 92.
Подготовка разрешена пользователем в #116 (scope #115). Эта ревизия не применена
к его репозиторию. Ни native smoke, ни Windows Sandbox/guest/SCM/Guard не разрешены.

## Что добавлено в #118

Worker получает отдельный `BEN01_WORKER_INGRESS_V1`: exact context, source rows,
interpreter pin и identity собственного child. Envelope — данные, НЕ permit.
Parent требует INIT/ACK до попытки запуска Sandbox; затем отдельный BIND seq1.
Повтор, неверный hash, чужая identity или поздний ACK останавливают подготовку.
Первые два sequence зарезервированы INIT и BIND. Обработчик артефактов не принимает
INIT/BIND как рабочую команду; существующий JSON request/ready/terminal wire не менялся.

`_worker_first_process()` содержит закрытый source-маршрут чтения собственных inherited
stdin/stdout pipe handles, bounded INIT, exact ten-module byte graph, проверки собственного
process identity и передачи в `serve_native_worker()`. В нём нет argv выбора handle,
команды или кода. Parent удерживает проверенные source/interpreter handles через launch.
Первый worker script — часть этого pinned source, не универсальная loader service.

Guest bootstrap задаёт ровно четыре positional data arguments: run_id, request SHA,
capsule SHA, bootstrap SHA. `_guest_first_process()` содержит source чтения фиксированных
локальных путей, проверки retained runtime, восьми source members, byte-loader и вызова
`main_fixed_guest(..., loader_plan=plan)`. Plan не хранится внутри/не заменяет permit.
Bootstrap и guest CLI по-прежнему завершаются CLOSED / 92 до этих действий.

## Не путать с runtime admission

Локальные `_require_local_worker_ingress` и `_require_local_guest_ingress` всегда
отказывают. Issuer в каждом новом процессе намеренно отсутствует. Объект из parent
нельзя переносить в child как opaque Python permit; ни JSON, ни hashes, ни argv его
не создают. Для будущего запуска потребуется отдельный reviewed issuer/entry routing
с конкретным одноразовым разрешением. Просто удалить `exit 92` запрещено и недостаточно.

Native/guest-маршруты пока НЕ выполнены. `140/140` относится к host pure/fake/static
suite (64 baseline + REG01–REG76). Guest byte-loader/PS проверены только по source/AST.
Native I/O thread/Windows ABI/CNG/guest import не проверены. WindowsOffline113 относится
к старому 22-file core; его результат не переносится на этот source-кандидат.

Все ограничения `traditional_wsb_logoncommand_v1`, Output RW/untrusted, Job=1 только
для собственного worker, forced=failure, supervisor-incarnation (не OS boot GUID),
отдельных benign/SCM grants сохраняются. Source-only review acceptance ещё OPEN.

## Историческая запись README Source117 (сохранена ниже)

# SCM01-WSB01-BEN01 — Source117 V2, закрытый source-кандидат

Подготовка по архитектуре/scope #115 и разрешению #116. Ровно 32 файла, только вне
пользовательского Git. Source116 V1 сохранён как историческая поставка.

## Что добавлено

Конкретный source для собственной пары parent/ArtifactWorker: удерживаемые process/Job
и pipe handles, фиксированные program pins, проверяемый контекст, completion-framing,
отдельный I/O thread и неблокирующий supervisor mailbox. Decoded IPC data сами по себе
остаются OFFLINE_MODEL. Native parent receipt создаётся только закрытой own-channel
сборкой после проверки собственной worker identity; private CNG/FS seals из JSON
не восстанавливаются. Это доверие к закреплённому собственному процессу, не к полю
producer, не remote attestation и не защита от hostile same-process/admin кода.

Для гостя подготовлены pure byte-plan, проверка AST import closure и standalone
loader source: восемь exact module members, hashes до project imports, импорт
из проверенных bytes без SourceFileLoader/pyc/добавления произвольного sys.path.
В guest subset добавлен уже существующий benign_capsule.py; новых repository paths нет.

## Исправленные сценарии

- Фрагментированный frame собирается до dispatch; EOF/лишний ответ отклоняется.
- Retirement, полученный раньше delayed terminal IPC, не теряется и не заменяет terminal.
- После deadline/sticky failure не допускается дальнейший PUBLISH в том же ходе.
- Ошибка записи PUBLICATION_UNKNOWN не выбрасывается вместо штатного failure outcome; cleanup worker сохраняется.
- Clock source для scan/supervisor единый: time.monotonic_ns.
- Некорректные типы capsule rows отклоняются как ошибки контракта.

## Что остаётся закрытым и непроверенным

Все public runtime/native factories, host/worker/guest entrypoints и PS bootstrap
CLOSED / 92. Live/first-process issuer не реализован. Ни JSON approved=true, ни fake
provider, ни изменение evidence_domain не являются полномочиями.

B116-01: own-worker channel/context/pump source подготовлены, но первый standalone
worker всё ещё выходит 92. Fixed context/channel ingress и permit/entry routing
требуют следующего source review. Native positive admission не исполнялся.
B116-02: byte-loader/context source подготовлены, но bootstrap-to-loader/permit handoff
не принят. Удаление раннего exit не является реализацией handoff.
R116-03: SUPERVISOR_PROCESS_INCARNATION_V1 не заменяет OS boot GUID; supervisor restart
не позволяет resume consumed run. Hypervisor disposal не доказан.

Поэтому scope acceptance остаётся OPEN / REVIEW REQUIRED. Пакет не применять в Git
и не запускать native smoke/Sandbox/guest/SCM/Guard/install/ACL/enrollment.

## Проверки и границы результата

Восьми test-модулям соответствуют 64 baseline cases #115 и REG01–REG44: 108 методов.
Результаты находятся во внешнем DELIVERY_VALIDATION_117.json, не в этом плане.
Native алгоритмы проверяются через fake API. Guest и PS source только читаются и
анализируются статически; они не импортируются и не запускаются.

Отдельный pipe-pump thread и Win32 ABI не исполнялись: unit tests проверяют mailbox,
framing, fake handles/ошибки и source-контракты. Audit hooks — контроль trusted test
process, не OS sandbox. Cancellation request не доказывает завершение I/O; при
неподтверждённом join сохраняется quarantine без закрытия использующихся handles.

Старые 22-file core, SCM01 V1, Guard V3, modules/tools и wire BENIGN_PROTOCOL.json
не изменяются. Retained 37-file runtime не скачивается и его актуальное наличие
не заявляется. Output RW остаётся лабораторным исключением, не дисковой квотой.
