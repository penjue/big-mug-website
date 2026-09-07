import html
import timeline_app as timeline

app = timeline.app

# Registers the editable homepage hero controls and public hero rendering.
import hero_admin


def footer_icon(kind):
    icons = {
        'whatsapp': "<svg class='footer-icon' viewBox='0 0 24 24' aria-hidden='true'><path fill='currentColor' d='M17.5 14.4c-.3-.2-1.8-.9-2.1-1s-.5-.2-.7.2c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-1.9-.9-3.1-1.7-4.4-3.9-.3-.5.3-.5.9-1.6.1-.2 0-.5-.1-.7s-.7-1.7-1-2.3c-.3-.6-.6-.5-.8-.5h-.7c-.2 0-.7.1-1 .5-.3.4-1.3 1.3-1.3 3.1s1.3 3.6 1.5 3.8c.2.3 2.6 4 6.3 5.6 2.4 1 3.4 1.1 4.6.9.7-.1 1.8-.7 2-1.4.3-.7.3-1.3.2-1.4-.1-.2-.3-.3-.6-.4z'/><path fill='currentColor' d='M12 2a9.9 9.9 0 0 0-8.5 15L2 22l5.1-1.4A10 10 0 1 0 12 2zm0 18.2c-1.5 0-2.9-.4-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2z'/></svg>",
        'email': "<svg class='footer-icon' viewBox='0 0 24 24' aria-hidden='true'><path fill='currentColor' d='M3 5h18a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm9 7 8-5H4l8 5zm0 2.3L3 8.7V17h18V8.7l-9 5.6z'/></svg>",
        'instagram': "<svg class='footer-icon' viewBox='0 0 24 24' aria-hidden='true'><path fill='currentColor' d='M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zm0 2a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3H7zm10.5 1.5a1.2 1.2 0 1 1 0 2.4 1.2 1.2 0 0 1 0-2.4zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'/></svg>",
        'facebook': "<svg class='footer-icon' viewBox='0 0 24 24' aria-hidden='true'><path fill='currentColor' d='M13.5 22v-9h3l.5-3h-3.5V8.1c0-.9.3-1.6 1.6-1.6H17V3.8c-.4 0-1.5-.2-2.8-.2-2.8 0-4.7 1.7-4.7 4.8V10H6.5v3h3v9h4z'/></svg>",
        'tiktok': "<svg class='footer-icon' viewBox='0 0 24 24' aria-hidden='true'><path fill='currentColor' d='M15.3 2c.3 2 1.5 3.7 3.7 4.1v3.1c-1.4 0-2.7-.4-3.7-1.1v6.2a6.3 6.3 0 1 1-5.4-6.2v3.2a3.1 3.1 0 1 0 2.2 3V2h3.2z'/></svg>",
    }
    return icons.get(kind, '')


def public_footer_html():
    email = timeline.setting('public_contact_email')
    whatsapp = timeline.setting('whatsapp_number')
    instagram = timeline.safe_url(timeline.setting('instagram_url'))
    facebook = timeline.safe_url(timeline.setting('facebook_url'))
    tiktok = timeline.safe_url(timeline.setting('tiktok_url'))
    wa = timeline.whatsapp_href(whatsapp)

    contact_bits = []
    for line in timeline.business_address_lines():
        contact_bits.append(f"<p>{html.escape(line)}</p>")
    if wa:
        contact_bits.append(f"<a class='footer-icon-link' href='{html.escape(wa)}' target='_blank' rel='noopener'>{footer_icon('whatsapp')}<span>WhatsApp Big Mug</span></a>")
    if email:
        contact_bits.append(f"<a class='footer-icon-link' href='mailto:{html.escape(email)}'>{footer_icon('email')}<span>{html.escape(email)}</span></a>")
    if not contact_bits:
        contact_bits.append("<p>Bookings and product enquiries available.</p>")

    social_bits = []
    if instagram:
        social_bits.append(f"<a class='footer-icon-link' href='{html.escape(instagram)}' target='_blank' rel='noopener'>{footer_icon('instagram')}<span>Instagram</span></a>")
    if facebook:
        social_bits.append(f"<a class='footer-icon-link' href='{html.escape(facebook)}' target='_blank' rel='noopener'>{footer_icon('facebook')}<span>Facebook</span></a>")
    if tiktok:
        social_bits.append(f"<a class='footer-icon-link' href='{html.escape(tiktok)}' target='_blank' rel='noopener'>{footer_icon('tiktok')}<span>TikTok</span></a>")
    if not social_bits:
        social_bits.append("<p>Social links coming soon.</p>")

    return (
        "<div><b>Contact</b>" + ''.join(contact_bits) + "</div>"
        "<div><b>Follow Us</b>" + ''.join(social_bits) + "</div>"
    )


def enhance_public_home(page):
    old_footer = ('<div><b>Contact</b><p>Nairobi, Kenya</p><p>Bookings and product enquiries available.</p></div>' '<div><b>Follow Us</b><p>Instagram</p><p>Facebook</p></div>')
    if old_footer in page: page = page.replace(old_footer, public_footer_html(), 1)

    public_style = """
<style id="bigmug-public-theme">
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
#enquire .flash{background:#f2dfbd;color:#2b211c;border:1px solid #d3a04f;font-weight:700}
#contact-trust{border-top:1px solid #ead7b5;padding:58px 0!important}
footer{background:#0f0d0a!important}
footer .footer-icon-link{display:flex!important;align-items:center;gap:9px;width:max-content;max-width:100%;margin:7px 0;color:#dfd2ca!important}
footer .footer-icon{width:18px;height:18px;flex:0 0 18px;color:#f0cf82}
footer .footer-icon-link span{overflow-wrap:anywhere}
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

    public_script = """
<script id="bigmug-public-refinements">
(function(){
  var guide=document.getElementById('booking-guide');
  if(guide){
    var steps=guide.querySelectorAll('.step');
    Array.prototype.forEach.call(steps,function(step){
      var title=step.querySelector('h3');
      if(title && title.textContent.trim().toLowerCase()==='enjoy the experience') step.remove();
    });
  }

  if(window.location.hash==='#enquire'){
    var book=document.getElementById('book');
    var enquire=document.getElementById('enquire');
    if(book && enquire){
      var flashes=book.querySelectorAll('.flash');
      var container=enquire.querySelector('.container');
      if(container && flashes.length){
        Array.prototype.forEach.call(flashes,function(flash){
          container.insertBefore(flash,container.firstChild);
        });
      }
    }
  }
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
#contact-reviews.compact-admin-section,
#booking-guide-settings.compact-admin-section,
#section-headings-settings.compact-admin-section,
#commerce-settings.compact-admin-section,
#story-settings.compact-admin-section,
#seo-settings.compact-admin-section,
#policy-settings.compact-admin-section,
#faq-settings.compact-admin-section,
#about-settings.compact-admin-section,
#hero-settings.compact-admin-section{background:#0f0d0a!important;color:#f5ead2!important;border:1px solid #5f481d!important}
#contact-reviews h2,
#booking-guide-settings h2,
#section-headings-settings h2,
#commerce-settings h2,
#story-settings h2,
#seo-settings h2,
#policy-settings h2,
#faq-settings h2,
#about-settings h2,
#hero-settings h2{color:#f0cf82!important}
#contact-reviews .compact-admin-head .muted,
#booking-guide-settings .compact-admin-head .muted,
#section-headings-settings .compact-admin-head .muted,
#commerce-settings .compact-admin-head .muted,
#story-settings .compact-admin-head .muted,
#seo-settings .compact-admin-head .muted,
#policy-settings .compact-admin-head .muted,
#faq-settings .compact-admin-head .muted,
#about-settings .compact-admin-head .muted,
#hero-settings .compact-admin-head .muted{color:#d5c7ad!important}
#booking-guide-settings .compact-admin-body .card,
#section-headings-settings .compact-admin-body .card,
#commerce-settings .compact-admin-body .card,
#story-settings .compact-admin-body .card,
#seo-settings .compact-admin-body .card,
#policy-settings .compact-admin-body .card,
#faq-settings .compact-admin-body .card,
#about-settings .compact-admin-body .card,
#hero-settings .compact-admin-body .card{background:#fffaf5!important;color:#3b2a1f!important;border:1px solid #d8bd84!important}
#experiences .compact-admin-body>form label,#products .compact-admin-body>form label,#branding .compact-admin-body>form label,#hero-settings .compact-admin-body>form label,#about-settings .compact-admin-body>form label,#faq-settings .compact-admin-body>form label,#policy-settings .compact-admin-body>form label,#seo-settings .compact-admin-body>form label,#story-settings .compact-admin-body>form label,#booking-guide-settings .compact-admin-body>form label,#section-headings-settings .compact-admin-body>form label,#commerce-settings .compact-admin-body>form label,#security .compact-admin-body>form label{color:#fff!important}
#booking-guide-settings .compact-admin-body form label,#booking-guide-settings .compact-admin-body form .muted,
#section-headings-settings .compact-admin-body form label,#section-headings-settings .compact-admin-body form .muted,
#commerce-settings .compact-admin-body form label,#commerce-settings .compact-admin-body form .muted,
#story-settings .compact-admin-body form label,#story-settings .compact-admin-body form .muted,
#seo-settings .compact-admin-body form label,#seo-settings .compact-admin-body form .muted,
#policy-settings .compact-admin-body form label,#policy-settings .compact-admin-body form .muted,
#faq-settings .compact-admin-body form label,#faq-settings .compact-admin-body form .muted,
#about-settings .compact-admin-body form label,#about-settings .compact-admin-body form .muted,
#hero-settings .compact-admin-body form label,#hero-settings .compact-admin-body form .muted{color:#3b2a1f!important}
#security .compact-admin-body .muted,#security .compact-admin-body form .muted,#security .compact-admin-body p{color:#3b2a1f!important}
#contact-reviews .compact-admin-body form h3,#contact-reviews .compact-admin-body form label,#contact-reviews .compact-admin-body form .muted{color:#3b2a1f!important}
.compact-admin-body>a[href="#top"],.compact-admin-body>a[href="#dashboard"],.compact-admin-body>a[href="/admin"],#contact-reviews .compact-admin-body>a{color:#f0cf82!important;text-decoration:none!important;font-weight:600}
@media(max-width:700px){.compact-admin-head{padding:11px 14px;min-height:58px}.compact-admin-section.is-collapsed .compact-admin-head{padding-top:11px;padding-bottom:11px}.compact-admin-body{padding:0 14px 15px}.compact-admin-toggle{padding:7px 11px!important}}
</style>
"""
        script = """
<script>
(function(){
  var ids=['enquiries','experiences','products','commerce-settings','section-headings-settings','booking-guide-settings','story-settings','seo-settings','policy-settings','faq-settings','about-settings','hero-settings','branding','contact-reviews','security'];
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
    if(window.location.hash==='#'+id) setOpen(true);
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