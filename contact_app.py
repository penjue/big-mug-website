import timeline_app as timeline

# timeline_app already provides the Contact & Reviews routes, public contact
# section, testimonials, booking timeline, and the single admin dashboard
# enhancement. Keep this module as Render's stable entry point without adding
# a second admin wrapper, which caused duplicated navigation buttons and
# duplicated Contact, Social & Reviews sections.
app = timeline.app
