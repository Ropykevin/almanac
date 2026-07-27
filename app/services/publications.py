"""Publication helpers for multi-tenant content."""

from __future__ import annotations

from app.extensions import db
from app.models import Publication


_LEGACY_PUBLICATION_NAMES = {"Liminal AI Africa", "Laminal AI Africa"}
_DEFAULT_PUBLICATION_NAME = "Almanac Africa AI"


def get_or_create_default_publication() -> Publication:
    """Return the first publication, creating a default workspace if needed."""
    publication = db.session.query(Publication).order_by(Publication.created_at.asc()).first()
    if publication is not None:
        if publication.name in _LEGACY_PUBLICATION_NAMES:
            publication.name = _DEFAULT_PUBLICATION_NAME
            db.session.commit()
        return publication

    publication = Publication(
        name=_DEFAULT_PUBLICATION_NAME,
        slug="almanac",
        description="Default publication workspace",
        primary_color="#0f766e",
    )
    db.session.add(publication)
    db.session.commit()
    return publication
