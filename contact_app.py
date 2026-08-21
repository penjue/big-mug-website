import html
import timeline_app as timeline

app = timeline.app


def public_footer_html():
    email = timeline.setting('public_contact_email')
    whatsapp = timeline.setting('whatsapp_number')
    instagram = timeline.safe_url(timeline.setting('instagram_url'))
    facebook = timeline.safe_url(timeline.setting('facebook_url'))
    wa = timeline.whatsapp_href(whatsapp)

    contact_bits = ["<p>Nairobi, Kenya</p>"]
    if wa:
        contact_bits.append(
            f"<a href='{html.escape(wa)}' target='_blank' rel='noopener'>WhatsApp Big Mug</a>"
        )
    if email:
        contact_bits.append(
            f"<a href='mailto:{html.escape(email)}'>{html.escape(email)}</a>"
        )
    if len(contact_bits) == 1:
        contact_bits.append("<p>Bookings and product enquiries available.</p>")

    social_bits = []
    if instagram:
        social_bits.append(
            f"<a href='{html.escape(instagram)}' target='_blank' rel='noopener'>Instagram</a>"
        )
    if facebook:
        social_bits.append(
            f"<a href='{html.escape(facebook)}' target='_blank' rel='noopener'>Facebook</a>"
        )
    if not social_bits:
        social_bits.append("<p>Social links coming soon.</p>")

    return (
        "<div><b>Contact</b>" + ''.join(contact_bits) + "</div>"
        "<div><b>Follow Us</b>" + ''.join(social_bits) + "</div>"
    )


def enhance_public_home(page):
    # Add the main public contact + testimonial block exactly once.
    if "id='contact-trust'" not in page and 'id="contact-trust"' not in page:
        public = timeline.public_trust_html()
        marker = '<section class="enquiry" id="enquire">'
        if marker in page:
            page = page.replace(marker, public + marker, 1)

    # Add Contact to the public navigation exactly once.
    if 'href="#contact-trust">Contact</a>' not in page:
        page = page.replace(
            '<a href="#enquire">Enquire</a><a class="cta"',
            '<a href="#contact-trust">Contact</a><a href="#enquire">Enquire</a><a class="cta"',
            1,
        )

    # Replace the old hard-coded footer contact/social blocks with live Admin values.
    old_footer = (
        '<div><b>Contact</b><p>Nairobi, Kenya</p><p>Bookings and product enquiries available.</p></div>'
        '<div><b>Follow Us</b><p>Instagram</p><p>Facebook</p></div>'
    )
    if old_footer in page:
        page = page.replace(old_footer, public_footer_html(), 1)

    return page


# Wrap the actual home view so public contact details always render even if a
# response hook is skipped by another layer.
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
