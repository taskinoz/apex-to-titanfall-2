"""Inventory Respawn map inputs without modifying game files."""
import argparse
import json
import struct
from pathlib import Path

HEADER_SIZE = 16 + 128 * 16


def inspect_bsp(path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(HEADER_SIZE)
    if len(header) != HEADER_SIZE or header[:4] != b'rBSP':
        raise ValueError('Not a complete little-endian Respawn BSP header')
    version, revision, last_lump = struct.unpack_from('<3I', header, 4)
    if last_lump != 127:
        raise ValueError(f'Unexpected last lump index: {last_lump}')
    lumps = []
    problems = []
    for index in range(128):
        offset, length, lump_version, four_cc = struct.unpack_from('<4I', header, 16 + index * 16)
        sidecars = [p for p in (path.with_name(f'{path.name}.{index:04x}.bsp_lump'),
                               path.with_name(f'{path.name}.{index:04x}.bsp_lump.client')) if p.is_file()]
        if not length and not sidecars:
            continue
        external = bool(sidecars or (length and (offset >= size or version >> 16 or (offset == 0 and size == HEADER_SIZE))))
        if external and not sidecars:
            problems.append(f'Lump {index:04x}: external data missing')
        elif length and not external and (offset < HEADER_SIZE or offset + length > size):
            problems.append(f'Lump {index:04x}: invalid byte range')
        lumps.append(dict(index=index, offset=offset, length=length, version=lump_version,
                          four_cc=four_cc, external=external,
                          sidecars=[str(p.resolve()) for p in sidecars]))
    return dict(path=str(path.resolve()), bytes=size, version=[version & 65535, version >> 16],
                revision=revision, lumps=lumps, problems=problems,
                entity_files=[str(p.resolve()) for p in sorted(path.parent.glob(path.stem + '_*.ent'))],
                playable_port=False)


def inventory(root):
    maps, errors = [], []
    for path in sorted(root.rglob('*.bsp')):
        try:
            maps.append(inspect_bsp(path))
        except (OSError, ValueError) as exc:
            errors.append(dict(path=str(path), error=str(exc)))
    return dict(root=str(root.resolve()), maps=maps, errors=errors,
                vpk_indexes=[str(p.resolve()) for p in sorted(root.rglob('*_dir.vpk'))],
                asset_packages=[str(p.resolve()) for p in sorted(root.rglob('*.rpak'))],
                note='Inventory only. No BSP conversion or game installation changes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Extracted maps folder or R5Reloaded installation')
    parser.add_argument('--output', type=Path, default=Path('map-inventory.json'))
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error('Input folder does not exist')
    args.output.write_text(json.dumps(inventory(args.root), indent=2), encoding='utf-8')
    print(f'Inventory saved to {args.output.resolve()}')
