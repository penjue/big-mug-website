import html
import re

from flask import request, redirect, url_for, flash, abort

import commerce_admin as commerce
import secure_payments as payments
import timeline_app as timeline

app = timeline.app
base = timeline.base


_METHOD_PROVIDER = {
    'M-Pesa': 'M-Pesa',
    'Visa / Card': 'Hosted Card Gateway',
    'Bank Transfer': 'Bank Transfer',
}


def _payment_note(method):
    if method == 'M-Pesa':
        return timeline.setting('mpesa_instructions') or 'M-Pesa payment instructions will be provided after the order is reviewed.'
    if method == 'Bank Transfer':
        return timeline.setting('bank_instructions') or 'Bank transfer instructions will be provided after the order is reviewed.'
    return 'Card payment will only be completed through a secure hosted payment provider after the order is reviewed.'


def secure_buy_product():
    product_name = request.form.get('product_name', '').strip()[:180]
    customer_name = request.form.get('customer_name', '').strip()[:120]
    email = request.form.get('email', '').strip()[:180]
    phone = request.form.get('phone', '').strip()[:60]
    location = request.form.get('delivery_location', '').strip()[:500]
    provider = request.form.get('delivery_provider', '').strip()[:40]
    payment_method = request.form.get('payment_method', '').strip()[:40]

    try:
        quantity = int(request.form.get('quantity', '1'))
        assert 1 <= quantity <= 50
    except Exception:
        flash('Please enter a valid quantity.', 'error')
        return redirect(url_for('home') + '#buy-product')

    if not customer_name or not email or '@' not in email or not product_name:
        flash('Please complete your name, email and product details.', 'error')
        return redirect(url_for('home') + '#buy-product')
    if payment_method not in commerce.enabled_payment_methods('product'):
        flash('Please choose an available payment method.', 'error')
        return redirect(url_for('home') + '#buy-product')
    if provider not in commerce.enabled_delivery_providers():
        flash('Please choose an available delivery option.', 'error')
        return redirect(url_for('home') + '#buy-product')
    if provider != 'Pickup' and not location:
        flash('Please enter the delivery location.', 'error')
        return redirect(url_for('home') + '#buy-product')

    conn = base.db()
    product = conn.execute('SELECT * FROM products WHERE name=? ORDER BY id DESC LIMIT 1', (product_name,)).fetchone()
    if not product:
        conn.close()
        flash('That product is no longer available.', 'error')
        return redirect(url_for('home') + '#marketplace')

    fee = commerce.delivery_fee(provider)
    amount_minor, currency = payments.calculate_order_total(product['price'] or '', quantity, fee)

    cur = conn.execute(
        '''INSERT INTO product_orders(product_name,product_price,quantity,customer_name,email,phone,delivery_provider,delivery_location,delivery_fee,payment_method,status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (product['name'], product['price'] or '', quantity, customer_name, email, phone, provider, location, fee, payment_method, 'Awaiting Payment')
    )
    order_id = cur.lastrowid
    conn.commit(); conn.close()

    order_ref = f'PO-{order_id:06d}'
    payment_ref = payments.create_payment(
        'product', order_id, payment_method,
        amount_minor=amount_minor,
        currency=currency,
        provider=_METHOD_PROVIDER.get(payment_method),
    )
    total_text = payments.format_amount(amount_minor, currency)

    body = (
        f"Hello {customer_name},\n\nWe have received your Big Mug product order.\n\n"
        f"Order reference: {order_ref}\nPayment reference: {payment_ref}\n"
        f"Product: {product['name']}\nQuantity: {quantity}\n"
        f"Product price: {product['price'] or 'Contact us'}\nDelivery: {provider}\n"
        f"Delivery fee: {fee or 'To be confirmed'}\nServer-calculated total: {total_text}\n"
        f"Payment method: {payment_method}\nPayment status: Awaiting Payment\n\n"
        f"{_payment_note(payment_method)}\n\n"
        "For your security, Big Mug will never ask you to enter a card PIN, card CVV or M-Pesa PIN into the Big Mug website. "
        "Payment is only marked Paid after verified confirmation.\n\nBig Mug Coffee & Tours"
    )
    base.send_booking_email(email, f'Big Mug Product Order Received - {order_ref}', body)
    notify = base.admin_email()
    if notify:
        base.send_booking_email(
            notify,
            f'[ORDER] New Big Mug product order - {order_ref}',
            body + f"\nCustomer phone: {phone or 'Not provided'}\nDelivery location: {location or 'Pickup'}"
        )
    flash(f'Your order request has been received. Order: {order_ref}. Payment reference: {payment_ref}.', 'success')
    return redirect(url_for('home') + '#buy-product')


# Replace the original order endpoint after commerce_admin has registered its route.
app.view_functions['buy_product'] = secure_buy_product


def secure_product_order_status(item_id):
    requested = request.form.get('status', 'New')
    allowed = {'New', 'Awaiting Payment', 'Preparing', 'Out for Delivery', 'Completed', 'Cancelled'}
    if requested == 'Paid':
        flash('Paid status is security-controlled and cannot be set manually. It must come from verified payment confirmation.', 'error')
        return redirect(url_for('admin') + '#commerce-settings')
    if requested not in allowed:
        abort(400)

    conn = base.db()
    order = conn.execute('SELECT * FROM product_orders WHERE id=?', (item_id,)).fetchone()
    if not order:
        conn.close(); abort(404)
    payment = conn.execute('SELECT * FROM payments WHERE order_type=? AND order_id=?', ('product', item_id)).fetchone()

    if requested in {'Preparing', 'Out for Delivery', 'Completed'} and (not payment or payment['status'] != 'Paid'):
        conn.close()
        flash('This order cannot move forward until its payment status is securely confirmed as Paid.', 'error')
        return redirect(url_for('admin') + '#commerce-settings')

    if requested == 'Cancelled' and payment and payment['status'] == 'Paid':
        conn.close()
        flash('A paid order cannot be cancelled directly. It must follow a verified refund process once the payment provider is connected.', 'error')
        return redirect(url_for('admin') + '#commerce-settings')

    conn.execute('UPDATE product_orders SET status=? WHERE id=?', (requested, item_id))
    conn.commit(); conn.close()

    if requested == 'Cancelled' and payment and payment['status'] == 'Awaiting Payment':
        try:
            payments.update_payment_status(payment['payment_ref'], 'Cancelled', 'admin', 'Order cancelled before payment confirmation.')
        except ValueError:
            pass

    flash('Product order status updated.', 'success')
    return redirect(url_for('admin') + '#commerce-settings')


app.view_functions['product_order_status'] = secure_product_order_status


_original_admin_commerce_html = commerce.admin_commerce_html


def secure_admin_commerce_html():
    page = _original_admin_commerce_html()

    # Remove the manual Paid option from the order status controls. Server-side enforcement remains authoritative.
    page = re.sub(r"<option value='Paid'[^>]*>Paid</option>", '', page)

    conn = base.db()
    ledger = conn.execute(
        '''SELECT p.*, o.product_name, o.customer_name
           FROM payments p
           LEFT JOIN product_orders o ON p.order_type='product' AND o.id=p.order_id
           ORDER BY p.id DESC LIMIT 50'''
    ).fetchall()
    conn.close()

    rows = []
    for p in ledger:
        amount = payments.format_amount(p['amount_minor'], p['currency'])
        provider_tx = html.escape(p['provider_transaction_id'] or 'Not received')
        rows.append(
            "<div class='card'>"
            f"<h3>{html.escape(p['payment_ref'])} — {html.escape(p['status'])}</h3>"
            f"<p><b>Order:</b> PO-{int(p['order_id']):06d} · <b>Customer:</b> {html.escape(p['customer_name'] or 'Unknown')}</p>"
            f"<p><b>Method:</b> {html.escape(p['payment_method'])} · <b>Provider:</b> {html.escape(p['provider'] or 'Not connected')}</p>"
            f"<p><b>Server total:</b> {html.escape(amount)} · <b>Provider transaction:</b> {provider_tx}</p>"
            "<p class='muted'>Payment status is audit-controlled. Paid cannot be selected manually.</p>"
            "</div>"
        )

    security = """
<div class='card' style='border:1px solid #d8bd84'>
  <h3>Secure Payments — Phase 1 Active</h3>
  <p><b>Real money processing is not enabled yet.</b> This layer creates immutable payment references, server-side totals, payment status controls, callback replay protection and an audit trail.</p>
  <p class='muted'>No card number, CVV, card PIN, M-Pesa PIN or provider secret is stored in Big Mug Admin or GitHub. Production credentials must stay in Render environment variables.</p>
</div>
"""
    ledger_html = (
        "<h3 style='margin-top:28px'>Secure Payment Ledger</h3><div class='cards'>" + ''.join(rows) + "</div>"
        if rows else
        "<h3 style='margin-top:28px'>Secure Payment Ledger</h3><p class='muted'>No payment records yet.</p>"
    )
    marker = "<a class='back' href='#top'>↑ Dashboard</a>"
    if marker in page:
        page = page.replace(marker, security + ledger_html + marker, 1)
    return page


commerce.admin_commerce_html = secure_admin_commerce_html
