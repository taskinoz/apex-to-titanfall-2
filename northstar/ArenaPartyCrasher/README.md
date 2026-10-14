# Party Crasher 0.4.0

Restores 380 exact-source placements: 168 facade sections, all 42 large boundary rocks, 42 rooftop vents and all 128 solar panels. Uses 97.66% of native world index capacity, with no additional gameplay entities. Existing lighting, collision, safety areas, spawns, loading screen and minimap are retained. Some dense window modules, roof foliage, animated advertisements and layered terrain materials remain incomplete. AI navigation and Titan modes are not supplied. Restart between previews; repeated mode cycling has an unresolved earlier failure.

The independent audit passed 2,930 checks. Native tests verified 29 new source collider contacts, clear supported team spawns, postmatch return, stock Coliseum loading and Party Crasher reloading. Eight native edge/roof views were captured from the exact mounted payload. Camera-only diagnostic runs temporarily removed safety trigger entities in the isolated process; gameplay checks restored all 67 out-of-bounds and two hurt triggers by reloading the unmodified map. The previous FFA registration and entities are byte-identical; this round exercises PS. No multiplayer FPS, AI capacity or all-five-map stress certification is implied.

Baseline rollback is retained on the build drive under `party-crasher/before-0.4.0/`. The rejected facade-first candidate and its receipts are also retained separately.

Reproduce with `recover_party_structure.py plan`, `materials`, `append`, then `verify_party_structure.py`, both harness surveys and `verify_party_structure_runtime.py`. Set APEX_PORT_WORK to the owned build workspace. The append is guarded against reapplication; restore the immutable snapshot before rebuilding.
