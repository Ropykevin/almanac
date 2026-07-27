"""Authentication forms."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length


class LoginForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
        render_kw={"autocomplete": "username", "placeholder": "you@example.com"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, max=128)],
        render_kw={"autocomplete": "current-password", "placeholder": "Your password"},
    )
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign in")


class ForgotPasswordForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)],
        render_kw={"autocomplete": "email", "placeholder": "you@example.com"},
    )
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New password",
        validators=[
            DataRequired(),
            Length(min=8, max=128, message="Password must be at least 8 characters."),
        ],
        render_kw={"autocomplete": "new-password", "placeholder": "At least 8 characters"},
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match."),
        ],
        render_kw={"autocomplete": "new-password", "placeholder": "Repeat new password"},
    )
    submit = SubmitField("Update password")
