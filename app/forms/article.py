"""Article management forms."""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.models.enums import ArticleStatus
from app.utils.slug import slugify


class MultiCheckboxField(SelectMultipleField):
    """Checkbox group for multi-select taxonomy fields."""

    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class ArticleForm(FlaskForm):
    title = StringField(
        "Title",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"placeholder": "Article title"},
    )
    subtitle = StringField(
        "Subtitle",
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Optional subtitle"},
    )
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "auto-generated-from-title"},
    )
    excerpt = TextAreaField(
        "Excerpt",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3, "placeholder": "Short summary for listings and SEO"},
    )
    content = TextAreaField(
        "Content",
        validators=[Optional()],
        render_kw={"rows": 16, "placeholder": "Write the full article…"},
    )
    featured_image_file = FileField(
        "Featured image",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Images only."),
        ],
    )
    clear_featured_image = BooleanField("Remove featured image")
    reading_time = IntegerField(
        "Reading time (minutes)",
        validators=[Optional(), NumberRange(min=0, max=600)],
        render_kw={"placeholder": "Auto from content if left blank"},
    )
    status = SelectField(
        "Status",
        choices=[(s.value, s.value.replace("_", " ").title()) for s in ArticleStatus],
        validators=[DataRequired()],
        default=ArticleStatus.DRAFT.value,
    )
    published_at = DateTimeLocalField(
        "Publish date",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    scheduled_at = DateTimeLocalField(
        "Schedule for",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    seo_title = StringField(
        "SEO title",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Defaults to article title"},
    )
    seo_description = TextAreaField(
        "SEO description",
        validators=[Optional(), Length(max=500)],
        render_kw={"rows": 3, "placeholder": "Meta description"},
    )
    canonical_url = StringField(
        "Canonical URL",
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "https://…"},
    )
    categories = MultiCheckboxField(
        "Categories",
        coerce=str,
        validators=[Optional()],
    )
    tags = MultiCheckboxField(
        "Tags",
        coerce=str,
        validators=[Optional()],
    )
    featured = BooleanField("Featured article")
    allow_comments = BooleanField("Allow comments", default=True)
    submit = SubmitField("Save article")

    def validate_slug(self, field) -> None:
        if field.data:
            cleaned = slugify(field.data)
            if not cleaned:
                raise ValidationError("Slug contains no valid characters.")
            field.data = cleaned

    def validate_scheduled_at(self, field) -> None:
        if self.status.data == ArticleStatus.SCHEDULED.value and not field.data:
            raise ValidationError("Scheduled articles require a schedule date/time.")

    def validate_status(self, field) -> None:
        try:
            ArticleStatus(field.data)
        except ValueError as exc:
            raise ValidationError("Invalid status.") from exc
