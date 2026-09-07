import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'faq_eyebrow': 'Before your visit',
    'faq_title': 'Frequently Asked Questions',
    'faq_q1': 'Is my booking confirmed when I submit the form?',
    'faq_a1': 'No. Your request is received first, then Big Mug reviews availability and confirms the booking with you directly.',
    'faq_q2': 'Can I ask questions before booking?',
    'faq_a2': 'Absolutely. Use the Ask Big Mug enquiry form for tour questions, group planning, marketplace products, partnerships or anything you need clarified.',
    'faq_q3': 'Can I change my preferred date or time?',
    'faq_a3': 'Yes. Contact Big Mug as early as possible and we will help you adjust the request subject to availability.',
    'faq_q4': 'Are Big Mug experiences suitable for groups?',
    'faq_a4': 'Yes. Couples, families, private groups and corporate guests can all be accommodated depending on the selected experience and availability.',
    'faq_q5': 'How will I receive booking updates?',
    'faq_a5': 'Booking and schedule updates can be sent to the email address you provide, and the Big Mug team can contact you directly when needed.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/faq-settings')
@base.login_required
def faq_settings():
    limits = {'faq_eyebrow': 120, 'faq_title': 180}
    for i in range(1, 6):
        limits[f'faq_q{i}'] = 240
        limits[f'faq_a{i}'] = 900
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])
    base.set_setting('faq_custom_active', '1')
    flash('FAQ section updated.', 'success')
    return redirect(url_for('admin') + '#faq-settings')


def admin_faq_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))
    items = []
    for i in range(1, 6):
        items.append(
            f"<label>Question {i}</label><input name='faq_q{i}' value='{v(f'faq_q{i}')}' required>"
            f"<label>Answer {i}</label><textarea name='faq_a{i}' required>{v(f'faq_a{i}')}</textarea>"
        )
    status = "<p class='muted'>Custom FAQ content is active on the public website.</p>" if timeline.setting('faq_custom_active') == '1' else "<p class='muted'>The current public FAQ remains unchanged until you save this panel.</p>"
    return f"""
<section class='sec' id='faq-settings'>
  <div class='head'><div><h2>FAQ</h2><p class='muted'>Edit the questions customers see before they book or enquire.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/faq-settings'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      {status}
      <label>Small heading</label><input name='faq_eyebrow' value='{v('faq_eyebrow')}' required>
      <label>Main heading</label><input name='faq_title' value='{v('faq_title')}' required>
      {''.join(items)}
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save FAQ</button><a href='/#faq' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_faq(page):
    if timeline.setting('faq_custom_active') != '1':
        return page
    start_marker = '<section id="faq">'
    start = page.find(start_marker)
    if start < 0:
        return page
    next_section = page.find('<section', start + len(start_marker))
    if next_section < 0:
        return page
    details = []
    for i in range(1, 6):
        q = html.escape(value(f'faq_q{i}'))
        a = html.escape(value(f'faq_a{i}'))
        details.append(f'<details><summary>{q}</summary><p>{a}</p></details>')
    replacement = (
        '<section id="faq"><div class="container"><div class="heading">'
        f'<small>{html.escape(value("faq_eyebrow"))}</small>'
        f'<h2>{html.escape(value("faq_title"))}</h2>'
        '</div><div class="faq-list">' + ''.join(details) + '</div></div></section>\n'
    )
    return page[:start] + replacement + page[next_section:]


@app.after_request
def faq_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_faq_html()
                markers = [
                    "<section class='sec' id='about-settings'>",
                    '<section class="sec" id="about-settings">',
                    "<section class='sec' id='hero-settings'>",
                    '<section class="sec" id="hero-settings">',
                ]
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        break
                page = page.replace('<a href="#about-settings">About</a>', '<a href="#faq-settings">FAQ</a><a href="#about-settings">About</a>', 1)
                page = page.replace('<a class="q" href="#about-settings">About</a>', '<a class="q" href="#faq-settings">FAQ</a><a class="q" href="#about-settings">About</a>', 1)
            elif request.path == '/':
                page = public_faq(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('FAQ enhancement failed:', exc)
    return response
