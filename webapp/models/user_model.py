import mongoengine as me
from flask_login import UserMixin
import datetime


class User(me.Document, UserMixin):
    username = me.StringField(required=True, unique=True)
    password = me.StringField(required=True)

    status = me.StringField(
        required=True, default="active", choices=["active", "disactive"]
    )

    created_date = me.DateTimeField(required=True, default=datetime.datetime.now)
    updated_date = me.DateTimeField(
        required=True, default=datetime.datetime.now, auto_now=True
    )
    last_login_date = me.DateTimeField(
        required=True, default=datetime.datetime.now, auto_now=True
    )

    meta = {"collection": "users", "indexs": ["username"]}

    def set_password(self, password):
        from werkzeug.security import generate_password_hash

        self.password = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash

        return bool(check_password_hash(self.password, password))
