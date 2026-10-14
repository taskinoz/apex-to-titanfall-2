# Diagnostic failures retained for Party Crasher 0.4.0

The accepted map is not a long-session or multiplayer certification.

- The first facade-first candidate restored 270 objects in 73,910 triangles.
  It was superseded by 380 placements in 72,590 triangles, prioritizing complete
  large boundary-rock and rooftop arrays. Its receipt is retained on the build
  drive under `structure-recovery-facade-candidate`.
- Remote camera poses crossed original out-of-bounds and hurt volumes. Some
  captures killed the protected test player; those captures were rejected.
  Final exterior camera runs temporarily removed both trigger classes only in
  the isolated runtime. The native gameplay test reloaded the original map,
  checked 67 out-of-bounds plus two hurt entities, and passed normal spawn,
  collision, postmatch and reload checks.
- A prolonged native diagnostic session reported an unregistered `goalState`
  in `PlayerEarnMeter_DisableGoal` / `EarnMeterMP_PlayerLifeThink`, then an access
  violation during shutdown. Cause and relationship to earlier mode-cycling
  failures remain unisolated. A later fresh process completed the eight-view
  survey without logged errors; its subsequent normal-speed gameplay test
  passed both teams, 29 collider contacts, postmatch lobby, stock Coliseum and
  Party Crasher reloads. These passes do not erase the longer failed run.
- One original R5R reference launch failed with `Connection to server overflowed
  (code:vulkan)`. A fresh owned launch captured both rooftop reference views.
- Running the two games together caused a validation launch failure; another
  all-five-map attempt reported a texture-allocation error (`8007000e`). The
  cause is not isolated. Final tests ran the games serially and included Party
  Crasher, Drop-Off and the shared UI in the native test profile. The older
  all-five-map UI-atlas proof remains a historical result, not a new stress
  certification for 0.4.0.

Private run evidence remains in the ignored harness output. Accepted binary,
native-contact and installation hashes are summarized in `validation.json`.
