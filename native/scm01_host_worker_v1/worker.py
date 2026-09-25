"""Fixed worker algorithm. No arbitrary data operation, shell, network or dynamic commands."""
from .contract import FRAME_LIMIT, need, digest
from .protocol import decode, encode, DIRECTIONS, response_payload


def read_exact(channel, n):
    out = bytearray()
    while len(out) < n:
        part = channel.read(n - len(out))
        need(type(part) is bytes and 0 < len(part) <= n - len(out), 'worker_eof_or_read')
        out.extend(part)
    return bytes(out)


def write_exact(channel, raw):
    at = 0
    while at < len(raw):
        n = channel.write(raw[at:])
        need(type(n) is int and 0 < n <= len(raw) - at, 'worker_write')
        at += n


def serve_fixed(plan, identity, channel):
    """Invoked after trusted bootstrap has narrowed inherited standard handles.
    Test channels are in-memory; this function does not create a process or issue a permit.
    """
    plan.validate()
    identity.validate()
    for seq in range(3):
        header = read_exact(channel, 4)
        n = int.from_bytes(header, 'little')
        need(0 < n <= FRAME_LIMIT, 'worker_frame_limit')
        frame = decode(plan, DIRECTIONS[0], seq, header + read_exact(channel, n))
        payload = response_payload(plan, seq, identity)
        if seq == 1:
            # Compute over the received bytes, AFTER protocol enforces the exact fixed input.
            received = bytes.fromhex(frame['payload']['data_hex'])
            payload = {'bytes': len(received), 'sha256': digest(received)}
        write_exact(channel, encode(plan, DIRECTIONS[1], seq, payload))
    # Parent closes its request writer only after it has received STOPPING.
    need(channel.read(1) == b'', 'worker_trailing_request')
    return 0
