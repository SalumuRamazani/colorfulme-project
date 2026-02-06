from colorfulme.app_factory import create_app

app = create_app()

if __name__ == '__main__':
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=int(app.config.get('PORT', 5003)),
        debug=app.config.get('DEBUG', False),
    )
