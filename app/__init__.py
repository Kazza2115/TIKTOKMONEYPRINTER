import os

from flask import Flask, Response, request


def create_app() -> Flask:
    app = Flask(__name__)

    from . import config  # noqa: F401 — charge .env et crée les dossiers

    # Protection par mot de passe (indispensable en ligne : sinon n'importe qui
    # peut lancer des jobs et consommer ta clé API). Définis APP_PASSWORD.
    password = (os.getenv("APP_PASSWORD") or "").strip()
    if password:

        @app.before_request
        def _check_auth():
            auth = request.authorization
            # tolérant : espaces parasites ignorés, et mot de passe accepté
            # même s'il a été tapé dans le champ identifiant
            supplied = []
            if auth:
                supplied = [
                    (auth.password or "").strip(),
                    (auth.username or "").strip(),
                ]
            if password not in supplied:
                return Response(
                    "Accès protégé — identifiant libre (ex: admin), "
                    "mot de passe : celui défini au lancement.",
                    401,
                    {"WWW-Authenticate": 'Basic realm="TikTokMoneyPrinter"'},
                )

    from .routes import bp

    app.register_blueprint(bp)
    return app
