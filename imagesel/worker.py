import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, add_user
from imagesel.auth import login_required, admin_required
import base64

# Create admin blueprint
bp = Blueprint('worker', __name__, url_prefix='/worker')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = execute_query(
            "SELECT * FROM tokens WHERE id = %s", (user_id,)
        )[0]

# Define worker page
@bp.route('/selection_choice', methods=('GET', 'POST'))
@login_required
def selection_choice():
    # If user is not in selection choice status, redirect to testing page
    if g.user["selected_class"] != "non":
        return redirect(url_for('worker.testing'))

    
    error = None
    if request.method == 'POST':
        choice = request.form['choice']
        if error is None:
            # Update user's inprogress to true and selected_class to choice
            execute_query(
                "UPDATE tokens SET selected_class = %s, inprogress = TRUE WHERE id = %s",
                (choice, g.user["id"]),
                fetch=False
            )

            return redirect(url_for('worker.testing'))

        flash(error)

    return render_template("worker/selection_choice.html")

@bp.route('/testing', methods=('GET', 'POST'))
@login_required
def testing():
    # If user is not in testing status, redirect to selection choice page
    if not g.user["inprogress"]:
        return redirect(url_for('worker.selection_choice'))
    
    # Query random image from database
    image = execute_query(
        "SELECT * FROM images ORDER BY RANDOM() LIMIT 1",
    )[0]
    print("-----------------")
    print(image["blob"].__dir__())
    # print(image["blob"].obj())
    print("-----------------")
    # Apply base64 encoding to image
    image["base64"] = base64.b64encode(image["blob"].tobytes()).decode()

    return render_template("worker/testing.html", image=image)