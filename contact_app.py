import html
import timeline_app as timeline

app = timeline.app


def diagnostic_send_booking_email(to_email, subject, message):
    base = timeline.base
    host = base.os.environ.get("BIG_MUG_SMTP_HOST")
    raw_port = base.os.environ.get("BIG_MUG_SMTP_PORT", "587")
    user = base.os.environ.get("BIG_MUG_SMTP_USER")
    password = base.os.environ.get("BIG_MUG_SMTP_PASSWORD")
    sender = base.os.environ.get("BIG_MUG_FROM_EMAIL", user)
    missing = [name for name, value in (
        ("BIG_MUG_SMTP_HOST", host),
        ("BIG_MUG_SMTP_USER", user),
        ("BIG_MUG_SMTP_PASSWORD", password),
        ("BIG_MUG_FROM_EMAIL", sender),
        ("recipient", to_email),
    ) if not value]
    if missing:
        print("SMTP diagnostic: missing required setting(s): " + ", ".join(missing), flush=True)
        return False
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        print("SMTP diagnostic: invalid BIG_MUG_SMTP_PORT", flush=True)
        return False
    print(f"SMTP diagnostic: configuration loaded host={host} port={port} user_set=yes sender_set=yes password_set=yes", flush=True)
    try:
        email = base.EmailMessage()
        email["Subject"] = subject
        email["From"] = sender
        email["To"] = to_email
        email.set_content(message)
        print("SMTP diagnostic: opening connection", flush=True)
        with base.smtplib.SMTP(host, port, timeout=15) as server:
            print("SMTP diagnostic: connection opened; starting TLS", flush=True)
            server.starttls()
            print("SMTP diagnostic: TLS established; authenticating", flush=True)
            server.login(user, password)
            print("SMTP diagnostic: authentication succeeded; sending message", flush=True)
            server.send_message(email)
        print("SMTP diagnostic: message accepted by SMTP server", flush=True)
        return True
    except Exception as exc:
        print(f"SMTP diagnostic: failed at SMTP stage: {type(exc).__name__}: {exc}", flush=True)
        return False


timeline.base.send_booking_email = diagnostic_send_booking_email


def public_footer_html():
    email = timeline.setting('public_contact_email')
    whatsapp = timeline.setting('whatsapp_number')
    instagram = timeline.safe_url(timeline.setting('instagram_url'))
    facebook = timeline.safe_url(timeline.setting('facebook_url'))
    wa = timeline.whatsapp_href(whatsapp)
    contact_bits = ["<p>Nairobi, Kenya</p>"]
    if wa: contact_bits.append(f"<a href='{html.escape(wa)}' target='_blank' rel='noopener'>WhatsApp Big Mug</a>")
    if email: contact_bits.append(f"<a href='mailto:{html.escape(email)}'>{html.escape(email)}</a>")
    if len(contact_bits) == 1: contact_bits.append("<p>Bookings and product enquiries available.</p>")
    social_bits = []
    if instagram: social_bits.append(f"<a href='{html.escape(instagram)}' target='_blank' rel='noopener'>Instagram</a>")
    if facebook: social_bits.append(f"<a href='{html.escape(facebook)}' target='_blank' rel='noopener'>Facebook</a>")
    if not social_bits: social_bits.append("<p>Social links coming soon.</p>")
    return ("<div><b>Contact</b>" + ''.join(contact_bits) + "</div>" "<div><b>Follow Us</b>" + ''.join(social_bits) + "</div>")


def enhance_public_home(page):
    # timeline_app is the single source that injects the public Contact Big Mug
    # section. Do not inject it here as well, otherwise it renders twice.
    if 'href="#contact-trust">Contact</a>' not in page:
        page = page.replace('<a href="#enquire">Enquire</a><a class="cta"','<a href="#contact-trust">Contact</a><a href="#enquire">Enquire</a><a class="cta"',1)
    old_footer = ('<div><b>Contact</b><p>Nairobi, Kenya</p><p>Bookings and product enquiries available.</p></div>' '<div><b>Follow Us</b><p>Instagram</p><p>Facebook</p></div>')
    if old_footer in page: page = page.replace(old_footer, public_footer_html(), 1)

    # Public-site refinement: preserve the hero exactly as designed, while
    # carrying the admin's black/gold/cream identity through later sections.
    public_style = """
<style id="bigmug-public-theme">
/* Hero/home intentionally untouched. */
#experiences{background:#fffaf5}
#compare{background:#0f0d0a!important}
#compare .heading small{color:#f0cf82!important}
#compare .heading h2{color:#f0cf82!important}
#compare .heading p{color:#f5ead2!important}
#compare .compare-wrap{border:1px solid #5f481d;box-shadow:0 16px 34px rgba(0,0,0,.22)}
#marketplace{background:#f7efe6!important}
.story{background:#0f0d0a!important}
.story h2{color:#f0cf82!important}
.story p{color:#f5ead2}
#booking-guide{background:#0f0d0a!important}
#booking-guide .heading small,#booking-guide .heading h2{color:#f0cf82!important}
#booking-guide .heading p{color:#f5ead2!important}
#booking-guide .step{background:#fffaf5;border:1px solid #d8bd84}
#booking-guide .steps{grid-template-columns:repeat(3,1fr)!important}
#faq{background:#f7efe6!important}
#faq .faq-list details{border:1px solid #ead7b5}
#book{background:#fffaf5}
#enquire{background:#0f0d0a!important;color:#f5ead2}
#enquire .heading small,#enquire .heading h2{color:#f0cf82!important}
#enquire .heading p,#enquire .enquiry-grid>div p{color:#f5ead2!important}
#enquire form{color:#2b211c}
#contact-trust{border-top:1px solid #ead7b5;padding:58px 0!important}
footer{background:#0f0d0a!important}
@media(max-width:980px){#booking-guide .steps{grid-template-columns:1fr!important}}
@media(max-width:600px){
  #contact-trust{padding:46px 0!important}
  #compare .compare-wrap{overflow:visible;background:transparent;box-shadow:none;border:0}
  #compare .compare-table{min-width:0;display:block}
  #compare .compare-table thead{display:none}
  #compare .compare-table tbody,#compare .compare-table tr,#compare .compare-table td{display:block;width:100%}
  #compare .compare-table tr{background:#fffaf5;border-radius:18px;margin:0 0 14px;padding:16px;box-shadow:0 8px 22px rgba(0,0,0,.18)}
  #compare .compare-table td{border:0;padding:5px 0;color:#2b211c}
  #compare .compare-table td:last-child{padding-top:12px}
  #compare .compare-table .btn{width:100%}
}
</style>
"""
    if 'id="bigmug-public-theme"' not in page and '</head>' in page:
        page = page.replace('</head>', public_style + '</head>', 1)

    # Step 4 ("Enjoy the experience") is not part of the after-booking process.
    public_script = """
<script id="bigmug-public-refinements">
(function(){
  var guide=document.getElementById('booking-guide');
  if(!guide) return;
  var steps=guide.querySelectorAll('.step');
  Array.prototype.forEach.call(steps,function(step){
    var title=step.querySelector('h3');
    if(title && title.textContent.trim().toLowerCase()==='enjoy the experience') step.remove();
  });
})();
</script>
"""
    if 'id="bigmug-public-refinements"' not in page and '</body>' in page:
        page = page.replace('</body>', public_script + '</body>', 1)
    return page


_original_home = app.view_functions['home']


def home_with_public_contact(*args, **kwargs):
    result = _original_home(*args, **kwargs)
    response = app.make_response(result)
    if response.content_type and 'text/html' in response.content_type:
        page = response.get_data(as_text=True)
        response.set_data(enhance_public_home(page))
        response.headers['Content-Length'] = str(len(response.get_data()))
    return response


app.view_functions['home'] = home_with_public_contact


@app.after_request
def compact_admin_sections(response):
    if request_path_is_admin() and response.content_type and 'text/html' in response.content_type:
        page = response.get_data(as_text=True)
        style = """
<style>
.compact-admin-section{padding:0!important;overflow:hidden}
.compact-admin-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 20px;cursor:pointer;min-height:64px}
.compact-admin-head>.head{flex:1;margin:0}
.compact-admin-head>h2{margin:0;flex:1}
.compact-admin-toggle{flex:0 0 auto;background:#f0cf82!important;color:#15120e!important;border:1px solid #8b6b2d!important;padding:7px 12px!important;font-size:.82rem}
.compact-admin-body{padding:0 20px 20px}
.compact-admin-section.is-collapsed .compact-admin-body{display:none}
.compact-admin-section.is-collapsed .compact-admin-head{padding-top:13px;padding-bottom:13px}
#contact-reviews.compact-admin-section{background:#0f0d0a!important;color:#f5ead2!important;border:1px solid #5f481d!important}
#contact-reviews h2{color:#f0cf82!important}
#contact-reviews .muted{color:#d5c7ad!important}
#experiences .compact-admin-body>form label,#products .compact-admin-body>form label,#branding .compact-admin-body>form label,#security .compact-admin-body>form label{color:#fff!important}
#security .compact-admin-body .muted,#security .compact-admin-body form .muted,#security .compact-admin-body p{color:#3b2a1f!important}
#contact-reviews .compact-admin-body form h3,#contact-reviews .compact-admin-body form label,#contact-reviews .compact-admin-body form .muted{color:#3b2a1f!important}
.compact-admin-body>a[href="#top"],.compact-admin-body>a[href="#dashboard"],.compact-admin-body>a[href="/admin"],#contact-reviews .compact-admin-body>a{color:#f0cf82!important;text-decoration:none!important;font-weight:600}
@media(max-width:700px){.compact-admin-head{padding:11px 14px;min-height:58px}.compact-admin-section.is-collapsed .compact-admin-head{padding-top:11px;padding-bottom:11px}.compact-admin-body{padding:0 14px 15px}.compact-admin-toggle{padding:7px 11px!important}}
</style>
"""
        script = """
<script>
(function(){
  var ids=['enquiries','experiences','products','branding','contact-reviews','security'];
  ids.forEach(function(id){
    var sec=document.getElementById(id);
    if(!sec || sec.classList.contains('compact-admin-section')) return;
    var directHead=sec.querySelector(':scope > .head');
    var directTitle=sec.querySelector(':scope > h2');
    var headNode=directHead || directTitle;
    if(!headNode) return;
    var nodes=Array.prototype.slice.call(sec.childNodes);
    var head=document.createElement('div'); head.className='compact-admin-head'; head.appendChild(headNode);
    var toggle=document.createElement('button'); toggle.type='button'; toggle.className='compact-admin-toggle'; toggle.textContent='Open'; toggle.setAttribute('aria-expanded','false'); head.appendChild(toggle);
    var body=document.createElement('div'); body.className='compact-admin-body'; nodes.forEach(function(node){if(node!==headNode) body.appendChild(node);}); sec.appendChild(head); sec.appendChild(body); sec.classList.add('compact-admin-section','is-collapsed');
    function setOpen(open){sec.classList.toggle('is-collapsed',!open);toggle.textContent=open?'Close':'Open';toggle.setAttribute('aria-expanded',open?'true':'false');}
    head.addEventListener('click',function(e){if(e.target.closest('a,button,input,select,textarea,label')) return;setOpen(sec.classList.contains('is-collapsed'));});
    toggle.addEventListener('click',function(e){e.stopPropagation();setOpen(sec.classList.contains('is-collapsed'));});
  });
})();
</script>
"""
        if '</head>' in page: page = page.replace('</head>', style + '</head>', 1)
        if '</body>' in page: page = page.replace('</body>', script + '</body>', 1)
        response.set_data(page); response.headers['Content-Length'] = str(len(response.get_data()))
    return response


def request_path_is_admin():
    from flask import request
    return request.path == '/admin'
