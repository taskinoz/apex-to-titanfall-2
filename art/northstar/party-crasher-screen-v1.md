# Party Crasher Northstar screen, version 1

Created 18 October 2026 with the built-in imagegen tool. The project’s
`northstar-banner-v1.png` served as the style and emblem reference. The new
landscape artwork is saved beside this document as
`party-crasher-northstar-screen-v1.png`.

The white Titan emblem follows the same Northstar launcher reference and MIT
license recorded in `README.md` and `NORTHSTAR-LICENSE.txt`. This is community
artwork and does not imply endorsement.

## Generation prompt

Use case: ads-marketing. Create a brand NEW landscape 16:9 flat digital billboard
texture for an in-world screen in the Titanfall 2 conversion of Party Crasher.
The attached vertical Northstar banner is a STYLE AND EMBLEM REFERENCE, not an
edit target. Recompose the visual identity into a polished horizontal screen
design: large crisp white Titan silhouette inside a purple/navy angular
hexagonal crest on the left, exact bold white text "NORTHSTAR" occupying the
broad right half. Preserve the recognisable Titan silhouette from the reference,
with the two raised shoulder pods, narrow arms, and sturdy legs. Navy background,
vivid violet geometric industrial panels, thin cyan circuit-like accents and
restrained chevrons, subtle luminous screen detail. The screen should feel
cohesive with Party Crasher's vibrant futuristic resort advertising while
clearly matching the Drop-Off Northstar banner family. High contrast, readable
at a distance, generous 8% safe margins, balanced generous negative space around
the wordmark. Edge-to-edge opaque graphic. Front-facing texture artwork only:
no photographed screen, no physical frame, no environment, no perspective, no
mockup, no folds, no baked scene illumination, no tiny labels, no extra words or
logos. Output landscape 16:9, preferably 1920x1080 or higher.

## Map texture integration

`party_crasher_northstar_screen.py` replaces the existing placeholder panel in
`oasis_signs_ad_atlas_01`. It retains the atlas dimensions, full mip chain and
BC3 sRGB header. Compressed blocks outside the panel are copied unchanged from
the accepted 0.6.3 atlas. The small mip levels necessarily combine neighboring
atlas regions as before. Existing geometry, UVs, collision, lighting, scripts,
materials and UI atlas inventory remain unchanged.

The atlas region is identified by the previous recovery receipt rather than a
new heuristic. The high-resolution original is retained for future textures;
the game samples the existing 1024-square atlas, so the screen panel itself is
approximately 391 by 217 texels.
