"""Make an uncompressed v8 RPak copy for extractors without ZSTD support."""
import argparse
import hashlib
import json
import struct
from compression import zstd
from pathlib import Path


def normalize_segments(data):
    """Recalculate in-memory allocation sizes from page alignment requirements.

    Matches RSX AllocateSegments; does not insert padding into the file payload.
    Only unpatched v8 packages are supported.
    """
    stream_size, optional_size, segment_count, page_count, patch_count = struct.unpack_from('<5H', data, 72)
    if patch_count:
        raise ValueError('Segment normalization does not support patched packages')
    segment_start = 128 + stream_size + optional_size
    page_start = segment_start + segment_count * 16
    if page_start + page_count * 12 > len(data):
        raise ValueError('Truncated segment/page tables')
    segments = [struct.unpack_from('<IIQ', data, segment_start + i * 16) for i in range(segment_count)]
    pages = [struct.unpack_from('<III', data, page_start + i * 12) for i in range(page_count)]
    def align(value, alignment):
        if alignment == 0 or alignment & (alignment - 1):
            raise ValueError('Invalid page or segment alignment')
        return (value + alignment - 1) & ~(alignment - 1)
    collections = [0] * 4
    changes = []
    for index, (flags, alignment, old_size) in enumerate(segments):
        kind = flags & 3
        start = align(collections[kind], alignment) if kind else 0
        cursor = start
        for segment_index, page_alignment, page_size in pages:
            if segment_index >= segment_count:
                raise ValueError('Page refers to invalid segment')
            if segment_index == index:
                cursor = align(cursor, page_alignment) + page_size
        new_size = cursor - start
        if old_size != new_size:
            struct.pack_into('<Q', data, segment_start + index * 16 + 8, new_size)
            changes.append(dict(segment=index, old_size=old_size, new_size=new_size))
        if kind:
            collections[kind] = cursor
    return changes


def decompress(source, target, normalize=False):
    if source.resolve() == target.resolve():
        raise ValueError('Output must differ from the original package')
    data = source.read_bytes()
    if len(data) < 128 or data[:4] != b'RPak':
        raise ValueError('Invalid or truncated RPak header')
    version, flags = struct.unpack_from('<2H', data, 4)
    compressed_size = struct.unpack_from('<Q', data, 24)[0]
    decoded_size = struct.unpack_from('<Q', data, 48)[0]
    if version != 8 or flags & 0x8300 != 0x8000:
        raise ValueError('Only ZSTD-compressed RPak v8 is supported')
    if len(data) != compressed_size or not 128 <= decoded_size <= 2**31:
        raise ValueError('Invalid RPak sizes')
    decoder = zstd.ZstdDecompressor()
    payload = decoder.decompress(data[128:], max_length=decoded_size - 128 + 1)
    if not decoder.eof or decoder.unused_data or len(payload) != decoded_size - 128:
        raise ValueError('Decoded length or ZSTD frame boundary mismatch')
    header = bytearray(data[:128])
    struct.pack_into('<H', header, 6, flags & ~0x8000)
    struct.pack_into('<Q', header, 24, decoded_size)
    result = header + payload
    changes = normalize_segments(result) if normalize else []
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result)
    report = dict(source=str(source.resolve()), output=str(target.resolve()),
                  source_sha256=hashlib.sha256(data).hexdigest(),
                  output_sha256=hashlib.sha256(result).hexdigest(),
                  compressed_bytes=len(data), decompressed_bytes=decoded_size,
                  segment_allocation_changes=changes,
                  note='Compression adapter only; RPak version and asset contents remain Apex v8.')
    target.with_suffix('.decompression.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--normalize-segments', action='store_true',
                        help='Recalculate allocation sizes for RSX on an unpatched package copy')
    args = parser.parse_args()
    decompress(args.source, args.output, args.normalize_segments)
