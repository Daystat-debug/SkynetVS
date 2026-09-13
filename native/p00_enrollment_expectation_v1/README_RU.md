# P00 enrollment expectation — source-only V1

Новая граница между независимым enrollment-вектором и существующим managed bridge.
Это **не enrollment, не P00StartSession и не production producer**.

## Реализовано

`IndependentEnrollmentSeed` сохраняет defensive copy независимого anchor-вектора и
различимых host/anchor/store/gate identities по существующему `DiagnosticEpochExpectation`.
SHA pin означает согласованность данных, а не доверенное происхождение.
`EnrollmentExpectationSession` выдаёт один reference-bound ticket и передаёт ожидание
в неизменённый bridge, сохраняя исходное окно 8000 мс от создания assessment owner.
Повторный/поддельный/чужой ticket, неверный поток, отзыв, clock fault и deadline
не позволяют создать новый период или продолжить dispatch. Экспорт — только detached diagnostic.

Только managed-цель с `P00_ENROLLMENT_MANAGED_TESTS` имеет фабрики тестовых seed/session
и `RunManagedBridge`. В library этих положительных test-seams и векторов нет.
`EnrollmentNativeBridgeFactory.OpenInstalled()` параметров не принимает и всегда отказывает.
Нет подмены существующей native factory, runtime account или доверенного старта.

## Проверки

Только EE001–EE036; старые IR/BR/epoch/gate suites не вызываются.
`BridgeManagedFixture.cs` используется как неизменённый test helper, не test runner.
Векторы EE записаны отдельно в `EnrollmentManagedVectors.cs`: они не читаются из
fixture.Expected, наблюдаемого anchor, registry Record или JSON caller-а.
Метаданные library проверяются через ReflectionOnlyLoadFrom — без исполнения DLL.

## Не реализовано и не разрешено

Нет production runtime/loader closure, принятого SID mode/token/process profile,
реального enrollment/start issuer, native bridge supervision, P00/P01 admission.
Не выполняются install/SCM/ACL/enrollment/provisioning/native execution.
Managed internal/private — не граница против враждебного кода внутри того же процесса.
См. `APPROVED_SCOPE.json`: это запись согласованной задачи, а не импортируемое разрешение.

`P00 NOT_ACCEPTED / P01 NOT_IMPLEMENTED / acquisition BLOCKED`.
