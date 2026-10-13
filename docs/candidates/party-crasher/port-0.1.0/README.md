# Party Crasher 0.1.0 — initial Northstar preview

Extract `ArenaPartyCrasher` into `Titanfall2/R2Northstar/mods/`, enable it and restart.
Every player needs the same version. Launch with `mp_gamemode ps` followed by
`map mp_party_crasher` (or choose `ffa` for Free For All).

Initial native preview for Pilots vs Pilots and Free For All. Recovers 1,855 static placements and uses 87.86% of this engine's measured per-view world index capacity.

Native checks cover both pilot modes, supported/clear spawns, both team start
selections in PS, viewing angles near those starts, postmatch return to lobby,
and a stock-map reload. Tests used one local client; multiplayer performance
and balance are not established. Scenery is baked into native world meshes.
A longer shared Overflow/Party Crasher session crashed during repeated mode
changes. The cause is unresolved. Restart between new preview maps and avoid
repeated mode cycling in the same process.

This is less complete than Phase Runner and Drop-Off. Decorations, dense
foliage, distant scenery and some materials are missing. Authored lower LODs,
1024-pixel texture caps, approximate sky mapping, coarse direct lightmaps and
point approximations of spot lights reduce fidelity. Animated/emissive source
materials use static approximations. Apex interactions, weapon stations,
training dummies, AI navigation, Titan modes, CTF/Hardpoint/Fastball objectives,
intro and evac are not supplied. Source safety volumes are retained, but each
hazard has not been physically exercised. The Firing Range minimap is generated;
the arena minimaps use original overview artwork. Enable only the preview map
you are testing to limit resident texture packs; all five ports together have
not been validated. Original game assets remain their creators' work.

Detailed counts and every omitted source placement are recorded in the repo's
`docs/candidates/party-crasher/port-0.1.0/`.
