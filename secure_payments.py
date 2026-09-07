import hashlib
import re
import secrets
from datetime import datetime, timezone

import timeline_app as timeline

base = timeline.base

PAYMENT_STATUSES = (
    'Awaiting Payment',
    'Processing',
    'Paid',
    'Failed',
    'Refunded',
    'Cancelled',
)


def ensure_payment_schema():
    conn = base.db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_ref TEXT UNIQUE NOT NULL,
        order_type TEXT NOT NULL,
        order_id INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        provider TEXT,
        amount_minor INTEGER,
        currency TEXT,
        status TEXT NOT NULL DEFAULT 'Awaiting Payment',
        provider_transaction_id TEXT UNIQUE,
        idempotency_key TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(order_type, order_id)
    );
    CREATE TABLE IF NOT EXISTS payment_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        old_status TEXT,
        new_status TEXT,
        source TEXT NOT NULL,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(payment_id) REFERENCES payments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS payment_callbacks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,
        provider_event_id TEXT NOT NULL,
        payload_hash TEXT NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(provider, provider_event_id)
    );
    """)
    conn.commit(); conn.close()


ensure_payment_schema()


_CURRENCY_SYMBOLS = {'KES': 'KES', 'KSH': 'KES', 'KSHS': 'KES', '£': 'GBP', 'GBP': 'GBP', '$': 'USD', 'USD': 'USD', '€': 'EUR', 'EUR': 'EUR'}
_MONEY_RE = re.compile(r'^\s*(KES|KSH|KSHS|GBP|USD|EUR|£|\$|€)?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(KES|KSH|KSHS|GBP|USD|EUR)?\s*$', re.I)


def parse_money(value):
    """Return (minor_units, currency) only for unambiguous fixed money strings."""
    text = (value or '').strip()
    if not text or any(word in text.lower() for word in ('from ', 'contact', 'custom', 'calculated', 'confirm', 'free')):
        return None, None
    match = _MONEY_RE.match(text)
    if not match:
        return None, None
    left, number, right = match.groups()
    token = (left or right or '').upper()
    currency = _CURRENCY_SYMBOLS.get(token)
    if not currency:
        return None, None
    normalized = number.replace(',', '')
    major, dot, decimals = normalized.partition('.')
    minor = int(major) * 100 + int((decimals + '00')[:2] if dot else '00')
    return minor, currency


def calculate_order_total(product_price, quantity, delivery_fee):
    unit_minor, unit_currency = parse_money(product_price)
    if unit_minor is None:
        return None, None
    fee_text = (delivery_fee or '').strip()
    if not fee_text or fee_text.lower() in {'free', '0', '0.00'}:
        fee_minor, fee_currency = 0, unit_currency
    else:
        fee_minor, fee_currency = parse_money(fee_text)
        if fee_minor is None or fee_currency != unit_currency:
            return None, None
    return unit_minor * int(quantity) + fee_minor, unit_currency


def _payment_ref():
    return 'PAY-' + secrets.token_hex(6).upper()


def create_payment(order_type, order_id, payment_method, amount_minor=None, currency=None, provider=None):
    conn = base.db()
    existing = conn.execute('SELECT * FROM payments WHERE order_type=? AND order_id=?', (order_type, order_id)).fetchone()
    if existing:
        conn.close(); return existing['payment_ref']
    ref = _payment_ref()
    idem = secrets.token_urlsafe(24)
    cur = conn.execute(
        '''INSERT INTO payments(payment_ref,order_type,order_id,payment_method,provider,amount_minor,currency,status,idempotency_key)
           VALUES(?,?,?,?,?,?,?,?,?)''',
        (ref, order_type, order_id, payment_method, provider, amount_minor, currency, 'Awaiting Payment', idem)
    )
    payment_id = cur.lastrowid
    conn.execute(
        '''INSERT INTO payment_events(payment_id,event_type,old_status,new_status,source,details)
           VALUES(?,?,?,?,?,?)''',
        (payment_id, 'created', None, 'Awaiting Payment', 'server', 'Payment record created from server-side order data.')
    )
    conn.commit(); conn.close()
    return ref


def payment_for_order(order_type, order_id):
    conn = base.db()
    row = conn.execute('SELECT * FROM payments WHERE order_type=? AND order_id=?', (order_type, order_id)).fetchone()
    conn.close(); return row


def payment_events(payment_id, limit=30):
    conn = base.db()
    rows = conn.execute('SELECT * FROM payment_events WHERE payment_id=? ORDER BY id DESC LIMIT ?', (payment_id, int(limit))).fetchall()
    conn.close(); return rows


def update_payment_status(payment_ref, new_status, source, details='', provider_transaction_id=None):
    """Internal status transition helper. Public provider endpoints must verify signatures before calling this."""
    if new_status not in PAYMENT_STATUSES:
        raise ValueError('Invalid payment status')
    conn = base.db()
    payment = conn.execute('SELECT * FROM payments WHERE payment_ref=?', (payment_ref,)).fetchone()
    if not payment:
        conn.close(); raise ValueError('Unknown payment reference')
    old_status = payment['status']
    if old_status == new_status:
        conn.close(); return False
    if old_status in {'Paid', 'Refunded', 'Cancelled'} and new_status not in {'Refunded'}:
        conn.close(); raise ValueError('Terminal payment status cannot be reopened')
    if provider_transaction_id:
        duplicate = conn.execute('SELECT id FROM payments WHERE provider_transaction_id=? AND id!=?', (provider_transaction_id, payment['id'])).fetchone()
        if duplicate:
            conn.close(); raise ValueError('Duplicate provider transaction id')
    conn.execute(
        '''UPDATE payments SET status=?, provider_transaction_id=COALESCE(?,provider_transaction_id), updated_at=CURRENT_TIMESTAMP WHERE id=?''',
        (new_status, provider_transaction_id, payment['id'])
    )
    conn.execute(
        '''INSERT INTO payment_events(payment_id,event_type,old_status,new_status,source,details)
           VALUES(?,?,?,?,?,?)''',
        (payment['id'], 'status', old_status, new_status, source[:40], (details or '')[:1000])
    )
    conn.commit(); conn.close(); return True


def register_provider_callback(provider, provider_event_id, raw_payload):
    """Idempotency/replay guard. Call only after provider authentication/signature verification."""
    payload_hash = hashlib.sha256(raw_payload if isinstance(raw_payload, bytes) else str(raw_payload).encode()).hexdigest()
    conn = base.db()
    try:
        conn.execute(
            'INSERT INTO payment_callbacks(provider,provider_event_id,payload_hash,processed) VALUES(?,?,?,0)',
            (provider[:60], provider_event_id[:180], payload_hash)
        )
        conn.commit(); conn.close(); return True
    except Exception:
        conn.rollback(); conn.close(); return False


def mark_callback_processed(provider, provider_event_id):
    conn = base.db()
    conn.execute('UPDATE payment_callbacks SET processed=1 WHERE provider=? AND provider_event_id=?', (provider, provider_event_id))
    conn.commit(); conn.close()


def format_amount(amount_minor, currency):
    if amount_minor is None or not currency:
        return 'Amount to be confirmed'
    return f'{currency} {amount_minor / 100:,.2f}'
