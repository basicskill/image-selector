from datetime import datetime, timedelta
import time
from random import shuffle, randint

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

from imagesel.db import execute_query, log_action
from imagesel.auth import login_required

# Create admin blueprint
bp = Blueprint('worker', __name__, url_prefix='/worker')


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


# Define worker page
@bp.route('/selection_choice', methods=('GET', 'POST'))
@login_required
def selection_choice():
    """Show selection choice page. User selects class and number of images to label."""
    # If user is not in selection choice status, redirect to testing page
    if session.get("selected_class"):
        return redirect(url_for('worker.testing'))

    eligible_classes = g.user["eligible_classes"]
    banned_classes = execute_query(
        "SELECT class FROM banned WHERE worker_id = %s",
        (g.user["id"],)
    )
    banned_classes = [row["class"] for row in banned_classes]

    if request.method == 'POST':
        choice = request.form['choice']
        num_of_imgs = request.form['num_of_imgs']

        # Check if user has selected class in banned classes
        if choice not in banned_classes:
            # Set session attribute to selected class
            session["selected_class"] = choice
            session["num_of_imgs"] = num_of_imgs

            # Log action
            log_action(f"User {g.user['username']} selected class {choice}", g.user["id"])

            return redirect(url_for('worker.testing'))
        else:
            flash("You are banned from labeling this class!", "error")

    # Query img_classes from admins database
    img_classes = execute_query(
        "SELECT img_classes FROM admins WHERE id = 1"
    )[0]["img_classes"]

    return render_template("worker/selection_choice.html", img_classes=img_classes, eligible_classes=eligible_classes, banned_classes=banned_classes)


def pick_testing_images():
    # Query NUM_CORRECT processed images with class equal to user's selected class
    session["selected_image_ids"] = [row["id"] for row in execute_query(
        "SELECT id FROM images WHERE classification = %s AND processing = 'processed' ORDER BY RANDOM() LIMIT %s",
        (session.get("selected_class"), current_app.config["NUM_TEST_CORRECT"],)
    )]

    # Query NUM_INCORRECT processed images with class different from user's selected class
    session["selected_image_ids"] += [row["id"] for row in execute_query(
        "SELECT id FROM images WHERE classification != %s AND processing = 'processed' ORDER BY RANDOM() LIMIT %s",
        (session.get("selected_class"), current_app.config["NUM_TEST_INCORRECT"],)
    )]

    # Query NUM_HOLDING unprocessed images
    session["selected_image_ids"] += [row["id"] for row in execute_query(
        "SELECT id FROM images WHERE processing = 'unprocessed' AND NOT %s = ANY(labeled_by) AND classification IN %s ORDER BY RANDOM() LIMIT %s",
        (g.user["id"], (session.get("selected_class"), "/"), current_app.config["NUM_TEST_HOLDING"],)
    )]


@bp.route('/testing', methods=('GET', 'POST'))
@login_required
def testing():
    """Show testing page. User labels images and is redirected to labeling page if correct."""
    # If user is not in testing status, redirect to selection choice page
    if not session.get("selected_class"):
        return redirect(url_for('worker.selection_choice'))

    # If user has selected class in eligible classes, redirect to labeling page
    if session.get("selected_class") in g.user["eligible_classes"]:
        return redirect(url_for('worker.labeling'))

    if "selected_image_ids" not in session:
        pick_testing_images()

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
def submit_testing(random_test=False):
    """Submit selected images from testing page."""
    # Get selected image id from request
    selected_image_ids = request.form.keys()
    selected_image_count = len(selected_image_ids)
    if len(selected_image_ids) == 0:
        selected_image_ids = [-1]

    # Check if user selected anything
    if not selected_image_ids and not random_test:
        flash("Select at least one image", "error")
        return redirect(url_for('worker.testing'))

    # Count processed images with class equal to session selected class
    selected_correct = execute_query(
        "SELECT COUNT(*) FROM images WHERE id IN %s AND classification = %s AND processing = 'processed'",
        (tuple(selected_image_ids), session["selected_class"])
    )[0]["count"]

    # Count processed images with class different from session selected class
    selected_wrong = execute_query(
        "SELECT COUNT(*) FROM images WHERE id IN %s AND classification != %s AND processing = 'processed'",
        (tuple(selected_image_ids), session["selected_class"])
    )[0]["count"]

    # Check if selected count is enough to pass to next stage
    # Threshold is read from config file
    if selected_correct >= current_app.config["NUM_TEST_CORRECT"] - 1 and selected_wrong <= 1:
        # Log action
        test_type = "random test" if random_test else "testing stage"
        log_action(f"User {g.user['username']} passed {test_type} for class {session['selected_class']}", g.user["id"])

        # Change selected images which are unprocessed to holding,
        # change their class count to 1 and their classification to user's selected class
        # And append user's id to their labeled_by
        execute_query(
            f"UPDATE images SET processing = 'holding', class_count = 1, classification = %s, labeled_by = array_append(labeled_by, %s) WHERE id IN %s AND processing = 'unprocessed'",
            (session["selected_class"], g.user["id"], tuple(selected_image_ids)),
            fetch=False
        )

        if not random_test:
            # Update worker to be eligible for selected class
            execute_query(
                f"UPDATE workers SET eligible_classes = array_append(eligible_classes, %s) WHERE id = %s",
                (session["selected_class"], g.user["id"]),
                fetch=False
            )

        # Update workers's cumulative_time_spent array in database
        execute_query(
            f"UPDATE workers SET cumulative_time_spent = array_append(cumulative_time_spent, 0) WHERE id = %s",
            (g.user["id"],),
            fetch=False
        )

        # Update workers's num_labeled array in database
        execute_query(
            f"UPDATE workers SET num_labeled = array_append(num_labeled, 0) WHERE id = %s",
            (g.user["id"],),
            fetch=False
        )

        if random_test:
            selected_class = session["selected_class"]
            num_of_imgs = session["num_of_imgs"]

            session.pop("selected_class", None)
            session.pop("num_of_imgs", None)
            session.pop("to_be_labeled_ids", None)
            session.pop("label_start", None)
            session.pop("random_testing", None)
            session.pop("selected_image_ids", None)

            return redirect(url_for("worker.feedback_success", selected_class=selected_class, num_of_labeled=selected_image_count, num_total=num_of_imgs))
        else:
            # Clear selected image ids from session
            session.pop("selected_image_ids", None)

            return redirect(url_for('worker.testing_passed'))
    else:
        if random_test:
            log_action(f"User {g.user['username']} failed random test for class {session['selected_class']}", g.user["id"])

            # flash("You failed random testing", "warning")

            # Add selected class to banned table for worker
            execute_query(
                "INSERT INTO banned (worker_id, class, expiration) VALUES (%s, %s, %s)",
                (g.user["id"], session["selected_class"], datetime.now().replace(microsecond=0) + timedelta(hours=current_app.config['HIDDEN_TEST_BAN_EXPIRE_HOURS'])),
                fetch=False
            )

            session.pop("selected_class", None)
            session.pop("num_of_imgs", None)
            session.pop("to_be_labeled_ids", None)
            session.pop("label_start", None)
            session.pop("random_testing", None)
            session.pop("selected_image_ids", None)

            return redirect(url_for('worker.feedback_fail_random'))
        else:
            log_action(f"User {g.user['username']} failed testing stage for class {session['selected_class']} and is banned", g.user["id"])

            # Add selected class to banned table for worker
            execute_query(
                "INSERT INTO banned (worker_id, class, expiration) VALUES (%s, %s, %s)",
                (g.user["id"], session["selected_class"], datetime.now().replace(microsecond=0) + timedelta(days=current_app.config['BAN_EXPIRE_DAYS'])),
                fetch=False
            )

            # Save user's class selection for feedback page
            selected_class = session["selected_class"]

            # Delete session
            session.pop("selected_class", None)
            session.pop("num_of_imgs", None)
            session.pop("selected_image_ids", None)

            return redirect(url_for('worker.testing_failed', selected_class=selected_class))


# Define testing passed feedback page
@bp.route('/testing_passed', methods=('GET', 'POST'))
@login_required
def testing_passed():
    """Testing passed feedback page."""
    return render_template("worker/testing_passed.html", selected_class=session["selected_class"])


# Define labeling page
@bp.route('/labeling', methods=('GET', 'POST'))
@login_required
def labeling():
    """Show images to be labeled and submit them."""
    # Check if user is eligible for selected class
    if session.get("selected_class") not in g.user["eligible_classes"]:
        return redirect(url_for('worker.selection_choice'))

    # Check if label start is in session
    if "label_start" not in session:
        # If not, set it to current time
        session["label_start"] = time.time()

    if "random_testing" not in session:
        session["random_testing"] = randint(1, current_app.config["RANDOM_TESTING_INTERVAL"]) == 1

    # Choose number of images to be labeled from session
    # Choose num_of_imgs random not processed images
    # and append their ids to session to_be_labeled_ids
    # Skip images already labeled by current user
    if "to_be_labeled_ids" not in session:
        if session["random_testing"]:
            pick_testing_images()
            session["to_be_labeled_ids"] = session["selected_image_ids"]
        else:
            session["to_be_labeled_ids"] = [row["id"] for row in execute_query(
                "SELECT * FROM images WHERE processing != 'processed' AND NOT %s = ANY(labeled_by) AND classification IN %s ORDER BY RANDOM() LIMIT %s",
                (g.user["id"], (session.get("selected_class"), "/"), session["num_of_imgs"],)
            )]

    # Query images from database with id from session selected_image_ids 
    selected_images = []
    for image_id in session["to_be_labeled_ids"]:
        image = execute_query(
            "SELECT * FROM images WHERE id = %s", (image_id,)
        )[0]
        selected_images.append(image)

    return render_template("worker/labeling.html", selected_images=selected_images)


# Submit selected images for labeling
@bp.route('/labeling_submit', methods=('POST',))
@login_required
def labeling_submit():
    """Update counts of selected images and change their processing to holding or processed."""

    if session.get("random_testing"):
        return submit_testing(random_test=True)

    # Get selected image id from request
    selected_image_ids = request.form.keys()
    selected_image_count = len(selected_image_ids)
    if len(selected_image_ids) == 0:
        selected_image_ids = [-1]

    # Save selected class
    selected_class = session["selected_class"]
    num_of_labeled = selected_image_count
    num_of_imgs = session["num_of_imgs"]

    # Calculate time spent labeling
    label_time = time.time() - session["label_start"]

    # Append worker's id to workers column in images table for selected images
    for img_id in session["to_be_labeled_ids"]:
        execute_query(
            "UPDATE images SET labeled_by = array_append(labeled_by, %s) WHERE id = %s",
            (g.user["id"], img_id),
            fetch=False
        )

    # Check if user selected anything
    if not selected_image_ids:
        # Format label time to minutes:seconds
        label_time = f"{int(label_time // 60):02}:{int(label_time % 60):02}"

        # Log action
        log_action(f"User {g.user['username']} labeled {session['num_of_imgs']} images of which 0 are in class {session['selected_class']} in {label_time}",
                g.user["id"])

        session.pop("selected_class", None)
        session.pop("num_of_imgs", None)
        session.pop("to_be_labeled_ids", None)
        session.pop("label_start", None)
        return redirect(url_for("worker.feedback_success", selected_class=selected_class, num_of_labeled=0, num_total=num_of_imgs))

    # Update num_labeled for worker
    execute_query(
        "UPDATE workers SET num_labeled[%s] = num_labeled[%s] + %s WHERE id = %s",
        (g.user["eligible_classes"].index(session["selected_class"]) + 1, g.user["eligible_classes"].index(session["selected_class"]) + 1, session["num_of_imgs"], g.user["id"]),
        fetch=False
    )

    # Add labeling time to cumulative time spent for worker
    execute_query(
        "UPDATE workers SET cumulative_time_spent[%s] = cumulative_time_spent[%s] + %s WHERE id = %s",
        (g.user["eligible_classes"].index(session["selected_class"]) + 1, g.user["eligible_classes"].index(session["selected_class"]) + 1, label_time, g.user["id"]),
        fetch=False
    ) 

    # Move unprocessed selected images to holding and set their class
    execute_query(
        "UPDATE images SET processing = 'holding', classification = %s, class_count = 1 WHERE id IN %s AND processing = 'unprocessed'",
        (session["selected_class"], tuple(selected_image_ids)),
        fetch=False
    )

    # Increase class count for selected holding images
    execute_query(
        "UPDATE images SET class_count = class_count + 1 WHERE id IN %s AND processing = 'holding' AND classification = %s",
        (tuple(selected_image_ids), session["selected_class"]),
        fetch=False
    )

    # Decrease class count for holding images with different class
    execute_query(
        "UPDATE images SET class_count = class_count - 1 WHERE id IN %s AND processing = 'holding' AND classification != %s",
        (tuple(selected_image_ids), session["selected_class"]),
        fetch=False
    )

    # Move holding images with class count equal to 0 to unprocessed
    execute_query(
        "UPDATE images SET processing = 'unprocessed' WHERE id IN %s AND processing = 'holding' AND class_count = 0",
        (tuple(selected_image_ids),),
        fetch=False
    )

    # Move holding images with class count equal to NUM_VOTES to processed
    execute_query(
        "UPDATE images SET processing = 'processed' WHERE id IN %s AND processing = 'holding' AND class_count = %s",
        (tuple(selected_image_ids), current_app.config["NUM_VOTES"]),
        fetch=False
    )

    # Format label time to minutes:seconds
    label_time = f"{int(label_time // 60):02}:{int(label_time % 60):02}"

    # Log action
    log_action(f"User {g.user['username']} labeled {session['num_of_imgs']} images of which {num_of_labeled} are in class {session['selected_class']} in {label_time}",
               g.user["id"])

    # Log into activity table
    execute_query(
        f"INSERT INTO activity (worker_id, class, num_labeled) VALUES (%s, %s, %s)",
        (g.user["id"], session["selected_class"], session['num_of_imgs']),
        fetch=False
    )

    # Clear session
    session.pop("selected_class", None)
    session.pop("num_of_imgs", None)
    session.pop("to_be_labeled_ids", None)
    session.pop("label_start", None)
    session.pop("selected_image_ids", None)
    session.pop("random_testing", None)

    # Redirect to feedback page
    return redirect(url_for("worker.feedback_success", selected_class=selected_class, num_of_labeled=num_of_labeled, num_total=num_of_imgs))


# Feedback page
@bp.route('/feedback_success', methods=('GET', 'POST'))
@login_required
def feedback_success():
    """Feedback page after labeling images."""
    selected_class = request.args.get("selected_class")
    num_of_labeled = request.args.get("num_of_labeled")
    num_total = request.args.get("num_total")
    return render_template("worker/feedback_success.html", selected_class=selected_class, num_of_labeled=num_of_labeled, num_total=num_total)    


# Feedback page
@bp.route('/testing_failed', methods=('GET', 'POST'))
@login_required
def testing_failed():
    """Feedback page after failing at testing phase."""
    selected_class = request.args.get("selected_class")
    return render_template("worker/testing_failed.html", selected_class=selected_class)


# Feedback page
@bp.route('/feedback_fail_random', methods=('GET', 'POST'))
@login_required
def feedback_fail_random():
    """Feedback page after failing at random testing."""
    return render_template("worker/feedback_fail_random.html")
