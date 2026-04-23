# Strata

Strata is a local-first document review and redaction-analysis tool for production review. This source tree is organized for an editable Flask backend, a localhost-hosted dark Web UI, and a Windows desktop shell based on WinUI 3 plus WebView2.

## Architecture

- `strata/`: backend services for extraction, OCR, search, exports, redaction detection, analytics, and API routes.
- `templates/` and `static/`: the review UI, including Index, Production, Redactions, help modal, preview dock, and dark design system.
- `desktop/Strata.Desktop/`: WinUI 3 desktop host source. The host starts the local Waitress-backed Flask app and points WebView2 at `http://127.0.0.1`.
- `packaging/`: runtime staging and MSIX-oriented packaging scripts for embedded Python and bundled OCR/conversion tools.
- `tests/`: smoke-level automated coverage for the Boolean query engine.

## Local Development

1. Install Python 3.11+ for development.
2. Install dependencies once:

```powershell
python -m pip install -r requirements.txt
```

3. Start Strata locally:

```powershell
python app.py
```

The local app runs only on `127.0.0.1:18741` using Waitress. The browser-launch path is for development only; the production Windows app uses the WinUI 3 host.

## Data Storage

Strata targets `~/Documents/Strata/` for mutable data:

- `datasets/`
- `exports/`
- `logs/`
- `cache/`

If that location is blocked by the local machine's policy, the app falls back to a writable local app-data location instead of crashing. You can force a specific location with `STRATA_DATA_ROOT`.

## Tool Resolution

The backend resolves bundled tools in this order:

1. Environment variable override (`STRATA_TESSERACT`, `STRATA_POPPLER_BIN`, `STRATA_LIBREOFFICE`)
2. Bundled repo/package paths under `tools/`
3. System `PATH`

Legacy Office files (`.doc`, `.xls`, `.ppt`) are converted through LibreOffice before extraction. In development, if LibreOffice is not available, Strata returns a clear conversion error instead of silently skipping the file.

## Analytics

Mixpanel support is built in with an anonymous device ID stored locally. Events currently emitted:

- `App Launched`
- `Index Built`
- `Search Run`
- `Production Search`
- `Production Export`
- `Redaction Scan Started`

Strata does not send document contents, snippets, paths, or extracted text. Disable analytics completely with:

```powershell
$env:STRATA_DISABLE_ANALYTICS = "1"
```

## Windows Desktop Host

The shipping architecture is:

- WinUI 3 desktop shell
- WebView2 host
- local Flask app bound to `127.0.0.1`
- Waitress for packaged runtime serving
- embedded Python staged into the app package
- bundled Tesseract, Poppler, and LibreOffice staged into the package layout

The package contents are intended to be read-only. User datasets and exports remain outside the package.

## Packaging Flow

Use the PowerShell scripts in `packaging/`:

```powershell
.\packaging\stage_runtime.ps1 `
  -EmbeddedPythonDir C:\tooling\python-embed `
  -TesseractDir C:\tooling\tesseract `
  -PopplerDir C:\tooling\poppler `
  -LibreOfficeDir C:\tooling\libreoffice
```

```powershell
.\packaging\build_msix.ps1 `
  -EmbeddedPythonDir C:\tooling\python-embed `
  -TesseractDir C:\tooling\tesseract `
  -PopplerDir C:\tooling\poppler `
  -LibreOfficeDir C:\tooling\libreoffice
```

The current script publishes the WinUI 3 host and stages the backend/runtime/tool layout for an enterprise MSIX/signing pipeline. The exact signed package generation step depends on your local Windows SDK, signing certificate, and Store/enterprise packaging setup.

## Tests

Run the search-engine smoke tests with:

```powershell
python -m unittest tests.test_search
```
