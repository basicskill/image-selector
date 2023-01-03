import os

from flask import Flask, render_template, g, url_for, redirect
import psycopg2

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        # DATABASE=os.path.join(app.instance_path, 'imagedb.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'
    
    # Init database
    from . import db
    db.init_app(app)

    # Register auth blueprint
    from . import auth
    app.register_blueprint(auth.bp)

    # Register admin blueprint
    from . import admin
    app.register_blueprint(admin.bp)

    # Register worker blueprint
    from . import worker
    app.register_blueprint(worker.bp)

    # Implement index page showing index.html
    @app.route('/')
    @app.route('/index')
    def index():
        if g.user is None:
            return redirect(url_for('auth.login'))
        elif g.user["token"] == "admin":
            return redirect(url_for('admin.dashboard'))
        
        return redirect(url_for('worker.selection_choice'))

    # Define possible classes
    app.config["CLASSES"] = [f"C{i}" for i in range(1, 6)]

    # Define states
    app.config["STATES"] = ["unprocessed", "processed", "holding"]

    return app