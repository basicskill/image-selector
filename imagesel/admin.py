import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, add_user
from imagesel.auth import login_required

# Create admin blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')

# Route to admin page
@bp.route('/dashboard', methods=('GET', 'POST'))
@login_required
def dashboard():
    # Don't allow non admin users to access this page
    if g.user["token"] != "admin":
        abort(404)
    
    # Get all tokens from tokens table
    g.tokens = execute_query(
        "SELECT * FROM tokens WHERE token != 'admin'"
    )

    if request.method == 'POST':
        token = request.form['token']
        error = None
        user = execute_query(
            "SELECT * FROM tokens WHERE token = %s", (token,)
        )

        if len(user) > 0:
            error = 'Token already exists.'

        if error is None:
            add_user(token, "")
            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template("dashboard.html")

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    execute_query('DELETE FROM tokens WHERE id = %s', (id,), fetch=False)

    return redirect(url_for('admin.dashboard'))