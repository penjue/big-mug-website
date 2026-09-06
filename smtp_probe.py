import html
import contact_app

app = contact_app.app
base = contact_app.timeline.base


@app.get('/admin/smtp-test')
@base.login_required
def smtp_test():
    host = base.os.environ.get('BIG_MUG_SMTP_HOST')
    raw_port = base.os.environ.get('BIG_MUG_SMTP_PORT', '587')
    user = base.os.environ.get('BIG_MUG_SMTP_USER')
    password = base.os.environ.get('BIG_MUG_SMTP_PASSWORD')
    sender = base.os.environ.get('BIG_MUG_FROM_EMAIL', user)

    missing = [name for name, value in (
        ('BIG_MUG_SMTP_HOST', host),
        ('BIG_MUG_SMTP_USER', user),
        ('BIG_MUG_SMTP_PASSWORD', password),
        ('BIG_MUG_FROM_EMAIL', sender),
    ) if not value]
    if missing:
        result = 'FAILED: missing ' + ', '.join(missing)
    else:
        try:
            port = int(raw_port)
            email = base.EmailMessage()
            email['Subject'] = 'Big Mug SMTP Test'
            email['From'] = sender
            email['To'] = user
            email.set_content('This is a Big Mug SMTP configuration test.')
            stage = 'opening connection'
            with base.smtplib.SMTP(host, port, timeout=15) as server:
                stage = 'starting TLS'
                server.starttls()
                stage = 'authenticating'
                server.login(user, password)
                stage = 'sending message'
                server.send_message(email)
            result = 'SUCCESS: Google SMTP accepted the test message.'
        except Exception as exc:
            result = f'FAILED at {stage}: {type(exc).__name__}: {exc}'

    safe = html.escape(result)
    return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>SMTP Test</title></head><body style="font-family:Arial,sans-serif;padding:24px;max-width:760px;margin:auto"><h1>Big Mug SMTP Test</h1><p><strong>{safe}</strong></p><p>No password or secret is displayed on this page.</p><p><a href="/admin">Back to Admin</a></p></body></html>'''
