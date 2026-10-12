> Historical stage notes. For the current 1.0.0 state, use README.md and docs/conversion/APEX_TO_TITANFALL2.md. Earlier counts and validation flags below describe that stage.

# Phase Runner map presentation — 0.1.37

The map command is now `map mp_phase_runner`. Its displayed name is
`Phase Runner`, with an all-caps token and a localized description.
UTF-16 localization resources cover English, French, German, Italian,
Japanese, Mexican Spanish, Polish, Portuguese, Russian, Spanish,
Traditional Chinese, Simplified Chinese and Korean. The proper name is
retained across languages.

The loading screen and lobby image use the original 2,560 × 1,440 Phase
Runner artwork from the user's local Apex installation. No artwork pixels
are edited; the image is encoded as a resident BC7 sRGB texture. Three
native loading materials and three UI atlas image names cover widescreen,
standard and lobby lookups for the renamed map.

The loading material's shader, render states, samplers and constant buffer
are derived from the locally installed Titanfall 2 Coliseum loading screen.
All material GUIDs, atlas names, dimensions, texture bindings and common
shader dependency are verified. The presentation RPak loads after common,
and the renamed map's loading RPak alias resolves to it.

The renamed map loads on an isolated native dedicated server without
script errors. This verifies map registration and scripts; it does not
render the client loading screen, lobby image or localized menu text.
Check those after restarting Northstar.
