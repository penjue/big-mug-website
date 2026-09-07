import html
from flask import request, redirect, url_for, flash, Response
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'seo_title': 'Big Mug Coffee & Tours | Coffee Experiences in Kenya',
    'seo_description': 'Discover Big Mug coffee experiences in Kenya — from farm visits and coffee journeys to local stories, flavour, roasting and memorable tours.',
    'seo_social_title': 'Big Mug Coffee & Tours',
    'seo_social_description': 'Discover coffee beyond the mug with authentic Big Mug coffee experiences, local stories and memorable journeys in Kenya.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/seo-settings')
@base.login_required
def seo_settings():
    fields = {
        'seo_title': request.form.get('seo_title', '').strip()[:180],
        'seo_description': request.form.get('seo_description', '').strip()[:320],
        'seo_social_title': request.form.get('seo_social_title', '').strip()[:180],
        'seo_social_description': request.form.get('seo_social_description', '').strip()[:320],
    }
    for key, default in DEFAULTS.items():
        base.set_setting(key, fields.get(key) or default)

    image = request.files.get('seo_social_image')
    if image and image.filename:
        filename, error = base.save_image_upload(image, base.SITE_IMAGE_DIR)
        if error:
            flash(error, 'error')
            return redirect(url_for('admin') + '#seo-settings')
        old = timeline.setting('seo_social_image_filename')
        base.set_setting('seo_social_image_filename', filename)
        if old and old != filename:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    if request.form.get('remove_seo_social_image') == '1':
        old = timeline.setting('seo_social_image_filename')
        base.set_setting('seo_social_image_filename', '')
        if old:
            base.remove_image_file(base.SITE_IMAGE_DIR, old)

    base.set_setting('seo_custom_active', '1')
    flash('SEO and sharing settings updated.', 'success')
    return redirect(url_for('admin') + '#seo-settings')


def admin_seo_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))

    current_image = timeline.setting('seo_social_image_filename')
    image_note = "<p class='muted'>A custom social preview image is active.</p>" if current_image else "<p class='muted'>The main Big Mug hero image will be used as the social preview.</p>"
    remove = "<label style='display:flex;gap:8px;align-items:center;margin-top:10px'><input type='checkbox' name='remove_seo_social_image' value='1' style='width:auto'> Use the default hero image instead</label>" if current_image else ''

    return f"""
<section class='sec' id='seo-settings'>
  <div class='head'><div><h2>SEO & Sharing</h2><p class='muted'>Control how Big Mug appears in search results and when the website is shared.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/seo-settings' enctype='multipart/form-data'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      <label>Search page title</label><input name='seo_title' value='{v('seo_title')}' required>
      <label>Search description</label><textarea name='seo_description' required>{v('seo_description')}</textarea>
      <label>Social sharing title</label><input name='seo_social_title' value='{v('seo_social_title')}' required>
      <label>Social sharing description</label><textarea name='seo_social_description' required>{v('seo_social_description')}</textarea>
      <label>Social preview image</label><input type='file' name='seo_social_image' accept='.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'>
      {image_note}{remove}
      <p class='muted'>Recommended social image: landscape format, approximately 1200 × 630 pixels.</p>
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save SEO Settings</button><a href='/' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_seo(page):
    title = html.escape(value('seo_title'))
    description = html.escape(value('seo_description'), quote=True)
    social_title = html.escape(value('seo_social_title'), quote=True)
    social_description = html.escape(value('seo_social_description'), quote=True)
    image = timeline.setting('seo_social_image_filename')
    image_url = f'https://bigmug.co.ke/site-images/{html.escape(image, quote=True)}' if image else 'https://bigmug.co.ke/static/images/hero.jpg'

    start = page.find('<title>')
    end = page.find('</title>', start)
    if start >= 0 and end >= 0:
        page = page[:start] + f'<title>{title}</title>' + page[end + 8:]

    metadata = (
        f'<meta name="description" content="{description}">'
        '<link rel="canonical" href="https://bigmug.co.ke/">'
        '<meta property="og:type" content="website">'
        '<meta property="og:url" content="https://bigmug.co.ke/">'
        f'<meta property="og:title" content="{social_title}">'
        f'<meta property="og:description" content="{social_description}">'
        f'<meta property="og:image" content="{image_url}">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{social_title}">'
        f'<meta name="twitter:description" content="{social_description}">'
        f'<meta name="twitter:image" content="{image_url}">'
    )
    if 'property="og:title"' not in page and '</head>' in page:
        page = page.replace('</head>', metadata + '</head>', 1)
    return page


@app.get('/robots.txt')
def robots_txt():
    return Response('User-agent: *\nAllow: /\nSitemap: https://bigmug.co.ke/sitemap.xml\n', mimetype='text/plain')


@app.get('/sitemap.xml')
def sitemap_xml():
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://bigmug.co.ke/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url></urlset>'
    return Response(xml, mimetype='application/xml')


@app.after_request
def seo_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_seo_html()
                markers = [
                    "<section class='sec' id='policy-settings'>",
                    '<section class="sec" id="policy-settings">',
                    "<section class='sec' id='faq-settings'>",
                    '<section class="sec" id="faq-settings">',
                ]
                inserted = False
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        inserted = True
                        break
                if not inserted and '</main>' in page:
                    page = page.replace('</main>', section + '</main>', 1)

                page = page.replace('<a href="#policy-settings">Policy</a>', '<a href="#seo-settings">SEO</a><a href="#policy-settings">Policy</a>', 1)
                page = page.replace('<a class="q" href="#policy-settings">Policy</a>', '<a class="q" href="#seo-settings">SEO</a><a class="q" href="#policy-settings">Policy</a>', 1)
            elif request.path == '/':
                page = public_seo(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('SEO enhancement failed:', exc)
    return response
