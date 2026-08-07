"""Admin site settings form."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, EmailField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp


class SiteSettingsForm(FlaskForm):
    site_name = StringField(
        "Site name",
        validators=[DataRequired(), Length(max=150)],
    )
    tagline = StringField(
        "Tagline",
        validators=[Optional(), Length(max=200)],
    )
    description = TextAreaField(
        "Short description",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
    primary_color = StringField(
        "Primary color",
        validators=[
            Optional(),
            Length(max=20),
            Regexp(
                r"^$|^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
                message="Use a hex color like #0f766e",
            ),
        ],
        render_kw={"placeholder": "#0f766e", "type": "text"},
    )
    logo_file = FileField(
        "Logo",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Images only."),
        ],
    )
    clear_logo = BooleanField("Remove current logo")

    home_welcome = TextAreaField(
        "Homepage welcome",
        validators=[Optional(), Length(max=4000)],
        render_kw={
            "rows": 5,
            "placeholder": "Shown below the hero on the homepage. Leave blank to hide.",
        },
    )

    footer_blurb = TextAreaField(
        "Footer text",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
    footer_copyright = StringField(
        "Copyright line",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Leave blank to use © Site name"},
    )

    contact_email = EmailField(
        "Contact email",
        validators=[Optional(), Email(), Length(max=150)],
    )
    contact_phone = StringField(
        "Contact phone",
        validators=[Optional(), Length(max=80)],
    )
    contact_address = TextAreaField(
        "Contact address",
        validators=[Optional(), Length(max=500)],
        render_kw={"rows": 2},
    )

    social_twitter = StringField(
        "X / Twitter URL",
        validators=[Optional(), Length(max=255)],
    )
    social_linkedin = StringField(
        "LinkedIn URL",
        validators=[Optional(), Length(max=255)],
    )
    social_facebook = StringField(
        "Facebook URL",
        validators=[Optional(), Length(max=255)],
    )
    social_instagram = StringField(
        "Instagram URL",
        validators=[Optional(), Length(max=255)],
    )
    social_youtube = StringField(
        "YouTube URL",
        validators=[Optional(), Length(max=255)],
    )
    social_substack = StringField(
        "Substack URL",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "https://yourpublication.substack.com"},
    )

    google_site_verification = StringField(
        "Google site verification",
        validators=[
            Optional(),
            Length(max=120),
            Regexp(
                r"^$|^[A-Za-z0-9_-]+$",
                message="Use only the verification content token (letters, numbers, _ or -).",
            ),
        ],
        render_kw={
            "placeholder": "Paste the content value from Google Search Console",
            "autocomplete": "off",
        },
    )

    submit = SubmitField("Save settings")
