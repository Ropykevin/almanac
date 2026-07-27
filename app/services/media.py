"""Media library: upload, list, replace, delete, search, pagination."""

from __future__ import annotations

import math
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from flask import current_app, url_for
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Media, User
from app.utils.activity import log_activity
from app.utils.slug import slugify

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_PDF_MIMES = {"application/pdf"}

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".txt",
    ".csv",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
ALLOWED_DOCUMENT_MIMES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "application/rtf",
    "text/rtf",
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = (
    ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS
)


class MediaUploadError(ValueError):
    """Raised when an upload fails validation."""


@dataclass
class MediaPage:
    items: list[Media]
    page: int
    per_page: int
    total: int
    pages: int
    q: str
    kind: str

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def media_kind(media: Media) -> str:
    mime = (media.mime_type or "").lower()
    suffix = Path(media.file_name or "").suffix.lower()
    if mime.startswith("image/") or suffix in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    if mime == "application/pdf" or suffix == ".pdf":
        return "pdf"
    return "document"


def media_public_url(media: Media) -> str:
    return url_for("static", filename=media.path)


def get_media(media_id: uuid.UUID) -> Media | None:
    stmt = (
        select(Media)
        .options(joinedload(Media.uploader))
        .where(Media.id == media_id)
    )
    return db.session.scalars(stmt).unique().first()


def _upload_root() -> Path:
    root = Path(current_app.config["UPLOAD_FOLDER"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _absolute_path(media: Media) -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"]) / Path(media.path).name


def _sniff_header(file: FileStorage, size: int = 16) -> bytes:
    """Read file header without consuming the stream for later save()."""
    stream = file.stream
    position = stream.tell() if hasattr(stream, "tell") else None
    header = stream.read(size) or b""
    if hasattr(stream, "seek") and position is not None:
        stream.seek(position)
    elif hasattr(file, "seek"):
        try:
            file.seek(0)
        except Exception:  # noqa: BLE001
            pass
    return header


def _validate_magic(suffix: str, header: bytes) -> None:
    """Reject spoofed image/PDF extensions when magic bytes do not match."""
    if suffix in {".jpg", ".jpeg"}:
        if not header.startswith(b"\xff\xd8\xff"):
            raise MediaUploadError("File content is not a valid JPEG image.")
    elif suffix == ".png":
        if not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise MediaUploadError("File content is not a valid PNG image.")
    elif suffix == ".gif":
        if not (header.startswith(b"GIF87a") or header.startswith(b"GIF89a")):
            raise MediaUploadError("File content is not a valid GIF image.")
    elif suffix == ".webp":
        if not (header.startswith(b"RIFF") and b"WEBP" in header[:16]):
            raise MediaUploadError("File content is not a valid WebP image.")
    elif suffix == ".pdf":
        if not header.startswith(b"%PDF"):
            raise MediaUploadError("File content is not a valid PDF.")


def _validate_file(
    file: FileStorage,
    *,
    images_only: bool = False,
) -> tuple[str, str, str]:
    if not file or not file.filename:
        raise MediaUploadError("No file provided.")

    original = secure_filename(file.filename)
    if not original:
        raise MediaUploadError("Invalid file name.")

    suffix = Path(original).suffix.lower()
    mime = (file.mimetype or "").lower() or (mimetypes.guess_type(original)[0] or "")
    header = _sniff_header(file)

    if images_only:
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise MediaUploadError("Unsupported image type. Use JPG, PNG, GIF, or WebP.")
        if mime and mime not in ALLOWED_IMAGE_MIMES:
            raise MediaUploadError("Unsupported image MIME type.")
        _validate_magic(suffix, header)
        return original, suffix, mime or "application/octet-stream"

    if suffix not in ALLOWED_EXTENSIONS:
        raise MediaUploadError(
            "Unsupported file type. Use images, PDF, or common documents."
        )

    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        if mime and mime not in ALLOWED_IMAGE_MIMES and mime != "application/octet-stream":
            raise MediaUploadError("Unsupported image MIME type.")
        _validate_magic(suffix, header)
    elif suffix in ALLOWED_PDF_EXTENSIONS:
        if mime and mime not in ALLOWED_PDF_MIMES and mime != "application/octet-stream":
            raise MediaUploadError("Unsupported PDF MIME type.")
        _validate_magic(suffix, header)
    elif suffix in ALLOWED_DOCUMENT_EXTENSIONS:
        if mime and mime not in ALLOWED_DOCUMENT_MIMES:
            # Browsers often send odd MIME types for Office files
            if not mime.startswith("application/") and not mime.startswith("text/"):
                raise MediaUploadError("Unsupported document MIME type.")

    return original, suffix, mime or "application/octet-stream"


def _stored_name(original: str, suffix: str) -> str:
    stem = Path(original).stem or "file"
    return f"{uuid.uuid4().hex}_{slugify(stem)[:40]}{suffix}"


def save_upload(
    file: FileStorage,
    uploader: User,
    *,
    alt_text: str | None = None,
    images_only: bool = False,
) -> Media:
    """Persist a file to disk and create a Media row."""
    original, suffix, mime = _validate_file(file, images_only=images_only)
    upload_root = _upload_root()
    stored_name = _stored_name(original, suffix)
    destination = upload_root / stored_name
    file.save(destination)

    stem = Path(original).stem or "file"
    media = Media(
        uploaded_by=uploader.id,
        file_name=stored_name,
        original_name=original,
        mime_type=mime,
        size=destination.stat().st_size,
        path=f"uploads/{stored_name}",
        alt_text=(alt_text or "").strip() or stem.replace("-", " ").replace("_", " "),
    )
    db.session.add(media)
    log_activity("media.uploaded", f"Uploaded {original}")
    db.session.flush()
    return media


def save_image_upload(
    file: FileStorage,
    uploader: User,
    *,
    alt_text: str | None = None,
) -> Media:
    """Persist an image only (article editor / featured image)."""
    return save_upload(file, uploader, alt_text=alt_text, images_only=True)


def replace_media_file(
    media: Media,
    file: FileStorage,
    *,
    images_only: bool = False,
) -> Media:
    """Replace the binary on disk; keep the Media row id."""
    original, suffix, mime = _validate_file(file, images_only=images_only)
    upload_root = _upload_root()
    stored_name = _stored_name(original, suffix)
    destination = upload_root / stored_name
    file.save(destination)

    old_path = _absolute_path(media)
    media.file_name = stored_name
    media.original_name = original
    media.mime_type = mime
    media.size = destination.stat().st_size
    media.path = f"uploads/{stored_name}"

    if old_path.exists() and old_path.resolve() != destination.resolve():
        try:
            old_path.unlink()
        except OSError:
            current_app.logger.warning("Could not remove old media file %s", old_path)

    log_activity("media.replaced", f"Replaced {media.original_name}")
    db.session.flush()
    return media


def update_media_meta(media: Media, *, alt_text: str | None, commit: bool = True) -> Media:
    media.alt_text = (alt_text or "").strip() or None
    log_activity("media.updated", f"Updated metadata for {media.original_name}")
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return media


def delete_media(media: Media) -> None:
    """Delete media row and file; clear FK references first."""
    # Clear optional references so delete is not blocked
    for article in list(media.featured_in_articles):
        article.featured_image = None
    for publication in list(media.publication_logos):
        publication.logo_id = None
    for publication in list(media.publication_banners):
        publication.banner_id = None

    # User avatars (no backref on Media)
    users = db.session.scalars(
        select(User).where(User.avatar_id == media.id)
    ).all()
    for user in users:
        user.avatar_id = None

    disk_path = _absolute_path(media)
    name = media.original_name
    log_activity("media.deleted", f"Deleted {name}")
    db.session.delete(media)
    db.session.commit()

    if disk_path.exists():
        try:
            disk_path.unlink()
        except OSError:
            current_app.logger.warning("Could not remove media file %s", disk_path)


def list_media(
    *,
    q: str | None = None,
    kind: str | None = None,
    page: int = 1,
    per_page: int = 24,
) -> MediaPage:
    page = max(1, page)
    per_page = min(max(1, per_page), 96)

    stmt = select(Media).options(joinedload(Media.uploader))
    count_stmt = select(func.count()).select_from(Media)

    if q:
        pattern = f"%{q.strip()}%"
        filt = or_(
            Media.original_name.ilike(pattern),
            Media.file_name.ilike(pattern),
            Media.alt_text.ilike(pattern),
            Media.mime_type.ilike(pattern),
        )
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)

    kind = (kind or "all").lower()
    if kind == "image":
        image_filt = or_(
            Media.mime_type.ilike("image/%"),
            Media.file_name.ilike("%.jpg"),
            Media.file_name.ilike("%.jpeg"),
            Media.file_name.ilike("%.png"),
            Media.file_name.ilike("%.gif"),
            Media.file_name.ilike("%.webp"),
        )
        stmt = stmt.where(image_filt)
        count_stmt = count_stmt.where(image_filt)
    elif kind == "pdf":
        pdf_filt = or_(
            Media.mime_type == "application/pdf",
            Media.file_name.ilike("%.pdf"),
        )
        stmt = stmt.where(pdf_filt)
        count_stmt = count_stmt.where(pdf_filt)
    elif kind == "document":
        doc_filt = or_(
            *[Media.file_name.ilike(f"%{ext}") for ext in ALLOWED_DOCUMENT_EXTENSIONS]
        )
        # Exclude images and PDFs explicitly when matching octet-stream docs
        stmt = stmt.where(doc_filt).where(
            ~Media.mime_type.ilike("image/%"),
            Media.mime_type != "application/pdf",
        )
        count_stmt = count_stmt.where(doc_filt).where(
            ~Media.mime_type.ilike("image/%"),
            Media.mime_type != "application/pdf",
        )
    else:
        kind = "all"

    total = int(db.session.scalar(count_stmt) or 0)
    pages = max(1, math.ceil(total / per_page)) if total else 1
    if page > pages:
        page = pages

    items = list(
        db.session.scalars(
            stmt.order_by(Media.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .unique()
        .all()
    )
    return MediaPage(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        q=q or "",
        kind=kind,
    )


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"
