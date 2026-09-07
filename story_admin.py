import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'story_title': 'The Story Behind the Flavour',
    'story_paragraph_1': 'Coffee changes long before it reaches your cup. Altitude, soil, variety, rainfall, harvesting, fermentation, drying and roasting all influence the final experience.',
    'story_paragraph_2': 'At Big Mug, we make that journey visible. You will learn how small choices along the chain create sweetness, acidity, body, aroma and balance.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/story-settings')
@base.login_required
def story_settings():
    limits = {
        'story_title': 180,
        'story_paragraph_1': 1000,
        'story_paragraph_2': 1000,
    }
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])

    image = request.files.get('story_image')
    if image and image.filename:
        filename, error = base.save_image_upload(image, base.SITE_IMAGE_DIR)
        if error:
            flash(error, 'error')
            return redirect(url_for('admin') + '#story-settings')
        old = timeline.setting('story_image_filename')
        base.set_setting('story_image_filename', filename)
        if old and old != filename:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    if request.form.get('remove_story_image') == '1':
        old = timeline.setting('story_image_filename')
        base.set_setting('story_image_filename', '')
        if old:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    base.set_setting('story_custom_active', '1')
    flash('Our Story section updated.', 'success')
    return redirect(url_for('admin') + '#story-settings')


def admin_story_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))

    current_image = timeline.setting('story_image_filename')
    image_note = "<p class='muted'>A custom Our Story image is currently active.</p>" if current_image else "<p class='muted'>The original Big Mug Our Story image is currently active.</p>"
    remove = "<label style='display:flex;gap:8px;align-items:center;margin-top:10px'><input type='checkbox' name='remove_story_image' value='1' style='width:auto'> Restore original Our Story image</label>" if current_image else ''

    return f"""
<section class='sec' id='story-settings'>
  <div class='head'><div><h2>Our Story</h2><p class='muted'>Edit the story section that explains the journey behind Big Mug coffee.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/story-settings' enctype='multipart/form-data'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      <label>Story heading</label><input name='story_title' value='{v('story_title')}' required>
      <label>Paragraph 1</label><textarea name='story_paragraph_1' required>{v('story_paragraph_1')}</textarea>
      <label>Paragraph 2</label><textarea name='story_paragraph_2' required>{v('story_paragraph_2')}</textarea>
      <label>Story image</label><input type='file' name='story_image' accept='.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'>
      {image_note}{remove}
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save Our Story</button><a href='/#story' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_story(page):
    if timeline.setting('story_custom_active') != '1' and not timeline.setting('story_image_filename'):
        return page

    start_marker = '<section class="story" id="story">'
    start = page.find(start_marker)
    if start < 0:
        return page
    next_section = page.find('<section', start + len(start_marker))
    if next_section < 0:
        return page

    image = timeline.setting('story_image_filename')
    if image:
        safe_image = html.escape(image, quote=True)
        image_html = f'<div class="story-image" style="background-image:url(\'/site-images/{safe_image}\')"></div>'
    else:
        image_html = '<div class="story-image"></div>'

    replacement = (
        '<section class="story" id="story"><div class="story-grid">'
        + image_html
        + '<div class="story-copy">'
        + f'<h2>{html.escape(value("story_title"))}</h2>'
        + f'<p>{html.escape(value("story_paragraph_1"))}</p>'
        + f'<p>{html.escape(value("story_paragraph_2"))}</p>'
        + '</div></div></section>\n'
    )
    return page[:start] + replacement + page[next_section:]


@app.after_request
def story_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_story_html()
                markers = [
                    "<section class='sec' id='seo-settings'>",
                    '<section class="sec" id="seo-settings">',
                    "<section class='sec' id='policy-settings'>",
                    '<section class="sec" id="policy-settings">',
                ]
                inserted = False
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        inserted = True
                        break
                if not inserted and '</main>' in page:
                    page = page.replace('</main>', section + '</main>', 1)

                page = page.replace('<a href="#seo-settings">SEO</a>', '<a href="#story-settings">Our Story</a><a href="#seo-settings">SEO</a>', 1)
                page = page.replace('<a class="q" href="#seo-settings">SEO</a>', '<a class="q" href="#story-settings">Our Story</a><a class="q" href="#seo-settings">SEO</a>', 1)
            elif request.path == '/':
                page = public_story(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Story enhancement failed:', exc)
    return response
