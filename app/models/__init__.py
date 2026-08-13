"""SQLAlchemy models — import all entities for Flask-Migrate discovery."""

from app.models.activity import ActivityLog
from app.models.article import (
    Article,
    ArticleCategory,
    ArticleLike,
    ArticleRevision,
    ArticleTag,
    ArticleView,
    Comment,
)
from app.models.enums import (
    ROLE_RANK,
    ArticleStatus,
    DeliveryStatus,
    NewsletterStatus,
    ProjectStatus,
    SubscriberStatus,
    UserRole,
)
from app.models.media import Media
from app.models.newsletter import Newsletter, NewsletterDelivery, Subscriber
from app.models.project import Project, ProjectDocument
from app.models.publication import Publication, PublicationUser
from app.models.settings import Setting
from app.models.taxonomy import Category, Tag
from app.models.user import User

__all__ = [
    "ActivityLog",
    "Article",
    "ArticleCategory",
    "ArticleLike",
    "ArticleRevision",
    "ArticleStatus",
    "ArticleTag",
    "ArticleView",
    "Category",
    "Comment",
    "DeliveryStatus",
    "Media",
    "Newsletter",
    "NewsletterDelivery",
    "NewsletterStatus",
    "Project",
    "ProjectDocument",
    "ProjectStatus",
    "Publication",
    "PublicationUser",
    "ROLE_RANK",
    "Setting",
    "Subscriber",
    "SubscriberStatus",
    "Tag",
    "User",
    "UserRole",
]
