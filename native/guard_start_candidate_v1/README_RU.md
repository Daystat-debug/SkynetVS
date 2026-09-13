# GuardStartCandidate V1

**НЕ УСТАНАВЛИВАТЬ И НЕ ЗАПУСКАТЬ Guard.exe.** Source/build-only по LP01 (сообщение #46).

Состав: 14 byte-exact baseline sources + параметрless closed CandidateEntryPoint.
Детали в MIGRATION_REVIEW_RU.md / SOURCE_ALLOWLIST.json / INTEROP_INVENTORY.json.

Сборка производится только внешним pinned runner в новом Downloads workspace,
с собственным offline restore и lock. `bin/obj/local-feed` не доставляются в репозиторий.
После успешного AOT build + PE checks доставляются только source/config/docs + candidate
packages.lock.json в native/guard_start_candidate_v1. Commit/push отдельным шагом.

Даже status AOT_BUILD_PASS_NOT_PRODUCTION не открывает B02/P00/native factory.
Не запускать csproj вручную через произвольный SDK/IDE и не подменять baseline sources.
