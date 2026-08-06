from __future__ import annotations

"""Deterministic trusted C# payloads for the V1B3C worker-isolation gate."""

import hashlib


WORKER_NATIVE_HELPER_FILE_NAME = "SkynetVS_V1B3C_native_helper.cs"
WORKER_PROBE_SOURCE_FILE_NAME = "SkynetVS_V1B3C_worker_probe.cs"
WORKER_PROBE_EXECUTABLE_FILE_NAME = "SkynetVS_V1B3C_worker_probe.exe"
WORKER_PAYLOAD_ENCODING = "utf-8"


_NATIVE_HELPER_SOURCE = r'''using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;

public sealed class WorkerAccountState
{
    public string UserName;
    public string UserSid;
}

public sealed class WorkerTokenState
{
    public IntPtr TokenHandle;
    public string UserName;
    public string UserSid;
    public int TokenType;
    public bool IsAdministrator;
    public int IntegrityRid;
}

public sealed class WorkerLaunchState
{
    public IntPtr ProcessHandle;
    public IntPtr ThreadHandle;
    public IntPtr JobHandle;
    public int ProcessId;
    public int ThreadId;
    public bool CreatedSuspended;
    public bool AssignedBeforeResume;
    public bool ProcessInJob;
}

public sealed class WorkerProcessSweepState
{
    public int Attempts;
    public int ConsecutiveEmptyScans;
    public int[] MatchingProcessIds;
}

public sealed class WorkerPasswordSecret : IDisposable
{
    private IntPtr buffer;
    private int charCount;

    private WorkerPasswordSecret(IntPtr value, int count)
    {
        buffer = value;
        charCount = count;
    }

    public IntPtr Pointer
    {
        get
        {
            if (buffer == IntPtr.Zero) throw new ObjectDisposedException("WorkerPasswordSecret");
            return buffer;
        }
    }

    public static WorkerPasswordSecret CreateRandom()
    {
        const string upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
        const string lower = "abcdefghijkmnopqrstuvwxyz";
        const string digits = "23456789";
        const string symbols = "!@#$%*-_+=";
        const string all = upper + lower + digits + symbols;
        const int length = 32;

        char[] chars = new char[length];
        byte[] random = new byte[length + 4];
        using (RandomNumberGenerator rng = RandomNumberGenerator.Create())
        {
            rng.GetBytes(random);
        }

        chars[0] = upper[random[0] % upper.Length];
        chars[1] = lower[random[1] % lower.Length];
        chars[2] = digits[random[2] % digits.Length];
        chars[3] = symbols[random[3] % symbols.Length];
        for (int index = 4; index < chars.Length; index++)
        {
            chars[index] = all[random[index] % all.Length];
        }

        IntPtr value = Marshal.AllocHGlobal((length + 1) * 2);
        try
        {
            for (int index = 0; index < length; index++)
            {
                Marshal.WriteInt16(value, index * 2, (short)chars[index]);
            }
            Marshal.WriteInt16(value, length * 2, 0);
            return new WorkerPasswordSecret(value, length);
        }
        catch
        {
            for (int index = 0; index <= length; index++) Marshal.WriteInt16(value, index * 2, 0);
            Marshal.FreeHGlobal(value);
            throw;
        }
        finally
        {
            Array.Clear(chars, 0, chars.Length);
            Array.Clear(random, 0, random.Length);
        }
    }

    private void Clear()
    {
        if (buffer == IntPtr.Zero) return;
        for (int index = 0; index <= charCount; index++) Marshal.WriteInt16(buffer, index * 2, 0);
        Marshal.FreeHGlobal(buffer);
        buffer = IntPtr.Zero;
        charCount = 0;
    }

    public void Dispose()
    {
        Clear();
        GC.SuppressFinalize(this);
    }

    ~WorkerPasswordSecret()
    {
        Clear();
    }
}

public static class V1B3CNative
{
    public const uint USER_PRIV_USER = 1;
    public const uint UF_SCRIPT = 0x0001;
    public const uint UF_PASSWD_CANT_CHANGE = 0x0040;
    public const uint UF_NORMAL_ACCOUNT = 0x0200;
    public const uint UF_DONT_EXPIRE_PASSWD = 0x10000;
    public const uint LOGON32_LOGON_INTERACTIVE = 2;
    public const uint LOGON32_PROVIDER_DEFAULT = 0;
    public const uint CREATE_SUSPENDED = 0x00000004;
    public const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
    public const uint CREATE_DEFAULT_ERROR_MODE = 0x04000000;
    public const uint CREATE_NO_WINDOW = 0x08000000;
    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    public const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
    public const uint TOKEN_QUERY = 0x0008;
    public const int TokenUser = 1;
    public const int TokenType = 8;
    public const int TokenIntegrityLevel = 25;
    public const int TokenPrimary = 1;
    public const int JobObjectExtendedLimitInformation = 9;
    public const uint WAIT_OBJECT_0 = 0;
    public const uint WAIT_TIMEOUT = 258;
    public const uint ERROR_SUCCESS = 0;
    public const uint NERR_USER_EXISTS = 2224;
    public const int ERROR_INSUFFICIENT_BUFFER = 122;
    public const int ERROR_NONE_MAPPED = 1332;
    public const uint WTS_ANY_SESSION = 0xFFFFFFFE;
    public const int WTSTypeProcessInfoLevel1 = 1;
    public const int WORKER_INTEGRITY_RID = 0x2000;
    public const int WORKER_SWEEP_MAX_ATTEMPTS = 8;
    public const int WORKER_SWEEP_DELAY_MS = 250;
    public const int WORKER_SWEEP_REQUIRED_EMPTY_SCANS = 3;
    public const string WORKER_EXECUTABLE_FILE_NAME = "SkynetVS_V1B3C_worker_probe.exe";

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct USER_INFO_1
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_name;
        public IntPtr usri1_password;
        public uint usri1_password_age;
        public uint usri1_priv;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_home_dir;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_comment;
        public uint usri1_flags;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_script_path;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct SECURITY_ATTRIBUTES
    {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        [MarshalAs(UnmanagedType.Bool)] public bool bInheritHandle;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct STARTUPINFO
    {
        public int cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct SID_AND_ATTRIBUTES
    {
        public IntPtr Sid;
        public uint Attributes;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct TOKEN_USER
    {
        public SID_AND_ATTRIBUTES User;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct TOKEN_MANDATORY_LABEL
    {
        public SID_AND_ATTRIBUTES Label;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct WTS_PROCESS_INFO_EXW
    {
        public uint SessionId;
        public uint ProcessId;
        public IntPtr pProcessName;
        public IntPtr pUserSid;
        public uint NumberOfThreads;
        public uint HandleCount;
        public uint PagefileUsage;
        public uint PeakPagefileUsage;
        public uint WorkingSetSize;
        public uint PeakWorkingSetSize;
        public long UserTime;
        public long KernelTime;
    }

    private enum SID_NAME_USE
    {
        SidTypeUser = 1,
        SidTypeGroup,
        SidTypeDomain,
        SidTypeAlias,
        SidTypeWellKnownGroup,
        SidTypeDeletedAccount,
        SidTypeInvalid,
        SidTypeUnknown,
        SidTypeComputer,
        SidTypeLabel
    }

    [DllImport("Netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetUserAdd(string servername, uint level, ref USER_INFO_1 buf, out uint parm_err);

    [DllImport("Netapi32.dll", CharSet = CharSet.Unicode)]
    private static extern uint NetUserDel(string servername, string username);

    [DllImport("advapi32.dll", EntryPoint = "LogonUserW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool LogonUserW(string username, string domain, IntPtr password, uint logonType, uint logonProvider, out IntPtr token);

    [DllImport("advapi32.dll", EntryPoint = "LookupAccountNameW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool LookupAccountNameW(string systemName, string accountName, IntPtr sid, ref uint sidSize, StringBuilder referencedDomainName, ref uint domainNameSize, out SID_NAME_USE use);

    [DllImport("userenv.dll", SetLastError = true)]
    private static extern bool CreateEnvironmentBlock(out IntPtr environment, IntPtr token, bool inherit);

    [DllImport("userenv.dll", SetLastError = true)]
    private static extern bool DestroyEnvironmentBlock(IntPtr environment);

    [DllImport("advapi32.dll", EntryPoint = "CreateProcessAsUserW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CreateProcessAsUserW(IntPtr token, string applicationName, StringBuilder commandLine, IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles, uint creationFlags, IntPtr environment, string currentDirectory, ref STARTUPINFO startupInfo, out PROCESS_INFORMATION processInformation);

    [DllImport("kernel32.dll", EntryPoint = "CreateJobObjectW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateJobObjectW(IntPtr securityAttributes, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool IsProcessInJob(IntPtr process, IntPtr job, out bool result);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint ResumeThread(IntPtr thread);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool TerminateProcess(IntPtr process, uint exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateEvent(ref SECURITY_ATTRIBUTES attributes, bool manualReset, bool initialState, string name);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(IntPtr tokenHandle, int tokenInformationClass, IntPtr tokenInformation, int tokenInformationLength, out int returnLength);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool ConvertSidToStringSid(IntPtr sid, out IntPtr stringSid);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthority(IntPtr sid, uint subAuthority);

    [DllImport("Wtsapi32.dll", EntryPoint = "WTSEnumerateProcessesExW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool WTSEnumerateProcessesExW(IntPtr server, ref uint level, uint sessionId, out IntPtr processInfo, out uint count);

    [DllImport("Wtsapi32.dll", EntryPoint = "WTSFreeMemoryExW", SetLastError = true)]
    private static extern bool WTSFreeMemoryExW(int typeClass, IntPtr memory, uint count);

    public static string BuildWorkerUserName(string requestId)
    {
        if (!IsLowerHex(requestId, 32)) throw new ArgumentException("requestId must be 32 lowercase hexadecimal characters.", "requestId");
        return "svb3c" + requestId.Substring(0, 12);
    }

    public static WorkerTokenState CreateFreshStandardUserAndLogon(string username)
    {
        ValidateWorkerUserName(username);
        if (ResolveLocalAccountSidOrNull(username) != null) throw new InvalidOperationException("Worker account already exists.");

        string createdSid = null;
        using (WorkerPasswordSecret password = WorkerPasswordSecret.CreateRandom())
        {
            USER_INFO_1 info = new USER_INFO_1();
            info.usri1_name = username;
            info.usri1_password = password.Pointer;
            info.usri1_priv = USER_PRIV_USER;
            info.usri1_comment = "SkynetVS V1B3C benign worker";
            info.usri1_flags = UF_SCRIPT | UF_DONT_EXPIRE_PASSWD | UF_PASSWD_CANT_CHANGE | UF_NORMAL_ACCOUNT;
            uint parameterError;
            uint status = NetUserAdd(null, 1, ref info, out parameterError);
            if (status == NERR_USER_EXISTS) throw new InvalidOperationException("Worker account collision detected.");
            if (status != ERROR_SUCCESS) throw new Win32Exception((int)status, "NetUserAdd failed.");

            createdSid = ResolveLocalAccountSidOrNull(username);
            if (String.IsNullOrEmpty(createdSid))
            {
                NetUserDel(null, username);
                throw new InvalidOperationException("Created worker account SID could not be resolved.");
            }

            try
            {
                IntPtr token;
                if (!LogonUserW(username, ".", password.Pointer, LOGON32_LOGON_INTERACTIVE, LOGON32_PROVIDER_DEFAULT, out token))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "LogonUserW failed.");
                }

                try
                {
                    string tokenSid = GetTokenUserSid(token);
                    int tokenType = GetTokenType(token);
                    int integrityRid = GetTokenIntegrityRid(token);
                    bool administrator = IsTokenAdministrator(token);

                    if (!String.Equals(tokenSid, createdSid, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Worker token SID does not match the created account SID.");
                    if (tokenType != TokenPrimary) throw new InvalidOperationException("Worker logon did not return a primary token.");
                    if (administrator) throw new InvalidOperationException("Worker token is administrative.");
                    if (integrityRid != WORKER_INTEGRITY_RID) throw new InvalidOperationException("Worker token integrity is not Medium.");

                    return new WorkerTokenState
                    {
                        TokenHandle = token,
                        UserName = username,
                        UserSid = tokenSid,
                        TokenType = tokenType,
                        IsAdministrator = administrator,
                        IntegrityRid = integrityRid
                    };
                }
                catch
                {
                    CloseHandle(token);
                    throw;
                }
            }
            catch (Exception logonError)
            {
                try
                {
                    DeleteLocalUserExact(username, createdSid);
                }
                catch (Exception cleanupError)
                {
                    throw new InvalidOperationException(
                        "Worker logon failed and exact account cleanup also failed.",
                        new AggregateException(logonError, cleanupError)
                    );
                }
                throw;
            }
        }
    }

    public static void DeleteLocalUserExact(string username, string expectedSid)
    {
        ValidateWorkerUserName(username);
        if (String.IsNullOrEmpty(expectedSid)) throw new ArgumentException("expectedSid is required.", "expectedSid");
        string currentSid = ResolveLocalAccountSidOrNull(username);
        if (currentSid == null) throw new InvalidOperationException("Worker account is missing before exact deletion.");
        if (!String.Equals(currentSid, expectedSid, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Worker account SID changed before deletion.");
        uint status = NetUserDel(null, username);
        if (status != ERROR_SUCCESS) throw new Win32Exception((int)status, "NetUserDel failed.");
        if (ResolveLocalAccountSidOrNull(username) != null) throw new InvalidOperationException("Worker account still resolves after deletion.");
    }

    public static void ProtectControllerPrivateDirectory(string path)
    {
        ApplyProtectedDirectoryAcl(path, null, (FileSystemRights)0);
    }

    public static void PrepareWorkerReadExecuteDirectory(string path, string workerSid)
    {
        ApplyProtectedDirectoryAcl(
            path,
            workerSid,
            FileSystemRights.ReadAndExecute | FileSystemRights.ListDirectory | FileSystemRights.ReadAttributes | FileSystemRights.ReadExtendedAttributes | FileSystemRights.ReadPermissions
        );
    }

    public static void PrepareWorkerResultDirectory(string path, string workerSid)
    {
        ApplyProtectedDirectoryAcl(
            path,
            workerSid,
            FileSystemRights.Write | FileSystemRights.ReadAttributes | FileSystemRights.ReadPermissions | FileSystemRights.Synchronize
        );
    }

    public static IntPtr CreateInheritableSentinelEvent()
    {
        SECURITY_ATTRIBUTES attributes = new SECURITY_ATTRIBUTES();
        attributes.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
        attributes.bInheritHandle = true;
        IntPtr handle = CreateEvent(ref attributes, false, false, null);
        if (handle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateEvent failed.");
        return handle;
    }

    public static WorkerLaunchState LaunchFixedWorkerSuspendedInJob(
        IntPtr token,
        string workerExecutablePath,
        string workerWorkingDirectory,
        string outputPath,
        string inputRoot,
        string controlRoot,
        string requestId,
        int controllerPid,
        long sentinelHandleValue)
    {
        ValidateFixedWorkerLaunchPaths(workerExecutablePath, workerWorkingDirectory, outputPath, inputRoot, controlRoot);
        if (!IsLowerHex(requestId, 32)) throw new ArgumentException("requestId must be 32 lowercase hexadecimal characters.", "requestId");
        if (controllerPid <= 0) throw new ArgumentOutOfRangeException("controllerPid");
        if (sentinelHandleValue == 0) throw new ArgumentOutOfRangeException("sentinelHandleValue");

        IntPtr environment = IntPtr.Zero;
        if (!CreateEnvironmentBlock(out environment, token, false)) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateEnvironmentBlock failed.");

        IntPtr job = IntPtr.Zero;
        PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
        WorkerLaunchState state = null;
        Exception launchError = null;
        int destroyEnvironmentError = 0;
        try
        {
            job = CreateJobObjectW(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed.");

            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            int limitsSize = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            IntPtr limitsBuffer = Marshal.AllocHGlobal(limitsSize);
            try
            {
                Marshal.StructureToPtr(limits, limitsBuffer, false);
                if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, limitsBuffer, (uint)limitsSize))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "SetInformationJobObject failed.");
                }
            }
            finally
            {
                Marshal.FreeHGlobal(limitsBuffer);
            }

            STARTUPINFO startup = new STARTUPINFO();
            startup.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            uint creationFlags = CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT;
            StringBuilder commandLine = new StringBuilder(BuildFixedWorkerCommandLine(
                workerExecutablePath,
                outputPath,
                inputRoot,
                controlRoot,
                requestId,
                controllerPid,
                sentinelHandleValue
            ));

            if (!CreateProcessAsUserW(
                token,
                workerExecutablePath,
                commandLine,
                IntPtr.Zero,
                IntPtr.Zero,
                false,
                creationFlags,
                environment,
                workerWorkingDirectory,
                ref startup,
                out processInformation))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateProcessAsUserW failed.");
            }

            if (!AssignProcessToJobObject(job, processInformation.hProcess)) throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject failed.");
            bool inJob;
            if (!IsProcessInJob(processInformation.hProcess, job, out inJob)) throw new Win32Exception(Marshal.GetLastWin32Error(), "IsProcessInJob failed.");
            if (!inJob) throw new InvalidOperationException("Worker process is not in the expected Job Object.");

            state = new WorkerLaunchState
            {
                ProcessHandle = processInformation.hProcess,
                ThreadHandle = processInformation.hThread,
                JobHandle = job,
                ProcessId = processInformation.dwProcessId,
                ThreadId = processInformation.dwThreadId,
                CreatedSuspended = true,
                AssignedBeforeResume = true,
                ProcessInJob = true
            };
        }
        catch (Exception error)
        {
            launchError = error;
        }
        finally
        {
            if (environment != IntPtr.Zero && !DestroyEnvironmentBlock(environment)) destroyEnvironmentError = Marshal.GetLastWin32Error();
        }

        if (launchError != null || destroyEnvironmentError != 0)
        {
            if (processInformation.hProcess != IntPtr.Zero)
            {
                TerminateProcess(processInformation.hProcess, 0xEE);
                WaitForSingleObject(processInformation.hProcess, 5000);
            }
            if (processInformation.hThread != IntPtr.Zero) CloseHandle(processInformation.hThread);
            if (processInformation.hProcess != IntPtr.Zero) CloseHandle(processInformation.hProcess);
            if (job != IntPtr.Zero) CloseHandle(job);
            if (launchError != null) throw launchError;
            throw new Win32Exception(destroyEnvironmentError, "DestroyEnvironmentBlock failed.");
        }

        return state;
    }

    public static uint ResumeWorker(IntPtr threadHandle)
    {
        uint previous = ResumeThread(threadHandle);
        if (previous == 0xFFFFFFFF) throw new Win32Exception(Marshal.GetLastWin32Error(), "ResumeThread failed.");
        if (previous != 1) throw new InvalidOperationException("Worker primary thread was not suspended exactly once.");
        return previous;
    }

    public static bool IsPidInSpecificJob(int processId, IntPtr jobHandle)
    {
        IntPtr processHandle = OpenProcessForQuery(processId);
        try
        {
            bool inJob;
            if (!IsProcessInJob(processHandle, jobHandle, out inJob)) throw new Win32Exception(Marshal.GetLastWin32Error(), "IsProcessInJob failed.");
            return inJob;
        }
        finally
        {
            CloseHandle(processHandle);
        }
    }

    public static WorkerProcessSweepState WaitForWorkerSidQuiescence(string expectedSid)
    {
        if (String.IsNullOrEmpty(expectedSid)) throw new ArgumentException("expectedSid is required.", "expectedSid");
        int consecutiveEmpty = 0;
        int[] last = new int[0];
        for (int attempt = 1; attempt <= WORKER_SWEEP_MAX_ATTEMPTS; attempt++)
        {
            last = EnumerateProcessIdsForSidStrict(expectedSid);
            if (last.Length == 0) consecutiveEmpty++;
            else consecutiveEmpty = 0;

            if (consecutiveEmpty >= WORKER_SWEEP_REQUIRED_EMPTY_SCANS)
            {
                return new WorkerProcessSweepState
                {
                    Attempts = attempt,
                    ConsecutiveEmptyScans = consecutiveEmpty,
                    MatchingProcessIds = last
                };
            }

            if (attempt < WORKER_SWEEP_MAX_ATTEMPTS) Thread.Sleep(WORKER_SWEEP_DELAY_MS);
        }

        throw new InvalidOperationException("Worker SID process set did not become quiescent within the bounded sweep window.");
    }

    private static int[] EnumerateProcessIdsForSidStrict(string expectedSid)
    {
        uint level = 1;
        IntPtr processInfo;
        uint count;
        if (!WTSEnumerateProcessesExW(IntPtr.Zero, ref level, WTS_ANY_SESSION, out processInfo, out count))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "WTSEnumerateProcessesExW failed.");
        }
        if (level != 1) throw new InvalidOperationException("WTSEnumerateProcessesExW returned an unexpected information level.");

        List<int> found = new List<int>();
        int freeError = 0;
        try
        {
            int itemSize = Marshal.SizeOf(typeof(WTS_PROCESS_INFO_EXW));
            for (uint index = 0; index < count; index++)
            {
                IntPtr itemPointer = new IntPtr(processInfo.ToInt64() + ((long)index * itemSize));
                WTS_PROCESS_INFO_EXW item = (WTS_PROCESS_INFO_EXW)Marshal.PtrToStructure(itemPointer, typeof(WTS_PROCESS_INFO_EXW));
                if (item.pUserSid == IntPtr.Zero) continue;
                string processSid = SidToString(item.pUserSid);
                if (String.Equals(processSid, expectedSid, StringComparison.OrdinalIgnoreCase)) found.Add((int)item.ProcessId);
            }
        }
        finally
        {
            if (processInfo != IntPtr.Zero && !WTSFreeMemoryExW(WTSTypeProcessInfoLevel1, processInfo, count)) freeError = Marshal.GetLastWin32Error();
        }
        if (freeError != 0) throw new Win32Exception(freeError, "WTSFreeMemoryExW failed.");
        return found.ToArray();
    }

    private static IntPtr OpenProcessForQuery(int processId)
    {
        IntPtr handle = NativeOpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
        if (handle == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "OpenProcess failed.");
        return handle;
    }

    [DllImport("kernel32.dll", EntryPoint = "OpenProcess", SetLastError = true)]
    private static extern IntPtr NativeOpenProcess(uint access, bool inheritHandle, int processId);

    private static string ResolveLocalAccountSidOrNull(string username)
    {
        string accountName = Environment.MachineName + "\\" + username;
        uint sidSize = 0;
        uint domainSize = 0;
        SID_NAME_USE use;
        LookupAccountNameW(null, accountName, IntPtr.Zero, ref sidSize, null, ref domainSize, out use);
        int firstError = Marshal.GetLastWin32Error();
        if (sidSize == 0)
        {
            if (firstError == ERROR_NONE_MAPPED) return null;
            throw new Win32Exception(firstError, "LookupAccountNameW sizing failed.");
        }
        if (firstError != ERROR_INSUFFICIENT_BUFFER && firstError != 0) throw new Win32Exception(firstError, "LookupAccountNameW sizing failed.");

        IntPtr sid = Marshal.AllocHGlobal((int)sidSize);
        try
        {
            StringBuilder domain = domainSize == 0 ? null : new StringBuilder((int)domainSize);
            if (!LookupAccountNameW(null, accountName, sid, ref sidSize, domain, ref domainSize, out use))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "LookupAccountNameW failed.");
            }
            if (use != SID_NAME_USE.SidTypeUser) throw new InvalidOperationException("Worker account name did not resolve to a user SID.");
            return SidToString(sid);
        }
        finally
        {
            Marshal.FreeHGlobal(sid);
        }
    }

    private static string GetTokenUserSid(IntPtr token)
    {
        int length;
        GetTokenInformation(token, TokenUser, IntPtr.Zero, 0, out length);
        if (length <= 0) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(TokenUser) sizing failed.");
        IntPtr buffer = Marshal.AllocHGlobal(length);
        try
        {
            if (!GetTokenInformation(token, TokenUser, buffer, length, out length)) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(TokenUser) failed.");
            TOKEN_USER user = (TOKEN_USER)Marshal.PtrToStructure(buffer, typeof(TOKEN_USER));
            return SidToString(user.User.Sid);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static int GetTokenType(IntPtr token)
    {
        int length;
        IntPtr buffer = Marshal.AllocHGlobal(sizeof(int));
        try
        {
            if (!GetTokenInformation(token, TokenType, buffer, sizeof(int), out length)) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(TokenType) failed.");
            return Marshal.ReadInt32(buffer);
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static int GetTokenIntegrityRid(IntPtr token)
    {
        int length;
        GetTokenInformation(token, TokenIntegrityLevel, IntPtr.Zero, 0, out length);
        if (length <= 0) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(TokenIntegrityLevel) sizing failed.");
        IntPtr buffer = Marshal.AllocHGlobal(length);
        try
        {
            if (!GetTokenInformation(token, TokenIntegrityLevel, buffer, length, out length)) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(TokenIntegrityLevel) failed.");
            TOKEN_MANDATORY_LABEL label = (TOKEN_MANDATORY_LABEL)Marshal.PtrToStructure(buffer, typeof(TOKEN_MANDATORY_LABEL));
            byte count = Marshal.ReadByte(GetSidSubAuthorityCount(label.Label.Sid));
            if (count == 0) throw new InvalidOperationException("Worker token integrity SID has no subauthorities.");
            return Marshal.ReadInt32(GetSidSubAuthority(label.Label.Sid, (uint)(count - 1)));
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }

    private static bool IsTokenAdministrator(IntPtr token)
    {
        using (WindowsIdentity identity = new WindowsIdentity(token))
        {
            WindowsPrincipal principal = new WindowsPrincipal(identity);
            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }
    }

    private static string SidToString(IntPtr sid)
    {
        IntPtr text;
        if (!ConvertSidToStringSid(sid, out text)) throw new Win32Exception(Marshal.GetLastWin32Error(), "ConvertSidToStringSid failed.");
        try
        {
            return Marshal.PtrToStringUni(text);
        }
        finally
        {
            LocalFree(text);
        }
    }

    private static void ApplyProtectedDirectoryAcl(string path, string workerSid, FileSystemRights workerRights)
    {
        if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path)) throw new ArgumentException("Directory path must be absolute.", "path");
        if (!Directory.Exists(path)) throw new DirectoryNotFoundException(path);

        SecurityIdentifier systemSid = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
        DirectorySecurity security = new DirectorySecurity();
        security.SetAccessRuleProtection(true, false);
        security.SetOwner(systemSid);
        security.AddAccessRule(new FileSystemAccessRule(
            systemSid,
            FileSystemRights.FullControl,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
            PropagationFlags.None,
            AccessControlType.Allow
        ));

        if (!String.IsNullOrEmpty(workerSid))
        {
            SecurityIdentifier worker = new SecurityIdentifier(workerSid);
            security.AddAccessRule(new FileSystemAccessRule(
                worker,
                workerRights,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                PropagationFlags.None,
                AccessControlType.Allow
            ));
        }

        Directory.SetAccessControl(path, security);
    }

    private static string BuildFixedWorkerCommandLine(
        string workerExecutablePath,
        string outputPath,
        string inputRoot,
        string controlRoot,
        string requestId,
        int controllerPid,
        long sentinelHandleValue)
    {
        return QuoteArgument(workerExecutablePath) +
            " --output " + QuoteArgument(outputPath) +
            " --input " + QuoteArgument(inputRoot) +
            " --control " + QuoteArgument(controlRoot) +
            " --request-id " + QuoteArgument(requestId) +
            " --controller-pid " + controllerPid.ToString(System.Globalization.CultureInfo.InvariantCulture) +
            " --sentinel-handle " + sentinelHandleValue.ToString(System.Globalization.CultureInfo.InvariantCulture);
    }

    private static string QuoteArgument(string value)
    {
        if (value == null) throw new ArgumentNullException("value");
        StringBuilder quoted = new StringBuilder();
        quoted.Append('"');
        int backslashes = 0;
        foreach (char character in value)
        {
            if (character == '\\')
            {
                backslashes++;
                continue;
            }
            if (character == '"')
            {
                quoted.Append('\\', (backslashes * 2) + 1);
                quoted.Append('"');
                backslashes = 0;
                continue;
            }
            if (backslashes > 0)
            {
                quoted.Append('\\', backslashes);
                backslashes = 0;
            }
            quoted.Append(character);
        }
        if (backslashes > 0) quoted.Append('\\', backslashes * 2);
        quoted.Append('"');
        return quoted.ToString();
    }

    private static void ValidateFixedWorkerLaunchPaths(string workerExecutablePath, string workerWorkingDirectory, string outputPath, string inputRoot, string controlRoot)
    {
        string[] paths = new string[] { workerExecutablePath, workerWorkingDirectory, outputPath, inputRoot, controlRoot };
        foreach (string path in paths)
        {
            if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path)) throw new ArgumentException("Worker launch paths must be absolute.");
        }
        if (!String.Equals(Path.GetFileName(workerExecutablePath), WORKER_EXECUTABLE_FILE_NAME, StringComparison.Ordinal)) throw new InvalidOperationException("Unexpected worker executable file name.");
        if (!String.Equals(Path.GetDirectoryName(workerExecutablePath), workerWorkingDirectory, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Worker executable and working directory are inconsistent.");
    }

    private static void ValidateWorkerUserName(string username)
    {
        if (String.IsNullOrEmpty(username) || username.Length > 20) throw new ArgumentException("Worker username is invalid.", "username");
        foreach (char character in username)
        {
            bool ok = (character >= 'a' && character <= 'z') || (character >= '0' && character <= '9');
            if (!ok) throw new ArgumentException("Worker username contains unsupported characters.", "username");
        }
        if (!username.StartsWith("svb3c", StringComparison.Ordinal)) throw new ArgumentException("Worker username prefix is invalid.", "username");
    }

    private static bool IsLowerHex(string value, int length)
    {
        if (value == null || value.Length != length) return false;
        foreach (char character in value)
        {
            if (!((character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'))) return false;
        }
        return true;
    }
}
'''


_WORKER_PROBE_SOURCE = r'''using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;

internal static class SkynetVSWorkerProbe
{
    private const uint PROCESS_VM_READ = 0x0010;
    private const int TokenIntegrityLevel = 25;

    [StructLayout(LayoutKind.Sequential)]
    private struct TOKEN_MANDATORY_LABEL
    {
        public SID_AND_ATTRIBUTES Label;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SID_AND_ATTRIBUTES
    {
        public IntPtr Sid;
        public uint Attributes;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetHandleInformation(IntPtr hObject, out uint lpdwFlags);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool IsProcessInJob(IntPtr processHandle, IntPtr jobHandle, out bool result);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr processHandle, uint desiredAccess, out IntPtr tokenHandle);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(IntPtr tokenHandle, int tokenInformationClass, IntPtr tokenInformation, int tokenInformationLength, out int returnLength);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthority(IntPtr sid, uint subAuthority);

    private static string Escape(string value)
    {
        if (value == null) return "";
        StringBuilder builder = new StringBuilder();
        foreach (char character in value)
        {
            switch (character)
            {
                case '\\': builder.Append("\\\\"); break;
                case '"': builder.Append("\\\""); break;
                case '\r': builder.Append("\\r"); break;
                case '\n': builder.Append("\\n"); break;
                case '\t': builder.Append("\\t"); break;
                default:
                    if (character < 32) builder.Append("\\u" + ((int)character).ToString("x4"));
                    else builder.Append(character);
                    break;
            }
        }
        return builder.ToString();
    }

    private static string Arg(string[] args, string name)
    {
        for (int index = 0; index + 1 < args.Length; index++)
        {
            if (String.Equals(args[index], name, StringComparison.OrdinalIgnoreCase)) return args[index + 1];
        }
        throw new ArgumentException("Missing argument: " + name);
    }

    private static bool IsAdministrator()
    {
        WindowsPrincipal principal = new WindowsPrincipal(WindowsIdentity.GetCurrent());
        return principal.IsInRole(WindowsBuiltInRole.Administrator);
    }

    private static int IntegrityRid()
    {
        const uint TOKEN_QUERY = 0x0008;
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, out token)) return -1;
        try
        {
            int length;
            GetTokenInformation(token, TokenIntegrityLevel, IntPtr.Zero, 0, out length);
            IntPtr buffer = Marshal.AllocHGlobal(length);
            try
            {
                if (!GetTokenInformation(token, TokenIntegrityLevel, buffer, length, out length)) return -1;
                TOKEN_MANDATORY_LABEL label = (TOKEN_MANDATORY_LABEL)Marshal.PtrToStructure(buffer, typeof(TOKEN_MANDATORY_LABEL));
                byte count = Marshal.ReadByte(GetSidSubAuthorityCount(label.Label.Sid));
                if (count == 0) return -1;
                return Marshal.ReadInt32(GetSidSubAuthority(label.Label.Sid, (uint)(count - 1)));
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        finally
        {
            CloseHandle(token);
        }
    }

    private static bool WriteMustFail(string root, string name)
    {
        string path = Path.Combine(root, name);
        try
        {
            File.WriteAllText(path, "blocked", new UTF8Encoding(false));
            return false;
        }
        catch
        {
            return true;
        }
    }

    private static bool OutputWriteWorks(string root)
    {
        string path = Path.Combine(root, "worker_output_probe_" + Process.GetCurrentProcess().Id.ToString() + ".txt");
        try
        {
            File.WriteAllText(path, "ok", new UTF8Encoding(false));
            return File.Exists(path);
        }
        catch
        {
            return false;
        }
    }

    private static int ChildMain()
    {
        Thread.Sleep(120000);
        return 0;
    }

    private static int WorkerMain(string[] args)
    {
        string outputPath = Arg(args, "--output");
        string inputRoot = Arg(args, "--input");
        string controlRoot = Arg(args, "--control");
        string requestId = Arg(args, "--request-id");
        int controllerPid = Int32.Parse(Arg(args, "--controller-pid"), System.Globalization.CultureInfo.InvariantCulture);
        long sentinelValue = Int64.Parse(Arg(args, "--sentinel-handle"), System.Globalization.CultureInfo.InvariantCulture);

        WindowsIdentity identity = WindowsIdentity.GetCurrent();
        string workerSid = identity.User == null ? "" : identity.User.Value;
        string workerName = identity.Name ?? "";
        bool administrator = IsAdministrator();
        int integrityRid = IntegrityRid();
        bool controllerSecretAbsent = String.IsNullOrEmpty(Environment.GetEnvironmentVariable("SKYNETVS_CONTROLLER_SECRET"));

        uint handleFlags;
        bool sentinelHandleInherited = GetHandleInformation(new IntPtr(sentinelValue), out handleFlags);

        IntPtr controllerHandle = OpenProcess(PROCESS_VM_READ, false, controllerPid);
        bool controllerVmReadBlocked = controllerHandle == IntPtr.Zero;
        if (controllerHandle != IntPtr.Zero) CloseHandle(controllerHandle);

        bool inputWriteBlocked = WriteMustFail(inputRoot, "worker_input_write_probe.txt");
        bool controlWriteBlocked = WriteMustFail(controlRoot, "worker_control_write_probe.txt");
        bool outputWritable = OutputWriteWorks(Path.GetDirectoryName(outputPath));

        bool selfInJob;
        bool selfJobQuery = IsProcessInJob(GetCurrentProcess(), IntPtr.Zero, out selfInJob);

        string executable = Assembly.GetExecutingAssembly().Location;
        ProcessStartInfo childStart = new ProcessStartInfo(executable, "--child");
        childStart.UseShellExecute = false;
        childStart.CreateNoWindow = true;
        childStart.WorkingDirectory = Path.GetDirectoryName(executable);
        Process child = Process.Start(childStart);
        Thread.Sleep(600);
        bool childInJob = false;
        bool childJobQuery = false;
        try
        {
            childJobQuery = IsProcessInJob(child.Handle, IntPtr.Zero, out childInJob);
        }
        catch
        {
        }

        bool overallOk =
            !administrator &&
            integrityRid == 0x2000 &&
            controllerSecretAbsent &&
            !sentinelHandleInherited &&
            controllerVmReadBlocked &&
            inputWriteBlocked &&
            controlWriteBlocked &&
            outputWritable &&
            selfJobQuery && selfInJob &&
            childJobQuery && childInJob &&
            child != null && child.Id > 0;

        string json = "{" +
            "\"schema_version\":1," +
            "\"request_id\":\"" + Escape(requestId) + "\"," +
            "\"worker_sid\":\"" + Escape(workerSid) + "\"," +
            "\"worker_name\":\"" + Escape(workerName) + "\"," +
            "\"worker_is_administrator\":" + (administrator ? "true" : "false") + "," +
            "\"worker_integrity_rid\":" + integrityRid.ToString(System.Globalization.CultureInfo.InvariantCulture) + "," +
            "\"controller_secret_absent\":" + (controllerSecretAbsent ? "true" : "false") + "," +
            "\"sentinel_handle_inherited\":" + (sentinelHandleInherited ? "true" : "false") + "," +
            "\"controller_vm_read_blocked\":" + (controllerVmReadBlocked ? "true" : "false") + "," +
            "\"input_write_blocked\":" + (inputWriteBlocked ? "true" : "false") + "," +
            "\"control_write_blocked\":" + (controlWriteBlocked ? "true" : "false") + "," +
            "\"output_writable\":" + (outputWritable ? "true" : "false") + "," +
            "\"worker_in_job\":" + (selfInJob ? "true" : "false") + "," +
            "\"child_pid\":" + child.Id.ToString(System.Globalization.CultureInfo.InvariantCulture) + "," +
            "\"child_in_job\":" + (childInJob ? "true" : "false") + "," +
            "\"overall_ok\":" + (overallOk ? "true" : "false") +
            "}";

        File.WriteAllText(outputPath, json, new UTF8Encoding(false));
        return overallOk ? 0 : 7;
    }

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length > 0 && String.Equals(args[0], "--child", StringComparison.OrdinalIgnoreCase)) return ChildMain();
            return WorkerMain(args);
        }
        catch (Exception error)
        {
            try
            {
                string outputPath = Arg(args, "--output");
                string json = "{\"schema_version\":1,\"overall_ok\":false,\"error\":\"" + Escape(error.GetType().Name + ": " + error.Message) + "\"}";
                File.WriteAllText(outputPath, json, new UTF8Encoding(false));
            }
            catch
            {
            }
            return 9;
        }
    }
}
'''


def _canonical_source_bytes(source: str) -> bytes:
    if "\r" in source:
        raise RuntimeError("V1B3C payload source must use canonical LF newlines.")
    if not source.endswith("\n"):
        raise RuntimeError("V1B3C payload source must end with one LF newline.")
    return source.encode(WORKER_PAYLOAD_ENCODING)


WORKER_NATIVE_HELPER_BYTES = _canonical_source_bytes(_NATIVE_HELPER_SOURCE)
WORKER_PROBE_SOURCE_BYTES = _canonical_source_bytes(_WORKER_PROBE_SOURCE)
WORKER_NATIVE_HELPER_SHA256 = hashlib.sha256(WORKER_NATIVE_HELPER_BYTES).hexdigest()
WORKER_PROBE_SOURCE_SHA256 = hashlib.sha256(WORKER_PROBE_SOURCE_BYTES).hexdigest()
