#!/bin/bash
# Strata — Mac Launcher
# Double-click this file in Finder to start Strata

cd "$(dirname "$0")"

echo ""
echo "================================================"
echo " Strata — Legal Document Search"
echo "================================================"
echo ""

# ── Find Python ───────────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd -c "import sys; print(sys.version_info.major * 10 + sys.version_info.minor)" 2>/dev/null)
        if [ "$VER" -ge "39" ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

# ── No Python found — install via Homebrew ────────────────────────────────────
if [ -z "$PYTHON" ]; then
    echo " Python not found. Installing..."

    # Install Homebrew if needed
    if ! command -v brew &>/dev/null; then
        echo " Installing Homebrew (this takes a few minutes)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add homebrew to PATH for Apple Silicon
        eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null
        eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null
    fi

    echo " Installing Python 3.12..."
    brew install python@3.12
    PYTHON=$(brew --prefix)/bin/python3.12
    if [ ! -f "$PYTHON" ]; then
        PYTHON=python3
    fi
fi

echo " Python: $PYTHON"

# ── Install dependencies ──────────────────────────────────────────────────────
$PYTHON -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo " Installing dependencies (first run only, ~2 minutes)..."
    $PYTHON -m pip install --quiet --upgrade pip
    $PYTHON -m pip install --quiet flask pdfplumber pypdf python-docx openpyxl reportlab python-pptx extract-msg pillow pytesseract pdf2image
    echo " Dependencies installed."
    echo ""
fi

# ── Install Tesseract for OCR if not present ──────────────────────────────────
if ! command -v tesseract &>/dev/null; then
    if command -v brew &>/dev/null; then
        echo " Installing Tesseract OCR..."
        brew install tesseract --quiet
    fi
fi

# ── Find free port ───────────────────────────────────────────────────────────
PORT=$($PYTHON -c "import socket; s=socket.socket(); s.bind(('',5000)); s.close(); print(5000)" 2>/dev/null || \
       $PYTHON -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")

echo " Starting Strata on port $PORT..."
echo " Opening browser..."
echo ""
echo " To stop Strata, close this window."
echo ""

# Open browser after short delay
(sleep 2 && open "http://127.0.0.1:$PORT") &

# Run the app
FLASK_PORT=$PORT $PYTHON app_flask.py
