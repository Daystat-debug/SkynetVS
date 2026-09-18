# R05 — принятие 18/18 только для synthetic-provider harness

Зафиксировано по результату сообщения #73. Это отдельная документальная запись, а не изменение существующих baselines или разрешение нового запуска.

## Принятый результат

Run `d0b5c66b01e84fdd99bfef143979d845`: `SCBH001–SCBH018`, 18 процессов / 18 попыток, каждый кейс принят заново. Использован неизменный Harness V2 и неизменный TEST_PLAN; `DETACHED_PROCESS`, job=1. Проверены raw stdout/stderr, ожидаемые ненулевые exit codes, job/handle cleanup, отдельные case-result/case-acceptance и последовательность журнала.

Offline-review сверил 41 член исходного ZIP, 95 членов Review.zip, 8 исходников выполнявшегося runner, 368 raw query buffers, 54 полученных completion packets и 567 записей журнала. Сохранённые данные согласованы; это не независимая аттестация ОС.

Каждый процесс завершился без принудительного TerminateJobObject/TerminateProcess. В каждом итоговом job active=0, total=1; дополнительный PID в собранных данных не обнаружен. stdout всего 12266 байт, stderr=0. Отсутствие дополнительных событий не объявляется полной историей процессов.

## Уровни записи результата

`supervision.case_accepted=false` и `supervision.passed_cases=0` — корректная граница низкоуровневого наблюдателя. CASE PASS ставит внешний orchestrator после успешных trace/exit, cleanup, проверки inputs и сохранения evidence.

В `case-result.json` остаётся `CASE_EVIDENCE_CAPTURED_PENDING_ACCEPTANCE`; в отдельном `case-acceptance.json` — окончательное принятие кейса. Внутренний `runtime-result.json` остаётся `R05_ALL_CASES_VERIFIED_PENDING_FINAL_CAPTURE`, поскольку лежит внутри ещё создававшегося ZIP. Окончательное принятие серии — во внешнем JSON после успешной упаковки. Исторические файлы не переписываются ради выравнивания этих статусов.

SCBH017: exit процесса=81, STOPPED specific_exit=78. Это исходное ожидание, не ошибка.

## Что не закрыто

Проверены callbacks и отказ на закрытой factory в сборке с тестовым ServiceNative provider. Настоящие SCM/service PInvoke, service scheduling, concurrency, token/process trusted start, независимый delivery/enrollment origin, интеграционная миграция Guard V2 и production Guard этим результатом не приняты. Исполнялся Harness V2, а не Guard.exe.

B02/P00 NOT_ACCEPTED; P01 NOT_IMPLEMENTED; acquisition BLOCKED; native factory CLOSED. Нет разрешения install/SCM/ACL/enrollment, изменения аудита или повышения прав. Job не является файловым или сетевым sandbox.

Harness V1 ERROR; R01 ERROR; R02/R03 REVIEW_REQUIRED; R04 DIAGNOSTIC ONLY сохраняются. Guard V1 NEEDS_REVIEW, V2 integration build и V3 service-refusal build не повышаются в production. Одноразовое разрешение #72 использовано; R05 не повторять и не продолжать с середины, markers не удалять.

## Checkpoint и дальнейшая работа

Исходный checkpoint: HEAD `811431d5ffb89faf6a59dacbb768b97aae06f31b`, tree `2007f0c8e02bf05668bf321519279f72f6a7a0f9`, parent `50c9f0786f50c34c5404341f8076916c7add0680`. По before/after R05 он неизменен; нового remote-read review не выполнял.

Этот subtree содержит только пять документов; существующие исходники не изменяются. Следующий Git commit требует отдельного preflight. Дальнейшее source-only проектирование должно адресовать оставшуюся trusted-start/origin boundary, не повторять 18/18 и не представлять успешный harness как доказательство настоящего SCM.

`SOURCE_BINDINGS.json` закрепляет 128 исходных файлов и четыре актуальных evidence-артефакта. Полные оригиналы остаются вне репозитория; их hashes приведены в ACCEPTANCE.json. `CASE_MATRIX.json` содержит компактные фактические наблюдения по всем 18 кейсам.
