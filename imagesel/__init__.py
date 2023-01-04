import os

from flask import Flask, render_template, g, url_for, redirect
import psycopg2

def create_app(*args, **kwargs):
    # Print args and kwargs
    print("Args: ", args)
    print("Kwargs: ", kwargs)

    test_config=None
    print("App started")
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        # DATABASE=os.path.join(app.instance_path, 'imagedb.sqlite'),
    )

    # if test_config is None:
    #     # load the instance config, if it exists, when not testing
    #     app.config.from_pyfile('config.py', silent=True)
    # else:
    #     # load the test config if passed in
    #     app.config.from_mapping(test_config)

    # # ensure the instance folder exists
    # try:
    #     os.makedirs(app.instance_path)
    # except OSError:
    #     pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'
    print("Generated index page")
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

    # Define number of images to be shown in each round
    app.config["NUM_IMAGES"] = 4

    # Define number of correct images to label to proceed testing
    app.config["NUM_CORRECT"] = 1
    return app