Current UI and ambulance behavior: [DISPATCH_WORKSPACE.md](DISPATCH_WORKSPACE.md). The explicit depot-fleet workflow supersedes earlier descriptions of preset civilian missions and GA redeployment.

# Pygame frontend optimization

The native desktop client uses the existing shared Python API. No simulation decision logic was moved into the renderer.

## What improved

- Static map layers (roads, nodes, labels, heatmap) are cached and rebuilt when model values or view settings change. Routes, markers and selection remain live overlays.
- A shared text-surface atlas avoids repeated glyph rendering. It is bounded to 2,048 entries and 8 MiB, and resets with the font lifecycle.
- The render loop stays on the UI thread; HTTP route requests run in a separate worker and return through the UI mailbox. Stale or cleared route results are discarded. A city change invalidates the old comparison instead of continuously launching replacement requests.
- Polling starts even when the server is initially offline, retries with capped backoff, and refreshes healthy connections every second. Refresh wakes the existing poller rather than creating another thread. Repeated identical connection errors are suppressed.
- Separate HTTP sessions keep slow polling and route requests from holding the mutation request lock. Async workers report exceptions and restore availability.
- Snapshots reject older revisions, including road changes at the same simulation step, and retired simulation IDs. Unchanged graphs retain their buffers; expensive validation does not repeat for heartbeat-only updates. Edge inspection uses an index.
- Ambulance validation shares one shortest-path tree per ambulance across civilian targets and caches unchanged results.
- Resizing uses a fixed logical canvas with aspect-preserving scaling and translated pointer coordinates. All nine screens and controls remain aligned; unusual aspect ratios use letterboxing. This is scaling, not responsive panel reflow.
- Unfocused windows render at 15 FPS instead of 60; minimized windows skip rendering. Live operations continue in the background.
- Global Play, Step and Help controls work across screens. Keyboard shortcuts respect text input. Playback pauses for a backend optimization job to avoid cancelling it accidentally.
- Ambulance Center now has real Optimize / Pause / Resume / Reset controls and backend generation progress. It runs one optimization run per start.
- Dashboard shows backend coverage, connectivity, dead zones and mission status. Heatmap coverage highlights backend-calculated residential coverage. A white medical cross identifies the active rescue team separately from ambulance staging positions.
- Metrics exports backend CSV to the project's `exports/` directory. Logs show newest events first; multiline debug messages are condensed to avoid overlapping rows. Full structured history remains in the backend.
- City Map inspector scrolling now clips correctly. God Mode status clears on leaving that screen. Shutdown closes pollers, workers, sessions and Pygame without terminating the caller with `sys.exit()`.
- `--auto-backend` respects the requested local HTTP host and port and uses a hidden child process on Windows.

## Controls

| Action | Control |
| --- | --- |
| Play / pause | Space or top Play button |
| Single step | N or top Step button |
| Change screen | 1–9 or navigation rail |
| Fit map | F or screen Fit button |
| Refresh | F5 or Ctrl+R |
| Help | F1 |
| Stop playback / dismiss help | Escape |
| Zoom at pointer | Mouse wheel |
| Pan | Right mouse drag |
| Select source/destination | Click map nodes in Route Lab |

Keyboard playback/navigation shortcuts do not intercept focused text fields. Closing the window exits. Escape pauses rather than quitting immediately.

## Run

From the inner project folder:

```powershell
python frontend-2d-pygame/main.py --auto-backend
```

To use an existing backend:

```powershell
python frontend-2d-pygame/main.py --backend-url http://127.0.0.1:8000 --screen city_map
```

## Measurement and checks

The reproducible offscreen benchmark uses a 225-node, 420-road static map over 300 frames. On this machine, median map draw time fell from **2.3499 ms** to **0.2314 ms**, about **10.2× faster**. The final measured p95 was **0.3335 ms**. This measures unchanged-map drawing only; it does not claim a tenfold improvement in whole-application FPS. Pan, zoom, road changes and new heatmaps rebuild the cached layer.

```powershell
python frontend-2d-pygame/tools/benchmark_renderer.py
python frontend-2d-pygame/tools/render_screens.py
python frontend-2d-pygame/tools/live_smoke.py
python -m pytest tests frontend-2d-pygame/tests -q
```

The render tool writes all nine screenshots to `frontend-2d-pygame/artifacts/`. The live smoke tool starts an isolated API on port 8104, exercises native connection, step, asynchronous route validation, real optimization and CSV export, renders all nine screens, then stops its own server. It requires port 8104 to be free. Tests render offscreen using SDL's dummy driver; they do not establish performance on every graphics driver or display.

Final verification: **83 tests passed** across the backend and desktop suites. The separate live native/API integration smoke test also passed connection, stepping, route validation, optimization completion, CSV export and all nine screen renders.
