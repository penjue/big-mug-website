BIG MUG — DEPLOYMENT READY BUILD

This package can be deployed to Render or Railway.

RECOMMENDED FIRST DEPLOYMENT: RAILWAY
1. Put this folder into a GitHub repository or deploy it with Railway CLI.
2. Create a Railway project and deploy the repository.
3. Attach a Railway Volume to the web service.
4. Mount the volume at: /data
5. Add these environment variables:
   BIG_MUG_SECRET_KEY=<long random secret>
   BIG_MUG_ADMIN_USER=bigmugadmin
   BIG_MUG_ADMIN_PASSWORD=<strong new first-run password>
   BIG_MUG_HTTPS=1
   BIG_MUG_TRUST_PROXY=1
   BIG_MUG_DB_PATH=/data/big_mug.db
   FLASK_DEBUG=0
6. Generate a Railway public domain.
7. Visit /health; it should return status=ok.
8. Visit /login and sign in with the first-run admin credentials.
9. Immediately change the admin password from the dashboard.
10. Attach the final custom Big Mug domain only after the application is tested.

RENDER DEPLOYMENT
This package also contains render.yaml. The blueprint defines a 1 GB persistent
disk mounted at /var/data and uses /var/data/big_mug.db. The admin password must
be supplied securely when creating the service.

IMPORTANT
SQLite works for the first version of Big Mug when one application instance owns
the database. If traffic, staff usage or booking volume grows, migrate to
PostgreSQL before horizontally scaling.

PAYMENTS ARE NOT ENABLED YET.
Do not collect real card details in this application. Payment integration should
use a hosted/secure payment provider checkout and verified server-side webhooks.

PRODUCTION CHECKLIST
- Custom domain
- HTTPS confirmed
- Fresh strong admin password
- Persistent database volume confirmed
- Backup downloaded and restoration tested
- Business email configured
- Booking confirmation email/SMS configured
- Privacy policy, terms and cancellation/refund policy
- Payment provider
- Monitoring and off-site backups
