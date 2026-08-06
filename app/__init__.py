import os

from flask import Flask, Response, request


def create_app() -> Flask:
    app = Flask(__name__)

    from . import config  # noqa: F401 — charge .env et crée les dossiers

    # Protection par mot de passe (indispensable en ligne : sinon n'importe qui
    # peut lancer des jobs et consommer ta clé API). Définis APP_PASSWORD.
    password = os.getenv("APP_PASSWORD")
    if password:

        @app.before_request
        def _check_auth():
            auth = request.authorization
            if not auth or auth.password != password:
                return Response(
                    "Accès protégé — entre le mot de passe.",
                    401,
                    {"WWW-Authenticate": 'Basic realm="TikTokMoneyPrinter"'},
                )

    from .routes import bp

    app.register_blueprint(bp)
    return app
