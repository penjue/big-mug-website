import html
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import request, redirect, url_for, flash, abort

import timeline_app as timeline
import commerce_admin as commerce
import secure_payments as payments

app = timeline.app
base = timeline.base

_METHOD_PROVIDER = {
    'M-Pesa': 'M-Pesa',
    'Visa / Card': 'Hosted Card Gateway',
    'Bank Transfer': 'Bank Transfer',
}


def ensure_booking_payment_schema():
    conn = base.db()
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(bookings)').fetchall()}
    additions = {
        'payment_choice': 'TEXT',
        'payment_method': 'TEXT',
        'booking_total_minor': 'INTEGER',
        'booking_currency': 'TEXT',
        'amount_due_now_minor': 'INTEGER',
        'balance_due_minor': 'INTEGER',
        'payment_ref': 'TEXT',
    }
    for name, sql_type in additions.items():
        if name not in cols:
            conn.execute(f'ALTER TABLE bookings ADD COLUMN {name} {sql_type}')
    conn.commit(); conn.close()


ensure_booking_payment_schema()


def _setting_key(exp_id, suffix):
    return f'booking_payment_{int(exp_id)}_{suffix}'


def _booking_amount_config(exp_id):
    raw_minor = timeline.setting(_setting_key(exp_id, 'amount_minor'))
    currency = (timeline.setting(_setting_key(exp_id, 'currency')) or '').upper()
    try:
        minor = int(raw_minor)
        if minor <= 0:
            return None, None
    except Exception:
        return None, None
    if currency not in {'KES', 'GBP', 'USD', 'EUR'}:
        return None, None
    return minor, currency


def _major_to_minor(value):
    text = (value or '').strip().replace(',', '')
    if not text:
        return None
    try:
        amount = Decimal(text).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0 or amount > Decimal('100000000'):
        return None
    return int(amount * 100)


def _allow_full_payment():
    current = timeline.setting('booking_allow_full_payment')
    return current != '0'


@app.post('/admin/booking-payment-settings')
@base.login_required
def booking_payment_settings():
    conn = base.db()
    experiences = conn.execute('SELECT id,name FROM experiences ORDER BY id').fetchall()
    conn.close()

    for exp in experiences:
        amount = _major_to_minor(request.form.get(f'amount_{exp["id"]}', ''))
        currency = request.form.get(f'currency_{exp["id"]}', '').strip().upper()
        if amount is None:
            base.set_setting(_setting_key(exp['id'], 'amount_minor'), '')
            base.set_setting(_setting_key(exp['id'], 'currency'), '')
        else:
            if currency not in {'KES', 'GBP', 'USD', 'EUR'}:
                flash(f'Choose a valid currency for {exp["name"]}.', 'error')
                return redirect(url_for('admin') + '#commerce-settings')
            base.set_setting(_setting_key(exp['id'], 'amount_minor'), str(amount))
            base.set_setting(_setting_key(exp['id'], 'currency'), currency)

    base.set_setting('booking_allow_full_payment', '1' if request.form.get('booking_allow_full_payment') == '1' else '0')
    flash('Booking deposit settings updated.', 'success')
    return redirect(url_for('admin') + '#commerce-settings')


def _booking_config_admin_html():
    csrf = html.escape(base.csrf_token())
    conn = base.db()
    experiences = conn.execute('SELECT id,name,price FROM experiences ORDER BY id').fetchall()
    conn.close()

    rows = []
    for exp in experiences:
        minor, currency = _booking_amount_config(exp['id'])
        amount = '' if minor is None else f'{minor / 100:.2f}'
        currency = currency or 'KES'
        options = ''.join(
            f"<option value='{code}' {'selected' if code == currency else ''}>{code}</option>"
            for code in ('KES', 'GBP', 'USD', 'EUR')
        )
        rows.append(f"""
<div class='card'>
  <h3>{html.escape(exp['name'])}</h3>
  <p class='muted'>Website display price: {html.escape(exp['price'] or 'Not set')}</p>
  <label>Secure booking total</label>
  <input name='amount_{exp['id']}' inputmode='decimal' value='{html.escape(amount)}' placeholder='e.g. 4500.00'>
  <label>Currency</label>
  <select name='currency_{exp['id']}'>{options}</select>
  <p class='muted'>The 50% deposit is calculated from this server-side amount. Leave blank to prevent online paid booking for this experience until the amount is configured.</p>
</div>""")

    checked = 'checked' if _allow_full_payment() else ''
    return f"""
<div class='card' style='border:1px solid #d8bd84'>
  <h3>Tour Booking Deposit Protection</h3>
  <p><b>50% deposit is required before a booking can be confirmed.</b> Customers can also choose full payment where enabled.</p>
  <p class='muted'>The remaining 50% is due on arrival for deposit bookings. Payment status remains security-controlled and cannot be marked Paid from the booking form.</p>
</div>
<form method='POST' action='/admin/booking-payment-settings'>
  <input type='hidden' name='_csrf_token' value='{csrf}'>
  <label><input type='checkbox' name='booking_allow_full_payment' value='1' style='width:auto' {checked}> Allow customers to choose full payment</label>
  <h3 style='margin-top:20px'>Booking totals by experience</h3>
  <div class='cards'>{''.join(rows)}</div>
  <button type='submit'>Save Booking Payment Settings</button>
</form>
"""


_original_admin_commerce_html = commerce.admin_commerce_html


def admin_commerce_with_booking_payments():
    page = _original_admin_commerce_html()
    marker = "<a class='back' href='#top'>↑ Dashboard</a>"
    block = _booking_config_admin_html()
    if marker in page:
        page = page.replace(marker, block + marker, 1)
    return page


commerce.admin_commerce_html = admin_commerce_with_booking_payments


def _public_booking_payment_block():
    methods = commerce.enabled_payment_methods('service')
    if not methods:
        return "<div class='choice-note'><b>Booking payment:</b> Payment methods are being configured. Please contact Big Mug before submitting a booking.</div>"

    conn = base.db()
    exps = conn.execute('SELECT id,name FROM experiences WHERE active=1 ORDER BY id').fetchall()
    conn.close()
    config = {}
    for exp in exps:
        minor, currency = _booking_amount_config(exp['id'])
        if minor is not None:
            config[exp['name']] = {'total_minor': minor, 'currency': currency}

    method_options = ''.join(f"<option value='{html.escape(m)}'>{html.escape(m)}</option>" for m in methods)
    full_option = "<label class='booking-pay-choice'><input type='radio' name='payment_choice' value='Full Payment'> <span><b>Pay in full</b><small>Pay 100% now and arrive with no balance due.</small></span></label>" if _allow_full_payment() else ''

    block = f"""
<div id='booking-payment-choice' class='booking-payment-choice'>
  <div class='booking-payment-title'>Secure your booking</div>
  <p>To reduce fake or unserious bookings, a verified payment is required before Big Mug confirms your reservation.</p>
  <div id='booking-payment-amount' class='booking-payment-amount'>Choose an experience to see the secure payment amount.</div>
  <label class='booking-pay-choice'><input type='radio' name='payment_choice' value='Deposit 50%' checked> <span><b>Pay 50% deposit</b><small>Secure your booking now. The remaining 50% is due on arrival.</small></span></label>
  {full_option}
  <label>Payment method</label>
  <select name='booking_payment_method' required><option value=''>Choose payment method</option>{method_options}</select>
  <div class='commerce-safe-note'>Big Mug never asks for your card PIN, CVV or M-Pesa PIN on this booking form. Real payment is only confirmed by the secure payment provider.</div>
</div>
<style id='booking-payment-style'>
.booking-payment-choice{{grid-column:1/-1;background:#fff8ec;border:1px solid #dfc18b;border-radius:16px;padding:18px;margin-top:4px}}
.booking-payment-title{{font-weight:900;color:#3b2418;font-size:1.15rem}}
.booking-payment-choice>p{{margin:5px 0 12px;color:#6d625c}}
.booking-payment-amount{{background:#0f0d0a;color:#f0cf82;border-radius:12px;padding:12px 14px;margin:12px 0;font-weight:800}}
.booking-pay-choice{{display:flex;align-items:flex-start;gap:10px;background:#fff;border:1px solid #ead7b5;border-radius:12px;padding:12px;margin:8px 0;cursor:pointer}}
.booking-pay-choice input{{width:auto;margin-top:4px}}
.booking-pay-choice span{{display:block}}.booking-pay-choice small{{display:block;color:#6d625c;font-weight:400;margin-top:2px}}
</style>
<script id='booking-payment-script'>
(function(){{
  var pricing={json.dumps(config)};
  var form=document.getElementById('booking-form'); if(!form) return;
  var exp=form.querySelector('select[name="experience"]');
  var box=document.getElementById('booking-payment-amount');
  function money(minor,currency){{return currency+' '+(minor/100).toLocaleString(undefined,{{minimumFractionDigits:2,maximumFractionDigits:2}});}}
  function update(){{
    if(!exp||!box) return;
    var cfg=pricing[exp.value];
    if(!cfg){{box.textContent=exp.value?'Online payment amount has not been configured for this experience yet. Please contact Big Mug.':'Choose an experience to see the secure payment amount.';return;}}
    var choice=form.querySelector('input[name="payment_choice"]:checked');
    var due=choice&&choice.value==='Full Payment'?cfg.total_minor:Math.round(cfg.total_minor/2);
    var balance=cfg.total_minor-due;
    box.textContent='Due now: '+money(due,cfg.currency)+(balance>0?' · Balance on arrival: '+money(balance,cfg.currency):' · Fully paid');
  }}
  if(exp) exp.addEventListener('change',update);
  form.querySelectorAll('input[name="payment_choice"]').forEach(function(r){{r.addEventListener('change',update);}});
  update();
}})();
</script>
"""
    return block


@app.after_request
def booking_payment_public_enhancement(response):
    if request.path == '/' and response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if 'id=\'booking-payment-choice\'' not in page and 'id="booking-form"' in page:
                marker = '<button type="submit" class="btn">Send Booking Request</button>'
                block = _public_booking_payment_block()
                if marker in page:
                    page = page.replace(marker, block + marker, 1)
                else:
                    # Fallback: insert immediately before the booking form closes.
                    start = page.find('id="booking-form"')
                    end = page.find('</form>', start)
                    if start >= 0 and end >= 0:
                        page = page[:end] + block + page[end:]
                response.set_data(page)
                response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Booking payment enhancement failed:', exc)
    return response


def secure_book():
    name = request.form.get('name', '').strip()[:120]
    email = request.form.get('email', '').strip()[:180]
    phone = request.form.get('phone', '').strip()[:60]
    country = request.form.get('country', '').strip()[:120]
    experience_name = request.form.get('experience', '').strip()[:180]
    date = request.form.get('booking_date', '').strip()[:20]
    preferred_time = request.form.get('preferred_time', '').strip()[:20]
    notes = request.form.get('notes', '').strip()[:1500]
    choice = request.form.get('payment_choice', 'Deposit 50%').strip()
    method = request.form.get('booking_payment_method', '').strip()

    try:
        guests = int(request.form.get('guests', '1'))
        assert 1 <= guests <= 100
    except Exception:
        flash('Please enter a valid number of guests.', 'error')
        return redirect(url_for('home') + '#book')

    if not all([name, email, experience_name, date]) or '@' not in email:
        flash('Please complete all required booking fields with a valid email.', 'error')
        return redirect(url_for('home') + '#book')
    if choice not in {'Deposit 50%', 'Full Payment'} or (choice == 'Full Payment' and not _allow_full_payment()):
        flash('Please choose an available booking payment option.', 'error')
        return redirect(url_for('home') + '#book')
    if method not in commerce.enabled_payment_methods('service'):
        flash('Please choose an available payment method.', 'error')
        return redirect(url_for('home') + '#book')

    conn = base.db()
    exp = conn.execute('SELECT * FROM experiences WHERE name=? AND active=1', (experience_name,)).fetchone()
    if not exp:
        conn.close()
        flash('Please choose a currently available experience.', 'error')
        return redirect(url_for('home') + '#book')

    total_minor, currency = _booking_amount_config(exp['id'])
    if total_minor is None:
        conn.close()
        flash('Online payment is not configured for this experience yet. Please contact Big Mug before booking.', 'error')
        return redirect(url_for('home') + '#book')

    due_now = total_minor if choice == 'Full Payment' else (total_minor + 1) // 2
    balance = total_minor - due_now

    cur = conn.execute(
        '''INSERT INTO bookings(name,email,phone,country,experience,booking_date,preferred_time,guests,status,notes,payment_choice,payment_method,booking_total_minor,booking_currency,amount_due_now_minor,balance_due_minor)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (name,email,phone,country,experience_name,date,preferred_time,guests,'Pending',notes,choice,method,total_minor,currency,due_now,balance)
    )
    booking_id = cur.lastrowid
    ref = f'BM-{booking_id:06d}'
    conn.commit(); conn.close()

    payment_ref = payments.create_payment(
        'booking', booking_id, method,
        amount_minor=due_now,
        currency=currency,
        provider=_METHOD_PROVIDER.get(method),
    )
    conn = base.db(); conn.execute('UPDATE bookings SET payment_ref=? WHERE id=?', (payment_ref, booking_id)); conn.commit(); conn.close()

    total_text = payments.format_amount(total_minor, currency)
    due_text = payments.format_amount(due_now, currency)
    balance_text = payments.format_amount(balance, currency)
    body = (
        f"Hello {name},\n\nThank you for choosing Big Mug Coffee & Tours.\n\n"
        f"Booking reference: {ref}\nPayment reference: {payment_ref}\nExperience: {experience_name}\n"
        f"Preferred date: {date}\nPreferred time: {preferred_time or 'Not specified'}\nGuests: {guests}\n"
        f"Booking total: {total_text}\nPayment option: {choice}\nAmount due now: {due_text}\n"
        f"Balance due on arrival: {balance_text if balance else 'None — full payment selected'}\n"
        f"Payment method: {method}\nPayment status: Awaiting Payment\n\n"
        "Your reservation is not confirmed until Big Mug verifies payment and confirms availability. "
        "For your security, never enter a card PIN, CVV or M-Pesa PIN anywhere except the authorised payment provider prompt.\n\n"
        "Big Mug Coffee & Tours"
    )
    base.send_booking_email(email, f'Big Mug Booking & Payment Request - {ref}', body)
    notify = base.admin_email()
    if notify:
        base.send_booking_email(notify, f'[BOOKING] Awaiting payment - {ref}', body + f"\nCustomer phone: {phone or 'Not provided'}")

    flash(f'Booking request received. Reference: {ref}. Payment reference: {payment_ref}. Your booking will only be confirmed after verified payment.', 'success')
    return redirect(url_for('home') + '#book')


app.view_functions['book'] = secure_book


_original_booking_status = app.view_functions.get('booking_status')


def secure_booking_status(item_id):
    requested = request.form.get('status', 'New')
    if requested == 'Confirmed':
        payment = payments.payment_for_order('booking', item_id)
        if not payment or payment['status'] != 'Paid':
            flash('This booking cannot be confirmed until the required deposit or full payment is securely verified as Paid.', 'error')
            return redirect(url_for('admin') + '#bookings')
    if _original_booking_status:
        return _original_booking_status(item_id)
    abort(404)


if _original_booking_status:
    app.view_functions['booking_status'] = secure_booking_status
