import timeline_app as timeline

app = timeline.app


def add_contact_reviews_to_admin(page):
    """Add Contact & Reviews directly to the current admin HTML."""
    if 'id="contact-reviews"' not in page:
        section = timeline.admin_contact_reviews_html()
        # Convert the generated section to the native dashboard classes.
        section = section.replace("class='section' id='contact-reviews'", "class='sec' id='contact-reviews'")
        section = section.replace("class='section-head'", "class='head'")
        section = section.replace("class='back-top'", "class='back'")
        section = section.replace("class='red'", "class='danger'")

        marker = '<section class="sec" id="security">'
        if marker in page:
            page = page.replace(marker, section + marker, 1)
        else:
            # Safe fallback: place it immediately before the closing dashboard wrapper.
            script_marker = '<script>document.querySelectorAll(\'.show\')'
            if script_marker in page:
                page = page.replace(script_marker, section + script_marker, 1)

    # Top navigation.
    if '<a href="#contact-reviews">Contact & Reviews</a>' not in page:
        page = page.replace(
            '<a href="#branding">Branding</a><a href="#security">Security</a>',
            '<a href="#branding">Branding</a><a href="#contact-reviews">Contact & Reviews</a><a href="#security">Security</a>',
            1,
        )

    # Dashboard shortcut buttons.
    if '<a class="q" href="#contact-reviews">Contact & Reviews</a>' not in page:
        page = page.replace(
            '<a class="q" href="#branding">Branding</a><a class="q" href="#security">Security</a>',
            '<a class="q" href="#branding">Branding</a><a class="q" href="#contact-reviews">Contact & Reviews</a><a class="q" href="#security">Security</a>',
            1,
        )

    # Keep the dashboard description accurate.
    page = page.replace(
        'Manage bookings, enquiries, experiences, marketplace, branding and security.',
        'Manage bookings, enquiries, experiences, marketplace, contact details, reviews, branding and security.',
        1,
    )
    return page


# Wrap the real /admin view itself. This is more reliable than waiting for a
# post-response hook and guarantees the feature is part of the rendered page.
_original_admin = app.view_functions['admin']


def admin_with_contact_reviews(*args, **kwargs):
    result = _original_admin(*args, **kwargs)
    response = app.make_response(result)
    if response.content_type and 'text/html' in response.content_type:
        page = response.get_data(as_text=True)
        response.set_data(add_contact_reviews_to_admin(page))
        response.headers['Content-Length'] = str(len(response.get_data()))
    return response


app.view_functions['admin'] = admin_with_contact_reviews
