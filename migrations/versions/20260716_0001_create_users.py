"""Initial schema from approved DBML (17 tables + 5 enums).

Revision ID: 20260716_0001
Revises:
Create Date: 2026-07-16

If you previously applied an older integer-based users migration, reset the DB:

    flask db downgrade base
    # or drop/recreate the PostgreSQL database, then:
    flask db upgrade
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260716_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role = postgresql.ENUM(
    "SUPER_ADMIN",
    "ADMIN",
    "EDITOR",
    name="user_role",
    create_type=False,
)
article_status = postgresql.ENUM(
    "DRAFT",
    "REVIEW",
    "SCHEDULED",
    "PUBLISHED",
    "ARCHIVED",
    name="article_status",
    create_type=False,
)
subscriber_status = postgresql.ENUM(
    "PENDING",
    "ACTIVE",
    "UNSUBSCRIBED",
    "BOUNCED",
    name="subscriber_status",
    create_type=False,
)
newsletter_status = postgresql.ENUM(
    "DRAFT",
    "SCHEDULED",
    "SENDING",
    "SENT",
    name="newsletter_status",
    create_type=False,
)
delivery_status = postgresql.ENUM(
    "PENDING",
    "SENT",
    "OPENED",
    "CLICKED",
    "FAILED",
    name="delivery_status",
    create_type=False,
)


def upgrade():
    bind = op.get_bind()

    # Clear legacy Milestone-2 schema (integer users / lowercase roles) if present.
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TYPE IF EXISTS user_role CASCADE")

    for enum_type in (
        postgresql.ENUM("SUPER_ADMIN", "ADMIN", "EDITOR", name="user_role"),
        postgresql.ENUM(
            "DRAFT",
            "REVIEW",
            "SCHEDULED",
            "PUBLISHED",
            "ARCHIVED",
            name="article_status",
        ),
        postgresql.ENUM(
            "PENDING",
            "ACTIVE",
            "UNSUBSCRIBED",
            "BOUNCED",
            name="subscriber_status",
        ),
        postgresql.ENUM(
            "DRAFT",
            "SCHEDULED",
            "SENDING",
            "SENT",
            name="newsletter_status",
        ),
        postgresql.ENUM(
            "PENDING",
            "SENT",
            "OPENED",
            "CLICKED",
            "FAILED",
            name="delivery_status",
        ),
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", user_role, server_default="EDITOR", nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_id", sa.Uuid(), nullable=True),
        sa.Column("banner_id", sa.Uuid(), nullable=True),
        sa.Column("primary_color", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_publications_slug"), "publications", ["slug"], unique=True)

    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_uploaded_by"), "media", ["uploaded_by"], unique=False)

    op.create_foreign_key(
        "fk_users_avatar_id",
        "users",
        "media",
        ["avatar_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_publications_logo_id",
        "publications",
        "media",
        ["logo_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_publications_banner_id",
        "publications",
        "media",
        ["banner_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "publication_users",
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("publication_id", "user_id"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "slug",
            name="uq_categories_publication_slug",
        ),
    )
    op.create_index(
        op.f("ix_categories_publication_id"),
        "categories",
        ["publication_id"],
        unique=False,
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", "slug", name="uq_tags_publication_slug"),
    )
    op.create_index(op.f("ix_tags_publication_id"), "tags", ["publication_id"], unique=False)

    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("featured_image", sa.Uuid(), nullable=True),
        sa.Column("reading_time", sa.Integer(), nullable=True),
        sa.Column("featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "allow_comments",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("status", article_status, server_default="DRAFT", nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["featured_image"], ["media.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "slug",
            name="uq_articles_publication_slug",
        ),
    )
    op.create_index(op.f("ix_articles_author_id"), "articles", ["author_id"], unique=False)
    op.create_index(
        op.f("ix_articles_publication_id"),
        "articles",
        ["publication_id"],
        unique=False,
    )
    op.create_index(op.f("ix_articles_published_at"), "articles", ["published_at"], unique=False)
    op.create_index(op.f("ix_articles_status"), "articles", ["status"], unique=False)

    op.create_table(
        "article_tags",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("article_id", "tag_id"),
    )

    op.create_table(
        "article_categories",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("article_id", "category_id"),
    )

    op.create_table(
        "subscribers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("verification_token", sa.Text(), nullable=True),
        sa.Column(
            "status",
            subscriber_status,
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "email",
            name="uq_subscribers_publication_email",
        ),
    )
    op.create_index(
        op.f("ix_subscribers_publication_id"),
        "subscribers",
        ["publication_id"],
        unique=False,
    )

    op.create_table(
        "newsletters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column(
            "status",
            newsletter_status,
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_newsletters_publication_id"),
        "newsletters",
        ["publication_id"],
        unique=False,
    )
    op.create_index(op.f("ix_newsletters_status"), "newsletters", ["status"], unique=False)

    op.create_table(
        "newsletter_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("newsletter_id", sa.Uuid(), nullable=False),
        sa.Column("subscriber_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            delivery_status,
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["newsletter_id"], ["newsletters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"], ["subscribers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "newsletter_id",
            "subscriber_id",
            name="uq_newsletter_deliveries_recipient",
        ),
    )
    op.create_index(
        op.f("ix_newsletter_deliveries_newsletter_id"),
        "newsletter_deliveries",
        ["newsletter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_newsletter_deliveries_subscriber_id"),
        "newsletter_deliveries",
        ["subscriber_id"],
        unique=False,
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comments_article_id"), "comments", ["article_id"], unique=False)
    op.create_index(op.f("ix_comments_approved"), "comments", ["approved"], unique=False)

    op.create_table(
        "article_views",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("browser", sa.String(length=100), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_article_views_article_id"),
        "article_views",
        ["article_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_article_views_viewed_at"),
        "article_views",
        ["viewed_at"],
        unique=False,
    )

    op.create_table(
        "article_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("editor_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "revision_number",
            name="uq_article_revisions_number",
        ),
    )
    op.create_index(
        op.f("ix_article_revisions_article_id"),
        "article_revisions",
        ["article_id"],
        unique=False,
    )

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_activity_logs_user_id"),
        "activity_logs",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("setting_key", sa.String(length=150), nullable=False),
        sa.Column("setting_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["publication_id"], ["publications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "setting_key",
            name="uq_settings_publication_key",
        ),
    )
    op.create_index(
        op.f("ix_settings_publication_id"),
        "settings",
        ["publication_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_settings_publication_id"), table_name="settings")
    op.drop_table("settings")
    op.drop_index(op.f("ix_activity_logs_user_id"), table_name="activity_logs")
    op.drop_table("activity_logs")
    op.drop_index(op.f("ix_article_revisions_article_id"), table_name="article_revisions")
    op.drop_table("article_revisions")
    op.drop_index(op.f("ix_article_views_viewed_at"), table_name="article_views")
    op.drop_index(op.f("ix_article_views_article_id"), table_name="article_views")
    op.drop_table("article_views")
    op.drop_index(op.f("ix_comments_approved"), table_name="comments")
    op.drop_index(op.f("ix_comments_article_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(
        op.f("ix_newsletter_deliveries_subscriber_id"),
        table_name="newsletter_deliveries",
    )
    op.drop_index(
        op.f("ix_newsletter_deliveries_newsletter_id"),
        table_name="newsletter_deliveries",
    )
    op.drop_table("newsletter_deliveries")
    op.drop_index(op.f("ix_newsletters_status"), table_name="newsletters")
    op.drop_index(op.f("ix_newsletters_publication_id"), table_name="newsletters")
    op.drop_table("newsletters")
    op.drop_index(op.f("ix_subscribers_publication_id"), table_name="subscribers")
    op.drop_table("subscribers")
    op.drop_table("article_categories")
    op.drop_table("article_tags")
    op.drop_index(op.f("ix_articles_status"), table_name="articles")
    op.drop_index(op.f("ix_articles_published_at"), table_name="articles")
    op.drop_index(op.f("ix_articles_publication_id"), table_name="articles")
    op.drop_index(op.f("ix_articles_author_id"), table_name="articles")
    op.drop_table("articles")
    op.drop_index(op.f("ix_tags_publication_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(op.f("ix_categories_publication_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_table("publication_users")
    op.drop_constraint("fk_publications_banner_id", "publications", type_="foreignkey")
    op.drop_constraint("fk_publications_logo_id", "publications", type_="foreignkey")
    op.drop_constraint("fk_users_avatar_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_media_uploaded_by"), table_name="media")
    op.drop_table("media")
    op.drop_index(op.f("ix_publications_slug"), table_name="publications")
    op.drop_table("publications")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    for name in (
        "delivery_status",
        "newsletter_status",
        "subscriber_status",
        "article_status",
        "user_role",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
