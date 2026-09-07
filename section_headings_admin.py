import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

# Adds icon styling to the public Contact Big Mug action buttons.
import contact_icons
# Registers product purchasing, delivery and payment controls.
import commerce_admin

app = timeline.app
base = timeline.base

DEFAULTS = {
    'experiences_eyebrow': 'Choose your journey',
    'experiences_title': 'Big Mug Experiences',
    'experiences_intro': 'Explore our coffee experiences and choose the journey that suits you.',
    'compare_eyebrow': 'Quick comparison',
    'compare_title': 'Compare Experiences',
    'marketplace_eyebrow': 'Take the flavour home',
    'marketplace_title': 'Coffee Marketplace',
    'marketplace_intro': 'Shop Big Mug coffee bags and useful barista tools.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/section-headings-settings')
@base.login_required
def section_headings_settings():
    limits = {
        'experiences_eyebrow': 120,
        'experiences_title': 180,
        'experiences_intro': 600,
        'compare_eyebrow': 120,
        'compare_title': 180,
        'marketplace_eyebrow': 120,
        'marketplace_title': 180,
        'marketplace_intro': 600,
    }
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])
    base.set_setting('section_headings_custom_active', '1')
    flash('Homepage section headings updated.', 'success')
    return redirect(url_for('admin') + '#section-headings-settings')


def admin_section_headings_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))
    status = "<p class='muted'>Custom homepage section headings are active on the public website.</p>" if timeline.setting('section_headings_custom_active') == '1' else "<p class='muted'>The current public headings remain unchanged until you save this panel.</p>"
    return f"""
<section class='sec' id='section-headings-settings'>
  <div class='head'><div><h2>Homepage Section Headings</h2><p class='muted'>Edit the Experiences, Compare and Marketplace headings without changing their products or cards.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/section-headings-settings'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      {status}
      <h3>Experiences</h3>
      <label>Small heading</label><input name='experiences_eyebrow' value='{v('experiences_eyebrow')}' required>
      <label>Main heading</label><input name='experiences_title' value='{v('experiences_title')}' required>
      <label>Introduction</label><textarea name='experiences_intro' required>{v('experiences_intro')}</textarea>
      <h3 style='margin-top:24px'>Compare Experiences</h3>
      <label>Small heading</label><input name='compare_eyebrow' value='{v('compare_eyebrow')}' required>
      <label>Main heading</label><input name='compare_title' value='{v('compare_title')}' required>
      <h3 style='margin-top:24px'>Marketplace</h3>
      <label>Small heading</label><input name='marketplace_eyebrow' value='{v('marketplace_eyebrow')}' required>
      <label>Main heading</label><input name='marketplace_title' value='{v('marketplace_title')}' required>
      <label>Introduction</label><textarea name='marketplace_intro' required>{v('marketplace_intro')}</textarea>
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save Section Headings</button><a href='/#experiences' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_section_headings(page):
    if timeline.setting('section_headings_custom_active') != '1':
        return page

    replacements = [
        (
            '<div class="heading"><small>Choose your journey</small><h2>Big Mug Experiences</h2><p>Explore our coffee experiences and choose the journey that suits you.</p></div>',
            f'<div class="heading"><small>{html.escape(value("experiences_eyebrow"))}</small><h2>{html.escape(value("experiences_title"))}</h2><p>{html.escape(value("experiences_intro"))}</p></div>'
        ),
        (
            '<div class="heading"><small>Quick comparison</small><h2>Compare Experiences</h2></div>',
            f'<div class="heading"><small>{html.escape(value("compare_eyebrow"))}</small><h2>{html.escape(value("compare_title"))}</h2></div>'
        ),
        (
            '<div class="heading"><small>Take the flavour home</small><h2>Coffee Marketplace</h2><p>Shop Big Mug coffee bags and useful barista tools.</p></div>',
            f'<div class="heading"><small>{html.escape(value("marketplace_eyebrow"))}</small><h2>{html.escape(value("marketplace_title"))}</h2><p>{html.escape(value("marketplace_intro"))}</p></div>'
        ),
    ]
    for old, new in replacements:
        if old in page:
            page = page.replace(old, new, 1)
    return page


@app.after_request
def section_headings_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_section_headings_html()
                markers = [
                    "<section class='sec' id='booking-guide-settings'>",
                    '<section class="sec" id="booking-guide-settings">',
                    "<section class='sec' id='story-settings'>",
                    '<section class="sec" id="story-settings">',
                ]
                inserted = False
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        inserted = True
                        break
                if not inserted and '</main>' in page:
                    page = page.replace('</main>', section + '</main>', 1)

                page = page.replace('<a href="#booking-guide-settings">Booking Guide</a>', '<a href="#section-headings-settings">Section Headings</a><a href="#booking-guide-settings">Booking Guide</a>', 1)
                page = page.replace('<a class="q" href="#booking-guide-settings">Booking Guide</a>', '<a class="q" href="#section-headings-settings">Section Headings</a><a class="q" href="#booking-guide-settings">Booking Guide</a>', 1)
            elif request.path == '/':
                page = public_section_headings(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Section headings enhancement failed:', exc)
    return response
