# ServiceCallbackHarness V2 — отдельный тестовый артефакт

## Разрешённый текущий этап

Только source/build-only после checkpoint `50c9f0786f50c34c5404341f8076916c7add0680`.
Собрать C++ callback driver и `ServiceCallbackHarness.exe`, проверить входы и PE,
сохранить исходники и evidence. **Не запускать полученный EXE или Guard.**
Никаких установки, изменения SCM/ACL/enrollment, staging/commit/push.

## Какая логика тестируется

`ServiceEntryPoint.cs` и `OriginRefusal.cs` подключены из зафиксированного V3
байт-в-байт. В том числе private `Main` остаётся настоящим entrypoint сборки.
Не добавляются partial-классы, reflection-доступ, test hooks или положительный origin.
Две структуры из `ServiceNative.cs` извлечены без изменений в `ServiceTypes.cs`.
Производственный класс с тремя ADVAPI32 DllImport **не компилируется**.
Его место занимает test-only класс `ServiceNative` с теми же сигнатурами.

Цепочка будущего теста:

`исходный Main → тестовый dispatcher → статический C++ driver → исходный UCO ServiceMain
→ тестовый registration/status → исходная отказывающая factory → возврат в driver`.

Handler также вызывается через C++ функцию, а не через reflection или managed-вызов
метода с UnmanagedCallersOnly. Это отдельная Native AOT-сборка; она не является
байт-идентичным производственным Guard.exe и не доказывает связь с настоящим SCM.
C++ driver не содержит Windows API, динамической загрузки или обращения к ОС.

## План, не результат исполнения

`TEST_PLAN.json` содержит 18 сценариев. В каждом будущем сценарии нужен свежий
дочерний процесс; исходные static guards не сбрасываются тестовыми обходами.
Harness выбирает только фиксированный case-id `SCBH001`–`SCBH018` из `--case`;
аргументы читает тестовый provider, не исходные callbacks.

Записываются попытки отправки статусов, порядок событий, результаты control codes,
счётчики callback и индикатор прохождения native frame. Trace не печатает PASS.
Отдельный внешний oracle должен сравнить trace и exit code процесса с TEST_PLAN.
Ненулевые коды 78–83 являются ожидаемыми отказами исходного Main, а не ошибками
runner-а сами по себе. Сам по себе ненулевой exit недостаточен: trace обязателен.

Регистрация/START_PENDING/STOPPED покрываются успешным возвратом, false и
инъекцией управляемого исключения в test provider. Проверяются последовательные
повторные callbacks, reentrancy при registration и pending, control matrix и
непрочитанные argc/argv/event-data. `SCBH014` — намеренно неблагоприятная подача
Handler после терминальной попытки; она не объявляется допустимым расписанием SCM.

**Не проверяются:** настоящий ADVAPI32 boundary, SCM routing, service identity,
реальный token/process/pre-entry origin, concurrency, аварийное прекращение процесса
после STOPPED, V2 reader/bridge migration или успешная выдача полномочий.
Не утверждается, что failed/throwing STOPPED был принят реальным SCM: в тесте это
только зарегистрированная попытка.

## Почему build PASS недостаточен

Build-runner не вызывает ни один из 18 сценариев. Он проверяет фактическую сборку,
пять Compile inputs, COFF driver, native map, CFG/CET-compatible marking,
DependentLoadFlags=0x800 и отсутствие настоящих service-imports в PE.
Даже успешное будущее исполнение harness подтверждает только поведение при
synthetic provider и native callback roundtrip — не service/start trust.

`B02/P00 NOT_ACCEPTED; P01 NOT_IMPLEMENTED; acquisition BLOCKED;
native_factory_enabled=false; callback_runtime_accepted=false`.

## Исправление V2

V1 остаётся ERROR (LNK4291), исходники тогда не доставлялись. В V2 меняется
только команда компиляции native driver: добавлен `/guard:ehcont`. Сам драйвер,
все C# файлы, проект, `TEST_PLAN.json` и compile define/trace schema V1 сохранены
байт-в-байт. У NativeAOT linker флаг уже присутствовал; runner отдельно требует
его в фактическом захвате linker inputs и не допускает `/IGNORE:4291`.
Флаг EHCONT в PE не заменяет проверку отсутствия warnings и не доказывает runtime.
V2 имеет отдельный workspace/report и subtree `native/service_callback_harness_v2`.
