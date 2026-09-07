import html
from flask import request, redirect, url_for, flash
import timeline_app as timeline

app = timeline.app
base = timeline.base

DEFAULTS = {
    'policy_eyebrow': 'Booking flexibility',
    'policy_title': 'Changes & Cancellations',
    'policy_intro': 'We understand that travel plans can change. Communication is the most important part.',
    'policy_card1_title': 'Need to change your plans?',
    'policy_card1_text': 'Contact Big Mug as early as possible with your booking reference. We will review the request and confirm what options are available.',
    'policy_card2_title': 'If Big Mug needs to make a change',
    'policy_card2_text': 'Weather, host availability, farm conditions or access can occasionally affect an experience. If arrangements change, Big Mug will contact you directly and help arrange the best available alternative.',
    'policy_note': 'Important: detailed payment and refund terms will be published before online payments are introduced.',
}


def value(key):
    current = timeline.setting(key)
    return current if current else DEFAULTS.get(key, '')


@app.post('/admin/policy-settings')
@base.login_required
def policy_settings():
    limits = {
        'policy_eyebrow': 120,
        'policy_title': 180,
        'policy_intro': 700,
        'policy_card1_title': 180,
        'policy_card1_text': 900,
        'policy_card2_title': 180,
        'policy_card2_text': 900,
        'policy_note': 900,
    }
    for key, limit in limits.items():
        base.set_setting(key, request.form.get(key, '').strip()[:limit] or DEFAULTS[key])
    base.set_setting('policy_custom_active', '1')
    flash('Booking and cancellation policy updated.', 'success')
    return redirect(url_for('admin') + '#policy-settings')


def admin_policy_html():
    csrf = html.escape(base.csrf_token())
    def v(key):
        return html.escape(value(key))
    status = "<p class='muted'>Custom booking policy content is active on the public website.</p>" if timeline.setting('policy_custom_active') == '1' else "<p class='muted'>The current public policy remains unchanged until you save this panel.</p>"
    return f"""
<section class='sec' id='policy-settings'>
  <div class='head'><div><h2>Booking / Cancellation Policy</h2><p class='muted'>Edit the customer-facing changes, cancellations and flexibility information.</p></div></div>
  <div class='cards'><div class='card'>
    <form method='POST' action='/admin/policy-settings'>
      <input type='hidden' name='_csrf_token' value='{csrf}'>
      {status}
      <label>Small heading</label><input name='policy_eyebrow' value='{v('policy_eyebrow')}' required>
      <label>Main heading</label><input name='policy_title' value='{v('policy_title')}' required>
      <label>Introduction</label><textarea name='policy_intro' required>{v('policy_intro')}</textarea>
      <label>Policy card 1 title</label><input name='policy_card1_title' value='{v('policy_card1_title')}' required>
      <label>Policy card 1 text</label><textarea name='policy_card1_text' required>{v('policy_card1_text')}</textarea>
      <label>Policy card 2 title</label><input name='policy_card2_title' value='{v('policy_card2_title')}' required>
      <label>Policy card 2 text</label><textarea name='policy_card2_text' required>{v('policy_card2_text')}</textarea>
      <label>Important note</label><textarea name='policy_note' required>{v('policy_note')}</textarea>
      <div style='display:flex;gap:10px;flex-wrap:wrap;margin-top:14px'><button type='submit'>Save Policy</button><a href='/#policy' target='_blank' rel='noopener' style='display:inline-flex;align-items:center;justify-content:center;padding:11px 16px;border-radius:999px;background:#fff3df;color:#3b2418;text-decoration:none;font-weight:800;border:1px solid #e1c28e'>View Website ↗</a></div>
    </form>
  </div></div>
  <a class='back' href='#top'>↑ Dashboard</a>
</section>
"""


def public_policy(page):
    if timeline.setting('policy_custom_active') != '1':
        return page
    start_marker = '<section class="faq" id="policy">'
    start = page.find(start_marker)
    if start < 0:
        return page
    next_section = page.find('<section', start + len(start_marker))
    if next_section < 0:
        return page
    replacement = (
        '<section class="faq" id="policy"><div class="container"><div class="heading">'
        f'<small>{html.escape(value("policy_eyebrow"))}</small>'
        f'<h2>{html.escape(value("policy_title"))}</h2>'
        f'<p>{html.escape(value("policy_intro"))}</p>'
        '</div><div class="policy-grid">'
        f'<div class="policy-card"><h3>{html.escape(value("policy_card1_title"))}</h3><p>{html.escape(value("policy_card1_text"))}</p></div>'
        f'<div class="policy-card"><h3>{html.escape(value("policy_card2_title"))}</h3><p>{html.escape(value("policy_card2_text"))}</p><p><b>Important:</b> {html.escape(value("policy_note")).removeprefix("Important:").strip()}</p></div>'
        '</div></div></section>\n'
    )
    return page[:start] + replacement + page[next_section:]


@app.after_request
def policy_admin_enhancements(response):
    if response.content_type and 'text/html' in response.content_type:
        try:
            page = response.get_data(as_text=True)
            if request.path == '/admin':
                section = admin_policy_html()
                markers = [
                    "<section class='sec' id='faq-settings'>",
                    '<section class="sec" id="faq-settings">',
                    "<section class='sec' id='about-settings'>",
                    '<section class="sec" id="about-settings">',
                ]
                for marker in markers:
                    if marker in page:
                        page = page.replace(marker, section + marker, 1)
                        break
                page = page.replace('<a href="#faq-settings">FAQ</a>', '<a href="#policy-settings">Policy</a><a href="#faq-settings">FAQ</a>', 1)
                page = page.replace('<a class="q" href="#faq-settings">FAQ</a>', '<a class="q" href="#policy-settings">Policy</a><a class="q" href="#faq-settings">FAQ</a>', 1)
            elif request.path == '/':
                page = public_policy(page)
            response.set_data(page)
            response.headers['Content-Length'] = str(len(response.get_data()))
        except Exception as exc:
            print('Policy enhancement failed:', exc)
    return response
