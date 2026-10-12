"""R5SDK netcon.proto framing, without a protobuf runtime dependency."""
import socket
import secrets
import struct

MAGIC = 0x6E6F4352
MAX_FRAME = 1 << 20


def varint(value):
    if value < 0:
        value &= (1 << 64) - 1
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode('utf-8')
    return varint((number << 3) | 2) + varint(len(value)) + value


def fields(data):
    offset = 0

    def read_int():
        nonlocal offset
        result = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise ValueError('Truncated protobuf integer')
            byte = data[offset]
            offset += 1
            result |= (byte & 127) << shift
            if byte < 128:
                return result
        raise ValueError('Oversized protobuf integer')

    result = {}
    while offset < len(data):
        key = read_int()
        number, wire = key >> 3, key & 7
        if not number:
            raise ValueError('Invalid protobuf field')
        if wire == 0:
            value = read_int()
        elif wire == 2:
            size = read_int()
            if offset + size > len(data):
                raise ValueError('Truncated protobuf string')
            value = data[offset:offset + size]
            offset += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            if offset + size > len(data):
                raise ValueError('Truncated protobuf fixed field')
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError('Unsupported protobuf wire type')
        result[number] = value
    return result


def request(kind, message='', value='', sequence=1):
    inner = field(1, -1) + field(3, kind) + field(4, message) + field(5, value)
    # Installed R5R v2.6.52: header {sequence, nonce64}, nonce bytes, tag
    # bytes, data. This differs from the older SDK's encrypted/nonce/data.
    header = field(1, sequence) + field(2, secrets.randbits(64))
    envelope = field(1, header) + field(4, inner)
    return struct.pack('>II', MAGIC, len(envelope)) + envelope


def receive(sock):
    def exact(count):
        chunks = bytearray()
        while len(chunks) < count:
            chunk = sock.recv(count - len(chunks))
            if not chunk:
                raise ConnectionError('R5R closed its remote console')
            chunks.extend(chunk)
        return bytes(chunks)

    magic, size = struct.unpack('>II', exact(8))
    if magic != MAGIC or not 0 < size <= MAX_FRAME:
        raise ValueError('Invalid R5R console frame')
    return decode(exact(size))


def decode(payload):
    envelope = fields(payload)
    if not isinstance(envelope.get(1), bytes) or 4 not in envelope:
        raise ValueError('Unsupported R5R protocol; expected v2.6 envelope')
    if envelope.get(2) or envelope.get(3):
        raise ValueError('Encrypted frame: use rcon_encryptframes 0 in this loopback harness')
    header = fields(envelope[1])
    response = fields(envelope[4])
    return {'type': response.get(3, 0), 'message': response.get(4, b'').decode('utf-8', 'replace'),
            'value': response.get(5, b'').decode('utf-8', 'replace'), 'sequence': header.get(1, 0)}


class Console:
    def __init__(self, port, password, timeout=10):
        self.sock = socket.create_connection(('::1', port), timeout)
        self.sequence = 1
        self.incoming_sequence = 0
        self.buffer = bytearray()
        self.sock.sendall(request(1, password))
        answer = self.read()
        if answer['type'] != 0 or 'successful' not in answer['message'].lower():
            self.close()
            raise PermissionError('R5R console authentication failed')
        self.sequence += 1
        self.sock.sendall(request(2, value='1', sequence=self.sequence))

    def execute(self, command):
        name = command.split(' ', 1)[0]
        self.sequence += 1
        self.sock.sendall(request(0, name, command, sequence=self.sequence))

    def read(self):
        # Retain partial TCP frames across timeout/retry boundaries.
        while True:
            if len(self.buffer) >= 8:
                magic, size = struct.unpack('>II', self.buffer[:8])
                if magic != MAGIC or not 0 < size <= MAX_FRAME:
                    raise ValueError('Invalid R5R console frame')
                if len(self.buffer) >= size + 8:
                    answer = decode(bytes(self.buffer[8:8 + size]))
                    del self.buffer[:8 + size]
                    if answer['sequence'] != self.incoming_sequence + 1:
                        raise ValueError('Out-of-order R5R response sequence')
                    self.incoming_sequence = answer['sequence']
                    return answer
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError('R5R closed its remote console')
            self.buffer.extend(chunk)

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
