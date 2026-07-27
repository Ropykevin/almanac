"""Public website forms."""

from flask_wtf import FlaskForm
from wtforms import EmailField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional


class SubscribeForm(FlaskForm):
    full_name = StringField(
        "Name",
        validators=[Optional(), Length(max=150)],
        render_kw={"placeholder": "Your name (optional)", "autocomplete": "name"},
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"placeholder": "Type your email…", "autocomplete": "email"},
    )
    submit = SubmitField("Subscribe")


class CommentForm(FlaskForm):
    full_name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=150)],
        render_kw={"placeholder": "Your name", "autocomplete": "name"},
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
        render_kw={"placeholder": "you@example.com", "autocomplete": "email"},
    )
    body = TextAreaField(
        "Comment",
        validators=[DataRequired(), Length(max=5000)],
        render_kw={"rows": 4, "placeholder": "Share your thoughts…"},
    )
    submit = SubmitField("Post comment")
