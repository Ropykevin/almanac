"""Subscriber admin / public forms."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import EmailField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

from app.models.enums import SubscriberStatus


class UnsubscribeForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"placeholder": "you@example.com", "autocomplete": "email"},
    )
    submit = SubmitField("Unsubscribe")


class SubscriberAdminForm(FlaskForm):
    full_name = StringField(
        "Name",
        validators=[Optional(), Length(max=150)],
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    status = SelectField(
        "Status",
        choices=[(s.value, s.value.title()) for s in SubscriberStatus],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save subscriber")


class SubscriberImportForm(FlaskForm):
    file = FileField(
        "CSV file",
        validators=[
            FileRequired(),
            FileAllowed(["csv"], "CSV files only."),
        ],
    )
    submit = SubmitField("Import CSV")
