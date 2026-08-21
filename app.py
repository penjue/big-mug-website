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
PRODUCT_CATEGORIES = {"Coffee Bags", "Barista Coffee Tools"}
ADMIN_SECURITY_EMAIL = "penjue@gmail.com"
PASSWORD_OTP_TTL = 10 * 60
PASSWORD_OTP_RESEND_WAIT = 60
PASSWORD_OTP_MAX_ATTEMPTS = 5
os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
os.makedirs(SITE_IMAGE_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("BIG_MUG_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.environ.get("BIG_MUG_HTTPS", "0") == "1", PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=12 * 1024 * 1024)
if os.environ.get("BIG_MUG_TRUST_PROXY", "0") == "1": app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
LOGIN_ATTEMPTS = {}; LOGIN_WINDOW = 15 * 60; LOGIN_LIMIT = 5

def send_booking_email(to_email, subject, message):
    host=os.environ.get("BIG_MUG_SMTP_HOST"); port=int(os.environ.get("BIG_MUG_SMTP_PORT","587")); user=os.environ.get("BIG_MUG_SMTP_USER"); password=os.environ.get("BIG_MUG_SMTP_PASSWORD"); sender=os.environ.get("BIG_MUG_FROM_EMAIL",user)
    if not all([host,user,password,sender,to_email]): return False
    try:
        email=EmailMessage(); email["Subject"]=subject; email["From"]=sender; email["To"]=to_email; email.set_content(message)
        with smtplib.SMTP(host,port,timeout=15) as server: server.starttls(); server.login(user,password); server.send_message(email)
        return True
    except Exception as e: print(f"Email sending failed: {e}"); return False

def admin_email():
    return os.environ.get("BIG_MUG_ADMIN_EMAIL") or os.environ.get("BIG_MUG_SMTP_USER")

def clear_password_otp():
    for key in ("password_otp_hash","password_otp_expires","password_otp_attempts","password_otp_sent_at"):
        session.pop(key,None)

def db():
    conn=sqlite3.connect(DB); conn.row_factory=sqlite3.Row; conn.execute("PRAGMA foreign_keys = ON"); return conn

def init_db():
    conn=db(); conn.executescript("""
    CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT,experience TEXT NOT NULL,booking_date TEXT NOT NULL,guests INTEGER NOT NULL CHECK(guests>=1),status TEXT NOT NULL DEFAULT 'New',notes TEXT,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS experiences(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price TEXT,duration TEXT,description TEXT,active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price TEXT,origin TEXT,stock TEXT NOT NULL DEFAULT 'In stock',description TEXT);
    CREATE TABLE IF NOT EXISTS enquiries(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,contact TEXT NOT NULL,interest TEXT,status TEXT NOT NULL DEFAULT 'New',created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS site_settings(key TEXT PRIMARY KEY,value TEXT);
    CREATE TABLE IF NOT EXISTS experience_images(id INTEGER PRIMARY KEY AUTOINCREMENT,experience_id INTEGER NOT NULL,filename TEXT NOT NULL,sort_order INTEGER NOT NULL DEFAULT 0,created_at DATETIME DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(experience_id) REFERENCES experiences(id) ON DELETE CASCADE);
    """)
    if not conn.execute("SELECT id FROM admins LIMIT 1").fetchone():
        conn.execute("INSERT INTO admins(username,password_hash) VALUES(?,?)",(os.environ.get("BIG_MUG_ADMIN_USER","bigmugadmin"),generate_password_hash(os.environ.get("BIG_MUG_ADMIN_PASSWORD","BigMug2026!"))))
    if conn.execute("SELECT COUNT(*) c FROM experiences").fetchone()["c"]==0:
        conn.executemany("INSERT INTO experiences(name,price,duration,description) VALUES(?,?,?,?)",[("Coffee Farm Experience","From £45","3 hours","Walk through the coffee journey from farm to cup."),("Coffee & Adventure Day","From £85","Full day","Combine Kenyan coffee culture with a curated local adventure."),("Private Big Mug Experience","Custom","Flexible","A tailored experience for couples, families, groups or corporate guests.")])
    bc={r["name"] for r in conn.execute("PRAGMA table_info(bookings)")}
    if "country" not in bc: conn.execute("ALTER TABLE bookings ADD COLUMN country TEXT")
    if "preferred_time" not in bc: conn.execute("ALTER TABLE bookings ADD COLUMN preferred_time TEXT")
    pc={r["name"] for r in conn.execute("PRAGMA table_info(products)")}
    if "image_filename" not in pc: conn.execute("ALTER TABLE products ADD COLUMN image_filename TEXT")
    if "category" not in pc: conn.execute("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Coffee Bags'")
    ec={r["name"] for r in conn.execute("PRAGMA table_info(experiences)")}
    if "image_filename" not in ec: conn.execute("ALTER TABLE experiences ADD COLUMN image_filename TEXT")
    if "included" not in ec: conn.execute("ALTER TABLE experiences ADD COLUMN included TEXT")
    if "itinerary" not in ec: conn.execute("ALTER TABLE experiences ADD COLUMN itinerary TEXT")
    if "audience" not in ec: conn.execute("ALTER TABLE experiences ADD COLUMN audience TEXT")
    if "meeting_point" not in ec: conn.execute("ALTER TABLE experiences ADD COLUMN meeting_point TEXT")
    qc={r["name"] for r in conn.execute("PRAGMA table_info(enquiries)")}
    if "email" not in qc: conn.execute("ALTER TABLE enquiries ADD COLUMN email TEXT")
    if "phone" not in qc: conn.execute("ALTER TABLE enquiries ADD COLUMN phone TEXT")
    if "message" not in qc: conn.execute("ALTER TABLE enquiries ADD COLUMN message TEXT")
    for exp in conn.execute("SELECT id,image_filename FROM experiences WHERE image_filename IS NOT NULL AND image_filename!=''").fetchall():
        if not conn.execute("SELECT id FROM experience_images WHERE experience_id=? AND filename=?",(exp["id"],exp["image_filename"])).fetchone(): conn.execute("INSERT INTO experience_images(experience_id,filename,sort_order) VALUES(?,?,0)",(exp["id"],exp["image_filename"]))
    conn.commit(); conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if not session.get("admin_id"): return redirect(url_for("login"))
        return fn(*args,**kwargs)
    return wrapped

def csrf_token():
    if "_csrf_token" not in session: session["_csrf_token"]=secrets.token_urlsafe(32)
    return session["_csrf_token"]
app.jinja_env.globals["csrf_token"]=csrf_token

def set_setting(key,value):
    conn=db(); conn.execute("INSERT INTO site_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value)); conn.commit(); conn.close()

def save_image_upload(image,destination):
    if not image or not image.filename: return None,"Please choose an image to upload."
    name=secure_filename(image.filename)
    if "." not in name or name.rsplit(".",1)[1].lower() not in ALLOWED_IMAGE_EXTENSIONS: return None,"Please upload a JPG, JPEG, PNG or WEBP image."
    ext=name.rsplit(".",1)[1].lower(); filename=f"{secrets.token_hex(12)}.{ext}"; image.save(os.path.join(destination,filename)); return filename,None

def remove_image_file(directory,filename):
    if filename:
        try:
            path=os.path.join(directory,os.path.basename(filename))
            if os.path.isfile(path): os.remove(path)
        except OSError as exc: print(f"Image cleanup failed: {exc}")

def clean_category(v): return v if v in PRODUCT_CATEGORIES else "Coffee Bags"

@app.before_request
def protect_posts():
    if request.method=="POST":
        submitted=request.form.get("_csrf_token",""); expected=session.get("_csrf_token","")
        if not expected or not secrets.compare_digest(submitted,expected): abort(400)

@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"]="nosniff"; resp.headers["X-Frame-Options"]="DENY"; resp.headers["Referrer-Policy"]="strict-origin-when-cross-origin"; resp.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"; resp.headers["Content-Security-Policy"]="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"; return resp

def client_key(): return request.headers.get("X-Forwarded-For",request.remote_addr or "unknown").split(",")[0].strip()
def login_blocked(key):
    now=time.time(); attempts=[t for t in LOGIN_ATTEMPTS.get(key,[]) if now-t<LOGIN_WINDOW]; LOGIN_ATTEMPTS[key]=attempts; return len(attempts)>=LOGIN_LIMIT
def record_failed_login(key): LOGIN_ATTEMPTS.setdefault(key,[]).append(time.time())

@app.get("/health")
def health():
    try: conn=db(); conn.execute("SELECT 1"); conn.close(); return {"status":"ok"},200
    except Exception: return {"status":"error"},503
@app.get("/product-images/<path:filename>")
def product_image(filename): return send_from_directory(PRODUCT_IMAGE_DIR,filename)
@app.get("/site-images/<path:filename>")
def site_image(filename): return send_from_directory(SITE_IMAGE_DIR,filename)

@app.route("/")
def home():
    conn=db(); exps=conn.execute("SELECT * FROM experiences WHERE active=1 ORDER BY id").fetchall(); bags=conn.execute("SELECT * FROM products WHERE category='Coffee Bags' ORDER BY id DESC LIMIT 12").fetchall(); tools=conn.execute("SELECT * FROM products WHERE category='Barista Coffee Tools' ORDER BY id DESC LIMIT 12").fetchall(); logo=conn.execute("SELECT value FROM site_settings WHERE key='logo_filename'").fetchone(); images=conn.execute("SELECT * FROM experience_images ORDER BY experience_id,sort_order,id").fetchall(); conn.close()
    galleries={}
    for image in images: galleries.setdefault(image["experience_id"],[]).append(image)
    return render_template("index.html",experiences=exps,coffee_bags=bags,barista_tools=tools,logo_filename=logo["value"] if logo else None,experience_galleries=galleries)

@app.post("/book")
def book():
    name=request.form.get("name","").strip()[:120]; email=request.form.get("email","").strip()[:180]; phone=request.form.get("phone","").strip()[:60]; country=request.form.get("country","").strip()[:120]; experience=request.form.get("experience","").strip()[:180]; date=request.form.get("booking_date","").strip()[:20]; preferred_time=request.form.get("preferred_time","").strip()[:20]; notes=request.form.get("notes","").strip()[:1500]
    try: guests=int(request.form.get("guests","1")); assert 1<=guests<=100
    except: flash("Please enter a valid number of guests.","error"); return redirect(url_for("home")+"#book")
    if not all([name,email,experience,date]) or "@" not in email: flash("Please complete all required booking fields with a valid email.","error"); return redirect(url_for("home")+"#book")
    conn=db()
    if not conn.execute("SELECT id FROM experiences WHERE name=? AND active=1",(experience,)).fetchone(): conn.close(); flash("Please choose a currently available experience.","error"); return redirect(url_for("home")+"#book")
    cur=conn.execute("INSERT INTO bookings(name,email,phone,country,experience,booking_date,preferred_time,guests,notes) VALUES(?,?,?,?,?,?,?,?,?)",(name,email,phone,country,experience,date,preferred_time,guests,notes)); ref=f"BM-{cur.lastrowid:06d}"; conn.commit(); conn.close()
    msg=f"Hello {name},\n\nThank you for choosing Big Mug Coffee & Tours.\n\nBooking Reference: {ref}\nExperience: {experience}\nPreferred Date: {date}\nPreferred Time: {preferred_time or 'Not specified'}\nNumber of Guests: {guests}\nCountry / Location: {country or 'Not provided'}\nStatus: Pending Confirmation\n\nThis is a booking request, not a confirmed reservation yet. We will review availability and contact you once your booking is confirmed.\n\nBig Mug Coffee & Tours"
    send_booking_email(email,f"Big Mug Booking Request Received - {ref}",msg)
    notify=admin_email()
    if notify: send_booking_email(notify,f"[BOOKING] New Big Mug request - {ref}",f"New booking request\n\nReference: {ref}\nCustomer: {name}\nEmail: {email}\nPhone: {phone or 'Not provided'}\nCountry / Location: {country or 'Not provided'}\nExperience: {experience}\nPreferred date: {date}\nPreferred time: {preferred_time or 'Not specified'}\nGuests: {guests}\nNotes: {notes or 'None'}\n\nReview this in Admin > Booking Requests.")
    flash(f"Booking request received — our team will review availability and contact you shortly. Your reference is {ref}.","success"); return redirect(url_for("home")+"#book")

@app.post("/enquire")
def enquire():
    name=request.form.get("name","").strip()[:120]; email=request.form.get("email","").strip()[:180]; phone=request.form.get("phone","").strip()[:60]; interest=request.form.get("interest","").strip()[:240]; message=request.form.get("message","").strip()[:2000]
    if not name or not email or "@" not in email or not message: flash("Please enter your name, a valid email and your enquiry.","error"); return redirect(url_for("home")+"#enquire")
    contact=email if not phone else f"{email} / {phone}"
    conn=db(); cur=conn.execute("INSERT INTO enquiries(name,contact,interest,status,email,phone,message) VALUES(?,?,?,?,?,?,?)",(name,contact,interest,"New",email,phone,message)); ref=f"EQ-{cur.lastrowid:06d}"; conn.commit(); conn.close()
    send_booking_email(email,f"Big Mug Enquiry Received - {ref}",f"Hello {name},\n\nThank you for contacting Big Mug Coffee & Tours. We have received your enquiry ({ref}) and will respond as soon as possible.\n\nBig Mug Coffee & Tours")
    notify=admin_email()
    if notify: send_booking_email(notify,f"[ENQUIRY] New Big Mug message - {ref}",f"New customer enquiry\n\nReference: {ref}\nCustomer: {name}\nEmail: {email}\nPhone: {phone or 'Not provided'}\nInterest: {interest or 'General enquiry'}\nMessage:\n{message}\n\nReview this in Admin > Customer Enquiries.")
    flash(f"Thank you. Your enquiry has been sent. Reference: {ref}.","success"); return redirect(url_for("home")+"#enquire")

@app.route("/login",methods=["GET","POST"])
def login():
    key=client_key()
    if request.method=="POST":
        if login_blocked(key): flash("Too many failed login attempts. Please try again later.","error"); return render_template("login.html"),429
        conn=db(); user=conn.execute("SELECT * FROM admins WHERE username=?",(request.form.get("username","").strip()[:120],)).fetchone(); conn.close()
        if user and check_password_hash(user["password_hash"],request.form.get("password","")): LOGIN_ATTEMPTS.pop(key,None); session.clear(); session.permanent=True; session["admin_id"]=user["id"]; session["username"]=user["username"]; csrf_token(); return redirect(url_for("admin"))
        record_failed_login(key); flash("Invalid username or password.","error")
    return render_template("login.html")
@app.get("/logout")
def logout(): session.clear(); return redirect(url_for("home"))

@app.get("/admin")
@login_required
def admin():
    conn=db(); bookings=conn.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall(); experiences=conn.execute("SELECT * FROM experiences ORDER BY id").fetchall(); products=conn.execute("SELECT * FROM products ORDER BY category,id DESC").fetchall(); enquiries=conn.execute("SELECT * FROM enquiries ORDER BY created_at DESC").fetchall(); logo=conn.execute("SELECT value FROM site_settings WHERE key='logo_filename'").fetchone(); images=conn.execute("SELECT * FROM experience_images ORDER BY experience_id,sort_order,id").fetchall(); conn.close(); galleries={}
    for image in images: galleries.setdefault(image["experience_id"],[]).append(image)
    return render_template("admin.html",bookings=bookings,experiences=experiences,products=products,enquiries=enquiries,logo_filename=logo["value"] if logo else None,experience_galleries=galleries,admin_security_email=ADMIN_SECURITY_EMAIL,password_otp_pending=bool(session.get("password_otp_hash") and session.get("password_otp_expires",0)>time.time()))

@app.post("/admin/site/logo")
@login_required
def update_logo():
    filename,error=save_image_upload(request.files.get("logo"),SITE_IMAGE_DIR)
    if error: flash(error,"error")
    else: set_setting("logo_filename",filename); flash("Website logo updated successfully.","success")
    return redirect(url_for("admin")+"#branding")

@app.post("/admin/booking/<int:item_id>/status")
@login_required
def booking_status(item_id):
    status=request.form.get("status","New")
    if status not in {"New","Pending","Confirmed","Completed","Cancelled"}: abort(400)
    conn=db(); booking=conn.execute("SELECT * FROM bookings WHERE id=?",(item_id,)).fetchone()
    if not booking: conn.close(); abort(404)
    old=booking["status"]; conn.execute("UPDATE bookings SET status=? WHERE id=?",(status,item_id)); conn.commit(); conn.close()
    if status!=old:
        ref=f"BM-{item_id:06d}"
        time_text=f" at {booking['preferred_time']}" if booking['preferred_time'] else ""
        if status=="Pending":
            send_booking_email(booking["email"],f"Big Mug Booking Update - {ref}",f"Hello {booking['name']},\n\nYour Big Mug booking request {ref} is now being reviewed by our team.\n\nExperience: {booking['experience']}\nRequested date: {booking['booking_date']}{time_text}\n\nWe are checking availability and will contact you again as soon as your booking is confirmed.\n\nThank you for your patience and for choosing Big Mug Coffee & Tours.\n\nBig Mug Coffee & Tours")
        elif status=="Confirmed":
            send_booking_email(booking["email"],f"Big Mug Booking Confirmed - {ref}",f"Hello {booking['name']},\n\nGreat news — your Big Mug booking {ref} is confirmed for {booking['booking_date']}{time_text}.\n\nExperience: {booking['experience']}\nGuests: {booking['guests']}\n\nWe look forward to welcoming you and sharing the Big Mug coffee experience with you.\n\nBig Mug Coffee & Tours")
        elif status=="Completed":
            send_booking_email(booking["email"],f"Thank You from Big Mug - {ref}",f"Hello {booking['name']},\n\nThank you for joining us for your Big Mug experience. We hope you enjoyed discovering the story, people and journey behind every cup.\n\nIt was a pleasure having you with us, and we truly appreciate you choosing Big Mug Coffee & Tours. We would be delighted to welcome you again in the future.\n\nWarm regards,\nBig Mug Coffee & Tours")
        elif status=="Cancelled":
            send_booking_email(booking["email"],f"Big Mug Booking Cancelled - {ref}",f"Hello {booking['name']},\n\nWe are sorry to let you know that your Big Mug booking {ref} has been cancelled.\n\nExperience: {booking['experience']}\nRequested date: {booking['booking_date']}{time_text}\n\nWe apologise for any inconvenience this may cause. If you would like to choose another date or discuss another Big Mug experience, please contact us and we will be happy to help.\n\nThank you for your understanding.\n\nBig Mug Coffee & Tours")
    return redirect(url_for("admin")+"#bookings")

@app.post("/admin/enquiry/<int:item_id>/status")
@login_required
def enquiry_status(item_id):
    status=request.form.get("status","New")
    if status not in {"New","Contacted","Closed"}: abort(400)
    conn=db()
    if not conn.execute("SELECT id FROM enquiries WHERE id=?",(item_id,)).fetchone(): conn.close(); abort(404)
    conn.execute("UPDATE enquiries SET status=? WHERE id=?",(status,item_id)); conn.commit(); conn.close(); flash("Enquiry status updated.","success"); return redirect(url_for("admin")+"#enquiries")

@app.post("/admin/enquiry/<int:item_id>/delete")
@login_required
def delete_enquiry(item_id):
    conn=db()
    if not conn.execute("SELECT id FROM enquiries WHERE id=?",(item_id,)).fetchone(): conn.close(); abort(404)
    conn.execute("DELETE FROM enquiries WHERE id=?",(item_id,)); conn.commit(); conn.close(); flash("Enquiry deleted.","success"); return redirect(url_for("admin")+"#enquiries")

@app.post("/admin/experience/add")
@login_required
def add_experience():
    name=request.form.get("name","").strip()[:160]
    if not name: flash("Experience name is required.","error"); return redirect(url_for("admin")+"#experiences")
    conn=db(); cur=conn.execute("INSERT INTO experiences(name,price,duration,description,included,itinerary,audience,meeting_point) VALUES(?,?,?,?,?,?,?,?)",(name,request.form.get("price","").strip()[:60],request.form.get("duration","").strip()[:80],request.form.get("description","").strip()[:1200],request.form.get("included","").strip()[:1600],request.form.get("itinerary","").strip()[:2000],request.form.get("audience","").strip()[:1200],request.form.get("meeting_point","").strip()[:800])); exp_id=cur.lastrowid; conn.commit(); conn.close()
    uploaded=0
    for image in request.files.getlist("images")[:8]:
        if image and image.filename:
            filename,error=save_image_upload(image,SITE_IMAGE_DIR)
            if not error:
                conn=db(); conn.execute("INSERT INTO experience_images(experience_id,filename,sort_order) VALUES(?,?,?)",(exp_id,filename,uploaded)); conn.commit(); conn.close(); uploaded+=1
    flash("Experience added successfully.","success"); return redirect(url_for("admin")+"#experiences")

@app.post("/admin/experience/<int:item_id>/edit")
@login_required
def edit_experience(item_id):
    name=request.form.get("name","").strip()[:160]
    if not name: flash("Experience name is required.","error"); return redirect(url_for("admin")+"#experiences")
    active=1 if request.form.get("active")=="1" else 0; conn=db()
    if not conn.execute("SELECT id FROM experiences WHERE id=?",(item_id,)).fetchone(): conn.close(); abort(404)
    conn.execute("UPDATE experiences SET name=?,price=?,duration=?,description=?,included=?,itinerary=?,audience=?,meeting_point=?,active=? WHERE id=?",(name,request.form.get("price","").strip()[:60],request.form.get("duration","").strip()[:80],request.form.get("description","").strip()[:1200],request.form.get("included","").strip()[:1600],request.form.get("itinerary","").strip()[:2000],request.form.get("audience","").strip()[:1200],request.form.get("meeting_point","").strip()[:800],active,item_id)); conn.commit(); conn.close(); flash("Experience updated successfully.","success"); return redirect(url_for("admin")+"#experiences")

@app.post("/admin/experience/<int:item_id>/images")
@login_required
def add_experience_images(item_id):
    conn=db()
    if not conn.execute("SELECT id FROM experiences WHERE id=?",(item_id,)).fetchone(): conn.close(); abort(404)
    count=conn.execute("SELECT COUNT(*) c FROM experience_images WHERE experience_id=?",(item_id,)).fetchone()["c"]; conn.close(); uploaded=0
    for image in request.files.getlist("images"):
        if count+uploaded>=8: break
        if image and image.filename:
            filename,error=save_image_upload(image,SITE_IMAGE_DIR)
            if error: flash(error,"error"); continue
            conn=db(); conn.execute("INSERT INTO experience_images(experience_id,filename,sort_order) VALUES(?,?,?)",(item_id,filename,count+uploaded)); conn.commit(); conn.close(); uploaded+=1
    flash(f"{uploaded} photo(s) added to the experience gallery.","success"); return redirect(url_for("admin")+"#experiences")

@app.post("/admin/experience-image/<int:image_id>/delete")
@login_required
def delete_experience_image(image_id):
    conn=db(); image=conn.execute("SELECT * FROM experience_images WHERE id=?",(image_id,)).fetchone()
    if not image: conn.close(); abort(404)
    conn.execute("DELETE FROM experience_images WHERE id=?",(image_id,)); conn.commit(); conn.close(); remove_image_file(SITE_IMAGE_DIR,image["filename"]); flash("Experience photo removed.","success"); return redirect(url_for("admin")+"#experiences")

@app.post("/admin/experience/<int:item_id>/delete")
@login_required
def delete_experience(item_id):
    conn=db(); exp=conn.execute("SELECT id FROM experiences WHERE id=?",(item_id,)).fetchone()
    if not exp: conn.close(); abort(404)
    images=conn.execute("SELECT filename FROM experience_images WHERE experience_id=?",(item_id,)).fetchall(); conn.execute("DELETE FROM experiences WHERE id=?",(item_id,)); conn.commit(); conn.close()
    for image in images: remove_image_file(SITE_IMAGE_DIR,image["filename"])
    flash("Experience deleted successfully.","success"); return redirect(url_for("admin")+"#experiences")

@app.post("/admin/product/add")
@login_required
def add_product():
    name=request.form.get("name","").strip()[:160]
    if not name: flash("Product name is required.","error"); return redirect(url_for("admin")+"#products")
    stock=request.form.get("stock","In stock"); stock=stock if stock in {"In stock","Sold out"} else "In stock"; image_filename=None; image=request.files.get("image")
    if image and image.filename:
        image_filename,error=save_image_upload(image,PRODUCT_IMAGE_DIR)
        if error: flash(error,"error"); return redirect(url_for("admin")+"#products")
    conn=db(); conn.execute("INSERT INTO products(name,price,origin,stock,description,image_filename,category) VALUES(?,?,?,?,?,?,?)",(name,request.form.get("price","").strip()[:60],request.form.get("origin","").strip()[:120],stock,request.form.get("description","").strip()[:1200],image_filename,clean_category(request.form.get("category","Coffee Bags")))); conn.commit(); conn.close(); flash("Product added successfully.","success"); return redirect(url_for("admin")+"#products")

@app.post("/admin/product/<int:item_id>/edit")
@login_required
def edit_product(item_id):
    name=request.form.get("name","").strip()[:160]
    if not name: flash("Product name is required.","error"); return redirect(url_for("admin")+"#products")
    conn=db(); product=conn.execute("SELECT * FROM products WHERE id=?",(item_id,)).fetchone()
    if not product: conn.close(); abort(404)
    filename=product["image_filename"]; image=request.files.get("image")
    if image and image.filename:
        new,error=save_image_upload(image,PRODUCT_IMAGE_DIR)
        if error: conn.close(); flash(error,"error"); return redirect(url_for("admin")+"#products")
        remove_image_file(PRODUCT_IMAGE_DIR,filename); filename=new
    stock=request.form.get("stock","In stock"); stock=stock if stock in {"In stock","Sold out"} else "In stock"
    conn.execute("UPDATE products SET name=?,price=?,origin=?,stock=?,description=?,image_filename=?,category=? WHERE id=?",(name,request.form.get("price","").strip()[:60],request.form.get("origin","").strip()[:120],stock,request.form.get("description","").strip()[:1200],filename,clean_category(request.form.get("category","Coffee Bags")),item_id)); conn.commit(); conn.close(); flash("Product updated successfully.","success"); return redirect(url_for("admin")+"#products")

@app.post("/admin/product/<int:item_id>/delete")
@login_required
def delete_product(item_id):
    conn=db(); product=conn.execute("SELECT * FROM products WHERE id=?",(item_id,)).fetchone()
    if not product: conn.close(); abort(404)
    conn.execute("DELETE FROM products WHERE id=?",(item_id,)); conn.commit(); conn.close(); remove_image_file(PRODUCT_IMAGE_DIR,product["image_filename"]); flash("Product deleted successfully.","success"); return redirect(url_for("admin")+"#products")

@app.post("/admin/enquiry/add")
@login_required
def add_enquiry():
    name=request.form.get("name","").strip()[:160]; contact=request.form.get("contact","").strip()[:180]
    if not name or not contact: flash("Customer name and contact are required.","error"); return redirect(url_for("admin")+"#enquiries")
    status=request.form.get("status","New"); status=status if status in {"New","Contacted","Closed"} else "New"; conn=db(); conn.execute("INSERT INTO enquiries(name,contact,interest,status,email,phone,message) VALUES(?,?,?,?,?,?,?)",(name,contact,request.form.get("interest","").strip()[:240],status,"","",request.form.get("message","").strip()[:2000])); conn.commit(); conn.close(); return redirect(url_for("admin")+"#enquiries")

@app.post("/admin/password/code")
@login_required
def request_password_code():
    current=request.form.get("current_password","")
    conn=db(); user=conn.execute("SELECT * FROM admins WHERE id=?",(session["admin_id"],)).fetchone(); conn.close()
    if not user or not check_password_hash(user["password_hash"],current):
        clear_password_otp(); flash("Current password is incorrect. Verification code was not sent.","error"); return redirect(url_for("admin")+"#security")
    now=time.time(); last=float(session.get("password_otp_sent_at",0) or 0)
    if now-last<PASSWORD_OTP_RESEND_WAIT:
        flash("Please wait one minute before requesting another verification code.","error"); return redirect(url_for("admin")+"#security")
    code=f"{secrets.randbelow(1000000):06d}"
    if not send_booking_email(ADMIN_SECURITY_EMAIL,"Big Mug Admin Security Code",f"Your Big Mug admin verification code is: {code}\n\nThis code expires in 10 minutes.\n\nIf you did not request a password change, do not share this code and keep your current password unchanged."):
        clear_password_otp(); flash("The security code could not be sent. Check the SMTP email settings and try again.","error"); return redirect(url_for("admin")+"#security")
    session["password_otp_hash"]=generate_password_hash(code); session["password_otp_expires"]=now+PASSWORD_OTP_TTL; session["password_otp_attempts"]=0; session["password_otp_sent_at"]=now
    flash(f"A 6-digit verification code was sent to {ADMIN_SECURITY_EMAIL}. It expires in 10 minutes.","success"); return redirect(url_for("admin")+"#security")

@app.post("/admin/password")
@login_required
def change_password():
    current=request.form.get("current_password",""); code=request.form.get("verification_code","").strip(); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
    if len(new)<12 or new!=confirm: flash("New passwords must match and be at least 12 characters.","error"); return redirect(url_for("admin")+"#security")
    conn=db(); user=conn.execute("SELECT * FROM admins WHERE id=?",(session["admin_id"],)).fetchone()
    if not user or not check_password_hash(user["password_hash"],current): conn.close(); flash("Current password is incorrect.","error"); return redirect(url_for("admin")+"#security")
    otp_hash=session.get("password_otp_hash"); expires=float(session.get("password_otp_expires",0) or 0); attempts=int(session.get("password_otp_attempts",0) or 0)
    if not otp_hash or expires<time.time():
        conn.close(); clear_password_otp(); flash("Your verification code is missing or expired. Request a new code.","error"); return redirect(url_for("admin")+"#security")
    if attempts>=PASSWORD_OTP_MAX_ATTEMPTS:
        conn.close(); clear_password_otp(); flash("Too many incorrect verification attempts. Request a new code.","error"); return redirect(url_for("admin")+"#security")
    if not code or not check_password_hash(otp_hash,code):
        conn.close(); session["password_otp_attempts"]=attempts+1
        if attempts+1>=PASSWORD_OTP_MAX_ATTEMPTS: clear_password_otp(); flash("Too many incorrect verification attempts. Request a new code.","error")
        else: flash("The verification code is incorrect.","error")
        return redirect(url_for("admin")+"#security")
    conn.execute("UPDATE admins SET password_hash=? WHERE id=?",(generate_password_hash(new),session["admin_id"])); conn.commit(); conn.close(); clear_password_otp(); flash("Admin password updated successfully with two-step verification.","success"); return redirect(url_for("admin")+"#security")

@app.get("/admin/backup")
@login_required
def backup_database():
    fd,path=tempfile.mkstemp(prefix="big_mug_backup_",suffix=".db"); os.close(fd); source=db(); dest=sqlite3.connect(path); source.backup(dest); dest.close(); source.close(); return send_file(path,as_attachment=True,download_name="big_mug_backup.db")

@app.errorhandler(400)
def bad_request(error): return render_template("error.html",code=400,message="That request could not be verified."),400
@app.errorhandler(404)
def not_found(error): return render_template("error.html",code=404,message="Page not found."),404
@app.errorhandler(413)
def too_large(error): return render_template("error.html",code=413,message="The submitted upload is too large."),413

init_db()
if __name__=="__main__": app.run(debug=os.environ.get("FLASK_DEBUG","0")=="1")