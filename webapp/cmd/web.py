from webapp.web import create_app, get_program_options


def main():
    app = create_app()
    options = get_program_options()

    from webapp.ws import socketio
    socketio.run(
        app,
        host=options.host,
        port=int(options.port),
        debug=options.debug,
        use_reloader=options.debug,
        log_output=True,
    )


if __name__ == "__main__":
    main()
