import html
from flask import request, redirect, url_for, flash, abort
import timeline_app as timeline

app = timeline.app
base = timeline.base

PAYMENT_METHODS = ('Visa / Card', 'M-Pesa', 'Bank Transfer')
DELIVERY_PROVIDERS = ('Uber', 'Bolt', 'Glovo', 'Pickup')


def ensure_commerce_schema():
    conn = base.db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS product_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        product_price TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        delivery_provider TEXT NOT NULL,
        delivery_location TEXT,
        delivery_fee TEXT,
        payment_method TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'New',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit(); conn.close()


ensure_commerce_schema()


def enabled_payment_methods(kind):
    prefix = 'product_payment_' if kind == 'product' else 'service_payment_'
    methods = []
    if timeline.setting(prefix + 'visa') == '1': methods.append('Visa / Card')
    if timeline.setting(prefix + 'mpesa') == '1': methods.append('M-Pesa')
    if timeline.setting(prefix + 'bank') == '1': methods.append('Bank Transfer')
    return methods


def enabled_delivery_providers():
    providers = []
    for provider, key in [('Uber','uber'),('Bolt','bolt'),('Glovo','glovo'),('Pickup','pickup')]:
        if timeline.setting('delivery_' + key + '_enabled') == '1':
            providers.append(provider)
    return providers


def delivery_fee(provider):
    key = provider.lower()
    return timeline.setting('delivery_' + key + '_fee')


@app.post('/admin/commerce-settings')
@base.login_required
def commerce_settings():
    checkbox_keys = [
        'product_payment_visa','product_payment_mpesa','product_payment_bank',
        'service_payment_visa','service_payment_mpesa','service_payment_bank',
        'delivery_uber_enabled','delivery_bolt_enabled','delivery_glovo_enabled','delivery_pickup_enabled',
    ]
    for key in checkbox_keys:
        base.set_setting(key, '1' if request.form.get(key) == '1' else '0')

    text_limits = {
        'mpesa_instructions': 500,
        'bank_instructions': 1000,
        'visa_checkout_url': 500,
        'delivery_uber_fee': 80,
        'delivery_bolt_fee': 80,
        'delivery_glovo_fee': 80,
        'delivery_pickup_fee': 80,
        'delivery_uber_connection': 500,
        'delivery_bolt_connection': 500,
        'delivery_glovo_connection': 500,
    }
    for key, limit in text_limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit])

    flash('Payment and delivery settings updated.', 'success')
    return redirect(url_for('admin') + '#commerce-settings')


@app.post('/buy-product')
def buy_product():
    product_name = request.form.get('product_name', '').strip()[:180]
    customer_name = request.form.get('customer_name', '').strip()[:120]
    email = request.form.get('email', '').strip()[:180]
    phone = request.form.get('phone', '').strip()[:60]
    location = request.form.get('delivery_location', '').strip()[:500]
    provider = request.form.get('delivery_provider', '').strip()[:40]
    payment = request.form.get('payment_method', '').strip()[:40]
    try:
        quantity = int(request.form.get('quantity', '1'))
        assert 1 <= quantity <= 50
    except Exception:
        flash('Please enter a valid quantity.', 'error')
        return redirect(url_for('home') + '#buy-product')

    if not customer_name or not email or '@' not in email or not product_name:
        flash('Please complete your name, email and product details.', 'error')
        return redirect(url_for('home') + '#buy-product')

    if payment not in enabled_payment_methods('product'):
        flash('Please choose an available payment method.', 'error')
        return redirect(url_for('home') + '#buy-product')
    if provider not in enabled_delivery_providers():
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
    fee = delivery_fee(provider)
    cur = conn.execute(
        '''INSERT INTO product_orders(product_name,product_price,quantity,customer_name,email,phone,delivery_provider,delivery_location,delivery_fee,payment_method,status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
        (product['name'], product['price'] or '', quantity, customer_name, email, phone, provider, location, fee, payment, 'New')
    )
    order_id = cur.lastrowid
    conn.commit(); conn.close()
    ref = f'PO-{order_id:06d}'

    payment_note = ''
    if payment == 'M-Pesa': payment_note = timeline.setting('mpesa_instructions')
    elif payment == 'Bank Transfer': payment_note = timeline.setting('bank_instructions')
    elif payment == 'Visa / Card':
        payment_note = 'Card payment will be completed through the secure Big Mug checkout once the order is confirmed.'

    body = (
        f"Hello {customer_name},\n\nWe have received your Big Mug product order.\n\n"
        f"Order reference: {ref}\nProduct: {product['name']}\nQuantity: {quantity}\n"
        f"Product price: {product['price'] or 'Contact us'}\nDelivery: {provider}\n"
        f"Delivery fee: {fee or 'To be confirmed'}\nPayment method: {payment}\n\n"
        f"{payment_note}\n\nYour order is not marked as paid until Big Mug confirms payment.\n\nBig Mug Coffee & Tours"
    )
    base.send_booking_email(email, f'Big Mug Product Order Received - {ref}', body)
    notify = base.admin_email()
    if notify:
        base.send_booking_email(notify, f'[ORDER] New Big Mug product order - {ref}', body + f"\nCustomer phone: {phone or 'Not provided'}\nDelivery location: {location or 'Pickup'}")
    flash(f'Your order request has been received. Reference: {ref}.', 'success')
    return redirect(url_for('home') + '#buy-product')


@app.post('/admin/product-order/<int:item_id>/status')
@base.login_required
def product_order_status(item_id):
    status = request.form.get('status', 'New')
    if status not in {'New','Awaiting Payment','Paid','Preparing','Out for Delivery','Completed','Cancelled'}:
        abort(400)
    conn = base.db()
    order = conn.execute('SELECT * FROM product_orders WHERE id=?', (item_id,)).fetchone()
    if not order:
        conn.close(); abort(404)
    conn.execute('UPDATE product_orders SET status=? WHERE id=?', (status, item_id))
    conn.commit(); conn.close()
    flash('Product order status updated.', 'success')
    return redirect(url_for('admin') + '#commerce-settings')


def checked(key):
    return 'checked' if timeline.setting(key) == '1' else ''


def field(key):
    return html.escape(timeline.setting(key) or '')


def admin_commerce_html():
    csrf = html.escape(base.csrf_token())
    conn = base.db()
    orders = conn.execute('SELECT * FROM product_orders ORDER BY id DESC LIMIT 50').fetchall()
    conn.close()

    order_cards = ''
    for order in orders:
        ref = f"PO-{order['id']:06d}"
        order_cards += f"""
<div class='card'>
  <h3>{html.escape(ref)} — {html.escape(order['product_name'])}</h3>
  <p><b>Customer:</b> {html.escape(order['customer_name'])} · {html.escape(order['email'])}</p>
  <p><b>Qty:</b> {order['quantity']} · <b>Payment:</b> {html.escape(order['payment_method'])} · <b>Delivery:</b> {html.escape(order['delivery_provider'])}</p>
  <p><b>Delivery fee:</b> {html.escape(order['delivery_fee'] or 'To be confirmed')} · <b>Status:</b> {html.escape(order['status'])}</p>
  <form method='POST' action='/admin/product-order/{order['id']}/status'>
    <input type='hidden' name='_csrf_token' value='{csrf}'>
    <label>Order status</label>
    <select name='status'>
      {''.join(f"<option value='{s}' {'selected' if s == order['status'] else ''}>{s}</option>" for s in ['New','Awaiting Payment','Paid','Preparing','Out for Delivery','Completed','Cancelled'])}
    </select>
    <button type='submit'>Update Order</button>
  </form>
</div>"""

    return f"""
<section class='sec' id='commerce-settings'>
  <div class='head'><div><h2>Payments & Delivery</h2><p class='muted'>Control customer payment choices, delivery providers and product orders.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/commerce-settings'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      <h3>Product payment methods</h3>
      <label><input type='checkbox' name='product_payment_visa' value='1' style='width:auto' {checked('product_payment_visa')}> Visa / Card</label>
      <label><input type='checkbox' name='product_payment_mpesa' value='1' style='width:auto' {checked('product_payment_mpesa')}> M-Pesa</label>
      <label><input type='checkbox' name='product_payment_bank' value='1' style='width:auto' {checked('product_payment_bank')}> Bank Transfer</label>

      <h3 style='margin-top:24px'>Service / tour payment methods</h3>
      <label><input type='checkbox' name='service_payment_visa' value='1' style='width:auto' {checked('service_payment_visa')}> Visa / Card</label>
      <label><input type='checkbox' name='service_payment_mpesa' value='1' style='width:auto' {checked('service_payment_mpesa')}> M-Pesa</label>
      <label><input type='checkbox' name='service_payment_bank' value='1' style='width:auto' {checked('service_payment_bank')}> Bank Transfer</label>

      <h3 style='margin-top:24px'>Payment connection details</h3>
      <label>M-Pesa instructions / Till / Paybill</label><textarea name='mpesa_instructions' placeholder='e.g. Paybill, Till number or payment instructions'>{field('mpesa_instructions')}</textarea>
      <label>Bank transfer instructions</label><textarea name='bank_instructions' placeholder='Bank name, account name and payment reference instructions'>{field('bank_instructions')}</textarea>
      <label>Visa / card hosted checkout URL</label><input name='visa_checkout_url' value='{field('visa_checkout_url')}' placeholder='Leave blank until a secure payment gateway is connected'>
      <div class='muted'>Card numbers are never collected directly on the Big Mug website. A secure hosted payment provider should be connected here later.</div>

      <h3 style='margin-top:24px'>Delivery options</h3>
      <label><input type='checkbox' name='delivery_uber_enabled' value='1' style='width:auto' {checked('delivery_uber_enabled')}> Uber delivery</label>
      <label>Uber delivery fee</label><input name='delivery_uber_fee' value='{field('delivery_uber_fee')}' placeholder='e.g. KES 350 or Calculated by Uber'>
      <label>Uber connection / integration reference</label><input name='delivery_uber_connection' value='{field('delivery_uber_connection')}' placeholder='Connection URL or integration reference (no secret keys)'>

      <label><input type='checkbox' name='delivery_bolt_enabled' value='1' style='width:auto' {checked('delivery_bolt_enabled')}> Bolt delivery</label>
      <label>Bolt delivery fee</label><input name='delivery_bolt_fee' value='{field('delivery_bolt_fee')}' placeholder='e.g. KES 350 or Calculated by Bolt'>
      <label>Bolt connection / integration reference</label><input name='delivery_bolt_connection' value='{field('delivery_bolt_connection')}' placeholder='Connection URL or integration reference (no secret keys)'>

      <label><input type='checkbox' name='delivery_glovo_enabled' value='1' style='width:auto' {checked('delivery_glovo_enabled')}> Glovo delivery</label>
      <label>Glovo delivery fee</label><input name='delivery_glovo_fee' value='{field('delivery_glovo_fee')}' placeholder='e.g. KES 350 or Calculated by Glovo'>
      <label>Glovo connection / integration reference</label><input name='delivery_glovo_connection' value='{field('delivery_glovo_connection')}' placeholder='Connection URL or integration reference (no secret keys)'>

      <label><input type='checkbox' name='delivery_pickup_enabled' value='1' style='width:auto' {checked('delivery_pickup_enabled')}> Customer pickup</label>
      <label>Pickup fee</label><input name='delivery_pickup_fee' value='{field('delivery_pickup_fee')}' placeholder='Usually Free'>
      <button type='submit'>Save Payments & Delivery</button>
    </form>
  </div></div>
  {("<h3 style='margin-top:28px'>Recent Product Orders</h3><div class='cards'>" + order_cards + "</div>") if orders else "<p class='muted'>No product orders yet.</p>"}
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_purchase_html():
    product_methods = enabled_payment_methods('product')
    service_methods = enabled_payment_methods('service')
    providers = enabled_delivery_providers()
    if not product_methods or not providers:
        return '', '', ''

    csrf = html.escape(base.csrf_token())
    payment_options = ''.join(f"<option value='{html.escape(m)}'>{html.escape(m)}</option>" for m in product_methods)
    delivery_options = ''.join(
        f"<option value='{html.escape(p)}' data-fee='{html.escape(delivery_fee(p) or 'To be confirmed')}'>"
        f"{html.escape(p)} — {html.escape(delivery_fee(p) or 'Fee to be confirmed')}</option>" for p in providers
    )
    service_badges = ''.join(f"<span class='commerce-badge'>{html.escape(m)}</span>" for m in service_methods)

    section = f"""
<section id='buy-product' class='commerce-checkout'>
  <div class='container'>
    <div class='heading'><small>SHOP WITH BIG MUG</small><h2>Buy a Product</h2><p>Select Buy Now on a marketplace item, choose delivery and your preferred payment method.</p></div>
    <div class='commerce-grid'>
      <div class='commerce-summary'><small>YOUR SELECTION</small><h3 id='commerce-product-display'>Choose a product above</h3><p id='commerce-price-display'>The product price will appear here.</p><p><b>Delivery fee:</b> <span id='commerce-delivery-fee'>Choose a delivery option</span></p></div>
      <form method='POST' action='/buy-product' id='commerce-order-form'>
        <input type='hidden' name='_csrf_token' value='{csrf}'>
        <input type='hidden' name='product_name' id='commerce-product-name'>
        <label>Quantity</label><input type='number' name='quantity' value='1' min='1' max='50' required>
        <label>Your name</label><input name='customer_name' required>
        <label>Email</label><input type='email' name='email' required>
        <label>Phone</label><input name='phone'>
        <label>Delivery option</label><select name='delivery_provider' id='commerce-delivery-provider' required><option value=''>Choose delivery</option>{delivery_options}</select>
        <label>Delivery location</label><textarea name='delivery_location' placeholder='Address, building, road, area and useful delivery directions. For pickup, you can leave this blank.'></textarea>
        <label>Payment method</label><select name='payment_method' required><option value=''>Choose payment method</option>{payment_options}</select>
        <div class='commerce-safe-note'>Payment is confirmed separately. Big Mug does not collect card numbers directly on this form.</div>
        <button type='submit'>Place Order Request</button>
      </form>
    </div>
  </div>
</section>
"""

    service_box = ''
    if service_methods:
        service_box = f"<div id='service-payment-options' class='service-payment-options'><b>Available payment methods for Big Mug experiences</b><div>{service_badges}</div><span>Payment instructions are provided when your booking is confirmed.</span></div>"

    style = """
<style id='bigmug-commerce-style'>
.commerce-checkout{background:#f7efe6}
.commerce-grid{display:grid;grid-template-columns:.8fr 1.2fr;gap:32px;align-items:start}
.commerce-summary{background:#0f0d0a;color:#f5ead2;border:1px solid #5f481d;border-radius:22px;padding:28px;position:sticky;top:100px}
.commerce-summary small,.commerce-summary h3{color:#f0cf82}.commerce-summary h3{font-size:1.8rem;margin:8px 0}.commerce-summary p{margin:8px 0}
.commerce-buy-btn{width:100%;margin-top:8px}.commerce-safe-note{background:#fff5e8;border-left:4px solid #d3a04f;padding:12px 14px;border-radius:10px;margin:14px 0;color:#3b2418}
.service-payment-options{margin-top:18px;padding:16px;border-radius:14px;background:#f4eadb;color:#3b2418}.service-payment-options>div{display:flex;gap:8px;flex-wrap:wrap;margin:9px 0}.service-payment-options span{font-size:.9rem;color:#6d625c}.commerce-badge{display:inline-block;background:#fff;border:1px solid #d8bd84;border-radius:999px;padding:6px 10px!important;color:#3b2418!important;font-weight:800}
@media(max-width:800px){.commerce-grid{grid-template-columns:1fr}.commerce-summary{position:static}}
</style>
"""

    script = f"""
<script id='bigmug-commerce-script'>
(function(){{
  document.querySelectorAll('#marketplace .market-grid article.card').forEach(function(card){{
    var actions=card.querySelector('.product-actions'); var title=card.querySelector('.body h3'); var price=card.querySelector('.price');
    if(!actions||!title||actions.querySelector('.commerce-buy-btn')) return;
    var btn=document.createElement('a'); btn.href='#buy-product'; btn.className='btn commerce-buy-btn'; btn.textContent='Buy Now →';
    btn.addEventListener('click',function(){{
      var name=title.textContent.trim(); var priceText=price?price.textContent.trim():'Price on request';
      var hidden=document.getElementById('commerce-product-name'); var display=document.getElementById('commerce-product-display'); var priceDisplay=document.getElementById('commerce-price-display');
      if(hidden) hidden.value=name; if(display) display.textContent=name; if(priceDisplay) priceDisplay.textContent=priceText;
    }});
    actions.insertBefore(btn,actions.firstChild);
  }});
  var provider=document.getElementById('commerce-delivery-provider');
  if(provider) provider.addEventListener('change',function(){{var opt=provider.options[provider.selectedIndex];var fee=document.getElementById('commerce-delivery-fee');if(fee) fee.textContent=opt&&opt.dataset.fee?opt.dataset.fee:'Choose a delivery option';}});
  var booking=document.getElementById('booking-form');
  if(booking && {str(bool(service_box)).lower()}){{
    var wrap=document.createElement('div'); wrap.innerHTML={service_box!r}; var node=wrap.firstElementChild; if(node) booking.appendChild(node);
  }}
}})();
</script>
"""
    return section, style, script


@app.after_request
def commerce_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_commerce_html()
                markers = [
                    "<section class='sec' id='section-headings-settings'>",
                    '<section class="sec" id="section-headings-settings">',
                    "<section class='sec' id='booking-guide-settings'>",
                    '<section class="sec" id="booking-guide-settings">',
                ]
                inserted = False
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1); inserted = True; break
                if not inserted and '</main>' in page:
                    page = page.replace('</main>', section + '</main>', 1)
                page = page.replace('<a href="#section-headings-settings">Section Headings</a>', '<a href="#commerce-settings">Payments & Delivery</a><a href="#section-headings-settings">Section Headings</a>', 1)
                page = page.replace('<a class="q" href="#section-headings-settings">Section Headings</a>', '<a class="q" href="#commerce-settings">Payments & Delivery</a><a class="q" href="#section-headings-settings">Section Headings</a>', 1)
            elif request.path == '/':
                section, style, script = public_purchase_html()
                if section:
                    marker = '<section class="story" id="story">'
                    if marker in page: page = page.replace(marker, section + marker, 1)
                    if style and '</head>' in page: page = page.replace('</head>', style + '</head>', 1)
                    if script and '</body>' in page: page = page.replace('</body>', script + '</body>', 1)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Commerce enhancement failed:', exc)
    return response
