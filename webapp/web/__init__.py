import os
import optparse
import json
from flask import Flask
from . import views
from .. import models
from .utils.error_handling import init_error_handling
from .utils import acl
from dotenv import load_dotenv


def load_config(app):
    load_dotenv()
    app.config.from_object("webapp.default_settings")

    try:
        settings_path = os.environ.get("APP_SETTINGS")
        if settings_path and os.path.exists(settings_path):
            app.config.from_pyfile(settings_path)
    except Exception:
        pass

    for k, v in os.environ.items():
        if v in ["True", "TRUE"]:
            v = True
        elif v in ["False", "FALSE"]:
            v = False
        else:
            try:
                v = json.loads(v)
            except Exception:
                pass
        app.config[k] = v


def create_app():
    app = Flask(__name__)
    load_config(app)

    # Secret key required for flask sessions
    app.config.setdefault("SECRET_KEY", "dev-secret-key-change-me")

    views.register_blueprint(app)
    views.init_htmx(app)
    models.init_db(app)
    acl.init_acl(app)
    init_error_handling(app)

    # Init Socket.IO
    from ..ws import socketio
    import webapp.ws.events  # noqa: F401 — registers all event handlers
    socketio.init_app(app)

    return app



def get_program_options(default_host="127.0.0.1", default_port="8080"):
    """
    Takes a flask.Flask instance and runs it. Parses
    command-line flags to configure the app.
    """

    # Set up the command-line options
    parser = optparse.OptionParser()
    parser.add_option(
        "-H",
        "--host",
        help="Hostname of the Flask app " + f"[default {default_host}]",
        default=default_host,
    )
    parser.add_option(
        "-P",
        "--port",
        help="Port for the Flask app " + f"[default {default_port}]",
        default=default_port,
    )

    # Two options useful for debugging purposes, but
    # a bit dangerous so not exposed in the help message.
    parser.add_option(
        "-c", "--config", dest="config", help=optparse.SUPPRESS_HELP, default=None
    )
    parser.add_option(
        "-d", "--debug", action="store_true", dest="debug", help=optparse.SUPPRESS_HELP
    )
    parser.add_option(
        "-p",
        "--profile",
        action="store_true",
        dest="profile",
        help=optparse.SUPPRESS_HELP,
    )

    options, _ = parser.parse_args()

    # If the user selects the profiling option, then we need
    # to do a little extra setup
    if options.profile:
        from werkzeug.middleware.profiler import ProfilerMiddleware

        app.config["PROFILE"] = True
        app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
        options.debug = True

    return options
