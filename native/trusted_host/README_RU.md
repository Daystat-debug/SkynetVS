# TrustedHost: исходная база, не установленная служба

Статус: SOURCE_BASELINE_ONLY_NOT_INSTALLED. Этот каталог добавлен после native
GateLeaseHandoff V2 b4c54808 и epoch-store fixture d42470b2. Это не новый PASS
runtime и не закрытие V1C3A1B. Положительные результаты относятся только к
маршрутам, перечисленным в исходных отчётах в evidence/.

## Состав и сборка

В src/ лежат 22 уникальных C#-файла с неизменёнными байтами. Общие
SameHandleFileObserver.cs и InstallationRegistration.cs имеют одну копию;
остальные исходники сохраняют исходные namespace и diagnostic entrypoints.
Источники каждого файла указаны в PROVENANCE.json.

BUILD_PLAN.json содержит ЯВНЫЕ списки исходников, а не рекурсивный поиск *.cs.
Два существующих gate diagnostic entrypoints не являются Guard.exe.
Предлагаемый library target epoch-store ранее отдельно не компилировался.
Этот каталог не содержит автоматического build/restore/install/start hook.

`python -I -S -B -X utf8 check_source_baseline.py` только проверяет байты
и точный состав этого каталога. Компиляция, C# suites и native fixtures
не выполняются. SELF-CONSISTENCY_CHECK_ONLY не является security admission;
подпись или доверенный release manifest данным инструментом не создаются.

## Граница интеграции

Не меняются main.py, tools/pipeline.py, requirements.txt, корневой .gitignore
и существующие roadmap/current-state документы. Не вызывается обычный check:
он включает исторические evaluator-ы. Служба SkynetVSGuard, её конфигурация,
Program Files/ProgramData и реестр не создаются и не изменяются.

Scoped .gitattributes запрещает автоматическую смену EOL и filters для этой
копии исходников/evidence. Выходные EXE/DLL/build сюда не входят.
Оригинальные отчёты, ERROR и retained work в Downloads не переносятся и
не удаляются. Копии evidence создаются впервые только внутри нового каталога.

## Следующий implementation boundary

Нужен installed-root resolver и independently approved enrollment/start
контекст. Отсутствие proposed installed directories и service key по
read-only probe не даёт права их автоматически создать. Нельзя выбирать
"последний" release сканированием; host_release_id и начальная policy
не поступают из проверяемого Record или пользовательского запроса.
Production runtime/loader closure и trusted startup ещё не приняты.

Сначала отдельный read-only installed-root entrypoint и его точный контракт
в новом подкаталоге; существующие diagnostic types не переименовываются
в production фабрики. Перед любой установкой или сменой ACL требуется
отдельное явное решение и preflight. Наличие этого каталога не даёт такого
разрешения.

P00 NOT_ACCEPTED; P01 NOT_IMPLEMENTED; V1C3A1B/V1C3A1C NOT OPEN;
RC044 NOT CREATED; acquisition BLOCKED.
