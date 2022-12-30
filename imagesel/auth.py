import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

from imagesel.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM tokens WHERE id = ?', (user_id,)
        ).fetchone()


@bp.route('/login', methods=('GET', 'POST'))
def login():
    # Check if user is already logged in
    if g.user:
        return redirect(url_for('index'))

    if request.method == 'POST':
        token = request.form['token']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM tokens WHERE token = ?', (token,)
        ).fetchone()

        if user is None:
            error = 'Incorrect token.'
        elif not check_password_hash(user['passhash'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            if user["token"] == "admin":
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')

# Decorator for logout
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# Decorator for login required
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view