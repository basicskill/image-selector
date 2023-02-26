import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, refresh_bans

bp = Blueprint('auth', __name__, url_prefix='/auth')


# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from."""
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')

    if user_id is None:
        g.user = None

    else:
        if is_admin:
            # Query admins table
            g.user = execute_query(
                "SELECT * FROM admins WHERE id = %s", (user_id,)
            )

        else:
            g.user = execute_query(
                "SELECT * FROM workers WHERE id = %s", (user_id,)
            )

        if len(g.user):
            g.user = g.user[0]


@bp.route('/login', methods=('GET',))
def login():
    """Show login page."""
    # Check if user is already logged in
    if g.user:
        return redirect(url_for('index'))

    return render_template('auth/login.html')


@bp.route('/admin', methods=('GET',))
def admin_login_page():
    """Show admin login page."""
    # Check if user is already logged in
    if g.user:
        return redirect(url_for('index'))

    return render_template('auth/login_admin.html')


# Decorator for worker login
@bp.route('/worker_login', methods=('POST',))
def worker_login():
    """Log in a registered user by adding the user id to the session."""
    if request.method == 'POST':
        token = request.form['token'].strip()
        error = None

        user = execute_query(
            'SELECT * FROM workers WHERE token = %s', (token,)
        )

        if len(user) == 0:
            flash('Incorrect token.')
            return render_template('auth/login.html')

        user = user[0]

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            session['is_admin'] = False
            refresh_bans()

            return redirect(url_for('index'))

        flash(error)
        return redirect(url_for('auth.login'))


# Decorator for admin login
@bp.route('/admin_login', methods=('POST',))
def admin_login():
    """Log in a registered user by adding the user id to the session."""
    username = request.form['username'].strip()
    password = request.form['password'].strip()
    error = None

    user = execute_query(
        'SELECT * FROM admins WHERE username = %s', (username,)
    )

    if len(user) == 0:
        flash('Incorrect username.')
        return render_template('auth/login.html')

    user = user[0]

    if not check_password_hash(user["password"], password):
        error = 'Incorrect password.'

    if error is None:
        session.clear()
        session['user_id'] = user['id']
        session['is_admin'] = True
        refresh_bans()

        return redirect(url_for('admin.dashboard'))

    flash(error)

    return redirect(url_for('auth.admin_login_page'))


# Decorator for logout
@bp.route('/logout')
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for('index'))


# Decorator for login required
def login_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view


# Decorator for admin login required
def admin_required(view):
    """View decorator that redirects anonymous users to the login page."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or session.get('is_admin') is None or not session.get('is_admin'):
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view