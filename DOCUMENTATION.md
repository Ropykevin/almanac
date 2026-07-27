# Almanac Africa AI — Application Documentation

Complete product and technical documentation for the Almanac publishing platform.

---

## 1. Product overview

**Almanac Africa AI** is a publishing platform for a journal focused on African artificial intelligence — policy, infrastructure, culture, and the people shaping the field.

It provides:

1. A **public website** where readers discover articles, search, subscribe, comment, like, and share.
2. A **staff admin console** where editors and admins publish content, manage media, moderate comments, run newsletters, and review analytics.
3. **Super Admin** tools for site settings and staff user management.

**Default brand defaults**

| Setting | Default |
|---------|---------|
| Site name | Almanac Africa AI |
| Tagline | Intelligence · Africa · Culture |
| Primary color | `#0f766e` |
| Publication slug | `almanac` |

---

## 2. Primary use cases

### 2.1 Reader (public visitor)

| Use case | How it works |
|----------|----------------|
| Browse the journal | Home page shows a brand-first hero, editable welcome message, and recent posts (latest large + next four in a side list). |
| Read an article | Open `/article/<slug>` for full content, author bio, related reading, reading progress bar. |
| Filter the archive | `/archive` with optional `?category=` / `?tag=` and pagination. |
| Search | `/search?q=` — PostgreSQL full-text search when available; ILIKE fallback otherwise. |
| Subscribe | `/subscribe` — double opt-in email confirmation; then ACTIVE on the list. |
| Unsubscribe | Link in emails or `/unsubscribe` with email / token. |
| Like an article | Heart control on the article; one like per browser visitor (cookie). Toggleable. |
| Share an article | Share menu: X, LinkedIn, Facebook, copy link, native share when available. |
| Comment | Name + email + comment when the article allows comments. Held for moderation before display. |
| Follow via RSS | `/feed.xml` or `/rss.xml`. |

### 2.2 Editor / Admin (staff)

| Use case | How it works |
|----------|----------------|
| Sign in | `/auth/login` — invite-only accounts (no public registration). |
| Write & publish | Create/edit articles with TinyMCE, featured image, categories/tags, SEO fields, schedule or publish. |
| Preview | Article preview before going live. |
| Manage taxonomy | Categories and tags for navigation and filtering. |
| Media library | Upload images, PDFs, documents; reuse in articles via media picker. |
| Moderate comments | Approve, unapprove, or delete reader comments. |
| Manage subscribers | List, search, add, import/export CSV, resend verification. |
| Send newsletters | Build campaign from articles, preview, test send, schedule or send now; track opens/clicks. |
| View analytics | Views, top articles, subscriber growth, newsletter engagement, country hints. |
| Edit site settings | Name, logo, theme color, homepage welcome, footer, contact, social URLs. |

### 2.3 Super Admin

Everything staff can do, plus:

| Use case | How it works |
|----------|----------------|
| Manage staff users | `/admin/users` — create Editors, Admins, Super Admins; edit; activate/deactivate. |
| Bootstrap first user | CLI `flask create-user` (also usable anytime). |

**Guards:** cannot deactivate yourself, demote yourself out of Super Admin, or remove the last active Super Admin.

---

## 3. Roles and permissions

| Role | Access |
|------|--------|
| **EDITOR** | Full staff console: articles, comments, taxonomy, subscribers, newsletters, media, analytics, settings. |
| **ADMIN** | Same staff surface as Editor (today). |
| **SUPER_ADMIN** | All staff areas + **Users** management. |

Decorators live in `app/decorators.py`:

- `@staff_required` — Editor, Admin, Super Admin  
- `@admin_required` — Admin, Super Admin (defined; not currently required on extra routes)  
- `@super_admin_required` — Super Admin only (Users)

Inactive users cannot sign in.

---

## 4. Architecture

### 4.1 Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.13+, Flask 3 |
| ORM / DB | SQLAlchemy 2, Flask-Migrate (Alembic), PostgreSQL |
| Auth | Flask-Login, Werkzeug password hashes, Flask-WTF CSRF |
| Security | Flask-Limiter rate limits, secure cookies (production), upload magic-byte checks |
| Templates | Jinja2 |
| CSS / JS | Tailwind (CDN + project CSS), vanilla JS, TinyMCE, Chart.js |
| Deploy | Gunicorn, Docker / docker-compose |

### 4.2 Application layout

```
laminal/
├── app/
│   ├── __init__.py           # App factory, extensions, context processors
│   ├── config.py             # Development / Testing / Production
│   ├── extensions.py         # db, migrate, login, csrf, limiter
│   ├── cli.py                # flask create-user, send-scheduled-newsletters
│   ├── decorators.py         # Role guards
│   ├── blueprints/
│   │   ├── main/             # Public site + tracking endpoints
│   │   ├── auth/             # Login / logout / password reset
│   │   └── admin/            # Staff console
│   ├── models/               # SQLAlchemy models
│   ├── forms/                # WTForms
│   ├── services/             # Business logic
│   ├── utils/                # Email, activity log, client info
│   ├── templates/            # Public, admin, auth, emails, errors, SEO
│   └── static/               # css/, js/, uploads/
├── migrations/               # Alembic revisions
├── tests/
├── wsgi.py
├── requirements.txt
├── docker-compose.yml
├── schema.dbml               # Canonical data model
├── DOCUMENTATION.md          # This file
└── README.md                 # Quick start
```

### 4.3 Request flow (simplified)

```
Browser → Flask blueprint → service layer → SQLAlchemy → PostgreSQL
                ↓
         Jinja template / JSON / redirect / email
```

Site settings are injected into templates via a context processor (`site`).

---

## 5. Data model (summary)

Approved schema: `schema.dbml` / `laminal.pdf`.

**Enums**

- `user_role`: `SUPER_ADMIN`, `ADMIN`, `EDITOR`
- `article_status`: `DRAFT`, `REVIEW`, `SCHEDULED`, `PUBLISHED`, `ARCHIVED`
- `subscriber_status`: `PENDING`, `ACTIVE`, `UNSUBSCRIBED`, `BOUNCED`
- `newsletter_status`: `DRAFT`, `SCHEDULED`, `SENDING`, `SENT`
- `delivery_status`: `PENDING`, `SENT`, `OPENED`, `CLICKED`, `FAILED`

**Core tables**

| Table | Purpose |
|-------|---------|
| `users` | Staff accounts |
| `publications` / `publication_users` | Workspace + membership |
| `articles` | Content (slug unique per publication) |
| `categories` / `tags` (+ join tables) | Taxonomy |
| `media` | Uploaded files |
| `comments` | Reader comments (`approved` flag) |
| `article_likes` | Likes by `visitor_key` |
| `article_views` | Analytics views |
| `article_revisions` | Edit history snapshots |
| `subscribers` | Newsletter audience |
| `newsletters` / `newsletter_deliveries` | Campaigns + per-recipient tracking |
| `settings` | Key/value site configuration |
| `activity_logs` | Admin activity feed |

---

## 6. Public website

### 6.1 Pages

| URL | Description |
|-----|-------------|
| `/` | Home: hero, welcome blurb, recent posts, newsletter CTA |
| `/archive` | All published articles |
| `/article/<slug>` | Article + engagement |
| `/about` | About the publication |
| `/search` | Search |
| `/subscribe` | Subscribe form + messaging |
| `/unsubscribe` | Leave the list |
| `/sitemap.xml`, `/robots.txt` | SEO |
| `/feed.xml`, `/rss.xml` | RSS |
| `/health` | Health check JSON |

### 6.2 Homepage content blocks

1. **Hero** — site name, featured article (if any), CTA  
2. **Welcome** — editable under Admin → Settings → Homepage (`home_welcome`); hidden if blank  
3. **Recent posts** — latest article large (image on top); up to four more with thumbnail; section hidden if none published  
4. **Newsletter strip** — link to subscribe  

### 6.3 Engagement

- **Comments:** stored with `approved=false` until staff approve; only approved comments appear publicly; gated by article `allow_comments`.  
- **Likes:** `article_likes` unique on `(article_id, visitor_key)`; cookie `liminal_vid`.  
- **Shares:** client-side share URLs + clipboard; no share counter stored.  
- **Views:** recorded on article open for analytics (bots filtered when possible).

### 6.4 SEO

Per article: `seo_title`, `seo_description`, `canonical_url` (blank = auto).  
Global: Open Graph / Twitter cards, JSON-LD, sitemap, robots, RSS.

---

## 7. Admin console (`/admin/`)

Requires login + staff role (except **Users**, Super Admin only).

| Area | Path | Capabilities |
|------|------|----------------|
| Dashboard | `/admin/` | Counts + recent activity |
| Analytics | `/admin/analytics` | Charts for views, subscribers, newsletters (7/30/90 days) |
| Articles | `/admin/articles` | CRUD, publish/archive/draft, preview, TinyMCE uploads |
| Users | `/admin/users` | Super Admin: create/edit/activate staff |
| Comments | `/admin/comments` | Approve / unapprove / delete |
| Categories / Tags | `/admin/categories`, `/admin/tags` | Taxonomy CRUD |
| Subscribers | `/admin/subscribers` | Manage list, CSV import/export, resend verify |
| Newsletters | `/admin/newsletters` | Campaigns, test, schedule, send |
| Media | `/admin/media` | Library + picker API |
| Settings | `/admin/settings` | Branding, homepage welcome, footer, contact, social, color |

---

## 8. Authentication

| Feature | Route |
|---------|--------|
| Login | `GET/POST /auth/login` |
| Logout | `GET/POST /auth/logout` |
| Forgot password | `GET/POST /auth/forgot-password` |
| Reset password | `GET/POST /auth/reset-password/<token>` |

- Passwords hashed with Werkzeug.  
- Rate limits on auth and public forms.  
- If SMTP is not configured, password-reset and verification links are written to the application log.

---

## 9. Newsletters & subscribers

### Subscribers (double opt-in)

1. Reader submits email (and optional name) on `/subscribe`.  
2. Status `PENDING`; verification email with token.  
3. `/subscribe/verify/<token>` → `ACTIVE`.  
4. Unsubscribe via token or form → `UNSUBSCRIBED`.  

### Campaigns

1. Staff create a newsletter (subject, HTML / article selection).  
2. Preview and optional test send.  
3. **Send now** or **schedule**.  
4. CLI or list-page processing: `flask send-scheduled-newsletters`.  
5. Tracking: open pixel `/n/o/<token>`, click `/n/c/<token>` → delivery status `OPENED` / `CLICKED`.

---

## 10. Media & uploads

- Stored under `app/static/uploads/`.  
- Images, PDFs, and allowed documents; size limits and magic-byte validation.  
- TinyMCE and article featured image use the media library / picker.  
- Settings logo upload uses the same media pipeline.

---

## 11. CLI commands

```bash
# Create staff user
flask create-user --email you@example.com --name "Name" --role SUPER_ADMIN
# Roles: SUPER_ADMIN | ADMIN | EDITOR

# Apply migrations
flask db upgrade

# Send due scheduled newsletters
flask send-scheduled-newsletters
```

---

## 12. Environment variables

Copy `.env.example` → `.env`. Important names (never commit secrets):

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Session / CSRF / signed tokens |
| `DATABASE_URL` | PostgreSQL connection (`postgresql+psycopg://...`) |
| `FLASK_ENV` / `FLASK_DEBUG` | Environment mode |
| `LOG_LEVEL` / `LOG_TO_STDOUT` | Logging |
| `RATELIMIT_STORAGE_URI` | Limiter storage (`memory://` or Redis in prod) |
| `PASSWORD_RESET_MAX_AGE` | Reset token lifetime (seconds) |
| `UNSUBSCRIBE_TOKEN_MAX_AGE` | Unsubscribe token lifetime |
| `NEWSLETTER_TRACKING_MAX_AGE` | Tracking token lifetime |
| `MAIL_*` | Optional SMTP |
| `WEB_CONCURRENCY` / `GUNICORN_BIND` | Production server |

---

## 13. Local setup

1. Create venv and `pip install -r requirements.txt`.  
2. Copy `.env.example` to `.env`; set `DATABASE_URL` and `SECRET_KEY`.  
3. Start Postgres (`docker compose up -d db` or local).  
4. `flask db upgrade`  
5. `flask create-user --role SUPER_ADMIN ...`  
6. `python -m flask run` → http://127.0.0.1:5000  

- Public site: `/`  
- Login: `/auth/login`  
- Admin: `/admin/`  

Docker full stack: `docker compose up --build` (see README).

**Migrations of note**

- Base schema: `20260716_0001`  
- Article FTS index (Postgres): `20260716_0013`  
- Article likes: `20260716_0014` — run `flask db upgrade` after pull  

---

## 14. Security notes

- CSRF on all state-changing forms; AJAX likes send `X-CSRFToken`.  
- Staff routes require authentication + role.  
- Public comment/like/subscribe endpoints are rate-limited.  
- Upload allowlists + content sniffing.  
- Production config enables secure cookies; set a strong `SECRET_KEY`.  
- Admin and auth paths are disallowed in `robots.txt`.

---

## 15. Testing

```bash
# Typical pattern (with venv active)
pytest
```

Tests use an isolated configuration (`TestingConfig`); see `tests/` and `app/config.py`.

---

## 16. Operational checklist

| Task | Action |
|------|--------|
| First deploy | Migrate DB, create Super Admin, configure SMTP for real email |
| Content launch | Categories/tags → media → publish articles → set featured |
| Branding | Settings: name, logo, color, welcome, footer, social |
| Audience | Promote `/subscribe`; import CSV if migrating a list |
| Newsletter cadence | Draft → test → schedule; cron `flask send-scheduled-newsletters` |
| Moderation | Review **Comments** regularly |
| Staff onboarding | Super Admin → Users → Add user |

---

## 17. Related files

| File | Role |
|------|------|
| `README.md` | Quick start and milestone notes |
| `schema.dbml` | Canonical schema |
| `laminal.pdf` | Original product / schema source |
| `.env.example` | Environment template |
| `DOCUMENTATION.md` | This document |

---

*Last updated: July 2026 — covers public site, admin console, engagement, newsletters, settings, and Super Admin user management.*
