"""Category and tag forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app.utils.slug import slugify


class CategoryForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=100)],
        render_kw={"placeholder": "e.g. Artificial Intelligence"},
    )
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "auto-generated-from-name"},
    )
    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 4, "placeholder": "Optional description"},
    )
    submit = SubmitField("Save category")

    def validate_slug(self, field) -> None:
        if field.data:
            cleaned = slugify(field.data)
            if not cleaned:
                raise ValidationError("Slug contains no valid characters.")
            field.data = cleaned


class TagForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired(), Length(max=100)],
        render_kw={"placeholder": "e.g. Africa"},
    )
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "auto-generated-from-name"},
    )
    submit = SubmitField("Save tag")

    def validate_slug(self, field) -> None:
        if field.data:
            cleaned = slugify(field.data)
            if not cleaned:
                raise ValidationError("Slug contains no valid characters.")
            field.data = cleaned
