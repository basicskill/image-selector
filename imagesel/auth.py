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
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')

    if user_id is None:
        g.user = None

    elif is_admin:
        # Query admins table
        g.user = execute_query(
            "SELECT * FROM admins WHERE id = %s", (user_id,)
        )[0]

    else:
        g.user = execute_query(
            "SELECT * FROM workers WHERE id = %s", (user_id,)
        )[0]


@bp.route('/login', methods=('GET',))
def login():

    # Check if user is already logged in
    if g.user:
        return redirect(url_for('index'))

    return render_template('auth/login.html')

# Decorator for worker login
@bp.route('/worker_login', methods=('POST',))
def worker_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        token = request.form['token'].strip()
        error = None
   
        user = execute_query(
            'SELECT * FROM workers WHERE username = %s', (username,)
        )

        if len(user) == 0:
            flash('Incorrect username.')
            return render_template('auth/login.html')
        
        user = user[0]
        
        if token != user["token"]:
            error = 'Incorrect token.'

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

        return redirect(url_for('admin.dashboard'))

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

# Decorator for admin login required
def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or session.get('is_admin') is None or not session.get('is_admin'):
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view