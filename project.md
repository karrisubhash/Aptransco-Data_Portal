# PROJECT.md — APTRANSCO Transmission Dataset Collection Portal

> A single, exhaustive reference for this project. Captures everything: purpose,
> stack, every app/file, every model field, every route, every management
> command, configuration, data on disk, tests, decisions, and known gaps.
> Generated 2026-06-26. Complements (does not replace) `README.md` and
> `ARCHITECTURE.md`.

---

## 1. One-line summary

A Django web portal that centralizes APTRANSCO transmission-line inspection
images (drone + field) so the data collected for **AI-based transmission line
inspection** is organized, searchable, **deduplicated**, and ready for model
training (YOLO, segmentation, etc.).

## 2. Problem it solves

Today drone/inspection images are collected manually and scattered across
folders and systems: not organized, hard to search, hard to retrieve for AI
training, duplicated, no upload history, no centralized dataset. This portal
fixes all of that.

## 3. What it does (functional overview)

- **Imports** APTRANSCO transmission-line master data from CSV (1,286 lines).
- **Collects** inspection images via a single per-location upload form, driven by
  a data-driven Component/Defect taxonomy (no hardcoded categories).
- **Organizes** every image on disk under
  `media/<line>/<location>/<Category>/<SubCategory>/` automatically.
- **Deduplicates** uploads by SHA-256 content hash, so the same photo is never
  stored twice.
- **Reviews** inspections through a Draft → Submitted → Approved/Rejected lifecycle.
- **Exports** Approved-only, per-category ZIP datasets plus CSV/Excel metadata.
- **Separates** regular users (upload / "My Inspections") from staff (dashboard,
  review queue, export tools) — the two audiences never share a screen.

## 4. Project status

- **Version:** 1.1 (per ARCHITECTURE.md)
- Milestones M1–M6 **complete**; **M7 (Deployment)** is next/in progress.
- Currently runs in development mode (`DEBUG=True`) against local PostgreSQL.

---

## 5. Technology stack

| Layer    | Technology                                                        |
|----------|-------------------------------------------------------------------|
| Language | Python **3.13.5** (venv at `.venv`, base interpreter Python313)    |
| Backend  | Django **6.0.6**                                                   |
| Database | PostgreSQL via `psycopg2-binary` 2.9.12, DB name `data_portal`     |
| Frontend | HTML, Bootstrap **5.3.3** (CDN), Bootstrap Icons 1.11.3, vanilla JS|
| Line picker | Tom Select **2.3.1** (CDN) type-ahead over ~1,200 lines         |
| Fonts    | Inter (Google Fonts CDN)                                           |
| Imaging  | Pillow **12.2.0** (validation via `Image.open().verify()`)         |
| Import   | pandas **3.0.3**, numpy **2.5.0**                                  |
| Export   | openpyxl **3.1.5** (Excel), stdlib `csv`, `zipfile`               |
| Static   | WhiteNoise (≥6.0,<7.0) — optional, auto-enabled if installed       |

### requirements.txt (full pinned list)

```
asgiref==3.11.1
Django==6.0.6
et_xmlfile==2.0.0
numpy==2.5.0
openpyxl==3.1.5
pandas==3.0.3
pillow==12.2.0
psycopg2-binary==2.9.12
python-dateutil==2.9.0.post0
six==1.17.0
sqlparse==0.5.5
tzdata==2026.2
whitenoise>=6.0,<7.0    # production static-file serving (optional in dev)
```

> Note: `requirements.txt` on disk is UTF-16 encoded (small gotcha if a tool
> reads it as UTF-8).

---

## 6. Repository layout

The Django **project package is named `config`** (not `Data_Portal`). Repo root
= Django `BASE_DIR` = `c:\Users\Admin\Documents\data`.

```
data/                          # repo root (= BASE_DIR)
├── manage.py                  # DJANGO_SETTINGS_MODULE = config.settings
├── requirements.txt           # pinned deps (UTF-16)
├── transmission_data.csv      # APTRANSCO master export, 1,287 lines incl. header
├── .env.example               # env var template (real .env is git-ignored)
├── .gitignore
├── README.md                  # quick start + ops
├── ARCHITECTURE.md            # design rationale + decision log (v1.1)
├── project.md                 # THIS FILE
├── .venv/                     # virtualenv (Python 3.13.5), git-ignored
├── config/                    # Django project package
│   ├── __init__.py
│   ├── settings.py            # env-driven 12-factor settings
│   ├── urls.py                # root URLconf + admin branding
│   ├── wsgi.py                # config.wsgi:application
│   └── asgi.py                # config.asgi:application
├── accounts/                  # public self-signup (+ django.contrib.auth login)
├── transmission/              # TransmissionLine master data + CSV import
├── masterdata/                # Category / SubCategory taxonomy (data-driven)
├── datasets/                  # CORE: Inspection upload, dedup, detail, review
├── dashboard/                 # role dispatcher, My Inspections, staff dashboard, healthz
├── reports/                   # dataset export (per-category ZIP + CSV/Excel)
├── templates/                 # project-level templates (DIRS = BASE_DIR/templates)
├── static/                    # global static (css/app.css, css/admin.css)
└── media/                     # uploaded images (MEDIA_ROOT), git-ignored except .gitkeep
```

`INSTALLED_APPS` registers all six local apps: `accounts`, `transmission`,
`masterdata`, `datasets`, `dashboard`, `reports` (plus the Django contrib apps).

---

## 7. Data model (complete)

### 7.1 `transmission.TransmissionLine`

Populated from CSV columns `lin_nm` (name) and `volt` (voltage).

| Field        | Type                       | Notes                                  |
|--------------|----------------------------|----------------------------------------|
| `id`         | BigAutoField PK            |                                        |
| `line_name`  | CharField(300), **unique** | e.g. `132KV Vemagiri-Rajahmundry`      |
| `voltage`    | CharField(20)              | normalized: `132KV`, `220KV`, `400KV`  |
| `created_at` | DateTimeField (auto_now_add)|                                       |
| `updated_at` | DateTimeField (auto_now)   |                                        |

- `Meta.ordering = ["line_name"]`; verbose names "Transmission Line(s)".
- Admin: `list_display`/`search_fields` on name+voltage, `list_filter` on voltage.
- Migration: `transmission/0001_initial.py`.

### 7.2 `masterdata.Category`

| Field  | Type                       | Notes                      |
|--------|----------------------------|----------------------------|
| `id`   | BigAutoField PK            |                            |
| `name` | CharField(100), **unique** | e.g. `Component`, `Defect` |

`Meta.ordering = ["name"]`; verbose plural "Categories".

### 7.3 `masterdata.SubCategory`

| Field      | Type                                                | Notes                              |
|------------|-----------------------------------------------------|------------------------------------|
| `id`       | BigAutoField PK                                     |                                    |
| `category` | FK → Category, `on_delete=CASCADE`, `related_name="subcategories"` | |
| `name`     | CharField(100)                                      | `unique_together` with `category`  |

`Meta.ordering = ["category","name"]`, `unique_together=("category","name")`,
verbose plural "Sub Categories". `__str__` = `"{category} - {name}"`.
Migration: `masterdata/0001_initial.py`.

### 7.4 `datasets.Inspection` — one row per tower/location inspection session

| Field               | Type                                              | Notes                                              |
|---------------------|---------------------------------------------------|----------------------------------------------------|
| `id`                | BigAutoField PK                                    |                                                    |
| `transmission_line` | FK → TransmissionLine, CASCADE, `related_name="inspections"` | |
| `location_id`       | CharField(100)                                    | free text for v1, e.g. `T045`                      |
| `remarks`           | TextField(blank=True)                             | optional, one note per location                    |
| `status`            | CharField(20, choices)                            | `draft`/`submitted`/`approved`/`rejected`, default `draft` |
| `uploaded_by`       | FK → auth.User, CASCADE, `related_name="inspections"` | |
| `created_at`        | DateTimeField (auto_now_add)                      |                                                    |
| `updated_at`        | DateTimeField (auto_now)                          |                                                    |

- Status constants on the model: `Inspection.DRAFT`, `.SUBMITTED`, `.APPROVED`,
  `.REJECTED`; `STATUS_CHOICES` list.
- `Meta.ordering = ["-created_at"]`.
- **Indexes:** `Index(["uploaded_by","-created_at"])` (My Inspections) and
  `Index(["status"])` (review queue / stats).
- `__str__` = `"{transmission_line} - {location_id}"`.

### 7.5 `datasets.InspectionImage` — one row per image

| Field         | Type                                                       | Notes                                                       |
|---------------|------------------------------------------------------------|-------------------------------------------------------------|
| `id`          | BigAutoField PK                                            |                                                             |
| `inspection`  | FK → Inspection, CASCADE, `related_name="images"`         |                                                             |
| `subcategory` | FK → masterdata.SubCategory, **`on_delete=PROTECT`**, `related_name="images"` | no `category` column — derived |
| `image`       | ImageField, `upload_to=upload_path`, **`max_length=255`** | path-safe deterministic path (see §10)                      |
| `checksum`    | CharField(64, blank, default="", **db_index=True**)       | SHA-256 of content, basis of dedup; blank for legacy rows   |
| `created_at`  | DateTimeField (auto_now_add)                              |                                                             |

- `Meta.ordering = ["created_at"]`.
- Read-only **`category` property** = `self.subcategory.category` (no stored column).
- `subcategory` uses `PROTECT` so deleting a taxonomy entry can never
  cascade-delete inspection images.
- `__str__` = `"{inspection.location_id} - {subcategory.name}"`.

### 7.6 Migrations on disk

- `transmission/0001_initial.py`
- `masterdata/0001_initial.py`
- `datasets/0001_initial.py` — Inspection + InspectionImage
- `datasets/0002_inspection_status.py` — add `status`
- `datasets/0003_alter_inspectionimage_image.py` — image `max_length=255`
- `datasets/0004_inspectionimage_checksum_and_more.py` — add `checksum` + two indexes
- `accounts`, `dashboard`, `reports` have **no models** (empty `migrations/`).

### 7.7 Inspection lifecycle

```
Draft  ──submit──►  Submitted  ──review──►  Approved
  ▲                                 └─────►  Rejected
  └ engineer keeps uploading / resumes after a dropped connection
```

- **Draft** (model default) — reserved for the future resumable/incremental
  upload flow.
- **Submitted** — what the current single-submit upload page actually creates.
- **Approved / Rejected** — set by staff (in-portal review or Django admin).
- **Only `Approved` images are exported** — drafts/submitted/rejected excluded.

---

## 8. Apps, files & responsibilities (file-by-file)

### 8.1 `config/` (Django project package)

- **settings.py** — env-driven (12-factor). Highlights:
  - Tiny dependency-free `.env` loader (`_load_dotenv`) that `setdefault`s into
    `os.environ` (real OS env always wins). Helpers: `env`, `env_bool`, `env_list`.
  - `BASE_DIR = Path(__file__).resolve().parent.parent` (= repo root).
  - `DEBUG` defaults True. Dev uses a deterministic insecure `SECRET_KEY`
    (`django-insecure-6wzg(...`); with `DEBUG=False` startup **raises
    `ImproperlyConfigured`** unless `DJANGO_SECRET_KEY` is set.
  - `ALLOWED_HOSTS` = `["*"]` in dev, env-list in prod.
  - WhiteNoise auto-wired if importable (middleware inserted at index 1 +
    `CompressedManifestStaticFilesStorage`); falls back gracefully if absent.
  - `TEMPLATES["DIRS"] = [BASE_DIR/"templates"]`, `APP_DIRS=True`.
  - **DATABASES.default**: PostgreSQL, NAME `data_portal`, USER `postgres`,
    **PASSWORD sourced from `DJANGO_DB_PASSWORD` (env/.env), no hardcoded
    fallback — empty default**, HOST localhost, PORT 5432, `CONN_MAX_AGE=60`.
  - `STATIC_URL="static/"`, `STATICFILES_DIRS=[BASE_DIR/"static"]`,
    `STATIC_ROOT=BASE_DIR/"staticfiles"`.
  - `MEDIA_URL="/media/"`, `MEDIA_ROOT=BASE_DIR/"media"` (env-overridable).
  - Upload caps: `DATA_UPLOAD_MAX_MEMORY_SIZE` 50 MB, `DATA_UPLOAD_MAX_NUMBER_FILES`
    500, `FILE_UPLOAD_MAX_MEMORY_SIZE` 10 MB, **`MAX_IMAGE_UPLOAD_SIZE` 25 MB**
    (per-image cap enforced in the upload view).
  - Auth redirects: `LOGIN_URL="login"`, `LOGIN_REDIRECT_URL="home"`,
    `LOGOUT_REDIRECT_URL="login"`.
  - `MESSAGE_TAGS` maps ERROR → Bootstrap `danger`.
  - `TIME_ZONE` default `Asia/Kolkata`, `USE_TZ=True`, `USE_I18N=True`.
  - **Production hardening (only when `DEBUG=False`):** `SECURE_PROXY_SSL_HEADER`,
    `SECURE_SSL_REDIRECT`, secure session/CSRF cookies, HSTS (30 days,
    includeSubDomains, preload), `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`.
  - **Logging:** console by default (verbose `{asctime} [{levelname}] {name}: {message}`);
    add a rotating 5 MB×5 file handler via `DJANGO_LOG_FILE`; level via `DJANGO_LOG_LEVEL`.
- **urls.py** — root URLconf; also brands the Django admin
  (`site_header="APTRANSCO Administration"`, `site_title="APTRANSCO Admin"`,
  `index_title="Dataset Portal Administration"`). Serves media in DEBUG.
- **wsgi.py / asgi.py** — standard callables; settings module `config.settings`.

### 8.2 `accounts/` — public self-registration

- **views.py::signup** — public page; `UserCreationForm` creates a regular
  **non-staff** account, logs them in, redirects to `home` (role dispatcher).
  Authenticated users are redirected away.
- **urls.py** — `signup/` → name `signup`.
- `models.py`/`admin.py` empty. `apps.py` = `AccountsConfig`.
- Login/logout come from `django.contrib.auth.urls` (included in config/urls).
- **tests.py** (`SignupTests`): page renders; signup creates non-staff + logs in;
  password mismatch rejected; authenticated user redirected.

### 8.3 `transmission/` — master data

- **models.py** — `TransmissionLine` (§7.1).
- **admin.py** — `TransmissionLineAdmin` (list_display, search_fields, list_filter
  on voltage, ordering by name).
- **management/commands/import_transmission_data.py** — `Command`:
  - Arg: `csv_file`. Reads with pandas.
  - `normalize_voltage(value)` → `"".join(str(value).split()).upper()` so
    `132KV`/`132kV`/`132 Kv` all become `132KV`.
  - For each row: strip `lin_nm`, normalize `volt`, `get_or_create` by unique
    `line_name` (idempotent). Prints Imported / Skipped counts.
- **tests.py** — `NormalizeVoltageTests` (uppercase, whitespace, canonical);
  `ImportCommandTests` (writes temp CSV, asserts normalized lines + idempotency).
- `views.py` empty. `apps.py` = `TransmissionConfig`.

### 8.4 `masterdata/` — data-driven taxonomy

- **models.py** — `Category`, `SubCategory` (§7.2/7.3).
- **admin.py** — `CategoryAdmin`, `SubCategoryAdmin` (list_filter on category).
- **management/commands/seed_masterdata.py** — `Command`, idempotent
  (`get_or_create`). Seeds the `TAXONOMY` dict:
  - **Component:** Peak, Cage, Cross Arms, Body, Legs & Stub Angles
  - **Defect:** Vegetation, Broken Insulator, Corrosion, Missing Hardware,
    Conductor Damage, Foreign Objects
  - Total: **2 categories, 11 subcategories.** Prints created counts.
- **tests.py** — `SeedMasterdataTests` (creates 2/11, idempotent);
  `SubCategoryConstraintTests` (unique_together raises IntegrityError).
- `views.py` empty. `apps.py` = `MasterdataConfig`.

### 8.5 `datasets/` — CORE upload / dedup / detail / review

- **models.py** — `Inspection`, `InspectionImage` (§7.4/7.5).
- **utils.py** — the path/dedup engine:
  - `sha256_of_file(f)` — chunked SHA-256 of an uploaded file; **rewinds to 0**
    after so the file is still saveable. Basis of dedup.
  - `safe_folder_name(name)` — replaces OS-illegal chars `< > : " / \ | ? *` and
    whitespace with `_`, collapses repeats, strips edges. **Case preserved.**
    (Critical: ~476 of 1,283 line names contain `/`.)
  - `safe_file_name(filename)` — sanitized + length-bounded (`_MAX_STEM_LEN=60`)
    + **unique** stem with an 8-char uuid token; drops inner dots so Django sees
    only the true extension. Prevents `SuspiciousFileOperation`/max_length overflow.
  - `upload_path(instance, filename)` — builds, with **posixpath** (forward
    slashes on every OS): `<line>/<location>/<Category>/<SubCategory>/<file>`.
    Category folder comes from `subcategory.category` (none stored on the row).
- **views.py**:
  - `staff_required = user_passes_test(lambda u: u.is_staff)`.
  - **`upload`** (`@login_required`) — GET renders form from
    `Category.prefetch_related("subcategories")` + all lines. POST:
    1. Hard validation (block whole submit): line must exist, location required,
       at least one image — errors re-render the form with the user's input kept.
    2. Per-file processing (skip-with-warning, don't fail the batch): reject
       oversize (> `MAX_IMAGE_UPLOAD_SIZE`), reject non-images (Pillow `verify()`),
       skip **in-submission duplicates** (checksum set), skip **dataset-wide
       duplicates** (`InspectionImage.filter(checksum__in=...)`).
    3. If nothing survives → warnings + error, re-render.
    4. In a `transaction.atomic()`: create one `Inspection` with
       **`status=SUBMITTED`**, then fan out N `InspectionImage` rows (with checksum).
    5. Success message (with skipped count) and **redirect to
       `inspection_detail`** of the new inspection.
  - **`inspection_detail`** (`@login_required`) — owners see their own; **staff
    see any**; others get 404. Groups images `category → subcategory → [images]`
    via `OrderedDict` for the preview.
  - **`review_inspection`** (`@login_required @staff_required`, POST) — action
    `approve`/`reject` sets status (`save(update_fields=["status"])`); safe
    open-redirect back via `url_has_allowed_host_and_scheme(next)`, else
    `staff_dashboard`.
- **urls.py** — `upload/`→`upload`, `inspection/<pk>/`→`inspection_detail`,
  `inspection/<pk>/review/`→`review_inspection`.
- **admin.py** — `InspectionAdmin` (list_display incl. status; list_filter on
  status / `transmission_line__voltage` / created_at; search; `InspectionImageInline`;
  bulk actions **mark_approved / mark_rejected**). `InspectionImageAdmin`
  (filterable by `subcategory__category` and `subcategory` — `category` works as a
  filter even though it's not a column, proving the normalization).
- **management/commands/backfill_checksums.py** — compute SHA-256 for stored
  images missing one (or `--all` to recompute); reports updated/total and any
  missing-on-disk files.
- **management/commands/find_duplicate_images.py** — group images by checksum
  (`Count>1`), print each duplicate group and a redundant-count summary; run
  `backfill_checksums` first for legacy rows.
- **tests.py** — extensive: `SafeNameTests`, `ChecksumTests`, `UploadPathTests`,
  `UploadViewTests` (login required, valid upload, missing line/location, no
  images, invalid image skipped, in-submission dup skipped, dataset dup skipped,
  oversize rejected), `DetailAndReviewTests` (owner/other/staff visibility,
  non-staff cannot review, staff approve/reject).

### 8.6 `dashboard/` — routing, user list, staff dashboard, health

- **views.py**:
  - **`healthz`** — public liveness/readiness probe; `connection.ensure_connection()`,
    returns JSON `{"status","database"}` with **200** ok / **503** on DB failure.
  - **`home`** (`@login_required`) — role dispatcher: staff → `staff_dashboard`,
    regular → `upload`. This is `LOGIN_REDIRECT_URL`.
  - **`my_inspections`** (`@login_required`) — own inspections only;
    `select_related("transmission_line")`, `annotate(image_count=Count("images"))`;
    filters: `q` (location/line `icontains`) + `status`; explicit
    `order_by("-created_at")` (annotate drops Meta ordering); paginated
    **PAGE_SIZE=25**; preserves filters in pagination querystring.
  - **`staff_dashboard`** (`@login_required @staff_required`) — totals
    (inspections, images), counts by status, images by category, top 10 lines,
    top 10 uploaders, and a paginated **"awaiting review" (Submitted)** queue.
- **urls.py** — `""`→`home`, `my-inspections/`→`my_inspections`, `staff/`→`staff_dashboard`.
- **tests.py** — `HealthCheckTests` (hits `/healthz`), `RoleDispatchTests`,
  `MyInspectionsTests` (pagination caps at 25, second page, filter, only-own).
- `models.py`/`admin.py` empty. `apps.py` = `DashboardConfig`.

### 8.7 `reports/` — dataset export (staff-only)

- **views.py**:
  - `staff_required`; `APPROVED = Q(inspection__status=Inspection.APPROVED)`.
  - `METADATA_HEADERS` = inspection_id, transmission_line, location_id, category,
    subcategory, status, uploaded_by, created_at, image_path.
  - `dataset_slug(name)` — `slugify(name).replace("-","_")`
    (`Cross Arms`→`cross_arms`, `Legs & Stub Angles`→`legs_stub_angles`).
  - `_metadata_rows()` — generator over **all** images (select_related joins),
    ordered by inspection then id; status via `get_status_display()`.
  - **`index`** — staff landing; each Category annotated with approved-image
    count; shows total + approved image counts.
  - **`export_category_zip`** — one in-memory `ZIP_DEFLATED` per Category,
    **Approved-only**, entries `"<subcategory_slug>/<inspection_id>_<basename>"`
    (inspection id prefix avoids collisions). Filename `"<category_slug>s.zip"`
    (Component→`components.zip`, Defect→`defects.zip`).
  - **`export_metadata_csv`** → `dataset_metadata.csv` (all images, status column).
  - **`export_metadata_xlsx`** → `dataset_metadata.xlsx` via openpyxl
    (sheet "Images").
- **urls.py** (mounted at `/reports/`): `""`→`reports`,
  `category/<id>/zip/`→`export_category_zip`, `metadata.csv`→`export_metadata_csv`,
  `metadata.xlsx`→`export_metadata_xlsx`.
- **tests.py** — `DatasetSlugTests`; `ExportTests` (staff-only gating, ZIP
  contains only the 2 approved images under `peak/`, CSV covers all 3 images,
  XLSX staff-only + content-type).
- `models.py`/`admin.py` empty. `apps.py` = `ReportsConfig`.

---

## 9. URL map (complete)

| Method | Path | Name | View | Access |
|--------|------|------|------|--------|
| GET/POST | `/` | `home` | dashboard.home | login (role dispatch) |
| GET | `/admin/...` | (admin) | Django admin (branded) | staff |
| GET/POST | `/accounts/signup/` | `signup` | accounts.signup | public |
| GET/POST | `/accounts/login/` | `login` | auth LoginView | public |
| POST | `/accounts/logout/` | `logout` | auth LogoutView | any |
| (auth) | `/accounts/password_*` | (auth) | django.contrib.auth.urls | per Django |
| GET | `/my-inspections/` | `my_inspections` | dashboard.my_inspections | login |
| GET | `/staff/` | `staff_dashboard` | dashboard.staff_dashboard | staff |
| GET/POST | `/upload/` | `upload` | datasets.upload | login |
| GET | `/inspection/<pk>/` | `inspection_detail` | datasets.inspection_detail | owner or staff |
| POST | `/inspection/<pk>/review/` | `review_inspection` | datasets.review_inspection | staff |
| GET | `/reports/` | `reports` | reports.index | staff |
| GET | `/reports/category/<id>/zip/` | `export_category_zip` | reports.export_category_zip | staff |
| GET | `/reports/metadata.csv` | `export_metadata_csv` | reports.export_metadata_csv | staff |
| GET | `/reports/metadata.xlsx` | `export_metadata_xlsx` | reports.export_metadata_xlsx | staff |
| GET | `/media/...` | — | static() | DEBUG only |
| GET | `/healthz` | `healthz` | dashboard.healthz | public (liveness/readiness probe; wired at project root in `config/urls.py`) |

Role-based navigation: regular users see **New Inspection** + **My Inspections**;
staff see **Dashboard** + **Export**. After uploading, a user lands on the new
inspection's detail page.

---

## 10. Media storage layout

Deterministic, path-safe, mirrors the database; directly consumable by training
pipelines:

```
MEDIA_ROOT/
└── <line>/                  # safe_folder_name(line_name)
    └── <location>/          # safe_folder_name(location_id)
        └── <Category>/      # safe_folder_name(subcategory.category.name)  e.g. Component | Defect
            └── <SubCategory>/  # safe_folder_name(subcategory.name)        e.g. Vegetation
                ├── <stem>_<uuid8>.jpg
                └── ...
```

Example — line `132KV Rentachintala- Parasakthi DC/SC Line (P)` (note the `/`),
location `T045`, subcategory `Vegetation` (category `Defect`):

```
media/132KV_Rentachintala-_Parasakthi_DC_SC_Line_(P)/T045/Defect/Vegetation/image001.jpg
```

---

## 11. Current data on disk (snapshot 2026-06-26)

- **`transmission_data.csv`**: 1,287 lines incl. header (= 1,286 transmission
  lines). 23 columns; key ones used: `lin_nm`, `volt`. Other columns present but
  unused by import: `object_id, frss, toss, lin_sap, frbay, tobay, circl,
  circl_id, rel_length, doc, loc, sp_cp, cond_tp, gis, created_on, line_tp,
  status, tower, oth_comp, leased, circuit_no`. The `loc`/`tower` columns each
  hold the *full ordered list* of tower/location identifiers per line (e.g.
  `[Boom of CKYP, 1 TT of CKYP/ANML, 2, 3, … Boom of JMDG]`, ~1,049 distinct
  strings) — reserved for a future location dropdown (Decision D-2).
- Voltage distribution after normalization: `132KV` (775), `220KV` (419),
  `400KV` (89).
- **`media/`**: 38 files (37 uploaded images + `.gitkeep`) across 6 lines /
  several locations. Subcategories present include Component/{Body, Cage,
  Legs & Stub Angles} and Defect/{Corrosion, Missing Hardware, Vegetation}.
  Largest cluster: `132KV Krishnapatnam Port - Posrt Line-02 (P)` /
  location `t23` / `Component/Legs & Stub Angles` (~24 WhatsApp images).

---

## 12. Configuration / environment variables

From `.env.example` (copy to `.env`, which is git-ignored). Dev needs nothing —
defaults work.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | dev insecure key | **Required when DEBUG=False** |
| `DJANGO_DEBUG` | `True` | `False` activates security hardening |
| `DJANGO_ALLOWED_HOSTS` | `*` (dev) | comma-separated; required in prod |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | full HTTPS origins for POSTs |
| `DJANGO_DB_ENGINE` | `django.db.backends.postgresql` | |
| `DJANGO_DB_NAME` | `data_portal` | |
| `DJANGO_DB_USER` | `postgres` | |
| `DJANGO_DB_PASSWORD` | empty (no hardcoded fallback) | **required** — set via env/.env |
| `DJANGO_DB_HOST` | `localhost` | |
| `DJANGO_DB_PORT` | `5432` | |
| `DJANGO_DB_CONN_MAX_AGE` | `60` | persistent-connection seconds |
| `DJANGO_TIME_ZONE` | `Asia/Kolkata` | |
| `DJANGO_MEDIA_ROOT` | `BASE_DIR/media` | where images are stored |
| `DJANGO_MAX_IMAGE_UPLOAD_SIZE` | `26214400` (25 MB) | per-image cap |
| `DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE` | 50 MB | total multipart body |
| `DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES` | `500` | max files per request |
| `DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE` | 10 MB | spill-to-disk threshold |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` | only used when DEBUG=False |
| `DJANGO_SECURE_HSTS_SECONDS` | `2592000` (30 days) | only when DEBUG=False |
| `DJANGO_LOG_LEVEL` | `INFO` | |
| `DJANGO_LOG_FILE` | empty | absolute path enables rotating file logs |

---

## 13. Setup & operations

### Development quick start

```bash
python -m venv .venv
.venv\Scripts\activate                # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements.txt
cp .env.example .env                   # optional in dev
# createdb data_portal                 # create the PostgreSQL DB once
python manage.py migrate
python manage.py seed_masterdata       # seed Component/Defect taxonomy (idempotent)
python manage.py import_transmission_data transmission_data.csv
python manage.py createsuperuser
python manage.py runserver             # http://127.0.0.1:8000/
```

### Management commands (all)

| Command | Effect |
|---------|--------|
| `seed_masterdata` | Seed/refresh the Component/Defect taxonomy (idempotent) |
| `import_transmission_data <csv>` | Import/normalize transmission lines from CSV |
| `backfill_checksums [--all]` | Compute SHA-256 for stored images (missing, or all) |
| `find_duplicate_images` | Report images sharing identical content |

### Tests

```bash
python manage.py test
```

Covers path/dedup utilities, the upload flow (incl. duplicate rejection),
access control, the review lifecycle, dataset export, signup, role dispatch,
pagination, and the health check.

### Deployment (Milestone 7)

1. Set `DJANGO_DEBUG=False`, strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
   `DJANGO_CSRF_TRUSTED_ORIGINS`.
2. `pip install -r requirements.txt` (installs WhiteNoise).
3. `python manage.py collectstatic --noinput`
4. `python manage.py migrate`
5. Serve behind TLS: Linux `gunicorn config.wsgi:application`, Windows
   `waitress-serve --port=8000 config.wsgi:application`.
6. Reverse proxy (nginx/IIS) terminates TLS and sets `X-Forwarded-Proto: https`
   so secure-cookie / SSL-redirect settings engage.

---

## 14. Frontend / UI notes

- `templates/base.html` — Bootstrap 5.3.3 + Bootstrap Icons + Inter font, sticky
  branded navbar with role-aware nav and a user dropdown (Manage users / Django
  admin / Sign out for staff), flash-message rendering (icon per level), footer.
- Auth pages (`registration/login.html`, `registration/signup.html`) — split
  "auth-shell" layout with a marketing aside; pages cross-link.
- `datasets/upload.html` — Tom Select type-ahead line picker; subcategory file
  inputs rendered dynamically from masterdata; live "N images across M
  components" counter; sidebar "How it works".
- `datasets/detail.html` — status badge, details, image gallery grouped
  category→subcategory; staff see an inline Approve/Reject panel when Submitted.
- `dashboard/my_inspections.html` — search/status filter, clickable rows,
  paginated table.
- `dashboard/staff.html` — KPI stat cards, breakdown panels (by category / top
  lines / by uploader), "Awaiting review" queue with inline Approve/Reject.
- `reports/index.html` — per-category download cards (disabled when 0 approved) +
  CSV/Excel metadata buttons.
- `partials/_pagination.html` — reusable pager preserving filter querystring.
- `admin/base_site.html` — branded Django admin.
- Static: `static/css/app.css` (575 lines, the portal design system) and
  `static/css/admin.css` (124 lines, admin theming).

---

## 15. Known gaps / discrepancies / TODO

> Items 1–3 were the M7 deployment blockers and are now **resolved in code**
> (this section previously described them as open). Kept here as a changelog;
> items 4–5 remain genuinely open.

1. ~~**`/healthz` is not wired into any URLconf.**~~ **Resolved.** The probe is
   registered at the project root in `config/urls.py` (above the catch-all app
   includes, no trailing slash) — and redundantly in `dashboard/urls.py`;
   `dashboard/tests.py` exercises it and it returns 200/503 on DB health.
2. ~~**Upload redirect vs. tests.**~~ **Resolved.** `datasets.upload` redirects
   to `inspection_detail`, and both `test_valid_upload_creates_inspection_and_images`
   and `test_duplicate_within_submission_skipped` now assert that target.
3. ~~**Hardcoded DB password `subhash`.**~~ **Resolved.** `config/settings.py`
   reads `DJANGO_DB_PASSWORD` from env/.env with **no hardcoded fallback** (empty
   default). The dev `SECRET_KEY` remains an inline insecure key *by design* —
   startup raises `ImproperlyConfigured` if it isn't overridden when `DEBUG=False`.
4. **Draft state unused in v1** — the upload page is single-submit, creating
   `Submitted` directly; `Draft` is reserved for a future resumable flow.
5. **Location ID is free text (Decision D-2)** — typo-prone; a future milestone
   could parse the CSV `loc`/`tower` lists into a `Location`/`Tower` master table
   and a line-scoped dropdown.

---

## 16. Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 | Project setup | ✅ Complete |
| M2 | Transmission master data + CSV import | ✅ Complete |
| M3 | Dataset upload module | ✅ Complete |
| M4 | User dashboard (My inspections, search, filters, detail/preview) | ✅ Complete |
| M5 | Admin dashboard (stats, monitoring, user management) | ✅ Complete |
| M6 | Dataset export (per-category ZIP + metadata) | ✅ Complete |
| **M7** | Deployment (prod config, APTRANSCO server) | 🔄 Next |

---

## 17. Decision log (summary — full text in ARCHITECTURE.md §13)

- **D-1** — Upload schema is multi-table (`Inspection` 1→N `InspectionImage`),
  not one flat `DatasetImage`.
- **D-2** — Location ID is free text for v1; CSV `loc`/`tower` could later back a
  dropdown.
- **D-3** — Superseded From-Station→To-Station→Tower hierarchy; current flow is
  Line → Location ID → Upload.
- **D-4** — Category/subcategory live on the **image**, not the inspection (an
  engineer captures many subcategories per location, submits once).
- **D-5** — Taxonomy is **data-driven** (`masterdata` tables), not model
  `choices`; upload form rendered from the DB. Trade-off: a runtime-added
  subcategory is an AI class the model won't know until retrained — coordinate
  taxonomy changes with the AI team.
- **D-6** — Inspections carry a status lifecycle; export ships Approved only.
- **D-7** — Separate user/admin areas (no mixed UI); `/` dispatches by role.

---

## 18. Key facts cheat-sheet

- Django project package: **`config`** (not `Data_Portal`).
- DB: PostgreSQL **`data_portal`**.
- Taxonomy: **2 categories, 11 subcategories**, seeded (editable in admin).
- Master data: **1,286 transmission lines**; voltages `132KV`/`220KV`/`400KV`.
- Dedup: **SHA-256** content hash, enforced both within a submission and against
  the whole dataset; `find_duplicate_images` + `backfill_checksums` support it.
- Per-image cap: **25 MB**; only image files (validated with Pillow).
- Export: **Approved-only** per-category ZIPs + all-images CSV/Excel metadata.
- Time zone: **Asia/Kolkata**; stored in UTC (`USE_TZ=True`).
- Python **3.13.5**, Django **6.0.6**.
