import io
import json
from pathlib import Path
import socket
import struct
import tempfile
import unittest
from unittest.mock import patch

import harness
from protocol import MAGIC, MAX_FRAME, Console, field, fields, receive, request


class FragmentedSocket:
    def __init__(self, data, chunk=1):
        self.stream = io.BytesIO(data)
        self.chunk = chunk

    def recv(self, size):
        return self.stream.read(min(size, self.chunk))


def response(kind=1, message='hello'):
    envelope = field(1, field(1, 1)) + field(4, field(3, kind) + field(4, message))
    return struct.pack('>II', MAGIC, len(envelope)) + envelope


class ProtocolTests(unittest.TestCase):
    def test_partial_frame_survives_socket_timeout(self):
        class TimedSocket:
            def __init__(self): self.chunks = [response()[:4], TimeoutError(), response()[4:]]
            def recv(self, size):
                item = self.chunks.pop(0)
                if isinstance(item, Exception): raise item
                return item
        console = object.__new__(Console)
        console.sock = TimedSocket(); console.buffer = bytearray(); console.incoming_sequence = 0
        with self.assertRaises(TimeoutError): console.read()
        self.assertEqual(console.read()['message'], 'hello')

    def test_replayed_response_rejected(self):
        console = object.__new__(Console)
        console.sock = FragmentedSocket(response() + response(), 65536)
        console.buffer = bytearray(); console.incoming_sequence = 0
        console.read()
        with self.assertRaisesRegex(ValueError, 'Out-of-order'): console.read()

    def test_fragmented_header_and_payload(self):
        self.assertEqual(receive(FragmentedSocket(response(message='αβγ')))['message'], 'αβγ')

    def test_coalesced_frames_remain_separate(self):
        sock = FragmentedSocket(response(message='one') + response(message='two'), 1000)
        self.assertEqual(receive(sock)['message'], 'one')
        self.assertEqual(receive(sock)['message'], 'two')

    def test_wrong_magic_rejected(self):
        with self.assertRaises(ValueError):
            receive(FragmentedSocket(struct.pack('>II', 42, 100)))

    def test_oversized_frame_rejected_before_read(self):
        with self.assertRaises(ValueError):
            receive(FragmentedSocket(struct.pack('>II', MAGIC, MAX_FRAME + 1)))

    def test_disconnect_mid_frame(self):
        with self.assertRaises(ConnectionError):
            receive(FragmentedSocket(response()[:-2]))

    def test_truncated_protobuf_string(self):
        with self.assertRaises(ValueError):
            fields(b'\x22\x0ahello')

    def test_oversized_varint(self):
        with self.assertRaises(ValueError):
            fields(b'\x08' + b'\xff' * 11)

    def test_encrypted_frame_fails_explicitly(self):
        envelope = field(1, field(1, 1)) + field(2, b'nonce') + field(3, b'tag') + field(4, b'opaque')
        with self.assertRaisesRegex(ValueError, 'Encrypted'):
            receive(FragmentedSocket(struct.pack('>II', MAGIC, len(envelope)) + envelope))

    def test_command_name_and_full_text(self):
        wire = request(0, 'script_client', 'script_client R5H_Status("ticket")')
        inner = fields(fields(wire[8:])[4])
        self.assertEqual(inner[3], 0)
        self.assertEqual(inner[4], b'script_client')
        self.assertEqual(inner[5], b'script_client R5H_Status("ticket")')

    def test_outgoing_sequence_is_in_nested_header(self):
        wire = request(2, value='1', sequence=9)
        self.assertEqual(fields(fields(wire[8:])[1])[1], 9)

    def test_legacy_envelope_rejected_with_actionable_error(self):
        envelope = field(3, field(4, 'legacy'))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            receive(FragmentedSocket(struct.pack('>II', MAGIC, len(envelope)) + envelope))


class RouteTests(unittest.TestCase):
    def test_partial_source_cache_checks_map_camera_route_and_image_hash(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder)/'view.png'
            image.write_bytes(b'native capture')
            job = dict(source_map='mp_test',source_offset=[100,200,0],shots=[dict(origin=[1,2,3],angles=[0,90,0],fov=90),dict(origin=[4,5,6],angles=[0,0,0])])
            record = dict(map='mp_test',camera=dict(origin=[101,202,3],angles=[0,90,0],fov=90),path=str(image),sha256=hashlib.sha256(image.read_bytes()).hexdigest())
            saved = dict(route=job,captures=[record])
            self.assertEqual(harness.cached_source_captures(saved,job),[record])
            with self.assertRaises(ValueError):
                harness.cached_source_captures(dict(route=job,captures=[dict(record,map='mp_other')]),job)
            with self.assertRaises(ValueError):
                harness.cached_source_captures(dict(route=job,captures=[dict(record,camera=dict(record['camera'],fov=75))]),job)
            image.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                harness.cached_source_captures(saved,job)

    def test_phase_runner_world_offset(self):
        self.assertEqual(harness.source_origin([-6080, -1530.2, -773.9], [26000,19000,0]), [19920,17469.8,-773.9])

    def test_drop_off_identity(self):
        self.assertEqual(harness.source_origin([1,2,3], [0,0,0]), [1,2,3])

    def test_nonfinite_camera_rejected(self):
        with self.assertRaises(ValueError): harness.vector([1, float('nan'), 0])

    def test_console_injection_in_map_rejected(self):
        with self.assertRaises(ValueError): harness.map_name('mp_lobby;quit')

    def test_routes_have_unique_labels_and_valid_vectors(self):
        for path in (harness.HOME / 'routes').glob('*.json'):
            job = json.loads(path.read_text())
            self.assertEqual(len(job['shots']), len({s['name'] for s in job['shots']}))
            harness.map_name(job['source_map'])
            harness.map_name(job['target_map'])
            for shot in job['shots']:
                harness.vector(shot['origin']); harness.vector(shot['angles'])


class IsolationTests(unittest.TestCase):
    def test_missing_process_timestamp_cannot_authorize_stop(self):
        with patch.object(harness, 'process_stamp', return_value=None):
            self.assertFalse(harness.owned_alive({'pid':1234,'process_stamp':None}))

    def test_source_never_reused_as_profile(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(harness, 'SESSION', Path(folder)/'none'):
            with self.assertRaises(ValueError): harness.stage(folder, folder)

    def test_existing_unowned_profile_untouched(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(harness, 'SESSION', Path(folder)/'none'):
            source, profile = Path(folder)/'source', Path(folder)/'profile'
            source.mkdir(); profile.mkdir()
            (source/'r5apex.exe').write_bytes(b'game')
            sentinel = profile/'sentinel'; sentinel.write_text('keep')
            with self.assertRaises(ValueError): harness.stage(source, profile)
            self.assertEqual(sentinel.read_text(), 'keep')

    def test_configs_independent_and_restaging_does_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(harness, 'SESSION', Path(folder)/'none'):
            source, profile = Path(folder)/'source', Path(folder)/'profile'
            scripts = source/'platform/scripts/vscripts'; scripts.mkdir(parents=True)
            (source/'r5apex.exe').write_bytes(b'game')
            (scripts/'scripts.rson').write_text('original')
            playlist = source/'platform/playlists_r5_patch.txt'
            playlist.write_text('playlists { Playlists { dev_default { inherit survival_dev vars { visible 0 } } } }')
            assets = source/'paks'; assets.mkdir(); (assets/'test.rpak').write_bytes(b'asset')
            harness.stage(source, profile)
            (profile/'platform/scripts/vscripts/scripts.rson').write_text('changed')
            harness.stage(source, profile)
            self.assertEqual((scripts/'scripts.rson').read_text(), 'original')
            self.assertEqual((profile/'platform/scripts/vscripts/scripts.rson').read_text().count('_r5_map_harness.nut'), 1)
            self.assertEqual((assets/'test.rpak').read_bytes(), b'asset')
            self.assertNotIn('max_players 2', playlist.read_text())
            self.assertEqual((profile/'platform/playlists_r5_patch.txt').read_text().count('max_players 2'), 1)


if __name__ == '__main__': unittest.main()
