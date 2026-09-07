import timeline_app as timeline


def contact_icon(kind):
    icons = {
        'whatsapp': "<svg aria-hidden='true' viewBox='0 0 24 24' style='width:19px;height:19px;flex:0 0 19px'><path fill='currentColor' d='M17.5 14.4c-.3-.2-1.8-.9-2.1-1s-.5-.2-.7.2c-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-1.9-.9-3.1-1.7-4.4-3.9-.3-.5.3-.5.9-1.6.1-.2 0-.5-.1-.7s-.7-1.7-1-2.3c-.3-.6-.6-.5-.8-.5h-.7c-.2 0-.7.1-1 .5-.3.4-1.3 1.3-1.3 3.1s1.3 3.6 1.5 3.8c.2.3 2.6 4 6.3 5.6 2.4 1 3.4 1.1 4.6.9.7-.1 1.8-.7 2-1.4.3-.7.3-1.3.2-1.4-.1-.2-.3-.3-.6-.4z'/><path fill='currentColor' d='M12 2a9.9 9.9 0 0 0-8.5 15L2 22l5.1-1.4A10 10 0 1 0 12 2zm0 18.2c-1.5 0-2.9-.4-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2z'/></svg>",
        'email': "<svg aria-hidden='true' viewBox='0 0 24 24' style='width:19px;height:19px;flex:0 0 19px'><path fill='currentColor' d='M3 5h18a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm9 7 8-5H4l8 5zm0 2.3L3 8.7V17h18V8.7l-9 5.6z'/></svg>",
        'instagram': "<svg aria-hidden='true' viewBox='0 0 24 24' style='width:19px;height:19px;flex:0 0 19px'><path fill='currentColor' d='M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zm0 2a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3H7zm10.5 1.5a1.2 1.2 0 1 1 0 2.4 1.2 1.2 0 0 1 0-2.4zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'/></svg>",
        'facebook': "<svg aria-hidden='true' viewBox='0 0 24 24' style='width:19px;height:19px;flex:0 0 19px'><path fill='currentColor' d='M13.5 22v-9h3l.5-3h-3.5V8.1c0-.9.3-1.6 1.6-1.6H17V3.8c-.4 0-1.5-.2-2.8-.2-2.8 0-4.7 1.7-4.7 4.8V10H6.5v3h3v9h4z'/></svg>",
        'tiktok': "<svg aria-hidden='true' viewBox='0 0 24 24' style='width:19px;height:19px;flex:0 0 19px'><path fill='currentColor' d='M15.3 2c.3 2 1.5 3.7 3.7 4.1v3.1c-1.4 0-2.7-.4-3.7-1.1v6.2a6.3 6.3 0 1 1-5.4-6.2v3.2a3.1 3.1 0 1 0 2.2 3V2h3.2z'/></svg>",
    }
    return icons.get(kind, '')


_original_public_trust_html = timeline.public_trust_html


def public_trust_html_with_icons():
    page = _original_public_trust_html()
    replacements = {
        '>WhatsApp Big Mug</a>': f">{contact_icon('whatsapp')}<span>WhatsApp Big Mug</span></a>",
        '>Email Us</a>': f">{contact_icon('email')}<span>Email Us</span></a>",
        '>Instagram</a>': f">{contact_icon('instagram')}<span>Instagram</span></a>",
        '>Facebook</a>': f">{contact_icon('facebook')}<span>Facebook</span></a>",
        '>TikTok</a>': f">{contact_icon('tiktok')}<span>TikTok</span></a>",
    }
    for old, new in replacements.items():
        page = page.replace(old, new, 1)

    page = page.replace(
        "style='display:inline-block;background:#d3a04f;color:#1d120d;padding:13px 20px;border-radius:999px;text-decoration:none;font-weight:900'",
        "style='display:inline-flex;align-items:center;gap:9px;background:#d3a04f;color:#1d120d;padding:13px 20px;border-radius:999px;text-decoration:none;font-weight:900'",
        1,
    )
    page = page.replace(
        "style='display:inline-block;background:#fff;color:#3b2418;padding:13px 20px;border:1px solid #d8cec4;border-radius:999px;text-decoration:none;font-weight:900'",
        "style='display:inline-flex;align-items:center;gap:9px;background:#fff;color:#3b2418;padding:13px 20px;border:1px solid #d8cec4;border-radius:999px;text-decoration:none;font-weight:900'",
        1,
    )
    for name in ('Instagram', 'Facebook', 'TikTok'):
        page = page.replace(
            "style='color:#3b2418;font-weight:800'",
            "style='display:inline-flex;align-items:center;gap:9px;background:#fff;color:#3b2418;padding:13px 18px;border:1px solid #d8cec4;border-radius:999px;text-decoration:none;font-weight:900'",
            1,
        )
    return page


timeline.public_trust_html = public_trust_html_with_icons
