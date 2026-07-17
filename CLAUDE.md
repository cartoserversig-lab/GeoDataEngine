# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

GeoData Engine is a Python geospatial engine that turns a simple geographic extent (a commune, via its INSEE code) into a ready-to-use GIS project: it searches, downloads, decompresses, quality-checks, reprojects, clips, and compiles geographic data into a structured database (GeoPackage + ArcGIS File Geodatabase), with full per-layer metadata/provenance tracking. It is the technical foundation for building a commune's digital twin.

The governing spec is `../Projet/CDC_GDE.pdf` (cahier des charges). `core/workflow.py::run_pipeline`'s docstring maps directly to the CDC §5.3 pipeline stages: Emprise → Identification → Téléchargement → Décompression → Contrôle qualité → Reprojection → Découpage → Organisation → Création GeoDatabase → Projet SIG final. When making architectural decisions, check the CDC first — several existing design choices (e.g. GeoPackage as primary DB format, the `core/`, `download/`, `processing/`, `database/` split) come directly from it, and diverging from it (e.g. the current `data/raw` + `data/processed` split vs. the flat tree the CDC originally sketched) has generally been a deliberate, discussed decision, not an oversight.

`README.md`, `ARCHITECTURE.md`, and `ROADMAP.md` describe the original scaffold/intent but have not been kept in sync with implementation (e.g. `ARCHITECTURE.md` still lists `download/ign.py`, which was split into per-source connectors instead). Trust the actual code over these docs for current state.

## Critical: data/ lives outside this repo

This repo (`GeoDataEngine/`) contains only code. All generated/downloaded data lives in a **sibling** `data/` directory (`../data/` relative to repo root), which is *not* version-controlled. Every default path in the codebase reflects this via `Path(__file__).resolve().parents[2] / "data" / ...` (two levels up from a file in e.g. `download/` or `processing/lidar/` reaches the repo root, then one more `data/`). When adding a new module that needs a default data path, follow this exact pattern rather than assuming `data/` is inside the repo.

Within `data/`:
- `data/raw/{vector,raster}/<theme>/` — as-downloaded (and reprojected-in-place if needed) data. Never hand-edit; connectors re-fetch and overwrite here. Lidar raw tiles (`raw/raster/lidar/*.laz`) are the one exception treated as immutable once downloaded — processing never touches them.
- `data/processed/{vector,raster}/<theme>/` — clipped-to-commune, ready-to-use data. Mirrors the raw/ theme subfolder structure.
- `data/processed/database/projet.gpkg` and `projet.gdb` — compiled multi-layer databases (see `database/geopackage.py`, `database/filegdb.py`).
- `data/metadata/metadata.json` — flat list of per-file provenance records (see `database/metadata.py` below).
- `data/logs/controle_qualite_<timestamp>.txt` — one report per quality-control run.
- `data/configuration/entites_exemple.csv` — the entity list driving a pipeline run (columns: `nom_entite;type_entite;code_insee;bbox` — `bbox` optional, auto-derived from the commune boundary + buffer if blank).
- `data/configuration/settings.toml` — global pipeline parameters (see below).

## Commands

Environment (conda/conda-forge, required for the GDAL/Fiona/Rasterio/PDAL binary stack):
```bash
conda env create -f environment.yml
conda activate geodataengine
```
One-time per clone, so notebook outputs are never committed:
```bash
nbstripout --install --attributes .gitattributes
```

Run the full test suite (from `GeoDataEngine/`; `pytest.ini` sets `pythonpath = .` and `testpaths = tests`):
```bash
pytest -v
```
Run a single test:
```bash
pytest tests/test_clipping.py::test_clip_to_boundary_with_buffer -v
```

Run the pipeline end-to-end:
```bash
python main.py --csv data/configuration/entites_exemple.csv --verbose
```
Notable flags (each overrides `settings.toml`, which overrides the hardcoded default — see `main.py`'s 3-tier precedence via `argparse.BooleanOptionalAction` + `None` defaults): `--include-lidar`, `--include-ortho`, `--classify-lidar-from-vectors`, `--buffer-decoupe`, `--buffer-telechargement`, `--auto-reproject`/`--no-auto-reproject`.

Launch the desktop GUI:
```bash
python gui.py
```

Execute a demo notebook in place (used to visually/functionally verify a feature before commit):
```bash
jupyter nbconvert --to notebook --execute --inplace notebook/NN_name.ipynb --ExecutePreprocessor.kernel_name=geodataengine
```

## Architecture

- **`core/config.py`** — `Entity`/`Settings` dataclasses, `load_entities` (CSV parsing), `load_settings` (TOML parsing). `TARGET_CRS = "EPSG:2154"` is a fixed module-level constant, deliberately *not* part of `Settings` or configurable — the whole pipeline (validation, reprojection, clipping) assumes it everywhere.
- **`core/workflow.py`** — the orchestrator. `download_all_layers` calls every connector; `run_quality_checks` runs CDC §5.1 controls + optional auto-reprojection + writes the log; `process_lidar` chains the six Lidar processing steps; `run_pipeline` ties it all together per entity in the CSV and returns `(geopackage_path, filegdb_path)`.
- **`core/project.py`** — stub, not yet implemented. Intended (per CDC §9/§11) to manage a project's lifecycle/output directory once a desktop UI exists; currently all paths are hardcoded relative to the repo via the `parents[2]` pattern above.
- **`download/`** — one connector module per data source (`bd_topo.py`, `lidar.py`, `ortho.py`, `osm.py`, `copernicus.py`, `limites_administratives.py`, `ban.py`, `cadastre.py`, `reseaux.py`, `risques.py`, `zones_protegees.py`). Vector connectors share `wfs_client.py::fetch_wfs_features` (paginated WFS client + datetime-column normalization workaround for a pyogrio/GDAL write bug). Every connector calls `database/metadata.py::record_layer_metadata` after writing a layer.
- **`processing/`** — `clipping.py` (vector `gpd.clip` + raster `rasterio.mask`, both to commune boundary + buffer), `reprojection.py` (CRS control/fix, dispatches by extension), `validation.py` (CDC §5.1 checks; iterates every layer of multi-layer GeoPackages via `fiona.listlayers` — a plain `gpd.read_file` would silently only see the default layer).
- **`processing/lidar/`** — PDAL-based point-cloud pipeline, one file per stage: `merge.py` (decompress+merge LAZ/COPC tiles), `clip.py` (`filters.crop` to boundary+buffer), `colorize.py` (`filters.colorization` from an orthophoto, forces LAS point format 7 for RGB support), `rasterize.py` (`compute_mnt`/`compute_mns`/`compute_mnh`, the last via `filters.hag_nn`), `classify.py` (`filters.overlay` reclassifies points from vector polygons — bâti/hydro/végétation). `pipeline.py` holds the shared `run_pipeline(stages) -> (pdal.Pipeline, num_points)` JSON-pipeline runner and `LidarProcessingError`. **Performance note:** `filters.overlay` in `classify.py` is expensive — roughly O(points × layers) with real-world cost on the order of minutes per hundred-thousand points; running it un-clipped or on a full commune can take hours. It is therefore gated behind `Settings.classify_lidar_from_vectors` (default `False`) rather than always run. `converter.py`, `reader.py`, `stats.py` are stub files (scaffolded, not yet implemented).
- **`database/geopackage.py` / `database/filegdb.py`** — compile every `data/processed/vector/**/*.gpkg` into one multi-layer `projet.gpkg` / `projet.gdb`. FileGDB feature classes only accept a single geometry type (unlike GeoPackage), so `filegdb.py` auto-splits mixed-geometry source layers (common on OSM-derived infrastructure layers) into `<layer>_point`/`<layer>_ligne`/`<layer>_polygone`.
- **`database/metadata.py`** — `record_layer_metadata` appends a provenance record (source, producteur, date, CRS, résolution, traitements) to `metadata.json`. `record_processing(input_path, output_path, traitement, ...)` is the chaining helper used by every processing step (clip, reproject, each Lidar stage): it looks up the record for `input_path` via `find_metadata_record`, inherits source/producteur/CRS/resolution, and appends `traitement` to the accumulated `traitements_appliques` list for a new record at `output_path`. Path comparisons are done on `Path.resolve()`, not raw strings — a relative vs. absolute path for the same file used to silently break the chain. Any processing function taking a `metadata_dir` parameter should be called with a `tmp_path`-based value in tests, or it will write to the real `data/metadata/metadata.json`.
- **`interface/desktop/`** — minimal PySide6 desktop app (CDC §11), launched via `python gui.py` at the repo root. `main_window.py` holds the form (entity name/code INSEE/optional bbox instead of hand-editing a CSV, output dir, buffers, the same boolean flags as `main.py`) and writes a one-row temp CSV consumed by `run_pipeline` — the GUI has no separate entity model, it just drives the same CLI-facing API. `worker.py::PipelineWorker` runs `run_pipeline` in a `QThread` so the window doesn't freeze during multi-minute/hour runs; `logging_bridge.py` relays every `logging` record (from any module, unchanged) to the window's log panel via a Qt signal — nothing in `core`/`download`/`processing`/`database` needs to know the GUI exists. `core/project.py` (project lifecycle/output-dir management) is still an unimplemented stub; the GUI works around its absence by writing straight to a user-chosen `data_dir`.
- **`tests/`** — mirrors the module structure (`test_clipping.py`, `test_metadata.py`, etc.). Network-only connectors (`download/*.py`) generally have no dedicated unit tests — they're verified live via the notebooks instead.
- **`notebook/`** — one numbered demonstration notebook per feature (`NN_description.ipynb`), each executed against real APIs/data and checked for `"output_type": "error"` before being considered done. Outputs are stripped by `nbstripout` at commit time (configured via `.gitattributes`), so notebooks are tiny in git despite being large on disk.

## Key conventions

- Two buffers are semantically distinct and never conflated: `buffer_telechargement` (expands the *download* bbox when auto-derived from the commune boundary, default 250 m) vs. `buffer_decoupe` (used when *clipping* processed layers to the boundary, default 50 m).
- Every processing/download function that writes a file it wants tracked accepts a `metadata_dir` parameter defaulting to `database.metadata.DEFAULT_METADATA_DIR`; thread this through rather than hardcoding metadata calls.
- Vector connectors treat "0 features returned, no error" as a legitimate, expected outcome for sparse/inapplicable layers (e.g. a commune with no water body) — not a bug to fix.
- `data/` lives under OneDrive sync on this machine. OneDrive (Files On-Demand) marks folders it has just synced as read-only, which breaks a naive `shutil.rmtree` on any *directory-based* output re-created across runs (confirmed on `projet.gdb`, `PermissionError [WinError 5]`, `Attributes: ReadOnly, ReparsePoint`) even with nothing else holding it open. `database/filegdb.py::_clear_readonly_and_retry` is the fix pattern (an `onerror` callback for `shutil.rmtree` that clears `stat.S_IWRITE` and retries) — apply the same pattern to any new code that deletes/replaces a directory under `data/`.
