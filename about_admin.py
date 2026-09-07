import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'about_eyebrow': 'WELCOME TO',
    'about_title': 'Big Mug',
    'about_paragraph_1': 'Big Mug is more than a coffee tour. It is an invitation to slow down, explore, ask questions and experience coffee from a completely different point of view.',
    'about_paragraph_2': 'Follow the journey from growing and harvesting to processing, roasting and brewing. Meet the stories behind the beans, understand what shapes flavour, and discover why every cup has a character of its own.',
    'about_paragraph_3': 'Whether you are a coffee lover, a curious traveller, a couple looking for a unique experience, or a group searching for something memorable, Big Mug is designed to leave you with more than information — it leaves you with a story to remember.',
    'about_feature_1_title': 'Authentic Experiences',
    'about_feature_1_text': 'Real farms, real people, real stories.',
    'about_feature_2_title': 'Local Connection',
    'about_feature_2_text': 'Support local farmers and communities.',
    'about_feature_3_title': 'Learn & Taste',
    'about_feature_3_text': 'From bean to brew — see, learn and taste.',
    'about_feature_4_title': 'Memories That Last',
    'about_feature_4_text': 'Capture moments you will never forget.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/about-settings')
@base.login_required
def about_settings():
    limits = {
        'about_eyebrow': 120, 'about_title': 160,
        'about_paragraph_1': 900, 'about_paragraph_2': 900, 'about_paragraph_3': 900,
        'about_feature_1_title': 120, 'about_feature_1_text': 240,
        'about_feature_2_title': 120, 'about_feature_2_text': 240,
        'about_feature_3_title': 120, 'about_feature_3_text': 240,
        'about_feature_4_title': 120, 'about_feature_4_text': 240,
    }
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])

    image = request.files.get('about_image')
    if image and image.filename:
        filename, error = base.save_image_upload(image, base.SITE_IMAGE_DIR)
        if error:
            flash(error, 'error')
            return redirect(url_for('admin') + '#about-settings')
        old = timeline.setting('about_image_filename')
        base.set_setting('about_image_filename', filename)
        if old and old != filename:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    if request.form.get('remove_about_image') == '1':
        old = timeline.setting('about_image_filename')
        base.set_setting('about_image_filename', '')
        if old:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    flash('Welcome / About section updated.', 'success')
    return redirect(url_for('admin') + '#about-settings')


def admin_about_html():
    csrf = html.escape(base.csrf_token())
    def v(k):
        return html.escape(value(k))

    current_image = timeline.setting('about_image_filename')
    image_note = "<p class='muted'>A custom About image is currently active.</p>" if current_image else "<p class='muted'>The original Big Mug welcome image is currently active.</p>"
    remove = "<label style='display:flex;gap:8px;align-items:center;margin-top:10px'><input type='checkbox' name='remove_about_image' value='1' style='width:auto'> Restore original About image</label>" if current_image else ''

    return f"""
<section class='sec' id='about-settings'>
  <div class='head'><div><h2>Welcome / About</h2><p class='muted'>Edit the introduction visitors see below the hero.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/about-settings' enctype='multipart/form-data'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      <label>Small heading</label><input name='about_eyebrow' value='{v('about_eyebrow')}' required>
      <label>Main heading</label><input name='about_title' value='{v('about_title')}' required>
      <label>Paragraph 1</label><textarea name='about_paragraph_1' required>{v('about_paragraph_1')}</textarea>
      <label>Paragraph 2</label><textarea name='about_paragraph_2' required>{v('about_paragraph_2')}</textarea>
      <label>Paragraph 3</label><textarea name='about_paragraph_3' required>{v('about_paragraph_3')}</textarea>
      <label>Feature 1 title</label><input name='about_feature_1_title' value='{v('about_feature_1_title')}' required>
      <label>Feature 1 text</label><input name='about_feature_1_text' value='{v('about_feature_1_text')}' required>
      <label>Feature 2 title</label><input name='about_feature_2_title' value='{v('about_feature_2_title')}' required>
      <label>Feature 2 text</label><input name='about_feature_2_text' value='{v('about_feature_2_text')}' required>
      <label>Feature 3 title</label><input name='about_feature_3_title' value='{v('about_feature_3_title')}' required>
      <label>Feature 3 text</label><input name='about_feature_3_text' value='{v('about_feature_3_text')}' required>
      <label>Feature 4 title</label><input name='about_feature_4_title' value='{v('about_feature_4_title')}' required>
      <label>Feature 4 text</label><input name='about_feature_4_text' value='{v('about_feature_4_text')}' required>
      <label>About image</label><input type='file' name='about_image' accept='.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'>
      {image_note}{remove}
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save About Section</button><a href='/' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_about(page):
    old = '<section class="intro" id="about"><div class="container"><div class="intro-grid"><div><small>WELCOME TO</small><h2>Big Mug</h2><p>Big Mug is more than a coffee tour. It is an invitation to slow down, explore, ask questions and experience coffee from a completely different point of view.</p><p>Follow the journey from growing and harvesting to processing, roasting and brewing. Meet the stories behind the beans, understand what shapes flavour, and discover why every cup has a character of its own.</p><p>Whether you are a coffee lover, a curious traveller, a couple looking for a unique experience, or a group searching for something memorable, Big Mug is designed to leave you with more than information — it leaves you with a story to remember.</p></div><div class="intro-photo"></div></div><div class="features"><div class="feature"><b>Authentic Experiences</b><br>Real farms, real people, real stories.</div><div class="feature"><b>Local Connection</b><br>Support local farmers and communities.</div><div class="feature"><b>Learn & Taste</b><br>From bean to brew — see, learn and taste.</div><div class="feature"><b>Memories That Last</b><br>Capture moments you will never forget.</div></div></div></section>'
    image = timeline.setting('about_image_filename')
    if image:
        safe_image = html.escape(image, quote=True)
        photo = f"<div class='intro-photo' style=\"background-image:url('/site-images/{safe_image}')\"></div>"
    else:
        photo = '<div class="intro-photo"></div>'

    new = (
        '<section class="intro" id="about"><div class="container"><div class="intro-grid"><div>'
        f'<small>{html.escape(value("about_eyebrow"))}</small>'
        f'<h2>{html.escape(value("about_title"))}</h2>'
        f'<p>{html.escape(value("about_paragraph_1"))}</p>'
        f'<p>{html.escape(value("about_paragraph_2"))}</p>'
        f'<p>{html.escape(value("about_paragraph_3"))}</p>'
        f'</div>{photo}</div><div class="features">'
        f'<div class="feature"><b>{html.escape(value("about_feature_1_title"))}</b><br>{html.escape(value("about_feature_1_text"))}</div>'
        f'<div class="feature"><b>{html.escape(value("about_feature_2_title"))}</b><br>{html.escape(value("about_feature_2_text"))}</div>'
        f'<div class="feature"><b>{html.escape(value("about_feature_3_title"))}</b><br>{html.escape(value("about_feature_3_text"))}</div>'
        f'<div class="feature"><b>{html.escape(value("about_feature_4_title"))}</b><br>{html.escape(value("about_feature_4_text"))}</div>'
        '</div></div></section>'
    )
    if old in page:
        page = page.replace(old, new, 1)
    return page


@app.after_request
def about_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_about_html()
                marker = '<section class="sec" id="hero-settings">'
                if marker in page:
                    page = page.replace(marker, section + marker, 1)
                else:
                    marker = '<section class="sec" id="branding">'
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                page = page.replace('<a href="#hero-settings">Hero</a>', '<a href="#about-settings">About</a><a href="#hero-settings">Hero</a>', 1)
                page = page.replace('<a class="q" href="#hero-settings">Hero</a>', '<a class="q" href="#about-settings">About</a><a class="q" href="#hero-settings">Hero</a>', 1)
            elif request.path == '/':
                page = public_about(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('About enhancement failed:', exc)
    return response
