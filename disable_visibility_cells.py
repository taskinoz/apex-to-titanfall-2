"""Send every point to the all-visible cell, so build_visibility_cells.py's cells no longer cull anything.

The cells have no portals (build_visibility_cells.py), and Titanfall culls entities by cell as well as world objects:
on Thermal Station 0.2.0's candidate, the ropes (move_rope/keyframe_rope) in another cell than the camera were not
drawn, and pointing the cell BSP at the all-visible cell brought them back (5 November 2026). Players are entities
too, so a player in another cell could be invisible. Retail maps connect their cells with portals; until the cells
stage writes portals, ports keep one all-visible cell.

Only the cell BSP (0x6A) changes: one leaf, the last cell, whose access tree holds every object.

  python disable_visibility_cells.py <package>
"""
import json
import os
import struct
import sys
from pathlib import Path

from repair_preview_index_padding import read_lumps
from compact_preview_bsp import compact

REPORT = 'visibility-cells-disabled.json'


def disable(package):
    package = Path(package); bsp = next((package/'mod/maps').glob('*.bsp'))
    l = read_lumps(bsp, (0x6a, 0x6b)); cells = len(l[0x6b])//8
    temp = bsp.with_suffix('.cells-off.bsp'); compact(bsp, temp, {0x6a: struct.pack('<iI', -1, cells-1)}); os.replace(temp, bsp)
    report = dict(cells=cells, every_point_in_cell=cells-1, previous_cell_bsp_nodes=len(l[0x6a])//8,
                  reason='Cells without portals hide entities (ropes, players) outside the camera cell')
    (package/REPORT).write_text(json.dumps(report, indent=2)+'\n'); print(json.dumps(report))


if __name__ == '__main__':
    disable(sys.argv[1])
