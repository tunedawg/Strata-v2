# -*- mode: python ; coding: utf-8 -*-
# Universal Search — PyInstaller spec (pywebview edition)

import os, sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
HERE = os.path.dirname(os.path.abspath(SPEC))

# ── Bundle Tesseract if present locally ──────────────────────────────────────
tesseract_dir    = os.path.join(HERE, "tesseract")
bundle_tesseract = os.path.isdir(tesseract_dir) and os.path.isfile(os.path.join(tesseract_dir, "tesseract.exe"))
if bundle_tesseract: print(f"[spec] Bundling Tesseract from: {tesseract_dir}")
else:                print("[spec] No local tesseract/ — OCR requires user install")

# ── Bundle Poppler if present locally ────────────────────────────────────────
poppler_bin    = os.path.join(HERE, "poppler", "bin")
bundle_poppler = os.path.isdir(poppler_bin) and os.path.isfile(os.path.join(poppler_bin, "pdftoppm.exe"))
if bundle_poppler: print(f"[spec] Bundling Poppler from: {poppler_bin}")
else:              print("[spec] No local poppler/bin/ — PDF-to-image unavailable")

# ── Data files ────────────────────────────────────────────────────────────────
datas = [("templates", "templates")]
if bundle_tesseract: datas.append((tesseract_dir, "tesseract"))
if bundle_poppler:   datas.append((poppler_bin, "poppler/bin"))

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden_imports = [
    # pywebview
    "webview", "webview.platforms", "webview.platforms.winforms",
    "webview.platforms.cocoa", "webview.platforms.gtk",
    "clr", "pythonnet",
    # PDF
    "pdfplumber", "pdfminer", "pdfminer.high_level", "pdfminer.layout",
    "pdfminer.converter", "pdfminer.pdfinterp", "pdfminer.pdfdevice",
    "pypdf", "pypdf.generic",
    # OCR
    "pytesseract", "PIL", "PIL.Image", "PIL.ImageDraw", "pdf2image",
    # Office
    "docx", "docx.oxml", "docx.oxml.ns", "pptx", "pptx.util",
    "openpyxl", "openpyxl.styles", "openpyxl.utils", "xlrd",
    # Email
    "email", "email.utils", "email.header", "extract_msg",
    # Reports
    "reportlab", "reportlab.lib", "reportlab.lib.pagesizes",
    "reportlab.platypus", "reportlab.lib.styles",
    # Stdlib
    "pickle", "threading", "pathlib", "zipfile", "io", "shutil",
    "xml.etree.ElementTree", "charset_normalizer", "cryptography",
]

for pkg in ("pdfminer", "pdfplumber", "reportlab", "openpyxl", "webview"):
    hidden_imports += collect_submodules(pkg)

extra_datas = []; extra_binaries = []
for pkg in ("pdfplumber", "pdfminer", "reportlab"):
    d, b, h = collect_all(pkg)
    extra_datas += d; extra_binaries += b; hidden_imports += h

datas += extra_datas

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "scipy", "IPython", "jupyter",
               "flask", "werkzeug", "tkinter", "_tkinter", "tk", "tcl"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Strata",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # no terminal window for end users
    icon="strata.ico",
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name="Strata",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Strata.app",
        icon=None,
        bundle_identifier="com.strata.app",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion":            "1.0.0",
            "NSHighResolutionCapable":    True,
            "LSUIElement":                False,
        },
    )
