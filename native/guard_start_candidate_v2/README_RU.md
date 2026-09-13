# GuardStartCandidate V2 — пять AOT API замен

Source/build-only. Не служба и не production release. Guard.exe НЕ запускать.
V1 source и его NEEDS_REVIEW отчёт не меняются. Общие baseline subtree не меняются.

12 baseline C# + 2 candidate-owned adaptation C# + неизменный CandidateEntryPoint.
См. AOT_MIGRATION.json и .diff: только три Marshal.SizeOf<T>() и два Enum.GetValues<StoreRole>().
Struct layout, NT/Win32 declarations, cleanup/deadline/ownership и factory не меняются.
C# / AOT / linker-warning logs проверяются без NoWarn; warnings запрещают source delivery.

Свой локальный restore в свежем workspace; shared SDK/cache не перезаписываются.
Compile/publish разрешены; исполнение Guard и старых suites, install/SCM/ACL/enrollment — нет.
Даже без warnings semantic_migration_accepted=false, B02/P00 NOT_ACCEPTED, P01 NOT_IMPLEMENTED, acquisition BLOCKED.
