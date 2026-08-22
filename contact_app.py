import html
import timeline_app as timeline

app = timeline.app


def public_footer_html():
    email = timeline.setting('public_contact_email')
    whatsapp = timeline.setting('whatsapp_number')
    instagram = timeline.safe_url(timeline.setting('instagram_url'))
    facebook = timeline.safe_url(timeline.setting('facebook_url'))
    wa = timeline.whatsapp_href(whatsapp)

    contact_bits = ["<p>Nairobi, Kenya</p>"]
    if wa:
        contact_bits.append(f"<a href='{html.escape(wa)}' target='_blank' rel='noopener'>WhatsApp Big Mug</a>")
    if email:
        contact_bits.append(f"<a href='mailto:{html.escape(email)}'>{html.escape(email)}</a>")
    if len(contact_bits) == 1:
        contact_bits.append("<p>Bookings and product enquiries available.</p>")

    social_bits = []
    if instagram:
        social_bits.append(f"<a href='{html.escape(instagram)}' target='_blank' rel='noopener'>Instagram</a>")
    if facebook:
        social_bits.append(f"<a href='{html.escape(facebook)}' target='_blank' rel='noopener'>Facebook</a>")
    if not social_bits:
        social_bits.append("<p>Social links coming soon.</p>")

    return ("<div><b>Contact</b>" + ''.join(contact_bits) + "</div>" "<div><b>Follow Us</b>" + ''.join(social_bits) + "</div>")


def enhance_public_home(page):
    if "id='contact-trust'" not in page and 'id="contact-trust"' not in page:
        public = timeline.public_trust_html()
        marker = '<section class="enquiry" id="enquire">'
        if marker in page:
            page = page.replace(marker, public + marker, 1)
    if 'href="#contact-trust">Contact</a>' not in page:
        page = page.replace('<a href="#enquire">Enquire</a><a class="cta"','<a href="#contact-trust">Contact</a><a href="#enquire">Enquire</a><a class="cta"',1)
    old_footer = ('<div><b>Contact</b><p>Nairobi, Kenya</p><p>Bookings and product enquiries available.</p></div>' '<div><b>Follow Us</b><p>Instagram</p><p>Facebook</p></div>')
    if old_footer in page:
        page = page.replace(old_footer, public_footer_html(), 1)
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
#experiences .compact-admin-body>form label,
#products .compact-admin-body>form label,
#branding .compact-admin-body>form label,
#security .compact-admin-body>form label{color:#fff!important}
#contact-reviews .compact-admin-body form h3,
#contact-reviews .compact-admin-body form label,
#contact-reviews .compact-admin-body form .muted{color:#3b2a1f!important}
/* Keep every return-to-dashboard link readable on the black admin cards. */
.compact-admin-body>a[href="#top"],
.compact-admin-body>a[href="#dashboard"],
.compact-admin-body>a[href="/admin"],
#contact-reviews .compact-admin-body>a{color:#f0cf82!important;text-decoration:none!important;font-weight:600}
@media(max-width:700px){
  .compact-admin-head{padding:11px 14px;min-height:58px}
  .compact-admin-section.is-collapsed .compact-admin-head{padding-top:11px;padding-bottom:11px}
  .compact-admin-body{padding:0 14px 15px}
  .compact-admin-toggle{padding:7px 11px!important}
}
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
    var head=document.createElement('div');
    head.className='compact-admin-head';
    head.appendChild(headNode);
    var toggle=document.createElement('button');
    toggle.type='button';
    toggle.className='compact-admin-toggle';
    toggle.textContent='Open';
    toggle.setAttribute('aria-expanded','false');
    head.appendChild(toggle);
    var body=document.createElement('div');
    body.className='compact-admin-body';
    nodes.forEach(function(node){if(node!==headNode) body.appendChild(node);});
    sec.appendChild(head);
    sec.appendChild(body);
    sec.classList.add('compact-admin-section','is-collapsed');
    function setOpen(open){
      sec.classList.toggle('is-collapsed',!open);
      toggle.textContent=open?'Close':'Open';
      toggle.setAttribute('aria-expanded',open?'true':'false');
    }
    head.addEventListener('click',function(e){
      if(e.target.closest('a,button,input,select,textarea,label')) return;
      setOpen(sec.classList.contains('is-collapsed'));
    });
    toggle.addEventListener('click',function(e){e.stopPropagation();setOpen(sec.classList.contains('is-collapsed'));});
  });
})();
</script>
"""
        if '</head>' in page:
            page = page.replace('</head>', style + '</head>', 1)
        if '</body>' in page:
            page = page.replace('</body>', script + '</body>', 1)
        response.set_data(page)
        response.headers['Content-Length'] = str(len(response.get_data()))
    return response


def request_path_is_admin():
    from flask import request
    return request.path == '/admin'
