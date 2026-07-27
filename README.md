# Almanac Africa AI

Production-ready publishing platform (Milestones 1–14).

Stack: **Python 3.13**, **Flask**, **SQLAlchemy**, **Flask-Migrate**, **Flask-Login**, **Flask-WTF**, **PostgreSQL**, **Tailwind CSS**, **Jinja2**, **Gunicorn**, **Docker**.

Milestone 2 adds authentication: login/logout, remember me, password reset, roles, and a protected dashboard.

## Project layout

```
laminal/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Development / Testing / Production
│   ├── extensions.py        # db, migrate, login, csrf
│   ├── logging_config.py
│   ├── models/              # User + roles
│   ├── forms/               # WTForms (auth)
│   ├── decorators.py        # Role guards
│   ├── blueprints/
│   │   ├── main/            # Public pages
│   │   ├── auth/            # Login / logout / password reset
│   │   └── admin/           # Protected dashboard
│   ├── templates/
│   └── static/              # CSS (Tailwind), JS
├── migrations/              # Flask-Migrate / Alembic
├── tests/
├── logs/
├── instance/
├── wsgi.py                  # Flask / Gunicorn entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── package.json             # Tailwind build scripts
└── .env.example
```

## Prerequisites

- Python 3.13+
- PostgreSQL 14+ (or Docker)
- Node.js 18+ (optional, for rebuilding Tailwind CSS)

## Quick start (local)

1. **Clone and enter the project**

   ```bash
   cd laminal
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS / Linux
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure environment**

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # macOS / Linux
   ```

   Edit `.env` so `DATABASE_URL` matches your PostgreSQL instance.

4. **Start PostgreSQL** (example with Docker Compose database only)

   ```bash
   docker compose up -d db
   ```

5. **Run database migrations**

   ```bash
   flask db upgrade
   ```

6. **Create a staff user**

   ```bash
   flask create-user --email admin@example.com --name "Super Admin" --role SUPER_ADMIN
   ```

   Roles: `SUPER_ADMIN`, `ADMIN`, `EDITOR`.

7. **Start the development server**

   ```bash
   python -m flask run
   ```

   Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Sign in at `/auth/login`. Dashboard: `/admin/` (authenticated staff only).

`.flaskenv` sets `FLASK_APP=wsgi.py` so `flask run` works without extra flags.

## Authentication

| Feature            | Route / mechanism                                      |
|--------------------|--------------------------------------------------------|
| Login              | `POST /auth/login` (Remember me supported)             |
| Logout             | `POST /auth/logout`                                    |
| Forgot password    | `POST /auth/forgot-password`                           |
| Reset password     | `POST /auth/reset-password/<token>`                    |
| Password hashing   | Werkzeug `generate_password_hash` / `check_password_hash` |
| Session auth       | Flask-Login                                            |
| Dashboard guard    | `@login_required` + `@staff_required`                  |

Roles: **Super Admin**, **Admin**, **Editor** (`SUPER_ADMIN`, `ADMIN`, `EDITOR`). Use `@admin_required`, `@super_admin_required`, `@staff_required`, or `@role_required(...)` from `app/decorators.py`.

Without SMTP configured, password-reset links are written to the application log (see terminal output after “Forgot password”).

## Database models (Milestone 3)

SQLAlchemy models match the approved DBML in `laminal.pdf` (17 tables, 5 enums, UUID primary keys).

```bash
# Apply schema to PostgreSQL
flask db upgrade

# Create a staff user afterward
flask create-user --email admin@example.com --name "Super Admin" --role SUPER_ADMIN
```

If you previously applied the Milestone 2 integer `users` table, reset first:

```bash
flask db downgrade base
flask db upgrade
```

Or drop/recreate the PostgreSQL database, then run `flask db upgrade`.

## Admin dashboard (Milestone 4)

Authenticated staff can open `/admin/` for:

- Sidebar + top navigation + breadcrumbs
- Metric cards: total / draft / published articles, active subscribers, newsletter campaigns
- Recent activity feed from `activity_logs`

```bash
python -m flask run
# sign in, then visit http://127.0.0.1:5000/admin/
```

## Article management (Milestone 5)

Staff routes under `/admin/articles`:

| Action | Path |
|--------|------|
| List / filter | `GET /admin/articles?status=DRAFT` |
| Create | `GET/POST /admin/articles/new` |
| Edit | `GET/POST /admin/articles/<id>/edit` |
| Delete | `POST /admin/articles/<id>/delete` |
| Publish | `POST /admin/articles/<id>/publish` |
| Archive | `POST /admin/articles/<id>/archive` |
| Preview | `GET /admin/articles/<id>/preview` |

Slugs auto-generate from the title (unique per publication). Reading time is estimated from content when left blank. Featured images upload to `app/static/uploads/`.

## Rich text editor (Milestone 6)

Article content uses **TinyMCE** with:

- Headings, lists, tables, block quotes, code samples, links
- Images (picker + **drag-and-drop** upload to `/admin/articles/editor/upload`)
- Video embeds (YouTube / Vimeo)
- Footnotes (semantic `aside.footnotes` + `role="doc-*"` markup)
- Server-side HTML sanitization via **Bleach** (scripts/handlers stripped; iframe hosts allowlisted)

```bash
pip install -r requirements.txt
```

## Categories & tags (Milestone 7)

Staff can manage taxonomy at:

- `/admin/categories` — category CRUD  
- `/admin/tags` — tag CRUD  

Articles support **many-to-many** relationships via checkbox multi-select on create/edit. Slugs auto-generate and stay unique per publication.

## Public website (Milestone 8)

Premium publication pages (published articles only):

| Page | Path |
|------|------|
| Home | `/` |
| Archive | `/archive` |
| Article | `/article/<slug>` |
| About | `/about` |
| Search | `/search?q=` |
| Subscribe | `/subscribe` |
| Verify email | `/subscribe/verify/<token>` |
| Unsubscribe | `/unsubscribe` or `/unsubscribe/<token>` |

Includes reading time, author section, related articles, responsive navigation, and publication typography.

## Subscribers (Milestone 9)

Double opt-in newsletter subscriptions with admin management:

- Public subscribe creates a **PENDING** subscriber and sends a verification email (logged when SMTP is unset)
- Email confirmation activates the subscription (**ACTIVE**)
- Unsubscribe via signed token link or email form (**UNSUBSCRIBED**)
- Duplicate emails per publication are rejected / resumed (no second row)
- Admin: `/admin/subscribers` — list/filter/search, add/edit/delete, resend verification, CSV import/export

Statuses: `PENDING`, `ACTIVE`, `UNSUBSCRIBED`, `BOUNCED`.

## Newsletters (Milestone 10)

Campaign workflow at `/admin/newsletters`:

- Create a campaign and optionally select a published article
- Preview responsive HTML email (`emails/newsletter.html`)
- Send a test email
- Schedule for later, or send immediately to all **ACTIVE** subscribers
- Per-recipient delivery records with open pixel (`/n/o/<token>`) and click redirect (`/n/c/<token>`)

Tracked metrics: **Sent**, **Delivered**, **Opened**, **Clicked**, **Failed**.

Due schedules are processed when opening the newsletters list, or via:

```bash
flask send-scheduled-newsletters
```

## Media library (Milestone 11)

Admin media manager at `/admin/media`:

- Upload images, PDFs, and documents (max 16&nbsp;MB)
- Preview, replace (keeps the same media ID), delete
- Search + type filters + pagination
- Article editor integration: drag-and-drop image upload, **Media library** button, and TinyMCE file picker

## Analytics (Milestone 12)

Admin analytics at `/admin/analytics` (7 / 30 / 90 day ranges):

- Article views (daily chart) — recorded on public article pages into `article_views`
- Subscriber growth
- Newsletter performance (open/click rates + campaign table)
- Most read articles
- Countries (from CDN/geo headers when present)
- Reading time distribution for published articles

Charts are rendered with Chart.js.

## SEO & search (Milestone 13)

- **Full-text search** on `/search` — PostgreSQL `tsvector`/`ts_rank` (with ILIKE fallback); SQLite uses multi-token ILIKE
- **Sitemap** — `/sitemap.xml`
- **robots.txt** — `/robots.txt` (disallows `/admin/` and `/auth/`)
- **RSS** — `/feed.xml` and `/rss.xml`
- **Article SEO** — `seo_title`, `seo_description`, `canonical_url`, Open Graph, Twitter Cards, JSON-LD `NewsArticle`

Apply the FTS index migration on Postgres:

```bash
flask db upgrade
```

## Settings & security (Milestone 14)

**Settings** at `/admin/settings`:

- Site name, tagline, description
- Logo upload + primary theme color
- Footer text / copyright
- Contact details
- Social links

Values render on the public nav and footer.

**Security hardening:**

- CSRF protection (Flask-WTF) on all forms / AJAX uploads
- Upload allowlists + magic-byte checks for images/PDFs
- Rate limits on login, password reset, subscribe, and uploads (Flask-Limiter)
- Secure / HttpOnly / SameSite cookies (`Secure` forced in production)
- Error pages for 400 / 403 / 404 / 413 / 429 / 500 with logging on failures


## Configuration

| Class               | When used                          |
|---------------------|------------------------------------|
| `DevelopmentConfig` | Default / `FLASK_CONFIG=development` |
| `TestingConfig`     | `FLASK_CONFIG=testing` / pytest    |
| `ProductionConfig`  | `FLASK_CONFIG=production`          |

Key environment variables (see `.env.example`):

| Variable        | Purpose                                      |
|-----------------|----------------------------------------------|
| `SECRET_KEY`    | Session / CSRF signing                       |
| `DATABASE_URL`  | SQLAlchemy URI (`postgresql+psycopg://...`)  |
| `FLASK_CONFIG`  | `development` \| `testing` \| `production`   |
| `LOG_LEVEL`     | Logging verbosity                            |
| `LOG_TO_STDOUT` | `1` to also log to the console               |

## Tailwind CSS

A compiled stylesheet ships at `app/static/css/main.css` so the app runs without Node.

To rebuild from `app/static/css/input.css`:

```bash
npm install
npm run build:css
# or: npm run watch:css
```

## Docker (full stack)

See **[DEPLOY.md](DEPLOY.md)** for the VPS path: Docker Compose + **nginx** + Let’s Encrypt.

```bash
copy .env.example .env
# Set SECRET_KEY and POSTGRES_PASSWORD, then:
docker compose up --build -d
```

- App (Gunicorn): `127.0.0.1:8000` (proxied by nginx on 80/443)
- Health: `curl http://127.0.0.1:8000/health`
- nginx configs: `deploy/nginx/`
- Migrations run automatically on container start
- Uploads persist in the `media_uploads` volume

Create the first admin:

```bash
docker compose exec web flask create-user --role SUPER_ADMIN
```

Production serves via **Gunicorn** (`wsgi:app`) behind **nginx**.

## Flask-Migrate

```bash
flask db migrate -m "describe change"
flask db upgrade
flask db downgrade
```

Models should live under `app/models/` and be imported from `app/models/__init__.py` so autogenerate can see them.

## Blueprints

| Blueprint | Prefix   | Role                          |
|-----------|----------|-------------------------------|
| `main`    | `/`      | Public pages, health check    |
| `auth`    | `/auth`  | Login / register / logout stubs |
| `admin`   | `/admin` | Admin dashboard stub          |

## License

Proprietary — all rights reserved.
