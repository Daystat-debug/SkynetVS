# GuardStartCandidate V1 — source migration / retention review

Основание: LP01 принят пользователем в сообщении #46. Это кандидат для source/build,
не установленный сервис, не P00StartSession и не разрешение исполнения.

## Состав и изменения

14 существующих C# файлов подключены byte-for-byte через явные Compile Include.
Ни один baseline файл не переписывается, не переводится на другой wire format
и не получает новый provenance issuer. Добавлен один CandidateEntryPoint.cs.

| Точный источник | Роль / ограничение |
|---|---|
| `native/trusted_host/src/EpochNativeContracts.cs` | Роли/идентичности, ожидания, ownership; InstalledEpochNativeAdmission остаётся refusing. |
| `native/trusted_host/src/EpochNativeIo.cs` | NtReadFile и unmanaged IOSB/buffers; отсутствие APC callback (нулевые APC/контекст). |
| `native/trusted_host/src/InstallationRegistration.cs` | Реальные canonical JSON и registration codec; Trust.OpenAuthenticated остаётся refusing. |
| `native/trusted_host/src/P00AnchorEpochContracts.cs` | Anchor/state/acceptance codecs и epoch window. SimulatedEnrollment остаётся диагностическим типом, не issuer. |
| `native/trusted_host/src/P00EpochNativeReadTransport.cs` | Точный transport ownership/cleanup. Диагностический native attach не production origin; Main к нему не обращается. |
| `native/trusted_host/src/ParentChainContracts.cs` | Структуры и ограничения parent-chain; без изменения поведения. |
| `native/trusted_host/src/ParentChainNativeApi.cs` | NativeShape layout плюс отключённый legacy NativeChainApi. Старые by-ref декларации не считаются production route. |
| `native/trusted_host/src/ParentChainNtTransport.cs` | Явные unmanaged frames, poison/quarantine, WindowsNtCalls; не изменяется lifetime model. |
| `native/trusted_host/src/SameHandleFileObserver.cs` | Реальные FileFacts/Descriptor и NativeFileApi; диагностический CaptureEngine не entrypoint кандидата. |
| `native/installed_root_v1/InstalledRootContract.cs` | LayoutPlan и интерфейсы; observation не становится authority. |
| `native/installed_root_v1/InstalledRootReadOnly.cs` | Reader retained для migration-analysis; handles закрываются, не источник live authority. |
| `native/installed_root_v1/InstalledRootWindows.cs` | 17 суммарных PInvoke в интеграции включают здесь KnownFolder/current-image/read-only open. Native callbacks не добавлены. |
| `native/live_root_epoch_bridge_v1/LiveRootEpochBridge.cs` | Managed-only aggregate retained для AOT-проверки. ForManagedTests остаётся в baseline, НЕ доступен через Main/CLI; OpenInstalled отказывает. |
| `native/p00_enrollment_expectation_v1/EnrollmentExpectationBoundary.cs` | Закрытый production origin. Условные EE test factories исключены: P00_ENROLLMENT_MANAGED_TESTS не определяется. |

## Что исключено

Старый InstalledRootEntryPoint, GateNativeEntryPoints и вся gate-launch/receiver
группа, RestrictedGateLaunch, managed test suites и BridgeManagedFixture не входят
в Compile inventory. NativeGateLeaseAdapter также исключён: bridge самостоятельно
координирует cleanup; оборачивание адаптером могло бы преждевременно закрыть Gate.

## Entry point и отказ

Параметрless Main вызывает только существующий EnrollmentNativeBridgeFactory.OpenInstalled.
Ожидаемое EnrollmentFailure даёт exit 78; неожиданный возврат любого object/null — 79;
иная ошибка — 80. Нет success branch, чтения argv/env/path/JSON, factory callback,
логирования в файл, service registration/dispatcher, SCM/ACL/enrollment или проб roots.
Сам Guard.exe ни здесь, ни на машине пользователя этим пакетом НЕ запускается.
Это source-level доказательство отказа, не runtime-тест production-процесса.

## Удержание кода

Одна лишь закрытая Main привела бы к удалению большинства проверок при AOT.
TrimmerRootAssembly=Guard намеренно сохраняет весь интегрированный application code
для миграционного анализа. Включены native map/mstat, metadata log и dependency DGML.
В отчёте отдельно сохраняется фактический --root:Guard из ILCompiler response file.
Наличие имён типов в карте — наблюдение, не доказательство корректности всех веток.
Инлайн/генерики/метаданные требуют анализа реальных outputs. Source delivery не
меняет semantic_migration_accepted=false.

В byte-exact baseline остаются отдельные диагностические/test seam методы и
SimulatedEnrollment. Мы НЕ утверждаем, что это готовая минимальная production-поставка.
У них нет пути вызова из текущей Main. Будущая production promotion требует отдельно
проверенного удаления/закрытия таких routes; это не делается скрытой заменой сейчас.

## Interop и загрузка

17 DllImport declarations перечислены с исходниками/строками в INTEROP_INVENTORY.json.
Модули: kernel32.dll, advapi32.dll, ntdll.dll, shell32.dll, ole32.dll.
Новые unmanaged callback или delegate-to-function-pointer не вводятся. Managed
Func/анонимные delegates — только прежняя managed-dispatch логика. NT APC параметры
в фактических call sites нулевые. Struct layout/Marshal paths остаются частью review.

DefaultDllImportSearchPaths не используется как доказательство direct-PInvoke search.
Эффективные DirectPInvoke/DirectPInvokeList и ILC response сохраняются из точной
сборки. Финальные static/delay imports снимаются с Guard.exe без LoadLibrary.
Любая discovered DLL — только inventory, не auto-allowlist. Recursive OS hash sweep,
Authenticode sweep и API-set fallback исключены. Platform trust не принят этим пакетом.

## Проверка сборки

Средства сборки уже существуют в отдельных Downloads roots. Runner проверяет их
manifest и копирует approved NuGet cache в новый workspace. Новый проект делает
свой restore из локального feed, собранного только из семи byte-pinned raw nupkg.
Smoke project.assets.json и его lock не копируются. Создаваемый candidate lock
сверяется с assets/metadata; PackageDownload runtime проверяется отдельно от libraries.
Publish выполняется --no-restore. Runtime/compiler версии не переключаются на latest.

NuGetAudit=false относится только к offline сборке: vulnerability audit не выполнен.
Raw hash pins не заменяют доверенный источник поставки. Сеть не заявляется физически
изолированной: новых network sources не задаётся, но network trace отсутствует.
Никакие сертификаты/правила firewall не устанавливаются.

Финальный PE обязан быть AMD64/PE32+, без CLR, с CFG table/count, ASLR/DEP/CET marking
и DependentLoadFlags=0x0800. Это свойства реального кандидата, не перенос smoke PASS.
Если компилятор вернул предупреждения или map требует разбора, отчёт сохраняет
NEEDS_REVIEW. Предупреждения не подавляются и не превращаются в PASS.

## Не закрыто

B02/P00 NOT_ACCEPTED; P01 NOT_IMPLEMENTED; acquisition BLOCKED. Trusted Windows
platform/pre-entry/service/token/process basis, независимый release enrollment,
B03/B07 и native bridge migration остаются отдельными задачами. Нет новой обязательной PKI.
