# APTRANSCO Transmission Dataset Collection Portal

A Django web portal that centralizes APTRANSCO transmission-line inspection
images (drone + field) so the data collected for **AI-based transmission line
inspection** is organized, searchable, **deduplicated**, and ready for model
training (YOLO, segmentation, etc.).

> Full design rationale and decision log live in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## What it does

- **Imports** the APTRANSCO transmission-line master data from CSV (1,286 lines).
- **Collects** inspection images through a single per-location upload form, with
  a data-driven Component/Defect taxonomy (no hardcoded categories).
- **Organizes** every image on disk under
  `media/<line>/<location>/<Category>/<SubCategory>/` automatically.
- **Deduplicates** uploads by content hash, so the same photo is never stored twice.
- **Reviews** inspections through a Draft → Submitted → Approved/Rejected lifecycle.
- **Exports** Approved-only, per-category ZIP datasets plus CSV/Excel metadata.

Regular users and staff get **separate areas** — collectors only see upload /
"My Inspections"; staff get the dashboard, review queue, and export tools.

---

## Tech stack

| Layer    | Technology                                              |
|----------|---------------------------------------------------------|
| Backend  | Python, Django 6.0                                      |
| Database | PostgreSQL (`psycopg2-binary`)                          |
| Frontend | HTML, Bootstrap 5, vanilla JS                           |
| Imaging  | Pillow                                                  |
| Import   | pandas / numpy                                          |
| Export   | openpyxl (Excel), CSV, zipfile                          |
| Static   | WhiteNoise (production)                                 |

---

## Quick start (development)

```bash
# 1. Create & activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment (optional in dev — defaults work out of the box)
cp .env.example .env        # then edit DB password etc.

# 4. Create the PostgreSQL database (once)
#    createdb data_portal   # or via pgAdmin / psql

# 5. Apply migrations
python manage.py migrate

# 6. Seed the Component/Defect taxonomy (idempotent)
python manage.py seed_masterdata

# 7. Import the transmission-line master data
python manage.py import_transmission_data transmission_data.csv

# 8. Create an admin user
python manage.py createsuperuser

# 9. Run the dev server
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>. Log in; staff land on the admin dashboard,
regular users on the upload page.

---

## Configuration

All configuration is environment-driven — see [.env.example](.env.example) for
the full list. The most important variables:

| Variable                      | Purpose                                              |
|-------------------------------|------------------------------------------------------|
| `DJANGO_DEBUG`                | `False` in production (activates security hardening). |
| `DJANGO_SECRET_KEY`           | **Required** when `DEBUG=False`.                     |
| `DJANGO_ALLOWED_HOSTS`        | Comma-separated hostnames (required in production).  |
| `DJANGO_DB_*`                 | PostgreSQL name/user/password/host/port.             |
| `DJANGO_MEDIA_ROOT`           | Where uploaded images are stored.                    |
| `DJANGO_TIME_ZONE`            | Defaults to `Asia/Kolkata`.                          |

In development, with `DEBUG=True`, a deterministic insecure secret key is used so
no setup is needed. With `DEBUG=False` the app refuses to start without a real
`DJANGO_SECRET_KEY`.

---

## Management commands

| Command                                         | What it does                                  |
|-------------------------------------------------|-----------------------------------------------|
| `seed_masterdata`                               | Seed/refresh the Component/Defect taxonomy.   |
| `import_transmission_data <csv>`                | Import transmission lines from the master CSV. |
| `backfill_checksums`                            | Compute content hashes for pre-existing images. |
| `find_duplicate_images`                         | Report images that share identical content.   |

---

## Running the tests

```bash
python manage.py test
```

The suite covers path/dedup utilities, the upload flow (including duplicate
rejection), access control, the review lifecycle, and dataset export.

---

## Deployment (Milestone 7)

1. Set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
   and `DJANGO_CSRF_TRUSTED_ORIGINS` in the server environment.
2. `pip install -r requirements.txt` (installs WhiteNoise for static serving).
3. `python manage.py collectstatic --noinput`
4. `python manage.py migrate`
5. Serve via a WSGI server behind TLS, e.g.
   - Linux: `gunicorn config.wsgi:application`
   - Windows: `waitress-serve --port=8000 config.wsgi:application`
6. Put a reverse proxy (nginx / IIS) in front for TLS termination; it should set
   `X-Forwarded-Proto: https` so the secure-cookie / SSL-redirect settings engage.

A liveness/readiness probe is available at **`/healthz`** (checks DB connectivity).

---

## Repository layout

```
data/                       # repo root = Django BASE_DIR
├── config/                 # Django project (settings/urls/wsgi/asgi)
├── accounts/               # users
├── transmission/           # transmission-line master data + CSV import
├── masterdata/             # Category / SubCategory taxonomy (data-driven)
├── datasets/               # inspection upload module (models/views/utils/dedup)
├── dashboard/              # user + staff dashboards
├── reports/                # dataset export (ZIP + CSV/Excel)
├── templates/  static/  media/
├── manage.py  requirements.txt  transmission_data.csv
└── ARCHITECTURE.md  README.md  .env.example
```
