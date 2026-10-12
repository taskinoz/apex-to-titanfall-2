# Drop-Off 0.10.0 for Northstar

Adds 366 original scenery placements. Uses 97.06% of the native world index capacity with no added dynamic entities. Existing minimaps, gameplay, collision exclusions and tunnel visibility are preserved. See SCENERY_FILL.md for measured budgets and validation. AI navigation remains incomplete.

## Previous release notes

# Drop-Off 0.9.0 for Northstar

Preview for Skirmish, Pilots vs Pilots and Free For All. Adds the original Apex minimap with Titanfall radar scaling. Includes Northstar banners, frozen Apex displays and recovered RGB paint. Preserves equipment supports, lighting-chart fixes, banner supports, room closures, safety volumes and two zipline pairs. Some props, animated materials and source runtime colouring remain incomplete. Intro and evac are disabled.

The minimap uses the original Apex artwork with corrected native radar scale. See MINIMAPS.md for conversion details and checks.

## Previous release notes

# Drop-Off 0.8.0 for Northstar

Preview for Skirmish, Pilots vs Pilots and Free For All. Adds Northstar banner artwork and frozen Apex display colours, with recovered RGB paint on pipes, cargo and structural surfaces. Preserves equipment supports, lighting-chart fixes, banner supports, room closures, safety volumes and two zipline pairs. Some props, animated materials and source runtime colouring remain incomplete. Intro and evac are disabled.

The texture pass is checked with matched native screenshots and same-process
map reloads. See BANNER_DISPLAYS.md for the source channels, exact scope and
limitations. Geometry submission budgets, collision, visibility, world lights
and character probes remain unchanged.

## Previous release notes

# Drop-Off 0.7.0 for Northstar
Restores authored RGB paint on 190,916 existing vertices with native
Titanfall colour-aware PBR shaders. Geometry, collision, lighting, visibility
and gameplay retain the prior working build. See VERTEX_PAINT.md and the repo
comparison site for baseline and repaired native views.

The prior release notes below describe the preserved gameplay and earlier
validation; the paint repair is documented above.


Port of Apex map `mp_rr_arena_composite`. Extract `ArenaComposite` into
`Titanfall2/R2Northstar/mods/`, enable it and restart. Server and clients need
the same version. Launch with `map mp_arena_composite`.

Supports Skirmish, Pilots vs Pilots and Free For All. Opposing teams have native
team starts. Intro and evac are disabled; other modes lack full objectives or
AI navigation. `composite_where` prints your position.

Restores missing equipment supports and stacked tank containers, removes the
orphan light and rebakes control-entrance wall panels. Source collision remains
unchanged. Includes the prior banner supports, screens, loading art, safety
volumes, native character lighting and source zipline pairs.

See `local-repairs-2026-10-07.md`, `MISSING_CONTENT.md` and `CONVERSION.md` for
capacity, omissions and reproduction. Original assets remain the work of their
respective creators.