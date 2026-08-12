from __future__ import annotations

"""Pinned V1B4B deterministic CPython runtime-bundle policy."""

import hashlib
import json
import zipfile

from dataclasses import dataclass
from typing import Any


RUNTIME_BUNDLE_POLICY_SCHEMA_VERSION = 1
RUNTIME_BUNDLE_POLICY_ID = "skynetvs-v1b4b-deterministic-runtime-bundle-cpython-3.13.15-v1"
RUNTIME_BUNDLE_POLICY_FINGERPRINT = "bc7ae3209f9395aa0186c51e48a1189163c5ee39ee0edb1673734c0a289f05ef"

RUNTIME_SOURCE_ID = "cpython-3.13.15-embed-amd64-official"
RUNTIME_SOURCE_KIND = "cpython_windows_embeddable"
RUNTIME_SOURCE_VERSION = "3.13.15"
RUNTIME_SOURCE_ARCHITECTURE = "AMD64"
RUNTIME_SOURCE_FILE_NAME = "python-3.13.15-embed-amd64.zip"
RUNTIME_SOURCE_SIZE_BYTES = 11_009_825
RUNTIME_SOURCE_SHA256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"
RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT = "232d65ce4fdb9d990e588f15133db3593cb69f31c5d4e3dfece28b79b827c503"
RUNTIME_SOURCE_FINGERPRINT = "6027ca87d35d94fa131d64c8210e5c6f5002f801274752421e480a9a180dba45"

RUNTIME_SOURCE_OUTER_ENTRY_COUNT = 34
RUNTIME_SOURCE_OUTER_TOTAL_BYTES = 21_337_150
RUNTIME_SOURCE_OUTER_MANIFEST_SHA256 = "808b0be8715e1f5d61ef1802010a9d6cab23504a786405d7c490b223c96d3640"
RUNTIME_SOURCE_PTH_SIZE_BYTES = 80
RUNTIME_SOURCE_PTH_SHA256 = "35ddf94682ff9aa713a8d63557242ad00f3f28fdd39337f02c3bda4c0f791577"
RUNTIME_SOURCE_PTH_CRLF_COUNT = 5
RUNTIME_SOURCE_PTH_NORMALIZED_LF_SIZE_BYTES = 75
RUNTIME_SOURCE_PTH_NORMALIZED_LF_SHA256 = "fdfd6b7b1b71a2f702d5cab53dd18857592dc3f1606da750fdd3d14cbbb65f5d"
RUNTIME_SOURCE_STDLIB_SIZE_BYTES = 3_825_631
RUNTIME_SOURCE_STDLIB_SHA256 = "1916abd946d2044ec8c04c3319f96c8415d5b6fce01e125622827f2b7756cbab"
RUNTIME_SOURCE_STDLIB_ENTRY_COUNT = 541
RUNTIME_SOURCE_STDLIB_TOTAL_BYTES = 9_001_540
RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256 = "89066e5e62decc5b0e96b2593e319fbc2338ef3b0e362ac107fa2b117a7480a2"
RUNTIME_SOURCE_PYTHON_EXE_SHA256 = "85b71d8c6ec1905935f74be0c9869aae198d00e98f39df699ec66f9c5a84cecd"
RUNTIME_SOURCE_PYTHON_DLL_SHA256 = "e820bf024efd2b56bb2b82791e6b6ddc7303f070f8e72cba7637482a8a906238"
RUNTIME_SOURCE_PE_FILE_COUNT = 30

RUNTIME_BUNDLE_ID = "v1b4b_cpython_3_13_15_deterministic_runtime_bundle_v1"
RUNTIME_LOCKED_PTH_FILE_NAME = "python313._pth"
RUNTIME_LOCKED_PTH_BYTES = b"python313.zip\r\n.\r\n"
RUNTIME_LOCKED_PTH_SHA256 = "44b7d2b931284d125d88b833eaa28c711504aafd49415bd5bcc7c076a4d18006"
RUNTIME_PROBE_FILE_NAME = "skynetvs_runtime_probe.py"
RUNTIME_PROBE_SHA256 = "33b74a058990ae4f9f0077cb6cbfaa60ad266050d04cf670121d96db929e5c9d"
RUNTIME_RUNNER_FILE_NAME = "skynetvs_runtime_runner.py"
RUNTIME_RUNNER_SHA256 = "d03e21a1867914b87dec61de67bfd0f80637ab5b15948e8d8e6d73839a322de1"
RUNTIME_MANIFEST_FILE_NAME = "runtime_manifest.json"
RUNTIME_LAUNCH_CONTRACT_FINGERPRINT = "8fedb32153b6227a61b699dd5a34d610c430883b4ddafc96f931f0757138cef6"
RUNTIME_BUNDLE_FINGERPRINT = "1c98ad24ec3e4bb1b8b4bcd530ffedcf6ff62a6fee5b94cb795f6c84fb1c8c4b"
RUNTIME_TREE_MANIFEST_SHA256 = "ab35bf73bf387d28cd14bdcf85c545706ae7522212f466bf10afbaf1e14ac7ed"
RUNTIME_MANIFEST_SHA256 = "41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d"
RUNTIME_BUNDLE_FILE_COUNT = 37
RUNTIME_BUNDLE_TOTAL_BYTES = 21346903

MAX_RUNTIME_SOURCE_BYTES = 32 * 1024 * 1024
MAX_RUNTIME_OUTER_ENTRIES = 256
MAX_RUNTIME_OUTER_TOTAL_BYTES = 96 * 1024 * 1024
MAX_RUNTIME_OUTER_ENTRY_BYTES = 48 * 1024 * 1024
MAX_RUNTIME_STDLIB_ENTRIES = 4096
MAX_RUNTIME_STDLIB_TOTAL_BYTES = 128 * 1024 * 1024
MAX_RUNTIME_STDLIB_ENTRY_BYTES = 8 * 1024 * 1024
MAX_RUNTIME_COMPRESSION_RATIO = 250
RUNTIME_ALLOWED_COMPRESSION = (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
RUNTIME_REQUIRED_STDLIB_FILES = ("encodings/__init__.pyc", "importlib/__init__.pyc")
RUNTIME_FORBIDDEN_COMPONENTS = ("ensurepip", "pip", "pip3", "pyvenv.cfg", "scripts", "site-packages")
RUNTIME_APPROVED_STDLIB_PLACEHOLDER = {
    "path": "site-packages/README.txt",
    "size_bytes": 121,
    "sha256": "1c99489111112d2150db0e18bbd474ff45f78fef80fa0e533dfd9ecfc6a3a480",
    "strict_utf8": True,
    "crlf_count": 2,
    "bare_lf_count": 0,
    "bare_cr_count": 0,
    "ends_with_crlf": True,
    "normalized_lf_size_bytes": 119,
    "normalized_lf_sha256": "cba8fece8f62c36306ba27a128f124a257710e41fc619301ee97be93586917cb",
}


_RUNTIME_PROBE_SOURCE = 'from __future__ import annotations\n\n"""Fixed benign V1B4 trusted-runtime probe."""\n\nimport importlib.util\nimport os\nimport platform\nimport struct\nimport sys\n\nfrom pathlib import Path\nfrom typing import Any\n\n\nRUNTIME_PROBE_SCHEMA_VERSION = 1\nRUNTIME_PROBE_ID = "skynetvs-v1b4-runtime-probe-v1"\nRUNTIME_WRITE_TEST_NAME = ".skynetvs_runtime_write_probe"\n\n\ndef _runtime_root_write_blocked(runtime_root: Path) -> tuple[bool, str]:\n    target = runtime_root / RUNTIME_WRITE_TEST_NAME\n    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, "O_BINARY", 0))\n\n    try:\n        descriptor = os.open(target, flags, 0o600)\n    except OSError as exc:\n        return True, f"{type(exc).__name__}:{getattr(exc, \'winerror\', None)}:{getattr(exc, \'errno\', None)}"\n\n    try:\n        os.write(descriptor, b"skynetvs-runtime-write-probe")\n        os.fsync(descriptor)\n    finally:\n        os.close(descriptor)\n\n    try:\n        target.unlink()\n    except OSError:\n        pass\n    return False, ""\n\n\ndef build_runtime_probe_report() -> dict[str, Any]:\n    runtime_root = Path(sys.executable).resolve().parent\n    write_blocked, write_error = _runtime_root_write_blocked(runtime_root)\n    python_environment_keys = [\n        key\n        for key in sorted(os.environ)\n        if key.upper().startswith(("PYTHON", "PIP_")) or key.upper() == "VIRTUAL_ENV"\n    ]\n\n    return {\n        "schema_version": RUNTIME_PROBE_SCHEMA_VERSION,\n        "probe_id": RUNTIME_PROBE_ID,\n        "implementation": platform.python_implementation(),\n        "version_info": list(sys.version_info[:3]),\n        "architecture_bits": struct.calcsize("P") * 8,\n        "machine": platform.machine(),\n        "executable_name": Path(sys.executable).name,\n        "runtime_root_name": runtime_root.name,\n        "flags": {\n            "isolated": sys.flags.isolated,\n            "ignore_environment": sys.flags.ignore_environment,\n            "no_user_site": sys.flags.no_user_site,\n            "safe_path": bool(getattr(sys.flags, "safe_path", False)),\n            "dont_write_bytecode": sys.flags.dont_write_bytecode,\n            "utf8_mode": sys.flags.utf8_mode,\n        },\n        "site_imported": "site" in sys.modules,\n        "sys_path": list(sys.path),\n        "python_environment_keys": python_environment_keys,\n        "pip_available": importlib.util.find_spec("pip") is not None,\n        "ensurepip_available": importlib.util.find_spec("ensurepip") is not None,\n        "runtime_root_write_blocked": write_blocked,\n        "runtime_root_write_error": write_error,\n        "execution_authorized": False,\n    }\n'
_RUNTIME_RUNNER_SOURCE = 'from __future__ import annotations\n\n"""Fixed V1B4 trusted-runtime probe runner."""\n\nimport json\nimport os\n\nfrom pathlib import Path\n\nfrom skynetvs_runtime_probe import build_runtime_probe_report\n\n\nRUNTIME_PROBE_RESULT_FILE_NAME = "skynetvs_runtime_probe_result.json"\n\n\ndef _canonical_json_bytes(value: object) -> bytes:\n    return (\n        json.dumps(\n            value,\n            ensure_ascii=False,\n            sort_keys=True,\n            separators=(",", ":"),\n            allow_nan=False,\n        )\n        + "\\n"\n    ).encode("utf-8")\n\n\ndef main() -> int:\n    result_path = Path.cwd() / RUNTIME_PROBE_RESULT_FILE_NAME\n    payload = build_runtime_probe_report()\n    data = _canonical_json_bytes(payload)\n    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, "O_BINARY", 0))\n    descriptor = os.open(result_path, flags, 0o600)\n\n    try:\n        total = 0\n        while total < len(data):\n            written = os.write(descriptor, data[total:])\n            if written <= 0:\n                raise OSError("runtime probe result write returned zero bytes")\n            total += written\n        os.fsync(descriptor)\n    finally:\n        os.close(descriptor)\n\n    print(\n        json.dumps(\n            {\n                "status": "runtime_probe_completed",\n                "result_file": RUNTIME_PROBE_RESULT_FILE_NAME,\n                "result_size_bytes": len(data),\n                "execution_authorized": False,\n            },\n            ensure_ascii=False,\n            sort_keys=True,\n            separators=(",", ":"),\n            allow_nan=False,\n        )\n    )\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
RUNTIME_PROBE_BYTES = _RUNTIME_PROBE_SOURCE.encode("utf-8")
RUNTIME_RUNNER_BYTES = _RUNTIME_RUNNER_SOURCE.encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskPythonRuntimeSourceFile:
    path: str
    size_bytes: int
    compressed_size: int
    compression: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size_bytes,
            "compressed_size": self.compressed_size,
            "compression": self.compression,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskPythonRuntimePolicy:
    schema_version: int
    policy_id: str
    source_files: tuple[DeveloperTaskPythonRuntimeSourceFile, ...]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.to_dict())).hexdigest()

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == RUNTIME_BUNDLE_POLICY_SCHEMA_VERSION
            and self.policy_id == RUNTIME_BUNDLE_POLICY_ID
            and len(self.source_files) == RUNTIME_SOURCE_OUTER_ENTRY_COUNT
            and self.fingerprint == RUNTIME_BUNDLE_POLICY_FINGERPRINT
            and hashlib.sha256(RUNTIME_LOCKED_PTH_BYTES).hexdigest() == RUNTIME_LOCKED_PTH_SHA256
            and hashlib.sha256(RUNTIME_PROBE_BYTES).hexdigest() == RUNTIME_PROBE_SHA256
            and hashlib.sha256(RUNTIME_RUNNER_BYTES).hexdigest() == RUNTIME_RUNNER_SHA256
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "source": {
                "source_id": RUNTIME_SOURCE_ID,
                "kind": RUNTIME_SOURCE_KIND,
                "version": RUNTIME_SOURCE_VERSION,
                "architecture": RUNTIME_SOURCE_ARCHITECTURE,
                "file_name": RUNTIME_SOURCE_FILE_NAME,
                "size_bytes": RUNTIME_SOURCE_SIZE_BYTES,
                "sha256": RUNTIME_SOURCE_SHA256,
                "provenance_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
                "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
                "outer_entry_count": RUNTIME_SOURCE_OUTER_ENTRY_COUNT,
                "outer_total_uncompressed_bytes": RUNTIME_SOURCE_OUTER_TOTAL_BYTES,
                "outer_manifest_sha256": RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
                "python313_pth_size_bytes": RUNTIME_SOURCE_PTH_SIZE_BYTES,
                "python313_pth_sha256": RUNTIME_SOURCE_PTH_SHA256,
                "python313_pth_crlf_count": RUNTIME_SOURCE_PTH_CRLF_COUNT,
                "python313_pth_normalized_lf_size_bytes": RUNTIME_SOURCE_PTH_NORMALIZED_LF_SIZE_BYTES,
                "python313_pth_normalized_lf_sha256": RUNTIME_SOURCE_PTH_NORMALIZED_LF_SHA256,
                "stdlib_size_bytes": RUNTIME_SOURCE_STDLIB_SIZE_BYTES,
                "stdlib_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
                "stdlib_entry_count": RUNTIME_SOURCE_STDLIB_ENTRY_COUNT,
                "stdlib_total_uncompressed_bytes": RUNTIME_SOURCE_STDLIB_TOTAL_BYTES,
                "stdlib_manifest_sha256": RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
                "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
                "python_dll_sha256": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
                "pe_file_count": RUNTIME_SOURCE_PE_FILE_COUNT,
                "files": [item.to_dict() for item in self.source_files],
            },
            "derived": {
                "bundle_id": RUNTIME_BUNDLE_ID,
                "locked_pth": {
                    "file_name": RUNTIME_LOCKED_PTH_FILE_NAME,
                    "size_bytes": len(RUNTIME_LOCKED_PTH_BYTES),
                    "sha256": RUNTIME_LOCKED_PTH_SHA256,
                    "active_lines": ["python313.zip", "."],
                    "import_site": False,
                },
                "trusted_probe": {
                    "file_name": RUNTIME_PROBE_FILE_NAME,
                    "size_bytes": len(RUNTIME_PROBE_BYTES),
                    "sha256": RUNTIME_PROBE_SHA256,
                },
                "trusted_runner": {
                    "file_name": RUNTIME_RUNNER_FILE_NAME,
                    "size_bytes": len(RUNTIME_RUNNER_BYTES),
                    "sha256": RUNTIME_RUNNER_SHA256,
                },
                "runtime_manifest_file_name": RUNTIME_MANIFEST_FILE_NAME,
                "launch_contract": runtime_launch_contract(),
            },
            "limits": {
                "max_source_bytes": MAX_RUNTIME_SOURCE_BYTES,
                "max_outer_entries": MAX_RUNTIME_OUTER_ENTRIES,
                "max_outer_total_bytes": MAX_RUNTIME_OUTER_TOTAL_BYTES,
                "max_outer_entry_bytes": MAX_RUNTIME_OUTER_ENTRY_BYTES,
                "max_stdlib_entries": MAX_RUNTIME_STDLIB_ENTRIES,
                "max_stdlib_total_bytes": MAX_RUNTIME_STDLIB_TOTAL_BYTES,
                "max_stdlib_entry_bytes": MAX_RUNTIME_STDLIB_ENTRY_BYTES,
                "max_compression_ratio": MAX_RUNTIME_COMPRESSION_RATIO,
            },
            "behavior": {
                "download_during_task": False,
                "dependency_installation": False,
                "candidate_interpreter_executed": False,
                "execution_authorized": False,
            },
        }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def runtime_launch_contract() -> dict[str, Any]:
    return {
        "mode": "runtime_probe",
        "application_file_name": "python.exe",
        "flags": ["-I", "-S", "-B", "-E", "-s", "-P", "-X", "utf8"],
        "runner_path_strategy": "runtime_root_join_fixed_runner_v1",
        "runner_file_name": RUNTIME_RUNNER_FILE_NAME,
        "working_directory_strategy": "worker_result_directory_v1",
        "shell": False,
        "caller_arguments": False,
        "caller_environment": False,
    }


def runtime_launch_contract_fingerprint() -> str:
    return hashlib.sha256(_canonical_json_bytes(runtime_launch_contract())).hexdigest()


RUNTIME_SOURCE_FILES = (
    DeveloperTaskPythonRuntimeSourceFile(path='LICENSE.txt', size_bytes=33861, compressed_size=9967, compression=8, sha256='62bec384df47b0328307db41455ff6ea2559e5546b394ac69148561b21703120'),
    DeveloperTaskPythonRuntimeSourceFile(path='_asyncio.pyd', size_bytes=72928, compressed_size=33534, compression=8, sha256='6941e2aeed3aad1a4658774ecb60309170066a040c2118a5efd16458ac3bed00'),
    DeveloperTaskPythonRuntimeSourceFile(path='_bz2.pyd', size_bytes=86752, compressed_size=46606, compression=8, sha256='261545bd24f15a783fc0c82568b766a4ab569dde14507a81701cccf5293e6e54'),
    DeveloperTaskPythonRuntimeSourceFile(path='_ctypes.pyd', size_bytes=134368, compressed_size=64719, compression=8, sha256='9d6dccb4cd84a44a107f9b06b91c0a44e85766d9bf4debb6abbde8fda7494c2c'),
    DeveloperTaskPythonRuntimeSourceFile(path='_decimal.pyd', size_bytes=286944, compressed_size=136231, compression=8, sha256='1e6a5707163d3c103e0eb4695eefedbea4b855fb227c61cc265b168970d6c6f0'),
    DeveloperTaskPythonRuntimeSourceFile(path='_elementtree.pyd', size_bytes=135904, compressed_size=62641, compression=8, sha256='26c5c2f3f2b8dac1499f07a50d7afd14315c20a6a541abbe4e306bcd9df404f1'),
    DeveloperTaskPythonRuntimeSourceFile(path='_hashlib.pyd', size_bytes=69344, compressed_size=31599, compression=8, sha256='79a26289aef0d92545a082507c7021f10e219621d137cb726c4d0fbbfd4b46ae'),
    DeveloperTaskPythonRuntimeSourceFile(path='_lzma.pyd', size_bytes=159456, compressed_size=89015, compression=8, sha256='ee224aacf5cf9c9974a1b842aac8d89d5d9b7eeebbf4d76619ae0ce4da8ecd96'),
    DeveloperTaskPythonRuntimeSourceFile(path='_multiprocessing.pyd', size_bytes=38112, compressed_size=20867, compression=8, sha256='db19972cf033b598f5826f8219bc2608412b84061d294f5972b43c2ab95f7af5'),
    DeveloperTaskPythonRuntimeSourceFile(path='_overlapped.pyd', size_bytes=57568, compressed_size=28778, compression=8, sha256='9db08b5449e18088754ce57e315657d00b46575e0151cd379efef8847488a606'),
    DeveloperTaskPythonRuntimeSourceFile(path='_queue.pyd', size_bytes=35552, compressed_size=19595, compression=8, sha256='4404c2569443ffb54e7cfffdca8ddf58c9a609175305970728ec12bc1c147b43'),
    DeveloperTaskPythonRuntimeSourceFile(path='_socket.pyd', size_bytes=86752, compressed_size=41652, compression=8, sha256='ccbd0f83df3784da08147b8e8765e28c978de28b5c0eddcfba5567b59d43fef9'),
    DeveloperTaskPythonRuntimeSourceFile(path='_sqlite3.pyd', size_bytes=131296, compressed_size=61066, compression=8, sha256='4c5fa9341a76ac525fd36e2cb23260934ad9b9f6825725ff139b26c8dc72436d'),
    DeveloperTaskPythonRuntimeSourceFile(path='_ssl.pyd', size_bytes=181984, compressed_size=73537, compression=8, sha256='8d2f51fa1dc929073a2ad8d1c7c0c911e8f695870dcf4dda2846f4b75a7f77fb'),
    DeveloperTaskPythonRuntimeSourceFile(path='_uuid.pyd', size_bytes=27872, compressed_size=16188, compression=8, sha256='b93832742a2348d6659fd62e8a8aff061594693fc537da74c7d2d1cdf83a8475'),
    DeveloperTaskPythonRuntimeSourceFile(path='_wmi.pyd', size_bytes=39648, compressed_size=21974, compression=8, sha256='db45362354fd4965329cb14bd974e60b26525045d09fb4fdfb1674a93b79d60c'),
    DeveloperTaskPythonRuntimeSourceFile(path='_zoneinfo.pyd', size_bytes=50912, compressed_size=27463, compression=8, sha256='6650db91accc05e625d3c5d8a40e15127a040ea1135e40e875fd78d8a7665a84'),
    DeveloperTaskPythonRuntimeSourceFile(path='libcrypto-3.dll', size_bytes=5238520, compressed_size=1871210, compression=8, sha256='09499e186cf0e434ffa17ad153aa9a66d6048c54a2c03b823e2a06c49d9affe4'),
    DeveloperTaskPythonRuntimeSourceFile(path='libffi-8.dll', size_bytes=39696, compressed_size=23208, compression=8, sha256='eff52743773eb550fcc6ce3efc37c85724502233b6b002a35496d828bd7b280a'),
    DeveloperTaskPythonRuntimeSourceFile(path='libssl-3.dll', size_bytes=794872, compressed_size=284730, compression=8, sha256='28c395290279fa4f4f54a57b85cd66d853895f925fefb8f6fdebc0d8b1cdd07c'),
    DeveloperTaskPythonRuntimeSourceFile(path='pyexpat.pyd', size_bytes=221920, compressed_size=106462, compression=8, sha256='b9c9c5a9f52af559a7eb4e8ddfd60558185bfc7794f32840bed1747d1ec9026a'),
    DeveloperTaskPythonRuntimeSourceFile(path='python.cat', size_bytes=578418, compressed_size=188064, compression=8, sha256='49eb507453b924ff70c19c8b8940b033ac5865f11cdd637447024725ed105bef'),
    DeveloperTaskPythonRuntimeSourceFile(path='python.exe', size_bytes=105696, compressed_size=55204, compression=8, sha256='85b71d8c6ec1905935f74be0c9869aae198d00e98f39df699ec66f9c5a84cecd'),
    DeveloperTaskPythonRuntimeSourceFile(path='python3.dll', size_bytes=72416, compressed_size=24680, compression=8, sha256='76e7fd69a01081726308317d6e502721c2ba6792b48880dc1ef649c755788db7'),
    DeveloperTaskPythonRuntimeSourceFile(path='python313._pth', size_bytes=80, compressed_size=77, compression=8, sha256='35ddf94682ff9aa713a8d63557242ad00f3f28fdd39337f02c3bda4c0f791577'),
    DeveloperTaskPythonRuntimeSourceFile(path='python313.dll', size_bytes=6135008, compressed_size=2513608, compression=8, sha256='e820bf024efd2b56bb2b82791e6b6ddc7303f070f8e72cba7637482a8a906238'),
    DeveloperTaskPythonRuntimeSourceFile(path='python313.zip', size_bytes=3825631, compressed_size=3780959, compression=8, sha256='1916abd946d2044ec8c04c3319f96c8415d5b6fce01e125622827f2b7756cbab'),
    DeveloperTaskPythonRuntimeSourceFile(path='pythonw.exe', size_bytes=104160, compressed_size=53387, compression=8, sha256='146c01e5448a084ff15d63113a790b9aa75250baf862d984c51dd695ac4775bc'),
    DeveloperTaskPythonRuntimeSourceFile(path='select.pyd', size_bytes=32992, compressed_size=18771, compression=8, sha256='024f955349fe46cf1bb2c22c6b57fcf38cf5755d46166fbf63e7e5b92433b111'),
    DeveloperTaskPythonRuntimeSourceFile(path='sqlite3.dll', size_bytes=1584864, compressed_size=849354, compression=8, sha256='c6812eaf0f8605df273b9bf7e359b83fd65038ecc66455c3f7a933768cb92f3f'),
    DeveloperTaskPythonRuntimeSourceFile(path='unicodedata.pyd', size_bytes=712928, compressed_size=321315, compression=8, sha256='111e0fdfeef9887c04f6ebf1972ce1ccbec55b226012e4a288c2d4a0b17b216b'),
    DeveloperTaskPythonRuntimeSourceFile(path='vcruntime140.dll', size_bytes=178616, compressed_size=85393, compression=8, sha256='d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7'),
    DeveloperTaskPythonRuntimeSourceFile(path='vcruntime140_1.dll', size_bytes=50112, compressed_size=26615, compression=8, sha256='a7146c08f89fe5b04541ab507cdb59ff7b44534d4ba3c668a426c6450a03434e'),
    DeveloperTaskPythonRuntimeSourceFile(path='winsound.pyd', size_bytes=31968, compressed_size=17928, compression=8, sha256='b078b7f5c53efd3c4201b63fa34a17c6747142e37298293f52c3a9ad643e69e2'),
)

TRUSTED_PYTHON_RUNTIME_POLICY_V1 = DeveloperTaskPythonRuntimePolicy(
    schema_version=RUNTIME_BUNDLE_POLICY_SCHEMA_VERSION,
    policy_id=RUNTIME_BUNDLE_POLICY_ID,
    source_files=RUNTIME_SOURCE_FILES,
)


def validate_trusted_python_runtime_policy(
    policy: DeveloperTaskPythonRuntimePolicy = TRUSTED_PYTHON_RUNTIME_POLICY_V1,
) -> None:
    if policy is not TRUSTED_PYTHON_RUNTIME_POLICY_V1:
        raise ValueError("Only the pinned V1B4B trusted Python runtime policy is accepted.")
    if runtime_launch_contract_fingerprint() != RUNTIME_LAUNCH_CONTRACT_FINGERPRINT:
        raise ValueError("Trusted runtime launch contract fingerprint changed unexpectedly.")
    if not policy.ok:
        raise ValueError("Trusted Python runtime policy failed its canonical self-check.")
