from __future__ import annotations

"""Windows CNG verification for V1B3 ECDSA P-256 signed terminal payloads."""

import ctypes
import hashlib
import struct
import sys

from dataclasses import dataclass
from typing import Any


_CNG_ECDSA_P256 = "ECDSA_P256"
_CNG_ECCPUBLIC_BLOB = "ECCPUBLICBLOB"
_ECCPUBLIC_P256_MAGIC = 0x31534345  # little-endian bytes: b"ECS1"
_P256_BYTES = 32
_P256_BLOB_BYTES = 8 + (_P256_BYTES * 2)
_P256_P = int("FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF", 16)
_P256_B = int("5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B", 16)
_P256_N = int("FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551", 16)


class DeveloperTaskExecutionBoundaryCryptoError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.actual = actual


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryPublicKey:
    blob_sha256: str
    x: int
    y: int
    blob: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "EccPublicBlob",
            "algorithm": "ECDSA_P256_SHA256_CNG",
            "size_bytes": len(self.blob),
            "sha256": self.blob_sha256,
            "x_hex": f"{self.x:064x}",
            "y_hex": f"{self.y:064x}",
        }


def validate_ecdsa_p256_public_blob(
    blob: bytes,
) -> DeveloperTaskExecutionBoundaryPublicKey:
    if not isinstance(blob, bytes):
        raise TypeError("public_key_blob must be bytes")
    if len(blob) != _P256_BLOB_BYTES:
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_public_key_blob_invalid",
            "ECDSA P-256 public key blob has an invalid size.",
            actual=str(len(blob)),
        )
    magic, key_bytes = struct.unpack("<II", blob[:8])
    if magic != _ECCPUBLIC_P256_MAGIC or key_bytes != _P256_BYTES:
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_public_key_blob_invalid",
            "ECDSA P-256 public key blob header is invalid.",
            actual=blob[:8].hex(),
        )
    x = int.from_bytes(blob[8:40], "big")
    y = int.from_bytes(blob[40:72], "big")
    if not (0 < x < _P256_P and 0 < y < _P256_P):
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_public_key_point_invalid",
            "ECDSA P-256 public key coordinates are out of range.",
        )
    if pow(y, 2, _P256_P) != (pow(x, 3, _P256_P) - (3 * x) + _P256_B) % _P256_P:
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_public_key_point_invalid",
            "ECDSA P-256 public key is not on the curve.",
        )
    return DeveloperTaskExecutionBoundaryPublicKey(
        blob_sha256=hashlib.sha256(blob).hexdigest(),
        x=x,
        y=y,
        blob=blob,
    )


def validate_ecdsa_p256_signature(signature: bytes) -> tuple[int, int]:
    if not isinstance(signature, bytes):
        raise TypeError("signature must be bytes")
    if len(signature) != 64:
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_signature_size_invalid",
            "ECDSA P-256 signature must be exactly 64 bytes.",
            actual=str(len(signature)),
        )
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not (0 < r < _P256_N and 0 < s < _P256_N):
        raise DeveloperTaskExecutionBoundaryCryptoError(
            "boundary_signature_scalar_invalid",
            "ECDSA P-256 signature scalars are out of range.",
        )
    return r, s


class _WindowsCngRuntime:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise DeveloperTaskExecutionBoundaryCryptoError(
                "boundary_crypto_unavailable",
                "Windows CNG signature verification is unavailable on this platform.",
                actual=sys.platform,
            )
        self.bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        self.bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
        ]
        self.bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
        self.bcrypt.BCryptImportKeyPair.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.bcrypt.BCryptImportKeyPair.restype = ctypes.c_long
        self.bcrypt.BCryptVerifySignature.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self.bcrypt.BCryptVerifySignature.restype = ctypes.c_long
        self.bcrypt.BCryptDestroyKey.argtypes = [ctypes.c_void_p]
        self.bcrypt.BCryptDestroyKey.restype = ctypes.c_long
        self.bcrypt.BCryptCloseAlgorithmProvider.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self.bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long

    def open_algorithm(self) -> tuple[int, Any]:
        handle = ctypes.c_void_p()
        status = int(
            self.bcrypt.BCryptOpenAlgorithmProvider(
                ctypes.byref(handle),
                _CNG_ECDSA_P256,
                None,
                0,
            )
        )
        return status, handle

    def import_public_key(self, algorithm: Any, blob: bytes) -> tuple[int, Any]:
        handle = ctypes.c_void_p()
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        status = int(
            self.bcrypt.BCryptImportKeyPair(
                algorithm,
                None,
                _CNG_ECCPUBLIC_BLOB,
                ctypes.byref(handle),
                buffer,
                len(blob),
                0,
            )
        )
        return status, handle

    def verify(self, key: Any, digest: bytes, signature: bytes) -> int:
        digest_buffer = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)
        signature_buffer = (ctypes.c_ubyte * len(signature)).from_buffer_copy(signature)
        return int(
            self.bcrypt.BCryptVerifySignature(
                key,
                None,
                digest_buffer,
                len(digest),
                signature_buffer,
                len(signature),
                0,
            )
        )

    def destroy_key(self, handle: Any) -> int:
        return int(self.bcrypt.BCryptDestroyKey(handle))

    def close_algorithm(self, handle: Any) -> int:
        return int(self.bcrypt.BCryptCloseAlgorithmProvider(handle, 0))


def _ntstatus_hex(value: int) -> str:
    return f"0x{ctypes.c_uint32(value).value:08x}"


def verify_ecdsa_p256_sha256_cng(
    public_key_blob: bytes,
    message: bytes,
    signature: bytes,
    *,
    _runtime: Any | None = None,
) -> bool:
    if not isinstance(message, bytes):
        raise TypeError("message must be bytes")
    public_key = validate_ecdsa_p256_public_blob(public_key_blob)
    validate_ecdsa_p256_signature(signature)
    digest = hashlib.sha256(message).digest()
    runtime = _runtime if _runtime is not None else _WindowsCngRuntime()
    algorithm = None
    key = None
    try:
        status, algorithm = runtime.open_algorithm()
        if status != 0 or not algorithm:
            raise DeveloperTaskExecutionBoundaryCryptoError(
                "boundary_crypto_open_failed",
                "Windows CNG ECDSA provider could not be opened.",
                actual=_ntstatus_hex(status),
            )
        status, key = runtime.import_public_key(algorithm, public_key.blob)
        if status != 0 or not key:
            raise DeveloperTaskExecutionBoundaryCryptoError(
                "boundary_public_key_import_failed",
                "Windows CNG could not import the ECDSA public key.",
                actual=_ntstatus_hex(status),
            )
        return runtime.verify(key, digest, signature) == 0
    finally:
        if key:
            runtime.destroy_key(key)
        if algorithm:
            runtime.close_algorithm(algorithm)
