# GuardStartCandidate V2: ограниченная AOT-миграция

V1 остаётся GUARD_START_CANDIDATE_SOURCE_ADDED_BUILD_CAPTURED_NEEDS_REVIEW.
Причина: ровно 5 IL3050 в реальном publish log, не сбой runner.

## Точный diff

ParentChainNativeApi.cs: NativeShape.Layout — три SizeOf(typeof(concreteType))
заменены на SizeOf<concreteType>(). Определения UnicodeString, ObjectAttributes,
IoStatusBlock и все Marshal.OffsetOf вызовы остаются byte-identical.
Это по-прежнему unmanaged Marshal size, не sizeof/managed size и не числовой hardcode.

LiveRootEpochBridge.cs: Repeat и RoleFor — два Enum.GetValues(typeof(StoreRole))
заменены на Enum.GetValues<StoreRole>(). StoreRole, bodies foreach, collection state,
deadline и порядок cleanup не меняются. Новый API даёт типизированный массив.
Runtime-эквивалентность ещё не тестировалась; compile-only PASS её не подменяет.

## Границы исходников

Полные адаптированные копии находятся только в migration/ кандидата V2.
Проект не компилирует одновременно baseline-копии этих двух типов.
AOT_MIGRATION.json связывает origin SHA256, точные строки/кратности и output SHA256.
Runner воспроизводит byte replacement из локальных pinned baseline sources и сравнивает
с доставляемыми копиями. При любом drift — отказ, без эвристического patch.

Неизменный Main вызывает только закрытую EnrollmentNativeBridgeFactory.OpenInstalled;
exit codes 78/79/80, успеха нет. TrimmerRootAssembly Guard сохранён для migration-analysis.
Оставшиеся diagnostic/test seams в baseline не считаются production API.

## Сборка и evidence

Новый проект выполняет собственный restore только из локальных pinned nupkg.
Общие caches и прежние obj/assets не меняются. Жёсткий compiler warning gate включён
в TreatWarningsAsErrors, IlcTreatWarningsAsErrors, ILLinkTreatWarningsAsErrors; логи тоже проверяются.
Проверки реального AMD64 PE: CFG, CET marking, DEP/ASLR, DependentLoadFlags=0x800, noCLR.
Native map проверяется по MethodCode записям Main, refusing factory и трёх изменённых методов.
Это retention-наблюдение, не проверка их runtime behavior.

## Не делается

Нет Guard execution, historical suites/smokes, recursive OS sweep, enrollment/install/SCM/ACL,
нового signing/PKI, commit/push или принятия B02/P00. Старые ERROR и V1 NEEDS_REVIEW неизменны.
