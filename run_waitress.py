from waitress import serve

from strata.web import create_app


app = create_app()


if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=app.config["STRATA_PORT"], threads=8)
