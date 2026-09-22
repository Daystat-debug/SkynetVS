# SCM01-WSB01 V1 — CLOSED_CORE / MODEL_ONLY

Scope #105 принят пользователем в сообщении #106. Подготовлены ровно 22 новых файла
вне пользовательского репозитория. Это не запускаемый Windows Sandbox adapter.
Ничего не установлено, не применено к Git и не разрешено для live runtime.

## Ревизия source V2 / review #107

Исправлены две ошибки reducer, найденные после исходных 60/60 тестов #106:
terminal с `MODEL_FAILURE_TRACE_VALID` немедленно устанавливает sticky failure;
valid retirement observation после host deadline сохраняет факт модельного
завершения, но никогда не отменяет failure и не выдаёт успех.
Неизвестное или не привязанное к session завершение по-прежнему не принимается.

Source #106 сохранён как исторический пакет. Wire protocol, policy, все старые
source bindings, gates и список 22 файлов не изменены. Добавлены пять regression
методов (REG17–REG21); результаты проверок находятся во внешнем review #107.
Применение к пользовательскому repository остаётся неразрешённым.

## Выполняемые функции

`parse_message` / `serialize_message` — единый строгий canonical JSON: ASCII-подмножество
UTF-8, ensure_ascii=true, recursive sort_keys=true, compact separators, один LF.
Ограничения проверяются до/при разборе; duplicate keys, float/NaN, bool вместо числа,
лишние поля, нарушение schemas, replay и overflow отклоняются. FrozenMessage хранит
immutable данные; as_dict() возвращает независимую изменяемую копию.

`plan_layout` / `validate_catalog` — исключительно лексический план Input/Runtime/Control
RO и Output RW, проверка предоставленных metadata. Это не проверка native handles,
Windows ACL, реального отсутствия aliases/junctions или права на файловую запись.

`pin_ready_model` / `validate_transcript_model` связывают request, ready, ключ,
authorization-spec, publication-commit, raw journal, terminal и fake подпись по hashes.
Post-retirement snapshot сравнивается с ранее закреплёнными байтами. Fake CryptoObservation
никогда не даёт crypto_verified=true. Публичный ключ проверяется лишь по размеру/заголовку,
не по принадлежности кривой. Реальная ECDSA/CNG отсутствует.

`validate_scm_trace_model` проверяет новый модельный JSONL, а НЕ legacy native SCM01 JSONL.
Обязательны собственный handle identity, prestart/config/status проверки, intent перед
Create/Start/Delete, бюджеты <=1, отсутствие службы после закрытия owned handles.
Сырые 36-byte status буферы декодируются без использования PID как handle.
Config fixture содержит девять буферов по 8192 bytes: raw_hex сохранён полностью.
Config buffers здесь opaque: native pointer decoding/replay не реализуется.
При явном ERROR модель требует FINAL с failure и не разрешает новую SCM mutation.
Это консервативный failure-trace формат; host cleanup моделируется отдельно.

`reduce_model` использует переданные host monotonic ticks, не системные часы.
Возвращает только immutable state и PlannedEffect — данные, не вызываемые действия.
Reservation/launch/publication бюджеты сгорают до моделируемой попытки. Неопределённый
исход, deadline, wrong-order event и forced cleanup оставляют sticky failure.
Тип события retirement не удостоверяет реальную ОС. Нет persistent host ledger.

`adapter_main.main()` всегда печатает `RUNTIME_CLOSED_SOURCE_ONLY` и возвращает 92.
`require_runtime_authority()` всегда бросает RuntimeClosed. Environment/JSON/receipt
не открывают gate; optional native provider и скрытый live fallback отсутствуют.

## Предел результата

Все модельные сообщения/receipts: `OFFLINE_MODEL`. Положительные коды только
`MODEL_BENIGN_TRACE_VALID`, `MODEL_SCM_REFUSAL_TRACE_VALID`, `MODEL_FAILURE_TRACE_VALID`.
Последний означает корректно описанную неудачу, а не успешный эксперимент.
`runtime_authorized=false`, `crypto_verified=false` всегда. Benign содержит нулевые
SCM budgets и не содержит Guard. Это не разрешение даже benign запуска Sandbox.

Нет .wsb/.ps1, процесса/SCM/CNG backend, guest bootstrap, physical Output reader,
копирования Guard, внешней сети, установки, ACL/enrollment или dependency acquisition.
Существующие modules/tools/native SCM01/Guard не импортируются и не изменяются.
Одна недоверенная writable Output mapping сохранена как согласованный lab design;
allowlist/лимиты чтения не являются квотой и не предотвращают malicious disk-fill.

## Offline-тесты в отдельной распакованной копии

Тестируются только новые файлы; не использовать старые Windows evaluators и one-shot пакеты.
Из корня распакованного source ZIP стандартная библиотека Python запускает suite:

```text
python -I -S -B -m unittest discover -s native/scm01_wsb01_adapter_v1/tests -t native -v
```

Команда не требует pip/venv/dependencies. Использовать отдельный каталог вне репозитория.
Не копировать `native/` в рабочий проект до отдельного согласования apply.
Фактические версия Python, платформа, число/перечень тестов и ограничения проверки
приведены в DELIVERY_VALIDATION_107.json внешнего review-пакета.

## Что дальше

Сначала review этих exact source bytes и offline evidence. Затем отдельно согласовать
доставку файлов и обновление двух canonical docs, не расширяя runtime scope.
Windows providers, guest capsule/import topology, настоящая криптография, filesystem
reader/writer, crash-consistent host ledger и concrete session/stop остаются отдельной
интеграцией. Benign и real-SCM потребуют разных новых разрешений. B02/P00 не приняты,
P01 не реализован, acquisition BLOCKED, RC044 не создан.
