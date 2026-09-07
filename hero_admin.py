import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'hero_eyebrow': 'Experience the journey behind every cup',
    'hero_title_main': 'Discover coffee',
    'hero_title_accent': 'beyond the mug.',
    'hero_description': 'Big Mug invites you into a deeper coffee experience — from the farm, the people and the process, to the aroma, flavour and story waiting in every cup.',
    'hero_button_text': 'Explore Experiences →',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/hero-settings')
@base.login_required
def hero_settings():
    fields = {
        'hero_eyebrow': request.form.get('hero_eyebrow', '').strip()[:180],
        'hero_title_main': request.form.get('hero_title_main', '').strip()[:180],
        'hero_title_accent': request.form.get('hero_title_accent', '').strip()[:180],
        'hero_description': request.form.get('hero_description', '').strip()[:800],
        'hero_button_text': request.form.get('hero_button_text', '').strip()[:120],
    }
    for key, default in DEFAULTS.items():
        base.set_setting(key, fields.get(key) or default)

    image = request.files.get('hero_image')
    if image and image.filename:
        filename, error = base.save_image_upload(image, base.SITE_IMAGE_DIR)
        if error:
            flash(error, 'error')
            return redirect(url_for('admin') + '#hero-settings')
        old = timeline.setting('hero_image_filename')
        base.set_setting('hero_image_filename', filename)
        if old and old != filename:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    if request.form.get('remove_hero_image') == '1':
        old = timeline.setting('hero_image_filename')
        base.set_setting('hero_image_filename', '')
        if old:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    flash('Hero section updated.', 'success')
    return redirect(url_for('admin') + '#hero-settings')


def admin_hero_html():
    csrf = html.escape(base.csrf_token())
    eyebrow = html.escape(value('hero_eyebrow'))
    title_main = html.escape(value('hero_title_main'))
    title_accent = html.escape(value('hero_title_accent'))
    description = html.escape(value('hero_description'))
    button = html.escape(value('hero_button_text'))
    current_image = timeline.setting('hero_image_filename')
    image_note = "<p class='muted'>A custom hero image is currently active.</p>" if current_image else "<p class='muted'>The original Big Mug hero image is currently active.</p>"
    remove = "<label style='display:flex;gap:8px;align-items:center;margin-top:10px'><input type='checkbox' name='remove_hero_image' value='1' style='width:auto'> Restore original hero image</label>" if current_image else ''
    return f"""
<section class='sec' id='hero-settings'>
  <div class='head'><div><h2>Homepage Hero</h2><p class='muted'>Edit the first section visitors see without changing the Big Mug layout.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/hero-settings' enctype='multipart/form-data'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      <label>Small heading</label><input name='hero_eyebrow' value='{eyebrow}' required>
      <label>Main headline</label><input name='hero_title_main' value='{title_main}' required>
      <label>Gold highlighted headline</label><input name='hero_title_accent' value='{title_accent}' required>
      <label>Hero description</label><textarea name='hero_description' required>{description}</textarea>
      <label>Button text</label><input name='hero_button_text' value='{button}' required>
      <label>Hero background image</label><input type='file' name='hero_image' accept='.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'>
      {image_note}{remove}
      <button type='submit'>Save Hero Section</button>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_hero(page):
    eyebrow = html.escape(value('hero_eyebrow'))
    title_main = html.escape(value('hero_title_main'))
    title_accent = html.escape(value('hero_title_accent'))
    description = html.escape(value('hero_description'))
    button = html.escape(value('hero_button_text'))

    old = '<div class="eyebrow">Experience the journey behind every cup</div><h1>Discover coffee <span>beyond the mug.</span></h1><p>Big Mug invites you into a deeper coffee experience — from the farm, the people and the process, to the aroma, flavour and story waiting in every cup.</p><a class="btn" href="#experiences">Explore Experiences →</a>'
    new = f'<div class="eyebrow">{eyebrow}</div><h1>{title_main} <span>{title_accent}</span></h1><p>{description}</p><a class="btn" href="#experiences">{button}</a>'
    if old in page:
        page = page.replace(old, new, 1)

    image = timeline.setting('hero_image_filename')
    if image:
        safe_image = html.escape(image, quote=True)
        marker = '<section class="hero">'
        replacement = f'<section class="hero" style="background:linear-gradient(90deg,rgba(20,12,8,.84),rgba(20,12,8,.28)),url(\'/site-images/{safe_image}\') center/cover">'
        page = page.replace(marker, replacement, 1)
    return page


@app.after_request
def hero_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_hero_html()
                marker = '<section class="sec" id="branding">'
                if marker in page:
                    page = page.replace(marker, section + marker, 1)
                else:
                    marker = '<section class="sec" id="contact-reviews">'
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                page = page.replace('<a href="#branding">Branding</a>', '<a href="#hero-settings">Hero</a><a href="#branding">Branding</a>', 1)
                page = page.replace('<a class="q" href="#branding">Branding</a>', '<a class="q" href="#hero-settings">Hero</a><a class="q" href="#branding">Branding</a>', 1)
            elif request.path == '/':
                page = public_hero(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Hero enhancement failed:', exc)
    return response
