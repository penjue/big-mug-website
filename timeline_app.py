import sqlite3
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
    """)
    # Backfill a received event for bookings that existed before timeline tracking.
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


@app.after_request
def add_history_links(response):
    # Keep the existing admin template intact; add a History button beside each booking using a tiny DOM enhancement.
    if request.path=='/admin' and response.content_type and 'text/html' in response.content_type:
        try:
            html=response.get_data(as_text=True)
            script="""<script>(function(){document.querySelectorAll('form[action^=\"/admin/booking/\"][action$=\"/status\"]').forEach(function(f){var m=f.action.match(/\/admin\/booking\/(\d+)\/status$/);if(!m)return;var link=document.createElement('a');link.href='/admin/booking/'+m[1]+'/history';link.textContent='View History';link.style.cssText='display:inline-block;margin-top:8px;padding:8px 12px;border-radius:999px;background:#eee5dd;color:#3b2418;text-decoration:none;font-weight:800;font-size:.82rem';var box=f.parentElement;box.appendChild(link);});})();</script>"""
            html=html.replace('</body>',script+'</body>')
            response.set_data(html)
            response.headers['Content-Length']=str(len(response.get_data()))
        except Exception as exc:
            print('History link injection failed:',exc)
    return response
