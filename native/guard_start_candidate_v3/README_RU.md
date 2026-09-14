# GuardStartCandidate V3 — служебный старт, завершающийся отказом

Это **не готовая служба Guard** и не замена integration baseline V2. Пакет можно только собирать.
Не устанавливать и не запускать Guard.exe; даже ненамеренный запуск вне SCM не разрешается этим пакетом.

V3 содержит настоящие dispatcher/ServiceMain/Handler callback объявления и 3 Win32 P/Invoke.
При гипотетическом запуске через SCM он зарегистрирует handler, отправит START_PENDING, вызовет
исходную отказывающую factory и завершится STOPPED с ненулевым service-specific кодом.
Пути SERVICE_RUNNING, рабочего потока, выдачи seed/ticket, открытия lifecycle или native acquisition нет.

V1/V2 и четыре общих baseline subtree не меняются. Reader/bridge/session и fake providers НЕ компилируются
в этот V3: отсутствующий функционал явно отмечен как неинтегрированный, а не доказанный удалением кода.
Следующие интеграция native bridge и независимый origin остаются отдельной работой.

## Проверки сборки
1. MSVC /c: реальные static_assert из service_abi.cpp против pinned Windows SDK; объект не линкуется/исполняется.
2. Новый локальный restore из 7 pinned nupkg, собственные assets/lock.
3. Native AOT publish --no-restore с warnings-as-errors.
4. PE: CFG/CET/DependentLoadFlags, noCLR, отсутствие delay imports, 3 service symbols ADVAPI32.
5. Native map: service callbacks/реальная refusing factory retained; known test/bridge types отсутствуют.

Source/build PASS НЕ подтверждает регистрацию, порядок callback-исполнения, token/process/SCM origin,
таймауты ОС, runtime ABI или безопасность сервиса. Установка и выполнение требуют отдельного разрешения.
Новый runner создаёт source subtree только после gates; commit/push отдельно.
