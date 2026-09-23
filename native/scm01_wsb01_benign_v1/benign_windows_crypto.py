"""Concrete bcrypt source with a closed public factory and separate fake receipt type.
No ctypes import or DLL load at module import. Never persist/export a private key.
"""
from dataclasses import dataclass, field
import hashlib
import struct
from .benign_contract import need, sha, READY_DOMAIN, TERMINAL_DOMAIN, BenignError
from .benign_runtime_gate import require_native_authority

P = int('FFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF', 16)
B = int('5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B', 16)
N = int('FFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551', 16)
_NATIVE_SEAL = object()


def validate_public(blob):
    need(type(blob) is bytes and len(blob) == 72, 'public_blob_size')
    need(struct.unpack('<II', blob[:8]) == (0x31534345, 32), 'public_blob_header')
    x, y = int.from_bytes(blob[8:40], 'big'), int.from_bytes(blob[40:], 'big')
    need(0 < x < P and 0 < y < P and y * y % P == (x * x * x - 3 * x + B) % P,
         'public_point')
    return blob


def validate_signature(sig):
    need(type(sig) is bytes and len(sig) == 64, 'signature_size')
    need(0 < int.from_bytes(sig[:32], 'big') < N and 0 < int.from_bytes(sig[32:], 'big') < N,
         'signature_scalar')
    return sig


def prehash(domain, raw):
    need(type(domain) is bytes and domain in (READY_DOMAIN, TERMINAL_DOMAIN), 'signing_domain')
    need(type(raw) is bytes and 0 < len(raw) <= 65536, 'signed_payload_limit')
    return hashlib.sha256(domain + raw).digest()


@dataclass(frozen=True)
class FakeCryptoReceipt:
    domain: bytes
    payload_sha256: str
    key_sha256: str
    signature_sha256: str
    evidence_domain: str = 'OFFLINE_MODEL'


@dataclass(frozen=True)
class _NativeCryptoReceipt:
    domain: bytes
    payload_sha256: str
    key_sha256: str
    signature_sha256: str
    _seal: object = field(repr=False, compare=False)


def is_native_receipt(receipt, domain, raw, key, signature):
    return (type(receipt) is _NativeCryptoReceipt and receipt._seal is _NATIVE_SEAL and
            receipt.domain == domain and receipt.payload_sha256 == sha(raw) and
            receipt.key_sha256 == sha(key) and receipt.signature_sha256 == sha(signature))


def _nt(status, action):
    need(type(status) is int, 'CNG_status_type')
    need(status == 0, 'CNG_' + action + '_' + format(status & 0xffffffff, '08x'))


class _CryptoEngine:
    """Algorithm implementation over bcrypt-shaped calls. Injected API is always fake."""
    def __init__(self, api):
        self.api = api

    def verify(self, key_blob, domain, raw, signature):
        validate_public(key_blob); validate_signature(signature)
        digest = prehash(domain, raw)
        alg = key = None
        try:
            st, alg = self.api.open_algorithm(); _nt(st, 'open'); need(bool(alg), 'CNG_alg_null')
            st, key = self.api.import_public(alg, key_blob); _nt(st, 'import'); need(bool(key), 'CNG_key_null')
            _nt(self.api.verify(key, digest, signature), 'verify')
        finally:
            # No receipt if destruction/close is uncertain. Always attempt both cleanup calls.
            try:
                if key:
                    _nt(self.api.destroy_key(key), 'destroy')
            finally:
                if alg:
                    _nt(self.api.close_algorithm(alg), 'close')
        args = (domain, sha(raw), sha(key_blob), sha(signature))
        if type(self.api) is _BcryptApi:
            return _NativeCryptoReceipt(*args, _NATIVE_SEAL)
        return FakeCryptoReceipt(*args)

    def signer(self):
        alg = key = None
        try:
            st, alg = self.api.open_algorithm(); _nt(st, 'open'); need(bool(alg), 'CNG_alg_null')
            st, key = self.api.generate(alg); _nt(st, 'generate'); need(bool(key), 'CNG_key_null')
            _nt(self.api.finalize(key), 'finalize')
            st, blob = self.api.export_public(key); _nt(st, 'export')
            validate_public(blob)
            return _Signer(self.api, alg, key, blob)
        except Exception:
            try:
                if key:
                    _nt(self.api.destroy_key(key), 'destroy')
            finally:
                if alg:
                    _nt(self.api.close_algorithm(alg), 'close')
            raise


class _Signer:
    def __init__(self, api, alg, key, public):
        self._api, self._alg, self._key, self.public_blob = api, alg, key, public
        self._used = set()

    def sign(self, domain, raw):
        need(self._key is not None and domain not in self._used, 'signer_closed_or_reused')
        digest = prehash(domain, raw)
        self._used.add(domain)  # Consume even when the native call fails.
        status, signature = self._api.sign(self._key, digest)
        _nt(status, 'sign'); return validate_signature(signature)

    def close(self):
        alg, key = self._alg, self._key
        self._alg = self._key = None
        try:
            if key:
                _nt(self._api.destroy_key(key), 'destroy')
        finally:
            if alg:
                _nt(self._api.close_algorithm(alg), 'close')

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def create_ephemeral_signer(permit=None):
    require_native_authority(permit)
    return _CryptoEngine(_BcryptApi(permit)).signer()


def verify_signature(key_blob, domain, payload, signature, permit=None):
    require_native_authority(permit)
    return _CryptoEngine(_BcryptApi(permit)).verify(key_blob, domain, payload, signature)


class _BcryptApi:
    """Exact Win32 fixed-width ABI, loaded only behind the unreleased native gate."""
    def __init__(self, permit):
        require_native_authority(permit)
        import ctypes as c
        import sys
        need(sys.platform == 'win32' and c.sizeof(c.c_void_p) == 8, 'win64_required')
        self.c = c
        self.dll = c.WinDLL('bcrypt.dll', winmode=0x00000800)
        H = c.c_void_p; U = c.c_uint32; S = c.c_int32; V = c.c_void_p; W = c.c_wchar_p
        signatures = {
            'BCryptOpenAlgorithmProvider': [c.POINTER(H), W, W, U],
            'BCryptGenerateKeyPair': [H, c.POINTER(H), U, U],
            'BCryptFinalizeKeyPair': [H, U],
            'BCryptExportKey': [H, H, W, V, U, c.POINTER(U), U],
            'BCryptImportKeyPair': [H, H, W, c.POINTER(H), V, U, U],
            'BCryptSignHash': [H, V, V, U, V, U, c.POINTER(U), U],
            'BCryptVerifySignature': [H, V, V, U, V, U, U],
            'BCryptDestroyKey': [H], 'BCryptCloseAlgorithmProvider': [H, U]}
        for name, args in signatures.items():
            f = getattr(self.dll, name); f.argtypes = args; f.restype = S

    def _buffer(self, data):
        return (self.c.c_ubyte * len(data)).from_buffer_copy(data)

    def open_algorithm(self):
        h = self.c.c_void_p()
        st = self.dll.BCryptOpenAlgorithmProvider(self.c.byref(h), 'ECDSA_P256', None, 0)
        return int(st), h.value

    def generate(self, alg):
        h = self.c.c_void_p()
        st = self.dll.BCryptGenerateKeyPair(alg, self.c.byref(h), 256, 0)
        return int(st), h.value

    def finalize(self, key):
        return int(self.dll.BCryptFinalizeKeyPair(key, 0))

    def export_public(self, key):
        out = (self.c.c_ubyte * 72)(); n = self.c.c_uint32()
        st = self.dll.BCryptExportKey(key, None, 'ECCPUBLICBLOB', out, 72, self.c.byref(n), 0)
        if st == 0:
            need(n.value == 72, 'export_size')
        return int(st), bytes(out[:n.value])

    def import_public(self, alg, blob):
        h = self.c.c_void_p(); b = self._buffer(blob)
        st = self.dll.BCryptImportKeyPair(alg, None, 'ECCPUBLICBLOB', self.c.byref(h), b, len(blob), 0)
        return int(st), h.value

    def sign(self, key, digest):
        need(len(digest) == 32, 'one_prehash')
        d = self._buffer(digest); out = (self.c.c_ubyte * 64)(); n = self.c.c_uint32()
        st = self.dll.BCryptSignHash(key, None, d, 32, out, 64, self.c.byref(n), 0)
        if st == 0:
            need(n.value == 64, 'signature_return_size')
        return int(st), bytes(out[:n.value])

    def verify(self, key, digest, sig):
        d, s = self._buffer(digest), self._buffer(sig)
        return int(self.dll.BCryptVerifySignature(key, None, d, 32, s, 64, 0))

    def destroy_key(self, key):
        return int(self.dll.BCryptDestroyKey(key))

    def close_algorithm(self, alg):
        return int(self.dll.BCryptCloseAlgorithmProvider(alg, 0))
