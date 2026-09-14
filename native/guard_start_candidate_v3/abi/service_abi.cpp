// Compile ONLY (/c). No executable, main, service install, or link step.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <winsvc.h>
#include <cstddef>
#include <type_traits>
static_assert(sizeof(void*) == 8, "x64 only");
static_assert(sizeof(BOOL) == 4 && sizeof(DWORD) == 4 && sizeof(WCHAR) == 2, "Win32 scalar ABI");
static_assert(sizeof(SERVICE_TABLE_ENTRYW) == 16, "service table size");
static_assert(offsetof(SERVICE_TABLE_ENTRYW, lpServiceName) == 0, "name offset");
static_assert(offsetof(SERVICE_TABLE_ENTRYW, lpServiceProc) == 8, "callback offset");
static_assert(sizeof(SERVICE_STATUS) == 28, "service status size");
static_assert(offsetof(SERVICE_STATUS, dwServiceType) == 0, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwCurrentState) == 4, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwControlsAccepted) == 8, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwWin32ExitCode) == 12, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwServiceSpecificExitCode) == 16, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwCheckPoint) == 20, "status offset");
static_assert(offsetof(SERVICE_STATUS, dwWaitHint) == 24, "status offset");
using MainFn = void (WINAPI*)(DWORD, LPWSTR*);
using HandlerFn = DWORD (WINAPI*)(DWORD, DWORD, LPVOID, LPVOID);
using DispatcherFn = BOOL (WINAPI*)(const SERVICE_TABLE_ENTRYW*);
using RegisterFn = SERVICE_STATUS_HANDLE (WINAPI*)(LPCWSTR, LPHANDLER_FUNCTION_EX, LPVOID);
using StatusFn = BOOL (WINAPI*)(SERVICE_STATUS_HANDLE, LPSERVICE_STATUS);
static_assert(std::is_same<MainFn, LPSERVICE_MAIN_FUNCTIONW>::value, "ServiceMain ABI");
static_assert(std::is_same<HandlerFn, LPHANDLER_FUNCTION_EX>::value, "Handler ABI");
static_assert(std::is_same<DispatcherFn, decltype(&StartServiceCtrlDispatcherW)>::value, "dispatcher ABI");
static_assert(std::is_same<RegisterFn, decltype(&RegisterServiceCtrlHandlerExW)>::value, "register ABI");
static_assert(std::is_same<StatusFn, decltype(&SetServiceStatus)>::value, "status ABI");
static_assert(SERVICE_WIN32_OWN_PROCESS == 0x10 && SERVICE_START_PENDING == 2 && SERVICE_STOPPED == 1, "states");
static_assert(ERROR_SERVICE_SPECIFIC_ERROR == 1066 && SERVICE_CONTROL_INTERROGATE == 4 && ERROR_CALL_NOT_IMPLEMENTED == 120, "codes");
