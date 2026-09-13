# LiveRootEpochBridge V1 — SOURCE / MANAGED ONLY

Новый отдельный модуль. `native/trusted_host/` и `native/installed_root_v1/` не изменяются.

`LiveRootEpochBridge.ForManagedTests` получает ОДИН synthetic provider, independent DiagnosticEpochExpectation и clock. Он сам наблюдает fixed layout, удерживает image/ancestor handles и передаёт те же два root handles существующему transport. Он не вызывает InstalledRootReadOnly.Run() и не импортирует его detached observations.

После успешного Attach ledger помечается transferred ДО любых следующих fallible операций. При ошибке конструктора оба root остаются у внешнего владельца. Nested clock не позволяет начинать новые 8 секунд при Attach.

Aggregate непосредственно выполняет диагностическое чтение anchor/gate/state/selected acceptance, bind/recheck и закрытие. NativeGateLeaseAdapter не оборачивается: его самостоятельный cleanup на ошибке нарушил бы агрегатный gate-last порядок. Все reads заканчиваются, пока spine/image живы; затем их handles закрываются в обратном порядке, затем transport закрывает свои семь ролей, Gate последним. Закрытие не является атомарным; ошибка close прекращает оставшийся cleanup и требует завершения диагностического процесса, без retry.

Передача числовых handles и стабильность snapshot проверяются между двумя views; epoch objects не могут alias удерживаемую spine/image. Это managed contract, не Windows security proof. Обе native/installed factories закрыты. No lease/IntPtr/transport escapes via the internal callable surface.

Проверки BR001–BR035 новые. Старые IR/epoch/gate/native suites не вызываются. Fake NT storage использует HGlobal, но не запускает Windows filesystem/native I/O. Quarantine освобождается только test-only методом после завершённого synthetic сценария, без разрешения повторного Run.

P00 NOT_ACCEPTED. P01 NOT_IMPLEMENTED. Acquisition BLOCKED. Внешний Windows supervisor, native attach и independent enrollment/loaded-image attestation этим пакетом не доставлены. Дальнейшая native-интеграция требует отдельного review, не смены флага в CLI.
