# Installed-root candidate reader V1 — новый read-only код

База: опубликованный commit `20c2af947f715b4ff4fb6a5590700639c66c92a2`.
Новые файлы находятся рядом с `native/trusted_host`, а не внутри него:
его исходный checker проверяет точный состав subtree. Поэтому его manifest,
исходники и permanent evidence здесь не изменяются.

## Реализация
`LayoutPlan.FromObservedLocations` задаёт две фиксированные ветви из Windows
Known Folders. `host_release_id` извлекается ТОЛЬКО из native image path
текущего процесса с точной структурой `.../releases/<id>/Guard.exe`.
Нет аргумента для пути/release, переменных среды, чтения candidate Record,
сканирования каталогов или выбора latest. Путь image — locator, НЕ доказательство
того, что по этому пути сейчас находится тот же загруженный образ.

`WindowsRootCalls` реализует SHGetKnownFolderPath (DONT_VERIFY без CREATE),
GetModuleFileNameW, open-existing drive root и relative NtCreateFile через
неизменённые NtOpenFrame/WindowsNtCalls. Each-directory Facts/Device/Security
берутся с открытого handle, сохраняются и сравниваются до обратного cleanup.
Guard.exe открывается только для observation, НЕ запускается и не читается
как DLL/configuration. Metadata/SD stability не означает ACL-policy approval.
Нельзя выдавать JSON или KnownFolder-ответ за независимо принятый P00.

Поддерживаются обычные локальные DOS пути с ASCII компонентами и верхним
регистром drive letter. UNC, extended prefixes, non-ASCII и прочие формы
отклоняются, а не нормализуются догадкой. Это сознательное ограничение V1.
Nt pending/неоднозначное завершение сохраняет frame и запрещает дальнейший
native cleanup до завершения diagnostic-процесса. Deadline и ограничение
операций не обещают прерывания блокированного kernel call.

## Сборка сейчас
Пакет проверки компилирует managed и native targets, запускает ТОЛЬКО 34
новых managed-кейса. Старые suites/fixtures не выполняются. Пять исходников
из `../trusted_host/src` используются с неизменёнными байтами.
Production factories безусловно отказывают. Native entrypoint пока ТОЛЬКО
компилируется: `InstalledRootReadOnly.exe --observe-current-layout`.
Не копировать/переименовывать EXE в Guard.exe ради прохождения layout-проверки.
Настоящий enrollment/store/service не создаются.

Даже ROOT_CANDIDATES_OBSERVED_NOT_ENROLLED не выдаёт live handles/P00.
Для будущего использования roots потребуется независимо принятое enrollment
и отдельное same-owner соединение с epoch-reader; результат после cleanup
нельзя импортировать как доверенный root-pair.
