from flask import url_for
import datetime


def static_url(filename: str):
    return add_date_url(url_for("static", filename=filename))


def add_date_url(url: str):
    now = datetime.datetime.now()
    return f'{url}?date={now.strftime("%Y%m%d")}'
