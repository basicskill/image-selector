import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort
)
from werkzeug.security import check_password_hash

from imagesel.db import get_db, add_user
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
    db = get_db()
    g.tokens = db.execute(
        'SELECT * FROM tokens WHERE token != "admin"'
    ).fetchall()

    if request.method == 'POST':
        token = request.form['token']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM tokens WHERE token = ?', (token,)
        ).fetchone()

        if user is not None:
            error = 'Token already exists.'

        if error is None:
            add_user(token, "")
            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template("dashboard.html")

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    print("\n" * 10)
    print("ID: ", id)
    print("\n" * 10)
    db = get_db()
    db.execute('DELETE FROM tokens WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('admin.dashboard'))