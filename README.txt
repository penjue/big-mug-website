BIG MUG — Launch-Preparation Build

Included:
- Database-backed bookings, experiences, products and enquiries
- Password-hashed admin account and server-side login session
- CSRF protection
- Login throttling
- Secure-cookie option for HTTPS
- Security headers
- Input validation
- Admin password change
- Downloadable database backup
- Gunicorn production command
- Environment-variable configuration

Demo / first-run admin:
Username: bigmugadmin
Password: BigMug2026!

Change the password immediately after first login.

Local run:
1. pip install -r requirements.txt
2. python app.py
3. Open http://127.0.0.1:5000

Production:
Set BIG_MUG_SECRET_KEY, BIG_MUG_ADMIN_PASSWORD, BIG_MUG_HTTPS=1,
BIG_MUG_DB_PATH to persistent storage, and FLASK_DEBUG=0.
Start with: gunicorn app:app

Still needed before real payments:
- Production hosting + persistent storage/database
- Domain + HTTPS
- Shared rate limiting for multi-instance hosting
- Transactional email/SMS confirmations
- Payment provider + verified webhooks
- Privacy/cookie/terms/cancellation policies
- Monitoring and automated off-site backups
