# Map comparison and release site

Open `dist/index.html` directly, or serve `site/dist/` with any static host.
The catalogue is embedded for local file access; there is no backend, account,
dependency installation, analytics or external asset request.
For the Codex browser or browsers that restrict local files, run
`./Run-MapSite.ps1` from the repo and open its printed local URL. This binds to
127.0.0.1 only. Close the preview with Ctrl+C; the saved site remains intact.

Register another map in `maps.json`, generate its matched harness captures,
then run from the workspace:

```powershell
python publish_comparison_site.py --snapshot 2026-10-12-area-survey --findings site/survey-findings.json
```

Capture sets are immutable. Use a new snapshot name after each repair. The build
selector keeps earlier captures available for comparison. `--drop-off` and
`--phase-runner` override the input gallery paths for a development build.
Use `--maps overflow party-crasher firing-range` to update only those previews;
other published maps and their current snapshots are preserved exactly. The
three previews retain their first 0.1.0 captures and add eight matched 0.2.0
views in **Source features and lighting**. They are labeled **Early preview**
and do not imply the same fidelity or mode coverage as the two older ports.
The 0.3.0 **Water, haze and glow** snapshot adds campaign water, source fog,
HDR masks and Party Crasher advertisements. The rejected vertex-colour
candidate is also retained, clearly labeled, for comparison with the correction.
Only whitelisted camera metadata and hash-verified PNGs leave private harness
output. Generated `dist/` is deliberately retained as the portable site.
The current export includes **Scenery recovery** with 12 Drop-Off views and
11 Phase Runner views. These are the verified 0.10.0 / 1.6.0 candidates at
97.06% / 97.04% of native world index capacity. The archived native PNG paths
retain previous comparison snapshots. R5R references are hash-verified saved
captures; the new Northstar views use the same camera poses. The western
Phase Runner bend keeps the known black source-reference limitation in its
reviewed notes. Use a new snapshot label for further changes.

`--findings` accepts plain-text observations keyed by map ID and shot name.
The viewer renders these as text, not HTML. Do not change notes in an archived
snapshot; create a new snapshot if the observations or captures change.

Party Crasher's **Edges and rooftops** snapshot shows the 0.4.0 boundary/facade
and rooftop recovery in six matched native/R5R views. The two close-up roof
views include source foliage still omitted from the port. Exterior diagnostic
camera sessions temporarily remove safety-trigger entities in the owned game;
gameplay validation reloads the original map and checks all 69 safety triggers.

Set a map's `download` to its public release URL when ready. Runtime ZIPs remain
separate from the site and retain the existing clean Northstar mod packaging.
Alternatively, append `--include-downloads` after packaging current versions:
the exporter verifies the clean player ZIP hashes and copies them into the
static site's `downloads/` directory. This optional release export adds roughly
a gigabyte with the current two maps; the comparison-only site stays compact.
Publish the static directory once the release catalogue is ready; this task
does not deploy the site. Keep original asset attribution in the footer.
