import functools, sys, os
from random import shuffle

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, abort, current_app
)
from werkzeug.security import check_password_hash

from imagesel.db import execute_query, log_action
from imagesel.auth import login_required, admin_required
import base64

# Create admin blueprint
bp = Blueprint('worker', __name__, url_prefix='/worker')

# Before all requests run blueprint
@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    is_admin = session.get('is_admin')

    if user_id is None:
        g.user = None

    elif is_admin:
        redirect(url_for('admin.dashboard'))

    else:
        g.user = execute_query(
            "SELECT * FROM workers WHERE id = %s", (user_id,)
        )[0]


# Define worker page
@bp.route('/selection_choice', methods=('GET', 'POST'))
@login_required
def selection_choice():

    # If user is not in selection choice status, redirect to testing page
    if session.get("selected_class"):
        return redirect(url_for('worker.testing'))

    error = None
    if request.method == 'POST':
        choice = request.form['choice']
        num_of_imgs = request.form['num_of_imgs']

        # Set session attribute to selected class
        session["selected_class"] = choice
        session["num_of_imgs"] = num_of_imgs

        # Log action
        log_action(f"User {g.user['token']} selected class {choice}")

        return redirect(url_for('worker.testing'))

    # Query img_classes from admins database
    img_classes = execute_query(
        "SELECT img_classes FROM admins WHERE id = 1"
    )[0]["img_classes"]

    return render_template("worker/selection_choice.html", img_classes=img_classes)

@bp.route('/testing', methods=('GET', 'POST'))
@login_required
def testing():
    # If user is not in testing status, redirect to selection choice page
    if not session.get("selected_class"):
        return redirect(url_for('worker.selection_choice'))
    
    # If user has selected class in eligible classes, redirect to labeling page
    if session.get("selected_class") in g.user["eligible_classes"]:
        return redirect(url_for('worker.labeling'))

    if "selected_image_ids" not in session:
        # Query NUM_CORRECT random images from database where classification is equal to user's selected class
        # and processing is equal to processed
        session["selected_image_ids"] = [row["id"] for row in execute_query(
            "SELECT id FROM images WHERE classification = %s AND processing = 'processed' ORDER BY RANDOM() LIMIT %s",
            (session.get("selected_class"), current_app.config["NUM_TEST_CORRECT"],)
        )]

        # Query NUM_INCORRECT random images with classification not equal to user's selected class
        # and processing is equal to processed
        session["selected_image_ids"] += [row["id"] for row in execute_query(
            "SELECT id FROM images WHERE classification != %s AND processing = 'processed' ORDER BY RANDOM() LIMIT %s",
            (session.get("selected_class"), current_app.config["NUM_TEST_INCORRECT"],)
        )]

        # Query NUM_HOLDING random images from database where processing is equal to unprocessed
        session["selected_image_ids"] += [row["id"] for row in execute_query(
            "SELECT id FROM images WHERE processing = 'unprocessed' ORDER BY RANDOM() LIMIT %s",
            (current_app.config["NUM_TEST_HOLDING"],)
        )]

    # Query images with id from session selected_image_ids
    selected_images = execute_query(
        "SELECT * FROM images WHERE id IN %s",
        (tuple(session["selected_image_ids"]),)
    )

    shuffle(selected_images)

    return render_template("worker/testing.html", selected_images=selected_images)


# Submit selected image
@bp.route('/submit_testing', methods=('POST',))
@login_required
def submit_testing():
    # Get selected image id from request
    selected_image_ids = request.form.keys()

    # Check if user selected anything
    if not selected_image_ids:
        flash("Select at least one image")
        return redirect(url_for('worker.testing'))

    # Count number of selected images with classification of session selected class
    selected_correct = execute_query(
        "SELECT COUNT(*) FROM images WHERE id IN %s AND classification = %s AND processing = 'processed'",
        (tuple(selected_image_ids), session["selected_class"])
    )[0]["count"]

    # Count number of selected images with classification not equal to session selected class and processing is equal to processed
    selected_wrong = execute_query(
        "SELECT COUNT(*) FROM images WHERE id IN %s AND classification != %s AND processing = 'processed'",
        (tuple(selected_image_ids), session["selected_class"])
    )[0]["count"]

    print(selected_correct, selected_wrong)

    # Check if selected count is enough to pass to next stage
    # Threshold is read from config file
    if selected_correct == current_app.config["NUM_TEST_CORRECT"] and selected_wrong == 0:
        # Log action
        log_action(f"User {g.user['username']} passed testing stage for class {session['selected_class']}")

        # Change selected images which are unprocessed to holding,
        # change their class count to 1 and their classification to user's selected class
        execute_query(
            f"UPDATE images SET processing = 'holding', class_count = 1, classification = %s WHERE id IN %s AND processing = 'unprocessed'",
            (session["selected_class"], tuple(selected_image_ids)),
            fetch=False
        )

        # Update worker database to be eligible for selected class
        execute_query(
            f"UPDATE workers SET eligible_classes = array_append(eligible_classes, %s) WHERE id = %s",
            (session["selected_class"], g.user["id"]),
            fetch=False
        )

        # Clear selected image ids from session
        session.pop("selected_image_ids", None)

        return redirect(url_for('worker.labeling'))

    # Log action
    log_action(f"User {g.user['token']} failed testing for class {session['selected_class']} and is banned")

    # TODO: Add class to banned for this user

    # Save user's class selection for feedback page
    selected_class = session["selected_class"]

    # Delete session
    session.clear()

    return render_template("worker/feedback_fail.html", selected_class=selected_class)


# Define labeling page
@bp.route('/labeling', methods=('GET', 'POST'))
@login_required
def labeling():
    # If user is not in labeling status, redirect to selection choice page
    if not g.user.get("labeling"):
        return redirect(url_for('worker.selection_choice'))
    
    # Choose NUM_LABELING random images from database where processing is not equal to processed
    if "to_be_labeled_ids" not in session:
        session["to_be_labeled_ids"] = [row["id"] for row in execute_query(
            "SELECT * FROM images WHERE processing != 'processed' ORDER BY RANDOM() LIMIT %s",
            (current_app.config["NUM_LABELING"],)
        )]

    # Query images from database with id from session selected_image_ids and apply base64 encoding
    selected_images = []
    for image_id in session["to_be_labeled_ids"]:
        image = execute_query(
            "SELECT * FROM images WHERE id = %s", (image_id,)
        )[0]
        selected_images.append(image)
    
    # Log action

    return render_template("worker/labeling.html", selected_images=selected_images)


# Submit selected images for labeling
@bp.route('/labeling_submit', methods=('POST',))
@login_required
def labeling_submit():
    """Update counts of selected images and change their processing to holding or processed."""

    # Get selected image id from request
    session["selected_image_ids"] = request.form.keys()

    # Selected images with processing equal to unprocessed move to holding
    # set their classification to user's selected class and class count to 1
    execute_query(
        "UPDATE images SET processing = 'holding', classification = %s, class_count = 1 WHERE id IN %s AND processing = 'unprocessed'",
        (g.user["selected_class"], tuple(session["selected_image_ids"])),
        fetch=False
    )

    # Selected images with processing equal to holding and classification equal to user's selected class
    # increase their class count by 1
    execute_query(
        "UPDATE images SET class_count = class_count + 1 WHERE id IN %s AND processing = 'holding' AND classification = %s",
        (tuple(session["selected_image_ids"]), g.user["selected_class"]),
        fetch=False
    )

    # Selected images with processing equal to holding and classification not equal to user's selected class
    # decrease their class count by 1
    execute_query(
        "UPDATE images SET class_count = class_count - 1 WHERE id IN %s AND processing = 'holding' AND classification != %s",
        (tuple(session["selected_image_ids"]), g.user["selected_class"]),
        fetch=False
    )

    # Selected images with processing equal to holding and class count equal to 0
    # change their processing to unprocessed
    execute_query(
        "UPDATE images SET processing = 'unprocessed' WHERE id IN %s AND processing = 'holding' AND class_count = 0",
        (tuple(session["selected_image_ids"]),),
        fetch=False
    )

    # Selected images with processing equal to holding and class count equal to NUM_VOTES
    # change their processing to processed
    execute_query(
        "UPDATE images SET processing = 'processed' WHERE id IN %s AND processing = 'holding' AND class_count = %s",
        (tuple(session["selected_image_ids"]), current_app.config["NUM_VOTES"]),
        fetch=False
    )
    # Save selected class
    selected_class = g.user["selected_class"]

    # Clear session
    session.clear()

    # Delete user from database
    execute_query(
        "DELETE FROM tokens WHERE id = %s",
        (g.user["id"],),
        fetch=False
    )

    # Log action
    log_action(f"User {g.user['token']} labeled images: {session['to_be_labeled_ids']} as {g.user['selected_class']}")
    log_action(f"User {g.user['token']} is being deleted")

    # Redirect to feedback page
    return render_template("worker/feedback_success.html", selected_class=selected_class)

