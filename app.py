from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, send_from_directory
import sqlite3, os, secrets, time, tempfile, smtplib
from datetime import timedelta
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("BIG_MUG_DB_PATH", os.path.join(BASE_DIR, "big_mug.db"))
PRODUCT_IMAGE_DIR = os.environ.get("BIG_MUG_PRODUCT_IMAGE_DIR", "/var/data/product_images")
SITE_IMAGE_DIR = os.environ.get("BIG_MUG_SITE_IMAGE_DIR", "/var/data/site_images")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
os.makedirs(SITE_IMAGE_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("BIG_MUG_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("BIG_MUG_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)
if os.environ.get("BIG_MUG_TRUST_PROXY", "0") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

LOGIN_ATTEMPTS = {}
LOGIN_WINDOW = 15 * 60
LOGIN_LIMIT = 5


def send_booking_email(to_email, subject, message):
    smtp_host = os.environ.get("BIG_MUG_SMTP_HOST")
    smtp_port = int(os.environ.get("BIG_MUG_SMTP_PORT", "587"))
    smtp_user = os.environ.get("BIG_MUG_SMTP_USER")
    smtp_password = os.environ.get("BIG_MUG_SMTP_PASSWORD")
    from_email = os.environ.get("BIG_MUG_FROM_EMAIL", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password, from_email]):
        print("Email not sent: SMTP settings are incomplete.")
        return False

    try:
        email = EmailMessage()
        email["Subject"] = subject
        email["From"] = from_email
        email["To"] = to_email
        email.set_content(message)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(email)
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        experience TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        guests INTEGER NOT NULL CHECK(guests >= 1),
        status TEXT NOT NULL DEFAULT 'New',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price TEXT,
        duration TEXT,
        description TEXT,
        active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price TEXT,
        origin TEXT,
        stock TEXT NOT NULL DEFAULT 'In stock',
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS enquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT NOT NULL,
        interest TEXT,
        status TEXT NOT NULL DEFAULT 'New',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS site_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    if not conn.execute("SELECT id FROM admins LIMIT 1").fetchone():
        username = os.environ.get("BIG_MUG_ADMIN_USER", "bigmugadmin")
        password = os.environ.get("BIG_MUG_ADMIN_PASSWORD", "BigMug2026!")
        conn.execute(
            "INSERT INTO admins(username,password_hash) VALUES(?,?)",
            (username, generate_password_hash(password))
        )

    if conn.execute("SELECT COUNT(*) c FROM experiences").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO experiences(name,price,duration,description) VALUES(?,?,?,?)",
            [
                ("Coffee Farm Experience", "From £45", "3 hours", "Walk through the coffee journey from farm to cup."),
                ("Coffee & Adventure Day", "From £85", "Full day", "Combine Kenyan coffee culture with a curated local adventure."),
                ("Private Big Mug Experience", "Custom", "Flexible", "A tailored experience for couples, families, groups or corporate guests.")
            ]
        )

    product_columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "image_filename" not in product_columns:
        conn.execute("ALTER TABLE products ADD COLUMN image_filename TEXT")

    experience_columns = {row["name"] for row in conn.execute("PRAGMA table_info(experiences)").fetchall()}
    if "image_filename" not in experience_columns:
        conn.execute("ALTER TABLE experiences ADD COLUMN image_filename TEXT")

    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


def get_setting(key, default=None):
    conn = db()
    row = conn.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = db()
    conn.execute(
        "INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


def save_image_upload(image, destination):
    if not image or not image.filename:
        return None, "Please choose an image to upload."

    original_name = secure_filename(image.filename)
    if "." not in original_name:
        return None, "Please upload a JPG, JPEG, PNG or WEBP image."

    extension = original_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None, "Please upload a JPG, JPEG, PNG or WEBP image."

    filename = f"{secrets.token_hex(12)}.{extension}"
    image.save(os.path.join(destination, filename))
    return filename, None


def remove_image_file(directory, filename):
    if not filename:
        return
    try:
        path = os.path.join(directory, os.path.basename(filename))
        if os.path.isfile(path):
            os.remove(path)
    except OSError as exc:
        print(f"Image cleanup failed: {exc}")


@app.before_request
def protect_posts():
    if request.method == "POST":
        submitted = request.form.get("_csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400, description="Invalid or missing CSRF token.")


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    return resp


def client_key():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


def login_blocked(key):
    now = time.time()
    attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if now - t < LOGIN_WINDOW]
    LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= LOGIN_LIMIT


def record_failed_login(key):
    LOGIN_ATTEMPTS.setdefault(key, []).append(time.time())


@app.get("/health")
def health():
    try:
        conn = db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "error"}, 503


@app.get("/product-images/<path:filename>")
def product_image(filename):
    return send_from_directory(PRODUCT_IMAGE_DIR, filename)


@app.get("/site-images/<path:filename>")
def site_image(filename):
    return send_from_directory(SITE_IMAGE_DIR, filename)


@app.route("/")
def home():
    conn = db()
    exps = conn.execute("SELECT * FROM experiences WHERE active=1 ORDER BY id").fetchall()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC LIMIT 12").fetchall()
    logo_row = conn.execute("SELECT value FROM site_settings WHERE key='logo_filename'").fetchone()
    conn.close()
    logo_filename = logo_row["value"] if logo_row else None
    return render_template("index.html", experiences=exps, products=products, logo_filename=logo_filename)


@app.post("/book")
def book():
    name = request.form.get("name", "").strip()[:120]
    email = request.form.get("email", "").strip()[:180]
    phone = request.form.get("phone", "").strip()[:60]
    experience = request.form.get("experience", "").strip()[:180]
    booking_date = request.form.get("booking_date", "").strip()[:20]
    guests = request.form.get("guests", "1").strip()
    notes = request.form.get("notes", "").strip()[:1500]

    if not all([name, email, experience, booking_date, guests]) or "@" not in email:
        flash("Please complete all required booking fields with a valid email.", "error")
        return redirect(url_for("home") + "#book")

    try:
        guests_i = int(guests)
        if guests_i < 1 or guests_i > 100:
            raise ValueError
    except ValueError:
        flash("Please enter a valid number of guests.", "error")
        return redirect(url_for("home") + "#book")

    conn = db()
    valid_exp = conn.execute("SELECT id FROM experiences WHERE name=? AND active=1", (experience,)).fetchone()
    if not valid_exp:
        conn.close()
        flash("Please choose a currently available experience.", "error")
        return redirect(url_for("home") + "#book")

    cursor = conn.execute(
        """INSERT INTO bookings(name,email,phone,experience,booking_date,guests,notes)
           VALUES(?,?,?,?,?,?,?)""",
        (name, email, phone, experience, booking_date, guests_i, notes)
    )
    booking_id = cursor.lastrowid
    booking_ref = f"BM-{booking_id:06d}"
    conn.commit()
    conn.close()

    email_message = f"""Hello {name},

Thank you for choosing Big Mug Coffee & Tours.

We have received your booking request.

Booking Reference: {booking_ref}
Experience: {experience}
Preferred Date: {booking_date}
Number of Guests: {guests_i}
Status: Pending Confirmation

Please keep your booking reference for any future communication with us.

We will contact you again once your booking has been confirmed.

Big Mug Coffee & Tours
Discover the journey. Taste the story. Remember the experience.
"""

    email_sent = send_booking_email(email, f"Big Mug Booking Received - {booking_ref}", email_message)
    if email_sent:
        flash(f"Thank you. Your booking request has been received. Your booking reference is {booking_ref}. A confirmation email has been sent to you.", "success")
    else:
        flash(f"Thank you. Your booking request has been received. Your booking reference is {booking_ref}. Please keep this reference for future communication.", "success")
    return redirect(url_for("home") + "#book")


@app.route("/login", methods=["GET", "POST"])
def login():
    key = client_key()
    if request.method == "POST":
        if login_blocked(key):
            flash("Too many failed login attempts. Please try again later.", "error")
            return render_template("login.html"), 429

        username = request.form.get("username", "").strip()[:120]
        password = request.form.get("password", "")
        conn = db()
        admin_user = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
        conn.close()

        if admin_user and check_password_hash(admin_user["password_hash"], password):
            LOGIN_ATTEMPTS.pop(key, None)
            session.clear()
            session.permanent = True
            session["admin_id"] = admin_user["id"]
            session["username"] = admin_user["username"]
            csrf_token()
            return redirect(url_for("admin"))

        record_failed_login(key)
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.get("/admin")
@login_required
def admin():
    conn = db()
    bookings = conn.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
    experiences = conn.execute("SELECT * FROM experiences ORDER BY id ASC").fetchall()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    enquiries = conn.execute("SELECT * FROM enquiries ORDER BY created_at DESC").fetchall()
    logo_row = conn.execute("SELECT value FROM site_settings WHERE key='logo_filename'").fetchone()
    conn.close()
    logo_filename = logo_row["value"] if logo_row else None
    return render_template(
        "admin.html",
        bookings=bookings,
        experiences=experiences,
        products=products,
        enquiries=enquiries,
        logo_filename=logo_filename
    )


@app.post("/admin/site/logo")
@login_required
def update_logo():
    filename, error = save_image_upload(request.files.get("logo"), SITE_IMAGE_DIR)
    if error:
        flash(error, "error")
        return redirect(url_for("admin") + "#branding")
    set_setting("logo_filename", filename)
    flash("Website logo updated successfully.", "success")
    return redirect(url_for("admin") + "#branding")


@app.post("/admin/experience/<int:item_id>/image")
@login_required
def update_experience_image(item_id):
    filename, error = save_image_upload(request.files.get("image"), SITE_IMAGE_DIR)
    if error:
        flash(error, "error")
        return redirect(url_for("admin") + "#experiences")

    conn = db()
    exists = conn.execute("SELECT id FROM experiences WHERE id=?", (item_id,)).fetchone()
    if not exists:
        conn.close()
        abort(404)
    conn.execute("UPDATE experiences SET image_filename=? WHERE id=?", (filename, item_id))
    conn.commit()
    conn.close()
    flash("Experience photo updated successfully.", "success")
    return redirect(url_for("admin") + "#experiences")


@app.post("/admin/booking/<int:item_id>/status")
@login_required
def booking_status(item_id):
    status = request.form.get("status", "New")
    if status not in {"New", "Confirmed", "Completed", "Cancelled"}:
        abort(400)

    conn = db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=?", (item_id,)).fetchone()
    if not booking:
        conn.close()
        abort(404)

    old_status = booking["status"]
    conn.execute("UPDATE bookings SET status=? WHERE id=?", (status, item_id))
    conn.commit()
    conn.close()

    if status == "Confirmed" and old_status != "Confirmed":
        booking_ref = f"BM-{item_id:06d}"
        confirmation_message = f"""Hello {booking['name']},

Great news! Your Big Mug Coffee & Tours booking has been confirmed.

Booking Reference: {booking_ref}
Experience: {booking['experience']}
Date: {booking['booking_date']}
Number of Guests: {booking['guests']}
Status: Confirmed

We look forward to welcoming you and sharing the journey of Kenyan coffee from farm to cup.

Please keep your booking reference for any future communication with us.

Big Mug Coffee & Tours
Discover the journey. Taste the story. Remember the experience.
"""
        email_sent = send_booking_email(booking["email"], f"Big Mug Booking Confirmed - {booking_ref}", confirmation_message)
        if email_sent:
            flash(f"Booking {booking_ref} confirmed and confirmation email sent.", "success")
        else:
            flash(f"Booking {booking_ref} confirmed, but the confirmation email could not be sent.", "error")

    return redirect(url_for("admin"))


@app.post("/admin/experience/add")
@login_required
def add_experience():
    name = request.form.get("name", "").strip()[:160]
    if not name:
        flash("Experience name is required.", "error")
        return redirect(url_for("admin"))

    conn = db()
    conn.execute(
        "INSERT INTO experiences(name,price,duration,description) VALUES(?,?,?,?)",
        (
            name,
            request.form.get("price", "").strip()[:60],
            request.form.get("duration", "").strip()[:80],
            request.form.get("description", "").strip()[:1200]
        )
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin") + "#experiences")


@app.post("/admin/product/add")
@login_required
def add_product():
    name = request.form.get("name", "").strip()[:160]
    if not name:
        flash("Product name is required.", "error")
        return redirect(url_for("admin"))

    stock = request.form.get("stock", "In stock")
    if stock not in {"In stock", "Sold out"}:
        stock = "In stock"

    image_filename = None
    image = request.files.get("image")
    if image and image.filename:
        image_filename, error = save_image_upload(image, PRODUCT_IMAGE_DIR)
        if error:
            flash(error, "error")
            return redirect(url_for("admin"))

    conn = db()
    conn.execute(
        """INSERT INTO products
           (name, price, origin, stock, description, image_filename)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            name,
            request.form.get("price", "").strip()[:60],
            request.form.get("origin", "").strip()[:120],
            stock,
            request.form.get("description", "").strip()[:1200],
            image_filename
        )
    )
    conn.commit()
    conn.close()
    flash("Product added successfully.", "success")
    return redirect(url_for("admin") + "#products")


@app.post("/admin/product/<int:item_id>/edit")
@login_required
def edit_product(item_id):
    name = request.form.get("name", "").strip()[:160]
    if not name:
        flash("Product name is required.", "error")
        return redirect(url_for("admin") + "#products")

    stock = request.form.get("stock", "In stock")
    if stock not in {"In stock", "Sold out"}:
        stock = "In stock"

    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (item_id,)).fetchone()
    if not product:
        conn.close()
        abort(404)

    image_filename = product["image_filename"]
    new_image = request.files.get("image")
    if new_image and new_image.filename:
        new_filename, error = save_image_upload(new_image, PRODUCT_IMAGE_DIR)
        if error:
            conn.close()
            flash(error, "error")
            return redirect(url_for("admin") + "#products")
        old_filename = image_filename
        image_filename = new_filename
        remove_image_file(PRODUCT_IMAGE_DIR, old_filename)

    conn.execute(
        """UPDATE products
           SET name=?, price=?, origin=?, stock=?, description=?, image_filename=?
           WHERE id=?""",
        (
            name,
            request.form.get("price", "").strip()[:60],
            request.form.get("origin", "").strip()[:120],
            stock,
            request.form.get("description", "").strip()[:1200],
            image_filename,
            item_id
        )
    )
    conn.commit()
    conn.close()
    flash("Product updated successfully.", "success")
    return redirect(url_for("admin") + "#products")


@app.post("/admin/product/<int:item_id>/delete")
@login_required
def delete_product(item_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (item_id,)).fetchone()
    if not product:
        conn.close()
        abort(404)

    image_filename = product["image_filename"]
    conn.execute("DELETE FROM products WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    remove_image_file(PRODUCT_IMAGE_DIR, image_filename)
    flash("Product deleted successfully.", "success")
    return redirect(url_for("admin") + "#products")


@app.post("/admin/enquiry/add")
@login_required
def add_enquiry():
    name = request.form.get("name", "").strip()[:160]
    contact = request.form.get("contact", "").strip()[:180]
    if not name or not contact:
        flash("Customer name and contact are required.", "error")
        return redirect(url_for("admin"))

    status = request.form.get("status", "New")
    if status not in {"New", "Contacted", "Confirmed", "Closed"}:
        status = "New"

    conn = db()
    conn.execute(
        "INSERT INTO enquiries(name,contact,interest,status) VALUES(?,?,?,?)",
        (name, contact, request.form.get("interest", "").strip()[:240], status)
    )
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/password")
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if len(new) < 12:
        flash("New password must be at least 12 characters.", "error")
        return redirect(url_for("admin") + "#security")
    if new != confirm:
        flash("New passwords do not match.", "error")
        return redirect(url_for("admin") + "#security")

    conn = db()
    admin_user = conn.execute("SELECT * FROM admins WHERE id=?", (session["admin_id"],)).fetchone()
    if not admin_user or not check_password_hash(admin_user["password_hash"], current):
        conn.close()
        flash("Current password is incorrect.", "error")
        return redirect(url_for("admin") + "#security")

    conn.execute("UPDATE admins SET password_hash=? WHERE id=?", (generate_password_hash(new), session["admin_id"]))
    conn.commit()
    conn.close()
    flash("Admin password updated.", "success")
    return redirect(url_for("admin") + "#security")


@app.get("/admin/backup")
@login_required
def backup_database():
    fd, path = tempfile.mkstemp(prefix="big_mug_backup_", suffix=".db")
    os.close(fd)
    source = db()
    dest = sqlite3.connect(path)
    source.backup(dest)
    dest.close()
    source.close()
    return send_file(path, as_attachment=True, download_name="big_mug_backup.db")


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message="That request could not be verified."), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(413)
def too_large(error):
    return render_template("error.html", code=413, message="The submitted request is too large."), 413


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
