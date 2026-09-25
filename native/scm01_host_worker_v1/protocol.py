"""HWA01 fixed host-only IPC, distinct from BEN01. No path/command/permit deserialization."""
import json
import struct
from .contract import (ContractError, Plan, Identity, FRAME_LIMIT, PROFILE,
                       FIXED_PAYLOAD, canonical, digest, need, uint, hex_digest)

KIND = 'HWA01_HOST_ONLY_FRAME_V1'
DIRECTIONS = ('HOST_TO_WORKER', 'WORKER_TO_HOST')
COMMANDS = ('INIT', 'PROBE', 'STOP')


def _reject(_value):
    raise ContractError('non_integer_json_number')


def _pairs(rows):
    out = {}
    for key, value in rows:
        need(key not in out, 'duplicate_json_key')
        out[key] = value
    return out


def _integer(text):
    need(len(text) <= 20, 'integer_length')
    return int(text)


def _depth(raw):
    depth = 0
    quoted = escaped = False
    for ch in raw:
        if quoted:
            if escaped:
                escaped = False
            elif ch == 92:
                escaped = True
            elif ch == 34:
                quoted = False
        elif ch == 34:
            quoted = True
        elif ch in (91, 123):
            depth += 1
            need(depth <= 8, 'json_depth')
        elif ch in (93, 125):
            depth -= 1
            need(depth >= 0, 'json_depth')
    need(depth == 0 and not quoted and not escaped, 'json_unbalanced')


def request_payload(sequence):
    uint(sequence, 2)
    if sequence == 0:
        return {'profile': PROFILE}
    if sequence == 1:
        return {'data_hex': FIXED_PAYLOAD.hex()}
    return {'reason': 'completed'}


def response_payload(plan, sequence, identity):
    plan.validate()
    need(type(identity) is Identity, 'identity_type')
    identity.validate()
    uint(sequence, 2)
    if sequence == 0:
        return {'pid': identity.pid, 'created': identity.created,
                'executable_sha256': plan.runtime.executable.sha256,
                'source_manifest_sha256': plan.source_manifest_sha256}
    if sequence == 1:
        return {'bytes': len(FIXED_PAYLOAD), 'sha256': digest(FIXED_PAYLOAD)}
    return {'status': 'STOPPING'}


def _payload(plan, direction, sequence, value):
    need(type(value) is dict, 'payload_object')
    if direction == DIRECTIONS[0]:
        need(value == request_payload(sequence), 'fixed_request')
    elif sequence == 0:
        need(set(value) == {'pid', 'created', 'executable_sha256', 'source_manifest_sha256'},
             'startup_reply_schema')
        uint(value['pid'], 0xffffffff, 1)
        uint(value['created'], (1 << 64) - 1, 1)
        need(value['executable_sha256'] == plan.runtime.executable.sha256 and
             value['source_manifest_sha256'] == plan.source_manifest_sha256, 'startup_reply_pins')
    elif sequence == 1:
        need(set(value) == {'bytes', 'sha256'}, 'probe_reply_schema')
        uint(value['bytes'], len(FIXED_PAYLOAD), len(FIXED_PAYLOAD))
        need(value['sha256'] == digest(FIXED_PAYLOAD), 'probe_digest')
    else:
        need(value == {'status': 'STOPPING'}, 'stop_reply')


def encode(plan: Plan, direction: str, sequence: int, payload: dict) -> bytes:
    need(type(plan) is Plan, 'plan_type')
    plan.validate()
    need(type(direction) is str and direction in DIRECTIONS, 'direction')
    uint(sequence, 2)
    _payload(plan, direction, sequence, payload)
    body = canonical({'kind': KIND, 'run_id': plan.run_id, 'nonce': plan.nonce,
                      'plan_sha256': plan.fingerprint(), 'direction': direction,
                      'sequence': sequence, 'command': COMMANDS[sequence], 'payload': payload})
    need(0 < len(body) <= FRAME_LIMIT, 'frame_limit')
    return struct.pack('<I', len(body)) + body


def decode(plan: Plan, direction: str, sequence: int, packet: bytes) -> dict:
    need(type(plan) is Plan, 'plan_type')
    plan.validate()
    need(type(direction) is str and direction in DIRECTIONS, 'direction')
    uint(sequence, 2)
    need(type(packet) is bytes and 4 < len(packet) <= FRAME_LIMIT + 4, 'packet_size')
    size = struct.unpack('<I', packet[:4])[0]
    need(0 < size <= FRAME_LIMIT and len(packet) == size + 4, 'packet_length')
    raw = packet[4:]
    _depth(raw)
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=_pairs, parse_int=_integer,
                           parse_float=_reject, parse_constant=_reject)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError('frame_json') from exc
    need(type(value) is dict and set(value) ==
         {'kind', 'run_id', 'nonce', 'plan_sha256', 'direction', 'sequence', 'command', 'payload'},
         'frame_schema')
    need(raw == canonical(value), 'frame_noncanonical')
    uint(value['sequence'], 2)
    need(value['kind'] == KIND and value['run_id'] == plan.run_id and value['nonce'] == plan.nonce and
         value['plan_sha256'] == plan.fingerprint(), 'frame_binding')
    need(value['direction'] == direction and value['sequence'] == sequence and
         value['command'] == COMMANDS[sequence], 'frame_order_or_direction')
    _payload(plan, direction, sequence, value['payload'])
    return value


class Decoder:
    """One bounded reply at a time. Any parse error or EOF permanently poisons this instance."""
    def __init__(self, plan: Plan, direction: str):
        need(type(plan) is Plan and type(direction) is str and direction in DIRECTIONS, 'decoder_binding')
        self.plan = plan.validate()
        self.direction = direction
        self.sequence = 0
        self.buffer = b''
        self.poisoned = False

    def feed(self, chunk: bytes):
        try:
            need(not self.poisoned and self.sequence < 3, 'decoder_consumed')
            need(type(chunk) is bytes and 0 < len(chunk) <= FRAME_LIMIT + 4, 'chunk_size')
            need(len(self.buffer) + len(chunk) <= FRAME_LIMIT + 4, 'buffer_size')
            self.buffer += chunk
            if len(self.buffer) < 4:
                return None
            size = struct.unpack('<I', self.buffer[:4])[0]
            need(0 < size <= FRAME_LIMIT, 'frame_limit')
            if len(self.buffer) < size + 4:
                return None
            result = decode(self.plan, self.direction, self.sequence, self.buffer)
            self.buffer = b''
            self.sequence += 1
            return result
        except ContractError:
            self.poisoned = True
            raise

    def eof(self):
        if self.poisoned or self.buffer or self.sequence != 3:
            self.poisoned = True
            raise ContractError('eof_before_complete_transcript')
        self.poisoned = True  # complete, but still not reusable
