import sqlite3
import html
import re
from urllib.parse import urlparse
from flask import render_template, request, redirect, url_for, flash, abort
import app as base

app = base.app


def ensure_timeline_schema():
    conn = base.db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS booking_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        details TEXT,
        customer_notified INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    );
    CREATE TRIGGER IF NOT EXISTS booking_received_timeline
    AFTER INSERT ON bookings
    BEGIN
        INSERT INTO booking_events(booking_id,event_type,title,details,customer_notified,created_at)
        VALUES(NEW.id,'received','Booking request received',
               'Experience: ' || NEW.experience || ' | Date: ' || NEW.booking_date ||
               CASE WHEN NEW.preferred_time IS NOT NULL AND NEW.preferred_time != '' THEN ' | Time: ' || NEW.preferred_time ELSE '' END,
               1,NEW.created_at);
    END;
    CREATE TABLE IF NOT EXISTS testimonials(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        customer_location TEXT,
        review_text TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.execute("""
        INSERT INTO booking_events(booking_id,event_type,title,details,customer_notified,created_at)
        SELECT b.id,'received','Booking request received',
               'Experience: ' || b.experience || ' | Date: ' || b.booking_date ||
               CASE WHEN b.preferred_time IS NOT NULL AND b.preferred_time != '' THEN ' | Time: ' || b.preferred_time ELSE '' END,
               1,b.created_at
        FROM bookings b
        WHERE NOT EXISTS (SELECT 1 FROM booking_events e WHERE e.booking_id=b.id)
    """)
    conn.commit(); conn.close()


def add_event(booking_id,event_type,title,details='',customer_notified=False):
    conn=base.db()
    conn.execute("INSERT INTO booking_events(booking_id,event_type,title,details,customer_notified) VALUES(?,?,?,?,?)",
                 (booking_id,event_type,title,details,1 if customer_notified else 0))
    conn.commit(); conn.close()


def setting(key):
    conn=base.db(); row=conn.execute("SELECT value FROM site_settings WHERE key=?",(key,)).fetchone(); conn.close()
    return row['value'] if row else ''


def safe_url(value):
    value=(value or '').strip()
    if not value: return ''
    try:
        parsed=urlparse(value)
        return value if parsed.scheme in {'http','https'} and parsed.netloc else ''
    except Exception:
        return ''


def whatsapp_href(value):
    digits=re.sub(r'\D','',value or '')
    return f'https://wa.me/{digits}' if len(digits)>=8 else ''


ensure_timeline_schema()


@base.login_required
def booking_history(item_id):
    conn=base.db()
    booking=conn.execute("SELECT * FROM bookings WHERE id=?",(item_id,)).fetchone()
    if not booking:
        conn.close(); abort(404)
    events=conn.execute("SELECT * FROM booking_events WHERE booking_id=? ORDER BY created_at DESC,id DESC",(item_id,)).fetchall()
    conn.close()
    return render_template("booking_history.html",booking=booking,events=events)

app.add_url_rule('/admin/booking/<int:item_id>/history','booking_history',booking_history,methods=['GET'])


@base.login_required
def timeline_booking_status(item_id):
    status=request.form.get('status','New')
    if status not in {'New','Pending','Confirmed','Completed','Cancelled'}: abort(400)
    conn=base.db(); booking=conn.execute('SELECT * FROM bookings WHERE id=?',(item_id,)).fetchone()
    if not booking: conn.close(); abort(404)
    old=booking['status']
    if status==old:
        conn.close(); flash('Booking status is already '+status+'.','success'); return redirect(url_for('admin')+'#bookings')
    conn.execute('UPDATE bookings SET status=? WHERE id=?',(status,item_id)); conn.commit(); conn.close()
    ref=f'BM-{item_id:06d}'; date=booking['booking_date']; time_text=f" at {booking['preferred_time']}" if booking['preferred_time'] else ''
    messages={
        'Pending':(f'Big Mug Booking Update - {ref}',f"Hello {booking['name']},\n\nYour booking request {ref} is now being reviewed. We are checking availability and will contact you as soon as possible.\n\nBig Mug Coffee & Tours"),
        'Confirmed':(f'Big Mug Booking Confirmed - {ref}',f"Hello {booking['name']},\n\nYour Big Mug booking {ref} is confirmed for {date}{time_text}.\n\nWe look forward to welcoming you.\n\nBig Mug Coffee & Tours"),
        'Completed':(f'Thank You from Big Mug - {ref}',f"Hello {booking['name']},\n\nThank you for sharing the Big Mug experience with us. We hope you enjoyed your coffee journey and that the memories stay with you long after the last cup.\n\nIt was a pleasure hosting you, and we would be delighted to welcome you again.\n\nBig Mug Coffee & Tours"),
        'Cancelled':(f'Big Mug Booking Cancelled - {ref}',f"Hello {booking['name']},\n\nWe are sorry to let you know that booking {ref} has been cancelled. We sincerely apologise for the inconvenience.\n\nIf you would like another date or a different Big Mug experience, please contact us and we will be happy to help.\n\nBig Mug Coffee & Tours")
    }
    sent=False
    if status in messages:
        subject,body=messages[status]; sent=base.send_booking_email(booking['email'],subject,body)
    add_event(item_id,'status',f'Status changed: {old} → {status}',
              'Customer email sent.' if sent else ('No automatic customer email for this status.' if status=='New' else 'Customer email could not be confirmed as sent.'),sent)
    flash('Booking status updated.','success'); return redirect(url_for('admin')+'#bookings')

app.view_functions['booking_status']=timeline_booking_status


@base.login_required
def timeline_schedule_update(item_id):
    update_type=request.form.get('update_type','Delay').strip()
    if update_type not in {'Delay','Time Changed','Date Changed'}: abort(400)
    new_date=request.form.get('new_date','').strip()[:20]; new_time=request.form.get('new_time','').strip()[:20]; note=request.form.get('update_message','').strip()[:1200]
    if update_type=='Time Changed' and not new_time: flash('Please enter the new time.','error'); return redirect(url_for('admin')+'#bookings')
    if update_type=='Date Changed' and not new_date: flash('Please enter the new date.','error'); return redirect(url_for('admin')+'#bookings')
    if update_type=='Delay' and not (new_time or new_date or note): flash('For a delay, enter a revised time/date or a short message.','error'); return redirect(url_for('admin')+'#bookings')
    conn=base.db(); booking=conn.execute('SELECT * FROM bookings WHERE id=?',(item_id,)).fetchone()
    if not booking: conn.close(); abort(404)
    old_date=booking['booking_date']; old_time=booking['preferred_time'] or 'Not specified'; final_date=new_date or old_date; final_time=new_time or booking['preferred_time']
    if new_date or new_time:
        conn.execute('UPDATE bookings SET booking_date=?, preferred_time=? WHERE id=?',(final_date,final_time,item_id)); conn.commit()
    conn.close()
    ref=f'BM-{item_id:06d}'; labels={'Delay':'Delay Notice','Time Changed':'Time Change','Date Changed':'Date Change'}
    body=f"Hello {booking['name']},\n\nWe are contacting you with an important update regarding your Big Mug booking {ref}.\n\nUpdate: {labels[update_type]}\nExperience: {booking['experience']}\nOriginal date: {old_date}\nOriginal time: {old_time}\nRevised date: {final_date}\nRevised time: {final_time or 'Not specified'}\n\n{note or 'We apologise for the inconvenience and appreciate your understanding.'}\n\nYour booking remains confirmed unless we contact you separately to say otherwise. We are sorry for any inconvenience caused and we look forward to welcoming you.\n\nBig Mug Coffee & Tours"
    sent=base.send_booking_email(booking['email'],f'Big Mug Booking Schedule Update - {ref}',body)
    details=f"Original: {old_date} {old_time} | Revised: {final_date} {final_time or 'Not specified'}"
    if note: details += f" | Message: {note}"
    add_event(item_id,'schedule',labels[update_type],details,sent)
    flash('Schedule update sent to the customer successfully.' if sent else 'The booking was updated, but the email could not be sent. Please check the email settings.','success' if sent else 'error')
    return redirect(url_for('admin')+'#bookings')

app.view_functions['booking_schedule_update']=timeline_schedule_update


@app.post('/admin/contact-settings')
@base.login_required
def contact_settings():
    values={
        'public_contact_email':request.form.get('contact_email','').strip()[:180],
        'whatsapp_number':request.form.get('whatsapp_number','').strip()[:40],
        'instagram_url':request.form.get('instagram_url','').strip()[:400],
        'facebook_url':request.form.get('facebook_url','').strip()[:400]
    }
    if values['public_contact_email'] and '@' not in values['public_contact_email']:
        flash('Please enter a valid public contact email.','error'); return redirect(url_for('admin')+'#contact-reviews')
    for key in ('instagram_url','facebook_url'):
        if values[key] and not safe_url(values[key]):
            flash('Instagram and Facebook links must be full http:// or https:// URLs.','error'); return redirect(url_for('admin')+'#contact-reviews')
    for key,value in values.items(): base.set_setting(key,value)
    flash('Contact and social links updated.','success'); return redirect(url_for('admin')+'#contact-reviews')


@app.post('/admin/testimonial/add')
@base.login_required
def testimonial_add():
    name=request.form.get('customer_name','').strip()[:120]
    location=request.form.get('customer_location','').strip()[:120]
    review=request.form.get('review_text','').strip()[:1200]
    if not name or not review:
        flash('Customer name and review are required.','error'); return redirect(url_for('admin')+'#contact-reviews')
    conn=base.db(); conn.execute('INSERT INTO testimonials(customer_name,customer_location,review_text,active) VALUES(?,?,?,1)',(name,location,review)); conn.commit(); conn.close()
    flash('Testimonial added.','success'); return redirect(url_for('admin')+'#contact-reviews')


@app.post('/admin/testimonial/<int:item_id>/edit')
@base.login_required
def testimonial_edit(item_id):
    name=request.form.get('customer_name','').strip()[:120]
    location=request.form.get('customer_location','').strip()[:120]
    review=request.form.get('review_text','').strip()[:1200]
    active=1 if request.form.get('active')=='1' else 0
    if not name or not review:
        flash('Customer name and review are required.','error'); return redirect(url_for('admin')+'#contact-reviews')
    conn=base.db(); exists=conn.execute('SELECT id FROM testimonials WHERE id=?',(item_id,)).fetchone()
    if not exists: conn.close(); abort(404)
    conn.execute('UPDATE testimonials SET customer_name=?,customer_location=?,review_text=?,active=? WHERE id=?',(name,location,review,active,item_id)); conn.commit(); conn.close()
    flash('Testimonial updated.','success'); return redirect(url_for('admin')+'#contact-reviews')


@app.post('/admin/testimonial/<int:item_id>/delete')
@base.login_required
def testimonial_delete(item_id):
    conn=base.db(); exists=conn.execute('SELECT id FROM testimonials WHERE id=?',(item_id,)).fetchone()
    if not exists: conn.close(); abort(404)
    conn.execute('DELETE FROM testimonials WHERE id=?',(item_id,)); conn.commit(); conn.close()
    flash('Testimonial deleted.','success'); return redirect(url_for('admin')+'#contact-reviews')


def public_trust_html():
    email=setting('public_contact_email'); whatsapp=setting('whatsapp_number'); instagram=safe_url(setting('instagram_url')); facebook=safe_url(setting('facebook_url')); wa=whatsapp_href(whatsapp)
    conn=base.db(); reviews=conn.execute('SELECT * FROM testimonials WHERE active=1 ORDER BY id DESC LIMIT 6').fetchall(); conn.close()
    review_cards=''.join(
        f"<article style='background:#fff;padding:24px;border-radius:20px;box-shadow:0 12px 28px rgba(35,22,14,.08)'><div style='color:#d3a04f;font-size:1.15rem;letter-spacing:2px'>★★★★★</div><p style='font-size:1.02rem'>“{html.escape(r['review_text'])}”</p><strong style='color:#3b2418'>{html.escape(r['customer_name'])}</strong>{('<div style=\"color:#6d625c;font-size:.9rem\">'+html.escape(r['customer_location'])+'</div>') if r['customer_location'] else ''}</article>"
        for r in reviews)
    reviews_block=(f"<div style='margin-top:55px'><div style='text-align:center;margin-bottom:28px'><small style='color:#b77d27;font-weight:900;letter-spacing:1.4px'>GUEST STORIES</small><h2 style='color:#3b2418;font-size:2.5rem;margin:4px 0'>What Guests Say</h2></div><div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px'>{review_cards}</div></div>" if reviews else '')
    actions=[]
    if wa: actions.append(f"<a href='{html.escape(wa)}' target='_blank' rel='noopener' style='display:inline-block;background:#d3a04f;color:#1d120d;padding:13px 20px;border-radius:999px;text-decoration:none;font-weight:900'>WhatsApp Big Mug</a>")
    if email: actions.append(f"<a href='mailto:{html.escape(email)}' style='display:inline-block;background:#fff;color:#3b2418;padding:13px 20px;border:1px solid #d8cec4;border-radius:999px;text-decoration:none;font-weight:900'>Email Us</a>")
    if instagram: actions.append(f"<a href='{html.escape(instagram)}' target='_blank' rel='noopener' style='color:#3b2418;font-weight:800'>Instagram</a>")
    if facebook: actions.append(f"<a href='{html.escape(facebook)}' target='_blank' rel='noopener' style='color:#3b2418;font-weight:800'>Facebook</a>")
    if not actions: actions.append("<a href='#enquire' style='display:inline-block;background:#d3a04f;color:#1d120d;padding:13px 20px;border-radius:999px;text-decoration:none;font-weight:900'>Ask Big Mug</a>")
    return f"""<section id='contact-trust' style='padding:78px 0;background:#fffaf5'><div class='container'><div style='text-align:center;max-width:760px;margin:0 auto 30px'><small style='color:#b77d27;font-weight:900;letter-spacing:1.4px'>WE'RE HERE TO HELP</small><h2 style='color:#3b2418;font-size:clamp(2.2rem,5vw,3.4rem);margin:6px 0;text-transform:uppercase'>Contact Big Mug</h2><p style='color:#6d625c'>Questions before you book, group planning, marketplace products or a confirmed-booking update? Reach Big Mug through the contact options below.</p></div><div style='display:flex;justify-content:center;align-items:center;gap:12px;flex-wrap:wrap'>{''.join(actions)}</div>{reviews_block}</div></section>"""


def admin_contact_reviews_html():
    csrf=html.escape(base.csrf_token()); email=html.escape(setting('public_contact_email')); whatsapp=html.escape(setting('whatsapp_number')); instagram=html.escape(setting('instagram_url')); facebook=html.escape(setting('facebook_url'))
    conn=base.db(); reviews=conn.execute('SELECT * FROM testimonials ORDER BY id DESC').fetchall(); conn.close()
    review_forms=''.join(f"""<div class='card'><h3>{html.escape(r['customer_name'])}</h3><form method='POST' action='/admin/testimonial/{r['id']}/edit'><input type='hidden' name='_csrf_token' value='{csrf}'><label>Customer name</label><input name='customer_name' value='{html.escape(r['customer_name'])}' required><label>Location</label><input name='customer_location' value='{html.escape(r['customer_location'] or '')}'><label>Review</label><textarea name='review_text' required>{html.escape(r['review_text'])}</textarea><label>Visibility</label><select name='active'><option value='1' {'selected' if r['active'] else ''}>Visible</option><option value='0' {'selected' if not r['active'] else ''}>Hidden</option></select><button>Save Testimonial</button></form><form method='POST' action='/admin/testimonial/{r['id']}/delete'><input type='hidden' name='_csrf_token' value='{csrf}'><button class='red' type='submit'>Delete Testimonial</button></form></div>""" for r in reviews)
    return f"""<section class='section' id='contact-reviews'><div class='section-head'><div><h2>Contact, Social & Reviews</h2><p class='muted'>Control the public contact buttons and guest testimonials without editing code.</p></div></div><div class='cards'><div class='card'><h3>Public Contact Details</h3><form method='POST' action='/admin/contact-settings'><input type='hidden' name='_csrf_token' value='{csrf}'><label>Public contact email</label><input type='email' name='contact_email' value='{email}' placeholder='hello@example.com'><label>WhatsApp number</label><input name='whatsapp_number' value='{whatsapp}' placeholder='+2547...'><div class='muted'>Include the country code. The website creates the WhatsApp link automatically.</div><label>Instagram URL</label><input name='instagram_url' value='{instagram}' placeholder='https://instagram.com/...'><label>Facebook URL</label><input name='facebook_url' value='{facebook}' placeholder='https://facebook.com/...'><button>Save Contact Details</button></form></div><div class='card'><h3>Add Guest Testimonial</h3><form method='POST' action='/admin/testimonial/add'><input type='hidden' name='_csrf_token' value='{csrf}'><label>Customer name</label><input name='customer_name' required><label>Location</label><input name='customer_location' placeholder='e.g. London, UK'><label>Review</label><textarea name='review_text' required placeholder='Use only genuine customer feedback you have permission to publish.'></textarea><button>Add Testimonial</button></form></div></div>{("<h3 style='margin-top:28px'>Manage Testimonials</h3><div class='cards'>"+review_forms+"</div>") if reviews else ''}<a class='back-top' href='#top'>↑ Back to dashboard</a></section>"""


@app.after_request
def enhance_pages(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page=response.get_data(as_text=True)
            if request.path=='/admin':
                history_script="""<script>(function(){document.querySelectorAll('form[action^=\"/admin/booking/\"][action$=\"/status\"]').forEach(function(f){var m=f.action.match(/\/admin\/booking\/(\d+)\/status$/);if(!m)return;var link=document.createElement('a');link.href='/admin/booking/'+m[1]+'/history';link.textContent='View History';link.style.cssText='display:inline-block;margin-top:8px;padding:8px 12px;border-radius:999px;background:#eee5dd;color:#3b2418;text-decoration:none;font-weight:800;font-size:.82rem';f.parentElement.appendChild(link);});})();</script>"""
                section=admin_contact_reviews_html()
                if "id=\"security\"" in page:
                    page=page.replace('<section class="section" id="security">',section+'<section class="section" id="security">',1)
                else:
                    page=page.replace('</div>\n<script>',section+'</div>\n<script>',1)
                page=page.replace('<a href="#security">Security</a>','<a href="#contact-reviews">Contact & Reviews</a><a href="#security">Security</a>',1)
                page=page.replace('</body>',history_script+'</body>')
            elif request.path=='/':
                public=public_trust_html()
                page=page.replace('<section class="enquiry" id="enquire">',public+'<section class="enquiry" id="enquire">',1)
                page=page.replace('<a href="#enquire">Enquire</a><a class="cta"','<a href="#contact-trust">Contact</a><a href="#enquire">Enquire</a><a class="cta"',1)
            response.set_data(page); response.headers['Content-Length']=str(len(response.get_data()))
        except Exception as exc:
            print('Page enhancement failed:',exc)
    return response
