"""Admin staff user forms."""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from app.models.enums import UserRole


def _role_choices():
    return [
        (UserRole.EDITOR.value, "Editor"),
        (UserRole.ADMIN.value, "Admin"),
        (UserRole.SUPER_ADMIN.value, "Super Admin"),
    ]


class UserCreateForm(FlaskForm):
    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(max=150)],
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    role = SelectField(
        "Role",
        choices=_role_choices(),
        validators=[DataRequired()],
        default=UserRole.EDITOR.value,
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128, message="Use at least 8 characters"),
        ],
    )
    password_confirm = PasswordField(
        "Confirm password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    bio = TextAreaField(
        "Bio",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
    is_active = BooleanField("Active account", default=True)
    submit = SubmitField("Create user")


class UserEditForm(FlaskForm):
    full_name = StringField(
        "Full name",
        validators=[DataRequired(), Length(max=150)],
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    role = SelectField(
        "Role",
        choices=_role_choices(),
        validators=[DataRequired()],
    )
    password = PasswordField(
        "New password",
        validators=[
            Optional(),
            Length(min=8, max=128, message="Use at least 8 characters"),
        ],
        render_kw={"placeholder": "Leave blank to keep current password"},
    )
    password_confirm = PasswordField(
        "Confirm new password",
        validators=[
            Optional(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    bio = TextAreaField(
        "Bio",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
    is_active = BooleanField("Active account")
    submit = SubmitField("Save changes")
