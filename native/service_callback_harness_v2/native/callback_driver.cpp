// Test-only callback bridge, not a Windows service provider. No OS calls or headers.
// Native frames exercise the exact raw callback signatures without loading a DLL.
#if !defined(_WIN32) || !defined(_M_X64)
#error This driver is Windows AMD64 only.
#endif
static_assert(sizeof(void*) == 8, "x64 pointer width");
static_assert(sizeof(unsigned int) == 4, "DWORD width");
using ScbhServiceMain = void (__stdcall *)(unsigned int, void*);
using ScbhHandler = unsigned int (__stdcall *)(unsigned int, unsigned int, void*, void*);
extern "C" __declspec(noinline) unsigned int ScbhInvokeServiceMain(
    void* address, unsigned int argc, void* argv)
{
    if (address == nullptr) return 0;
    volatile unsigned long long sentinel = 0x5343424853564331ULL;
    auto callback = reinterpret_cast<ScbhServiceMain>(address);
    callback(argc, argv);
    return sentinel == 0x5343424853564331ULL ? 0x53564331U : 0;
}
extern "C" __declspec(noinline) unsigned int ScbhInvokeHandler(
    void* address, unsigned int control, unsigned int eventType,
    void* eventData, void* context, unsigned int* output)
{
    if (address == nullptr || output == nullptr) return 0;
    volatile unsigned long long sentinel = 0x5343424843544C31ULL;
    auto callback = reinterpret_cast<ScbhHandler>(address);
    *output = callback(control, eventType, eventData, context);
    return sentinel == 0x5343424843544C31ULL ? 0x43544C31U : 0;
}
