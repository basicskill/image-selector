import functools, base64
import io, os
import gzip
from zipfile import ZipFile
from datetime import timedelta
from math import ceil

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort,
    send_file, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash

from imagesel.db import execute_query, add_worker, log_action
from imagesel.auth import login_required, admin_required
from imagesel.images import get_object, upload_file, rename_file

# Create admin blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')


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
        redirect(url_for('auth.login'))


# Route to admin page
@bp.route('/dashboard', methods=('GET', 'POST'))
@admin_required
def dashboard():
    # Get all workers from workers table
    g.workers = execute_query(
        "SELECT * FROM workers"
    )

    if request.method == 'POST':
        username = request.form['username'].strip()
        error = None
        user = execute_query(
            "SELECT * FROM workers WHERE username = %s", (username,)
        )

        if len(user) > 0:
            error = 'Token already exists.'

        if error is None:
            # Add token to database
            acc_token = add_worker(username)

            # Log action
            log_action(f"User {username} with access token {acc_token} created")

            return redirect(url_for('admin.dashboard'))

        flash(error)

    return render_template("admin/dashboard.html")

@bp.route('/<int:id>/delete', methods=('POST',))
@admin_required
def delete(id):
    # Get token from database
    worker = execute_query('SELECT * FROM workers WHERE id = %s', (id,))

    # Delete token from database
    execute_query('DELETE FROM workers WHERE id = %s', (id,), fetch=False)

    # Log action
    log_action(f"User {worker[0]['username']} deleted")

    return redirect(url_for('admin.dashboard'))


# Delete classification type from admins page
@bp.route('/<classification>/delete_classification', methods=('POST',))
@admin_required
def delete_classification(classification):
    # Fetch classification from admins table
    img_classes = execute_query('SELECT img_classes FROM admins')[0]['img_classes']

    # Remove classification from list
    img_classes.remove(classification)

    # Update admins table
    execute_query('UPDATE admins SET img_classes = %s', (img_classes,), fetch=False)

    # Log action
    log_action(f"Classification {classification} deleted")

    return redirect(url_for('admin.image_explorer'))


# Upload image
@bp.route('/upload_images', methods=('GET', 'POST'))
@admin_required
def upload_images():

    if request.method == 'POST':
        # Get all images from request
        images = request.files.getlist("images")
        classification = request.form['classification']

        # Loop through all images
        for image in images:
            # Check if image is not empty
            if image.filename != '':
                # Check if mimetype is image
                if image.mimetype.startswith('image/'):
                    # Check if file already exists
                    if os.path.isfile(os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename)):

                        # Save image with suffix
                        idx = 1
                        while os.path.isfile(os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename)):
                            image.filename = image.filename.split('.')[0] + f'_{idx}.' + image.filename.split('.')[1]
                            idx += 1

                    # Save image to images folder
                    image.save(os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename))

                    # Save image metadata to database
                    if classification == 'unprocessed':
                        execute_query("INSERT INTO images (filename, processing) VALUES (%s, %s)",
                            (image.filename, classification),
                            fetch=False
                        )
                    else:
                        execute_query("INSERT INTO images (filename, processing, classification) VALUES (%s, %s, %s)",
                            (image.filename, 'processed', classification),
                            fetch=False
                        )


                    # Log action
                    log_action(f"Image {image.filename} uploaded as class {classification}") 


                else:
                    flash(f'File "{image.filename}" is not an image.')

        flash(f'{len(images)} images uploaded successfully')

    return redirect(url_for('admin.image_explorer'))


# Image explorer page
@bp.route('/image_explorer', methods=('GET', 'POST'))
@admin_required
def image_explorer():

    if request.method == 'POST':
        # Flash error if no choice is made
        if not request.form.get('processing') or not request.form.get('classification'):
            flash('Please make a choice.')
            return redirect(url_for('admin.image_explorer'))

        # Get choice field from request
        return redirect(url_for('admin.image_explorer', processing=request.form['processing'], classification=request.form['classification'], curr_page=1))

    # Query img_classes field from admins table
    class_names = execute_query(
        "SELECT img_classes FROM admins LIMIT 1"
    )[0]['img_classes']

    # Count number of images in each class
    class_counts = {}

    # Count number of unprocessed images
    class_counts['unprocessed'] = execute_query(
        "SELECT COUNT(*) FROM images WHERE processing = 'unprocessed'"
    )[0]['count']

    for class_name in class_names:
        class_counts[class_name] = execute_query(
            "SELECT COUNT(*) FROM images WHERE classification = %s AND processing = 'processed'", 
            (class_name,)
        )[0]['count']
    
    g.classes = class_counts

    # If request does not have "processing" and "class" args in url render template
    if not request.args.get("processing") or not request.args.get("classification"):
        return render_template("admin/image_explorer.html", curr_page=0)

    # Get processing and class from url
    processing = request.args.get("processing")
    classification = request.args.get("classification")

    # Generate image query if processing is "all" and class is "all"
    if processing == "all" and classification == "all":
        g.images = execute_query(
            "SELECT * FROM images"
        )
    
    # Generate image query if processing is "all" and class is not "all"
    elif processing == "all":
        g.images = execute_query(
            "SELECT * FROM images WHERE classification = %s", (classification,)
        )
    
    # Generate image query if processing is not "all" and class is "all"
    elif classification == "all":
        g.images = execute_query(
            "SELECT * FROM images WHERE processing = %s", (processing,)
        )
    
    # Generate image query if processing is not "all" and class is not "all"
    else:
        g.images = execute_query(
            "SELECT * FROM images WHERE classification = %s AND processing = %s", (classification, processing)
        )
    
    # Implement page scrolling
    page_size = current_app.config['PAGE_SIZE']
    g.pages = ceil(len(g.images) / page_size)
    curr_page = int(request.args.get('page', '1'))

    if curr_page > g.pages:
        curr_page = g.pages
    if curr_page < 1:
        curr_page = 1    

    g.images = g.images[(curr_page - 1) * page_size: curr_page * page_size]

    return render_template("admin/image_explorer.html", processing=processing, classification=classification, curr_page=curr_page)


# Decorator for adding class
@bp.route('/add_class', methods=('POST',))
@admin_required
def add_class():
    # Get img_classes field from admins table
    classes = execute_query(
        "SELECT img_classes FROM admins"
    )

    # Get class from request
    new_class = request.form.get('new_class').strip()

    # Check if class is not empty
    if new_class:
        # Check if class already exists
        if new_class in classes[0]['img_classes']:
            flash(f'Class "{new_class}" already exists.')

        else:
            # Add class to img_classes field in admins table
            classes[0]['img_classes'].append(new_class)
            execute_query("UPDATE admins SET img_classes = %s", (classes[0]['img_classes'],), fetch=False)

            # Log action
            log_action(f"Class {new_class} added")

    return redirect(url_for('admin.image_explorer'))


# Edit image page
@bp.route('/<int:id>/edit_image', methods=('GET', 'POST'))
@admin_required
def edit_image(id):
    # Get image from database
    image = execute_query(
        "SELECT * FROM images WHERE id = %s", (id,)
    )[0]
    if request.method == 'POST':
        # Get form fields from request with get attribute
        classification = request.form.get('classification')
        processing = request.form.get('processing')
        filename = request.form.get('filename')

        # If some fields are empty copy field from image variable
        if not classification:
            classification = image['classification']
        if not processing:
            processing = image['processing']
        if not filename:
            filename = image['filename']

        # Update image in database
        execute_query("UPDATE images SET classification = %s, processing = %s, filename = %s WHERE id = %s",
            (classification, processing, filename, id), fetch=False)

        # Rename image file
        rename_file(image['filename'], filename)

        # Log action
        log_action(f"Image {image['filename']} edited to classification {classification} and processing {processing}")

        # Redirect to edit image page
        return redirect(url_for('admin.edit_image', id=id))
        
    return render_template("admin/edit_image.html", image=image)


# Page to change admin password
@bp.route('/change_password', methods=('GET', 'POST'))
@admin_required
def change_password():
    if request.method == 'POST':
        # Get form fields from request
        old_password = request.form['old_password'].strip()
        new_password = request.form['new_password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        # Get admin from database
        admin = execute_query(
            "SELECT * FROM admins WHERE username = 'admin'"
        )[0]

        # Check if old password is correct
        if not check_password_hash(admin['password'], old_password):
            flash('Incorrect password.')
            return redirect(url_for('admin.change_password'))

        # Check if new password and confirm password are the same
        if new_password != confirm_password:
            flash('New password and confirm password are not the same.')
            return redirect(url_for('admin.change_password'))

        # Update admin password in database
        execute_query("UPDATE admins SET password = %s WHERE username = 'admin'",
            (generate_password_hash(new_password),), 
            fetch=False
        )
        flash("Password changed successfully")
    
        # Log action
        log_action(f"Admin password changed")
    
    return render_template("admin/change_password.html")


# Page to download database
@bp.route('/download_data', methods=('GET', 'POST'))
@admin_required
def download_data():

    if request.method == 'POST':
        # Init zip file 
        mem = io.BytesIO()
        zip_f = ZipFile(mem, 'w')
        
        # Get images from database
        for classification in current_app.config["CLASSES"]:
            images = execute_query(
                "SELECT * FROM images WHERE classification = %s", (classification,)
            )
            # Create folder for each class
            zip_f.writestr(f"{classification}/", "")

            # Add images to zip file
            for image in images:
                zip_f.writestr(f"{classification}/{image['filename']}", base64.b64decode(image["base64_enc"]))

        # Close zip file
        zip_f.close()
        mem.seek(0)
        
        return send_file(mem, as_attachment=True, download_name="processed_images.zip",
                            mimetype='application/gzip')

    # Get all logs from database
    logs = execute_query(
        "SELECT * FROM logs"
    )

    logs_content = ""

    for log in logs:
        logs_content += f"{log['created']} - {log['textmsg']}\n\n"

    return render_template("admin/download_data.html", logs_content=logs_content)

# Define user page page
@bp.route('/user_page/<worker_name>', methods=('GET', 'POST'))
@admin_required
def user_page(worker_name):
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    worker_eligible = {class_name: num_labeled for class_name, num_labeled in zip(worker['eligible_classes'], worker['num_labeled'])}

    # Select all banned classes for worker
    banned_classes = execute_query("SELECT * FROM banned WHERE worker_id = %s", (worker['id'],))

    # Calculate ban expiration date for each class
    for idx in range(len(banned_classes)):
        cls = banned_classes[idx]
        cls['ban_expiration'] = cls['created'] + timedelta(days=current_app.config['BAN_DELETE_PERIOD'])
        banned_classes[idx] = cls

    return render_template("admin/user.html", worker=worker, worker_eligible=worker_eligible, banned_classes=banned_classes)


# Delete user eligible class
@bp.route('/user_page/<worker_name>/delete_eligible_class/<class_name>', methods=('POST',))
@admin_required
def delete_eligible_class(worker_name, class_name):
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    # Get index of class in eligible
    class_idx = worker['eligible_classes'].index(class_name)
    print(class_idx)

    # Delete class from eligible
    worker['eligible_classes'].pop(class_idx)

    # Delete num_labeled for class
    worker['num_labeled'].pop(class_idx)

    # Write to database
    execute_query("UPDATE workers SET eligible_classes = %s, num_labeled = %s WHERE username = %s",
        (worker['eligible_classes'], worker['num_labeled'], worker_name), fetch=False)
    
    # Log action
    log_action(f"Class {class_name} deleted from eligible classes for worker {worker_name}")

    # Return to user page
    return redirect(url_for('admin.user_page', worker_name=worker_name))


# Delete ban for user in banned table
@bp.route('/user_page/<worker_name>/delete_ban/<class_name>', methods=('POST',))
@admin_required
def delete_ban(worker_name, class_name):
    # Get user from database
    worker = execute_query(
        "SELECT * FROM workers WHERE username = %s", (worker_name,)
    )[0]

    # Get ban from database
    ban = execute_query("SELECT * FROM banned WHERE worker_id = %s AND class = %s", (worker['id'], class_name))[0]

    # Delete ban from database
    execute_query("DELETE FROM banned WHERE id = %s", (ban['id'],), fetch=False)
    
    # Log action
    log_action(f"Ban for class {class_name} deleted for worker {worker_name}")

    # Return to user page
    return redirect(url_for('admin.user_page', worker_name=worker_name))
