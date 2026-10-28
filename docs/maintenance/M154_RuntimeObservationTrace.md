# M154 — наблюдаемость обычного речевого маршрута

## Причина изменения

Аудит v2 в `ee40c46862670b366ec4c582d768fe8f879e5b39` прочитал полный выбранный
runtime log: 22 581 корректная строка, 963 события `nlu` и 0
`learning_observation_unconfirmed`. Эти данные охватывают журнал с несколькими
запусками и не связывают конкретную команду с активной learning epoch. Отсутствие
сообщения об отказе не подтверждает сохранение наблюдения.

`main.handle_phrase_event` раньше сохранял только TTS/ACK времена результата и
терял его `reason`, включая ранний `voice_learning_nlu_error`. У нормального
возврата writer также не было отдельного диагностического события. Причина
исходного нулевого числа current-epoch observations остаётся не установлена.

## Новые события

Один `RuntimeObservationTrace` создаётся внутри `main()` и использует уже
созданный runtime logger. Он не создаёт отдельного файла и не меняет LOG_ENABLE
или LOG_PATH. Случайный `session_id` относится к этому экземпляру main, а
`phrase_sequence` нумерует обработанные им фразы; вложенные вызовы команды и
writer получают тот же контекст. Это локальная корреляция, не удостоверение
источника журнала и не криптографическое подтверждение команды пользователя.
После ordinal `2**31 - 1` дальнейшая диагностика экземпляра отключается:
номер не переиспользуется, основная обработка фразы продолжается.

Все записи используют kind `runtime_observation_trace` и закрытый payload:
`schema`, `session_id`, `phrase_sequence`, `event`, `reason`, `control_state`,
`history_scope`. Существующий logger добавляет обычный timestamp. Новые payload
не содержат текстов фраз, intent, slots, содержимого исключения, event_id истории,
epoch, путей или хешей частных файлов. Неизвестный phrase reason становится
`OTHER`, неизвестная причина RuntimeRefused — `RUNTIME_REFUSED`.

| События | Точная граница |
| --- | --- |
| `SESSION_STARTED` | Trace и LearningMemory созданы после существующих STT/TTS/logger constructors |
| `LOOP_READY` | Достигнута точка перед существующим event-loop try |
| `LOOP_EXITED` | Началось существующее finally event loop; shutdown сервисов ещё не завершён |
| `PHRASE_ENTERED`, `PHRASE_RETURNED`, `PHRASE_RAISED` | Вызов существующего process_phrase и его закрытый итог |
| `COMMAND_ENTERED`, `COMMAND_RETURNED`, `COMMAND_RAISED` | Вызов существующего CommandProcessor.process |
| `OBSERVATION_ATTEMPTED` | Вход в LearningMemory.log_command до writer-lock |
| `OBSERVATION_APPEND_RETURNED` | Append и выход из writer-lock вернулись нормально |
| `OBSERVATION_REFUSED`, `OBSERVATION_RAISED` | Вызов writer завершился RuntimeRefused либо другим Exception; первоначальная ошибка пробрасывается |

`control_state` — уже прочитанное writer значение `ACTIVE`, `PREPARING`,
`LEGACY` либо `UNKNOWN`, если контроль не был успешно прочитан. Callback
вызывается до входа или после выхода из writer-lock, дополнительного I/O под
этим lock нет. Control не перечитывается ради диагностики, epoch не передаётся.

`history_scope` сравнивает normalised absolute spelling фактического base,
заданного main, с project/data/learning в момент создания trace. Значения —
`PROJECT`, `OTHER`, `UNKNOWN`. Это лексическое сравнение без проверки физической
идентичности, симлинков или последующего изменения cwd. Значение base остаётся
`data/learning`; данное изменение не закрепляет его за project root.

## Поведение и ограничения

Диагностический logger и optional writer callback подавляют только собственные
`Exception`. Они не подменяют результат основного вызова, не повторяют его и не
изменяют существующую маршрутизацию. `BaseException`, в том числе KeyboardInterrupt
и SystemExit, не перехватываются как ошибки команды. Исходные writer payload,
возврат `None`, lock/control contract и существующая обработка RuntimeRefused
в CommandProcessor сохранены.

`APPEND_RETURNED` не означает fsync durability, проверку чтением, включение в
ledger, успешное действие или готовность к обучению. История может быть дописана,
а последующий выход из lock либо resolver-candidate write — завершиться ошибкой.
Первый случай не даёт APPEND_RETURNED; второй может дать APPEND_RETURNED и затем
COMMAND_RAISED. Ни один случай не разрешает автоматический retry append.

Отсутствие SESSION_STARTED не исключает импортную/startup/model ошибку до
создания trace. LOOP_EXITED не подтверждает чистый shutdown всего процесса.
Отключённый/неисправный logger, принудительное завершение и частичная запись
могут оставлять неполный trace. Старые события других компонентов не получают
задним числом session_id. Новые события не доказывают версию всех загруженных
модулей; источник и целостность журнала остаются отдельной границей.

## Доставка и следующий шаг

Пакет №103 устанавливает пять исходных/проверочных/документальных файлов,
выполняет согласованные проверки и публикует обезличенный PASS/FAIL в experiment.
Приложение, модели и обучение им не запускаются, настоящие learning data не
изменяются. Main promotion остаётся отложен до завершения блока.

После подтверждённого результата установки будет подготовлен отдельный сбор
нового сеанса. До этого новый голосовой цикл не требуется. Collector должен
оставлять session_id и phrase_sequence в частном контексте, публикуя только
фиксированные счётчики/статусы и явно показывая отсутствие или неоднозначность
сессии. Повтор completed maintenance package не считается новым сбором.

## Ограниченная проверка

`tools/eval_runtime_observation_trace.py` содержит шесть именованных случаев:
реальный synthetic append в LEGACY/PREPARING/ACTIVE с общей корреляцией и
проверкой освобождения lock; ранний VoiceLearningEntryPort NLU error;
RuntimeRefused/другая ошибка/ошибка выхода из lock; отказ диагностических sinks;
закрытая schema; AST composition и loop boundaries main. Два вложенных handler
исполняются отдельно от main с fake processors; runtime writer работает только
с временными synthetic файлами. Приложение, модели, пользовательские данные и
package initializers не импортируются. Эти проверки не являются полным
прогоном проекта и не заменяют последующий обычный запуск на Windows.
