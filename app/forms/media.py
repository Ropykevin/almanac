"""Media library forms."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import StringField, SubmitField
from wtforms.validators import Length, Optional

IMAGE_EXTS = ["jpg", "jpeg", "png", "gif", "webp"]
PDF_EXTS = ["pdf"]
DOC_EXTS = [
    "doc",
    "docx",
    "odt",
    "rtf",
    "txt",
    "csv",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
]
ALL_EXTS = IMAGE_EXTS + PDF_EXTS + DOC_EXTS


class MediaUploadForm(FlaskForm):
    file = FileField(
        "File",
        validators=[
            FileRequired(),
            FileAllowed(ALL_EXTS, "Images, PDFs, or documents only."),
        ],
    )
    alt_text = StringField(
        "Alt text / description",
        validators=[Optional(), Length(max=500)],
    )
    submit = SubmitField("Upload")


class MediaEditForm(FlaskForm):
    alt_text = StringField(
        "Alt text / description",
        validators=[Optional(), Length(max=500)],
    )
    file = FileField(
        "Replace file",
        validators=[
            Optional(),
            FileAllowed(ALL_EXTS, "Images, PDFs, or documents only."),
        ],
    )
    submit = SubmitField("Save changes")
