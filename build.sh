#!/usr/bin/env bash
# ============================================================
#  Universal Search — macOS build script
#  Produces: dist/UniversalSearch.dmg
#
#  ONE-TIME SETUP (run these once before building):
#    pip3 install pyinstaller flask pdfplumber pypdf python-docx
#    pip3 install openpyxl reportlab python-pptx extract-msg
#    pip3 install pillow pytesseract pdf2image
#    brew install create-dmg
#
#  OPTIONAL — OCR support for end users:
#    brew install tesseract poppler
#    (end users need these too, OR you bundle them — see below)
# ============================================================

set -e

echo ""
echo " Universal Search — macOS Build"
echo " ================================"
echo ""

# ── Step 1: Check PyInstaller ────────────────────────────────────────────────
if ! python3 -m pyinstaller --version &>/dev/null; then
    echo " Installing PyInstaller..."
    pip3 install pyinstaller
fi

# ── Step 2: Clean ────────────────────────────────────────────────────────────
rm -rf build dist

# ── Step 3: Build .app ───────────────────────────────────────────────────────
echo " Building application bundle..."
python3 -m pyinstaller universal_search.spec --noconfirm

echo ""
echo " .app bundle: dist/UniversalSearch.app"

# ── Step 4: Sign the app (optional but recommended for Gatekeeper) ───────────
# Uncomment and fill in your Apple Developer ID if you have one:
# DEVELOPER_ID="Developer ID Application: Your Name (TEAMID)"
# codesign --deep --force --verify --verbose \
#     --sign "$DEVELOPER_ID" \
#     --options runtime \
#     dist/UniversalSearch.app

# ── Step 5: Package into a .dmg ──────────────────────────────────────────────
if command -v create-dmg &>/dev/null; then
    echo " Creating .dmg..."
    create-dmg \
        --volname "Universal Search" \
        --window-pos 200 120 \
        --window-size 540 360 \
        --icon-size 128 \
        --icon "UniversalSearch.app" 160 180 \
        --app-drop-link 380 180 \
        "dist/UniversalSearch.dmg" \
        "dist/UniversalSearch.app" || true

    if [ -f "dist/UniversalSearch.dmg" ]; then
        echo ""
        echo " ============================================================"
        echo "  Installer ready: dist/UniversalSearch.dmg"
        echo "  Share this file — users drag the app to Applications."
        echo " ============================================================"
    fi
else
    echo ""
    echo " create-dmg not found — skipping .dmg creation."
    echo " Install with: brew install create-dmg"
    echo " Or zip dist/UniversalSearch.app and distribute that."
fi

echo ""
