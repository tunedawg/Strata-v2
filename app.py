import os
import webbrowser

from waitress import serve

from strata.web import create_app


if __name__ == "__main__":
    app = create_app()
    url = f"http://127.0.0.1:{app.config['STRATA_PORT']}"
    if os.environ.get("STRATA_OPEN_BROWSER") == "1":
        try:
            webbrowser.open(url)
        except Exception:
            pass
    serve(app, host="127.0.0.1", port=app.config["STRATA_PORT"], threads=8)
