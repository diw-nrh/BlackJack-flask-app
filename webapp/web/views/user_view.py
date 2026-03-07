from flask import Blueprint, render_template, redirect, url_for, request
from ..forms.user_form import LoginForm, RegisterForm
from ...services.user_service import UserService

module = Blueprint("users", __name__, url_prefix="/users")


@module.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    error_msg = ""
    if not form.validate_on_submit():
        if "password" in form.errors:
            if "Field must be at least 6 characters long." in form.errors["password"]:
                error_msg = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
            elif "This field is required." in form.errors["password"]:
                error_msg = "กรุณากรอกรหัสผ่าน"
            else:
                error_msg = "เกิดข้อผิดพลาดในการป้อนรหัสผ่าน"

        return render_template("/users/login.html", form=form, error_msg=error_msg)

    # Authenticate user
    login_result = UserService.login(form.username.data, form.password.data)
    if not login_result["success"]:
        return render_template(
            "/users/login.html", form=form, error_msg=login_result["error_msg"]
        )

    return redirect(request.args.get("next", url_for("index.index")))


@module.route("/register", methods=["get", "post"])
def register():
    form = RegisterForm()

    if not form.validate_on_submit():
        return render_template("/users/register.html", form=form)

    register_result = UserService.register(form)
    if register_result["success"] is False:
        return render_template(
            "/users/register.html", form=form, error_msg=register_result["error_msg"]
        )

    return redirect(url_for("users.login"))
