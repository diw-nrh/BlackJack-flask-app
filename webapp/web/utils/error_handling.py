from flask import Flask, render_template


def init_error_handling(app: Flask):
    @app.errorhandler(403)
    def forbidden(e):
        return (
            render_template(
                "error.html",
                error_msg="Access Denied: You do not have permission to access this page.",
            ),
            403,
        )

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("error.html", error_msg="Page Not Found"), 404

    @app.errorhandler(500)
    def server_error(e):
        return (
            render_template(
                "error.html", error_msg="An error occurred. Please try again later."
            ),
            500,
        )
