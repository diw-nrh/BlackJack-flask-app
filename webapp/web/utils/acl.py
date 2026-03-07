from flask import abort, Flask, request, redirect, url_for
from flask_login import current_user, LoginManager, login_url
from werkzeug.exceptions import Forbidden, Unauthorized

from functools import wraps
from ...models.user_model import User

login_manager = LoginManager()


def init_acl(app: Flask):
    login_manager.init_app(app)


def roles_required(roles: list[str]):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                raise Unauthorized()

            for role in roles:
                if role in current_user.roles:
                    return func(*args, **kwargs)

            raise Forbidden()

        return wrapper

    return decorator


def permissions_required(permissions: list[str]):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                raise Unauthorized()

            for permission in permissions:
                if not current_user.has_permission(permission):
                    return func(*args, **kwargs)

            raise Forbidden()

        return wrapper

    return decorator


@login_manager.user_loader
def load_user(user_id):
    return User.objects.with_id(user_id)


@login_manager.unauthorized_handler
def unauthorized_callback():
    if request.method == "GET":
        response = redirect(login_url("accounts.login", request.url))
        return response

    return redirect(url_for("accounts.login"))
