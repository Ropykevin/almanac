"""Newsletter campaign forms."""

from flask_wtf import FlaskForm
from wtforms import (
    DateTimeLocalField,
    EmailField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, Optional


class NewsletterForm(FlaskForm):
    subject = StringField(
        "Subject",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"placeholder": "This week’s dispatch"},
    )
    article_id = SelectField(
        "Featured article",
        choices=[],
        validators=[Optional()],
    )
    html_content = TextAreaField(
        "Email body (optional)",
        validators=[Optional()],
        render_kw={
            "rows": 10,
            "placeholder": "Leave blank to use the article excerpt/content in the template.",
        },
    )
    submit = SubmitField("Save campaign")


class NewsletterScheduleForm(FlaskForm):
    scheduled_at = DateTimeLocalField(
        "Send at",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    submit = SubmitField("Schedule send")


class NewsletterTestForm(FlaskForm):
    email = EmailField(
        "Test email",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"placeholder": "you@example.com"},
    )
    submit = SubmitField("Send test")
