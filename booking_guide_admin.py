import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'booking_guide_eyebrow': 'Simple from request to experience',
    'booking_guide_title': 'What Happens After You Book?',
    'booking_guide_intro': 'Your request stays transparent from the moment you send it until your Big Mug experience is complete.',
    'booking_guide_step1_title': 'Send your request',
    'booking_guide_step1_text': 'Choose an experience, preferred date and optional time. You receive a booking reference by email.',
    'booking_guide_step2_title': 'We check availability',
    'booking_guide_step2_text': 'Big Mug reviews your request. Your booking is not confirmed until you receive the confirmation email.',
    'booking_guide_step3_title': 'Stay updated',
    'booking_guide_step3_text': 'If arrangements change, Big Mug can send you a direct schedule update with the revised details.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/booking-guide-settings')
@base.login_required
def booking_guide_settings():
    limits = {
        'booking_guide_eyebrow': 120,
        'booking_guide_title': 180,
        'booking_guide_intro': 700,
        'booking_guide_step1_title': 180,
        'booking_guide_step1_text': 700,
        'booking_guide_step2_title': 180,
        'booking_guide_step2_text': 700,
        'booking_guide_step3_title': 180,
        'booking_guide_step3_text': 700,
    }
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])
    base.set_setting('booking_guide_custom_active', '1')
    flash('Booking Guide updated.', 'success')
    return redirect(url_for('admin') + '#booking-guide-settings')


def admin_booking_guide_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))
    status = "<p class='muted'>Custom Booking Guide content is active on the public website.</p>" if timeline.setting('booking_guide_custom_active') == '1' else "<p class='muted'>The current public Booking Guide remains unchanged until you save this panel.</p>"
    return f"""
<section class='sec' id='booking-guide-settings'>
  <div class='head'><div><h2>Booking Guide</h2><p class='muted'>Edit what customers are told happens after they submit a booking request.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/booking-guide-settings'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      {status}
      <label>Small heading</label><input name='booking_guide_eyebrow' value='{v('booking_guide_eyebrow')}' required>
      <label>Main heading</label><input name='booking_guide_title' value='{v('booking_guide_title')}' required>
      <label>Introduction</label><textarea name='booking_guide_intro' required>{v('booking_guide_intro')}</textarea>
      <label>Step 1 title</label><input name='booking_guide_step1_title' value='{v('booking_guide_step1_title')}' required>
      <label>Step 1 text</label><textarea name='booking_guide_step1_text' required>{v('booking_guide_step1_text')}</textarea>
      <label>Step 2 title</label><input name='booking_guide_step2_title' value='{v('booking_guide_step2_title')}' required>
      <label>Step 2 text</label><textarea name='booking_guide_step2_text' required>{v('booking_guide_step2_text')}</textarea>
      <label>Step 3 title</label><input name='booking_guide_step3_title' value='{v('booking_guide_step3_title')}' required>
      <label>Step 3 text</label><textarea name='booking_guide_step3_text' required>{v('booking_guide_step3_text')}</textarea>
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save Booking Guide</button><a href='/#booking-guide' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_booking_guide(page):
    if timeline.setting('booking_guide_custom_active') != '1':
        return page
    start_marker = '<section id="booking-guide">'
    start = page.find(start_marker)
    if start < 0:
        return page
    next_section = page.find('<section', start + len(start_marker))
    if next_section < 0:
        return page

    steps = []
    for i in range(1, 4):
        steps.append(
            f'<div class="step"><div class="step-num">{i}</div>'
            f'<h3>{html.escape(value(f"booking_guide_step{i}_title"))}</h3>'
            f'<p>{html.escape(value(f"booking_guide_step{i}_text"))}</p></div>'
        )
    replacement = (
        '<section id="booking-guide"><div class="container"><div class="heading">'
        f'<small>{html.escape(value("booking_guide_eyebrow"))}</small>'
        f'<h2>{html.escape(value("booking_guide_title"))}</h2>'
        f'<p>{html.escape(value("booking_guide_intro"))}</p>'
        '</div><div class="steps">' + ''.join(steps) + '</div></div></section>\n'
    )
    return page[:start] + replacement + page[next_section:]


@app.after_request
def booking_guide_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_booking_guide_html()
                markers = [
                    "<section class='sec' id='story-settings'>",
                    '<section class="sec" id="story-settings">',
                    "<section class='sec' id='seo-settings'>",
                    '<section class="sec" id="seo-settings">',
                ]
                inserted = False
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        inserted = True
                        break
                if not inserted and '</main>' in page:
                    page = page.replace('</main>', section + '</main>', 1)

                page = page.replace('<a href="#story-settings">Our Story</a>', '<a href="#booking-guide-settings">Booking Guide</a><a href="#story-settings">Our Story</a>', 1)
                page = page.replace('<a class="q" href="#story-settings">Our Story</a>', '<a class="q" href="#booking-guide-settings">Booking Guide</a><a class="q" href="#story-settings">Our Story</a>', 1)
            elif request.path == '/':
                page = public_booking_guide(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Booking Guide enhancement failed:', exc)
    return response
