"""Admin project forms."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.forms.media import ALL_EXTS
from app.models.enums import ProjectStatus
from app.utils.slug import slugify


class ProjectForm(FlaskForm):
    title = StringField(
        "Title",
        validators=[DataRequired(), Length(max=255)],
    )
    slug = StringField(
        "Slug",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Leave blank to generate from title"},
    )
    description = TextAreaField(
        "Short description",
        validators=[DataRequired(), Length(max=4000)],
        render_kw={"rows": 3},
    )
    body = TextAreaField(
        "Full write-up",
        validators=[Optional(), Length(max=50000)],
        render_kw={"rows": 10, "placeholder": "Optional longer content for the project page"},
    )
    status = SelectField(
        "Status",
        choices=[
            (ProjectStatus.LIVE.value, "Live"),
            (ProjectStatus.COMING_SOON.value, "Coming soon"),
        ],
        validators=[DataRequired()],
        default=ProjectStatus.LIVE.value,
    )
    sort_order = IntegerField(
        "Sort order",
        validators=[Optional(), NumberRange(min=0, max=9999)],
        default=0,
        render_kw={"placeholder": "0 = first"},
    )
    is_published = BooleanField("Show on public site", default=True)
    submit = SubmitField("Save project")

    def validate_slug(self, field):
        if field.data:
            field.data = slugify(field.data)


class ProjectDocumentForm(FlaskForm):
    file = FileField(
        "Document",
        validators=[
            FileRequired(),
            FileAllowed(ALL_EXTS, "Images, PDFs, or documents only."),
        ],
    )
    title = StringField(
        "Display title",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Optional — defaults to the file name"},
    )
    submit = SubmitField("Upload document")
