# APTRANSCO Transmission Dataset Collection Portal — Architecture Blueprint

**Version:** 1.1
**Status:** Active development (Milestones 1–2 complete, Milestone 3 next)
**Last updated:** 2026-06-26

---

## 1. Purpose

A centralized web portal that manages all APTRANSCO transmission-line inspection
datasets (drone images and field inspection images), so that data collected for
**AI-based transmission line inspection** is organized, searchable, deduplicated,
and ready for model training (YOLO, segmentation, etc.).

### 1.1 Problem statement

Today, drone and inspection images are collected manually and stored across
scattered folders and systems. The consequences:

- Images are not organized.
- Hard to search.
- Hard to retrieve for AI training.
- Duplicate data.
- No upload history.
- No centralized dataset.

### 1.2 Objectives

The system must:

1. Import APTRANSCO transmission-line master data.
2. Let users upload inspection images.
3. Organize images automatically on disk.
4. Store metadata in PostgreSQL.
5. Let users view their previous uploads.
6. Let administrators search and download datasets.

---

## 2. Technology stack

Pinned versions are taken from `requirements.txt` and `config/settings.py`.

| Layer       | Technology                                                       |
|-------------|-----------------------------------------------------------------|
| Backend     | Python, Django **6.0.6**                                         |
| Database    | PostgreSQL (`psycopg2-binary` 2.9.12), DB name `data_portal`     |
| Frontend    | HTML, Bootstrap, JavaScript, AJAX                               |
| Image       | Pillow 12.2.0                                                    |
| Data import | pandas 3.0.3, numpy 2.5.0                                        |
| Export      | openpyxl 3.1.5 (Excel), CSV                                      |

---

## 3. Repository layout (actual)

> The Django **project package is named `config`** (not `Data_Portal`). The
> earlier blueprint referred to `Data_Portal`; the code on disk uses `config`.

```
data/                              # repository root  (= Django BASE_DIR)
├── manage.py
├── requirements.txt
├── transmission_data.csv          # APTRANSCO master export (1,286 rows)
├── templates/                     # base.html, registration/login.html, dashboard/, datasets/
├── static/                        # global static files (settings: BASE_DIR/static)
├── media/                         # uploaded images      (MEDIA_ROOT = BASE_DIR/media)
├── config/                        # Django project package (settings/urls/wsgi/asgi)
│   ├── settings.py
│   ├── urls.py                    # admin, auth, dashboard, datasets, + dev media
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                      # client self-signup (views, urls) + django.contrib.auth login
├── transmission/                  # transmission-line master data + CSV import
│   └── management/commands/import_transmission_data.py
├── masterdata/                    # Category / SubCategory taxonomy (data-driven)
│   └── management/commands/seed_masterdata.py
├── datasets/                      # Inspection upload module (models, views, urls, utils)
├── dashboard/                     # user dashboard + staff admin dashboard (views, urls)
└── reports/                       # dataset export — ZIPs + CSV/Excel metadata (views, urls)
```

`INSTALLED_APPS` registers all five local apps: `accounts`, `transmission`,
`datasets`, `dashboard`, `reports`.

---

## 4. System architecture

```
                   APTRANSCO CSV (transmission_data.csv)
                         │
                         ▼
        ./manage.py import_transmission_data  (pandas)
                         │
                         ▼
                 PostgreSQL (data_portal)
                         │
      ┌──────────────────┼───────────────────────────────┐
      ▼                  ▼                                ▼
TransmissionLine    Inspection  ─1:N─►  InspectionImage  (files on disk: MEDIA_ROOT)
      │                  │                                │
      └──────────────────┴────────────────┬──────────────┘
                                           ▼
                               Django Web Application
                                           │
                          ┌────────────────┴────────────────┐
                          ▼                                  ▼
                        Users                              Admin
              (upload, view history)         (search, stats, download datasets)
```

---

## 5. Data model

### 5.1 `TransmissionLine` — implemented ✅

Source: `transmission/models.py`. Populated from the CSV `lin_nm` / `volt`
columns by the import command.

| Field        | Type                       | Notes                          |
|--------------|----------------------------|--------------------------------|
| `id`         | auto PK                    |                                |
| `line_name`  | CharField(300), **unique** | e.g. `132KV Vemagiri-Rajahmundry` |
| `voltage`    | CharField(20)              | e.g. `132KV`, `220KV`, `400KV` |
| `created_at` | DateTimeField (auto)       |                                |
| `updated_at` | DateTimeField (auto)       |                                |

Registered in admin with `list_display`, `search_fields`, `list_filter` on
voltage. Default ordering by `line_name`.

### 5.2 `Category` / `SubCategory` (masterdata app) — implemented ✅

> **Decision (D-5):** the component/defect taxonomy is **data-driven**, stored in
> the database in a dedicated `masterdata` app, rather than hardcoded as model
> `choices`. Administrators can add new categories/subcategories (e.g. "Thermal
> Image", "Drone Image", "Video") without code changes, and the upload page is
> rendered from the database. (See §13, Decision D-5.)

**`Category`** — top-level type

| Field  | Type                       | Notes                      |
|--------|----------------------------|----------------------------|
| `id`   | auto PK                    |                            |
| `name` | CharField(100), **unique** | e.g. `Component`, `Defect` |

**`SubCategory`** — type within a category

| Field      | Type                                           | Notes                           |
|------------|------------------------------------------------|---------------------------------|
| `id`       | auto PK                                         |                                 |
| `category` | FK → `Category` (related_name=`subcategories`)  |                                 |
| `name`     | CharField(100)                                  | `unique_together` with `category` |

Both registered in admin. Seeded by `./manage.py seed_masterdata` (idempotent):
**Component** → Peak, Cage, Cross Arms, Body, Legs & Stub Angles;
**Defect** → Vegetation, Broken Insulator, Corrosion, Missing Hardware,
Conductor Damage, Foreign Objects. (2 categories, 11 subcategories.)

### 5.3 Inspection schema — models implemented ✅ (Milestone 3) — **per-tower inspection**

> **Decision (revised):** model the upload as one **`Inspection`** per
> tower/location, with many **`InspectionImage`** rows beneath it — and tag the
> **image** with its type (via an FK to `masterdata.SubCategory`), not the
> inspection. A field engineer inspects one location at a time and captures
> everything they see there (components *and* defects, across many subcategories)
> before moving on, then submits once. Each image therefore points to its own
> subcategory, while the line, location, remarks, and uploader are shared by the
> whole inspection. (See §13, Decisions D-1, D-4 and D-5.)

**`Inspection`** — one row per tower/location inspection session

| Field               | Type                     | Notes                              |
|---------------------|--------------------------|------------------------------------|
| `id`                | auto PK                  |                                    |
| `transmission_line` | FK → `TransmissionLine`  |                                    |
| `location_id`       | CharField                | Free text for v1 (e.g. `T045`) — see §6.1 |
| `remarks`           | TextField (blank)        | optional, one note for the location |
| `status`            | CharField (choices)      | `draft` \| `submitted` \| `approved` \| `rejected`, default `draft` — see §5.4 |
| `uploaded_by`       | FK → `auth.User` (`on_delete=CASCADE`) |                      |
| `created_at`        | DateTimeField (auto)     |                                    |
| `updated_at`        | DateTimeField (auto)     | for future edits                   |

**`InspectionImage`** — one row per image

| Field         | Type                       | Notes                                   |
|---------------|----------------------------|-----------------------------------------|
| `id`          | auto PK                    |                                         |
| `inspection`  | FK → `Inspection` (related_name=`images`) |                          |
| `subcategory` | FK → `masterdata.SubCategory` (`on_delete=PROTECT`) | **no `category` column** — reached via `subcategory.category` (§5.2) |
| `image`       | ImageField (`upload_to=upload_path`) | path-safe, see §8       |
| `created_at`  | DateTimeField (auto)       |                                         |

**Principle:** one image = one `InspectionImage` record, and each record points to
one `SubCategory` (and thus its `Category`). This is normalized (no metadata
repeated on the inspection, no hardcoded taxonomy), scalable, and makes
searching, filtering, deleting, and AI dataset generation straightforward.

`InspectionImage` exposes a read-only `category` property (`subcategory.category`)
for convenience in admin/templates, and `subcategory` uses `on_delete=PROTECT` so
deleting a taxonomy entry can never cascade-delete inspection images.

Example — Inspection #145 (`132KV Vemagiri-Rajahmundry`, location `T045`,
remarks "Heavy vegetation observed"):

| inspection | category  | subcategory | image      |
|------------|-----------|-------------|------------|
| 145        | Component | Peak        | peak1.jpg  |
| 145        | Component | Peak        | peak2.jpg  |
| 145        | Component | Body        | body1.jpg  |
| 145        | Defect    | Vegetation  | veg1.jpg   |
| 145        | Defect    | Vegetation  | veg2.jpg   |
| 145        | Defect    | Corrosion   | rust1.jpg  |

### 5.4 Inspection lifecycle (status)

`Inspection.status` gives every inspection a quality-control lifecycle so partial
work isn't lost and only vetted data reaches the AI dataset:

```
Draft  ──submit──►  Submitted  ──review──►  Approved
  ▲                                 └─────►  Rejected
  └ engineer keeps uploading / resumes after a dropped connection
```

- **Draft** (default) — created as soon as an inspection starts; images can be
  added incrementally, so a dropped connection mid-upload loses nothing.
- **Submitted** — the engineer finishes and submits; awaits admin review.
- **Approved** / **Rejected** — set by an admin (admin list actions exist today —
  §11). **Only `Approved` inspections' images are exported** (§10), keeping
  incomplete or bad data out of the training set.

Constants live on the model (`Inspection.DRAFT`, `.SUBMITTED`, `.APPROVED`,
`.REJECTED`) so views and the admin reference them by name. (See §13, Decision D-6.)

> **v1 note:** the upload page is single-submit, so an inspection is created
> directly as `Submitted`; the `Draft` state is reserved for the future
> resumable/incremental upload flow.

---

## 6. Upload workflow (user)

One inspection per location, submitted once. The single form exposes a file
input for every component and defect subcategory; the engineer fills in only the
ones they have images for and submits the whole location at once.

> **✅ Implemented** at `/upload/` (login-required): the form is rendered from
> masterdata (no hardcoded subcategories), each file validated with Pillow, and
> on submit one `Inspection` (`status=Submitted`) is created with all its images
> (`datasets/views.py`, `templates/datasets/upload.html`).

```
Login → (role-based landing) → Upload page
   → Select Transmission Line   (dropdown from TransmissionLine)
   → Enter Location ID          (free text)
   → COMPONENTS: Peak / Cage / Cross Arms / Body / Legs & Stub Angles
                                (choose files per subcategory)
   → DEFECTS:    Vegetation / Broken Insulator / Corrosion /
                 Missing Hardware / Conductor Damage / Foreign Objects
                                (choose files per subcategory)
   → Remarks                    (one note for the location)
   → Submit once → Inspection detail page (preview the images you just uploaded)
```

On submit, the view creates **one `Inspection`**, then for every file in every
subcategory input creates an `InspectionImage` tagged with that category and
subcategory. Empty subcategories are simply skipped.

### 6.3 Role-based navigation (no mixed user/admin UI)

New inspectors **self-register** at `/accounts/signup/` (a public page;
`UserCreationForm` creates a regular non-staff account, logs them in, and routes
them straight to the upload page). The login and signup pages link to each other.

`/` is a role dispatcher (`dashboard/views.py::home`) and `LOGIN_REDIRECT_URL`,
so the two audiences never share a screen:

| Role | Lands on | Navigation shows |
|------|----------|------------------|
| Regular user | `/upload/` | **New Inspection**, **My Inspections** (`/my-inspections/`) |
| Staff / admin | `/staff/` | **Admin** (dashboard + review queue), **Export** |

A regular user uploads, then is redirected to that **inspection's detail page** to
preview exactly what they submitted (the full list is one click away under **My
Inspections**); staff get the separate admin area (stats, review, export).
(See §13, D-7.)

### 6.1 Note on Location ID

For v1, Location ID is a **free-text field** the user types. This is the
simplest path and matches the current requirement.

Future enhancement (not v1): the master CSV already carries per-line location
data. The `loc` and `tower` columns each hold the *full ordered list* of
tower/location identifiers along a line, e.g.
`[Boom of CKYP, 1 TT of CKYP/ANML, 2, 3, … 296 TT of JMDG, Boom of JMDG]`
(~1,049 distinct location strings across 1,286 lines). A later milestone could
parse these into a `Location`/`Tower` master table and replace the free-text box
with a dropdown scoped to the selected line, eliminating typos. Deferred because
the bracketed strings are irregular (`Boom of …`, `VT 1A`, `43/1`) and need a
dedicated parser. (See §13, Decision D-2.)

### 6.2 Upload form layout

```
----------------------------------------------------
 Transmission Line   [ Dropdown ▼ ]
 Location ID         [______________]
----------------------------------------------------
 COMPONENTS
   Peak                 [ Choose Files ]
   Cage                 [ Choose Files ]
   Cross Arms           [ Choose Files ]
   Body                 [ Choose Files ]
   Legs & Stub Angles   [ Choose Files ]
----------------------------------------------------
 DEFECTS
   Vegetation           [ Choose Files ]
   Broken Insulator     [ Choose Files ]
   Corrosion            [ Choose Files ]
   Missing Hardware     [ Choose Files ]
   Conductor Damage     [ Choose Files ]
   Foreign Objects      [ Choose Files ]
----------------------------------------------------
 Remarks
   [____________________________________]

                       [ SUBMIT ]
----------------------------------------------------
```

Each "Choose Files" control is a multi-file input
(`<input type="file" multiple>`) bound to one `SubCategory`. The COMPONENTS and
DEFECTS rows are **rendered from the `masterdata` tables** (§5.2), not hardcoded,
so adding a subcategory in the admin makes a new input appear automatically.

---

## 7. Categories & subcategories

> These now live in the `masterdata` tables (§5.2), seeded by `seed_masterdata`
> and editable in the admin. The list below is the **seeded default**, not a
> hardcoded enum.

**Components**
- Peak
- Cage
- Cross Arms
- Body
- Legs & Stub Angles

**Defects**
- Vegetation
- Broken Insulator
- Corrosion
- Missing Hardware
- Conductor Damage
- Foreign Objects

---

## 8. Media storage layout

Images are written to a deterministic, path-safe location derived from the upload
metadata, so the on-disk tree mirrors the database and is directly consumable by
training pipelines:

```
MEDIA_ROOT/
└── <line>/                      # safe_folder_name(line_name)
    └── <location>/              # safe_folder_name(location_id)
        └── <Category>/          # safe_folder_name(subcategory.category.name)  e.g. Component | Defect
            └── <SubCategory>/   # safe_folder_name(subcategory.name)           e.g. Vegetation
                ├── image001.jpg
                └── image002.jpg
```

Segments come from `datasets/utils.py::safe_folder_name`, which replaces the
filesystem-unsafe / Windows-illegal characters `/ \ : * ? " < > |` with spaces
and collapses whitespace to underscores (**case preserved** — names are *not*
lowercased). This matters because 476 of 1,283 line names contain `/`; without it
those names would fork into extra directories.

Example — line `132KV Rentachintala- Parasakthi DC/SC Line (P)` (note the `/`),
location `T045`, subcategory `Vegetation` (category `Defect`):

```
media/132KV_Rentachintala-_Parasakthi_DC_SC_Line_(P)/T045/Defect/Vegetation/image001.jpg
```

The `InspectionImage.image` field sets `upload_to=upload_path`
(also in `datasets/utils.py`), which assembles the four `safe_folder_name` segments from
`subcategory.category.name`, `subcategory.name`, and the parent `Inspection`'s
line and location.

---

## 9. Known issues / corrections

Items 1–2 are **resolved**; item 3 remains for the deployment milestone.

1. **✅ RESOLVED — Static / template / media paths.** `config/settings.py`
   computes `BASE_DIR = Path(__file__).resolve().parent.parent` (= repo root
   `data/`) and points `TEMPLATES["DIRS"]`, `STATICFILES_DIRS`, and `MEDIA_ROOT`
   at `BASE_DIR / …`. The `templates/`, `static/`, and `media/` folders had been
   living inside `config/` (one level too deep); they were **moved up to the repo
   root** to match the settings. `manage.py check` now reports 0 warnings.

2. **✅ RESOLVED — Voltage casing.** The CSV `volt` column had 4 distinct values
   including both `132KV` and `132kV`. The import command now normalizes voltage
   via `normalize_voltage()` (collapse whitespace + uppercase), and the 3 existing
   `132kV` rows were normalized in place. The database now holds 3 clean values:
   `132KV` (775), `220KV` (419), `400KV` (89).

3. **⬜ Secrets are hardcoded.** `SECRET_KEY` and the PostgreSQL password are
   inline in `settings.py` with `DEBUG = True`. Move both to environment
   variables before the deployment milestone (M7).

---

## 10. Dataset export (Milestone 6) — implemented ✅

Built in the `reports` app, **staff-only**, at `/reports/`. Exports preserve the
category/subcategory folder structure the AI pipeline expects.

**Component dataset — `components.zip`**
```
peak/  cage/  cross_arms/  body/  legs_stub_angles/
```

**Defect dataset — `defects.zip`**
```
vegetation/  broken_insulator/  corrosion/  missing_hardware/
conductor_damage/  foreign_objects/
```

**Only images from `Approved` inspections are exported** (§5.4) — drafts,
submitted-but-unreviewed, and rejected inspections are excluded, so incomplete or
bad data never enters the training set.

Plus a metadata export (CSV / Excel via openpyxl) describing each image and its
source `Inspection`.

**Implementation** (`reports/views.py`, `templates/reports/index.html`):
- One ZIP per `Category` at `/reports/category/<id>/zip/`, named `<category>s.zip`
  (e.g. `components.zip`, `defects.zip`). Folder names use `dataset_slug` —
  lowercase, underscore-separated (`Cross Arms` → `cross_arms`).
- Files are stored as `<subcategory>/<inspection_id>_<filename>` to avoid
  collisions across inspections.
- Metadata at `/reports/metadata.csv` and `/reports/metadata.xlsx` covers **all**
  images with a `status` column (so it doubles as a report); the **ZIPs are
  Approved-only**.
- All endpoints require `is_staff`; an "Export" nav link shows for staff.

---

## 11. Features

**User**
- Self sign-up — choose your own username/password at `/accounts/signup/`, no manual account creation ✅
- Login ✅
- Create an inspection (one location, many images across components and defects, single submit) ✅
- View inspection history — "My inspections" list + a detail page with image preview grouped by category/subcategory ✅
- Search & filter inspections (line/location text, status) ✅
- Edit remarks (optional) — planned

**Admin** (staff-only, at `/staff/`)
- Manage users — via Django admin ✅
- Review inspections — Approve / Reject in-portal (detail page + Admin dashboard queue) and via Django admin ✅ (§5.4)
- View statistics — totals + counts by status / category / line / uploader ✅
- Monitor uploads — "awaiting review" (Submitted) queue ✅
- Download datasets (per-category ZIP, Approved only) ✅ (§10)
- Export reports (CSV / Excel) ✅ (§10)

---

## 12. Roadmap

| Milestone | Scope                          | Status        |
|-----------|--------------------------------|---------------|
| M1        | Project setup                  | ✅ Complete   |
| M2        | Transmission master data + CSV import | ✅ Complete |
| M3        | Dataset upload module          | ✅ Complete   |
| M4        | User dashboard (My inspections, search, filters, detail/preview) | ✅ Complete |
| M5        | Admin dashboard (stats, monitoring, user management) | ✅ Complete |
| M6        | Dataset export (per-category ZIP + metadata) | ✅ Complete |
| **M7**    | Deployment (prod config, APTRANSCO server) | 🔄 **Next** |

### Milestone 3 task breakdown (complete ✅)

0. ✅ `masterdata` app: `Category` / `SubCategory` + idempotent seed (done — §5.2).
1. ✅ §9 path + voltage fixes applied (done — `manage.py check` clean).
2. ✅ `Inspection` model (done).
3. ✅ `InspectionImage` model (`subcategory` FK → `masterdata.SubCategory`) + path-safe `upload_to` (done — §8).
4. ✅ Migrations (`datasets.0001_initial` + `0002_inspection_status`, applied).
4a. ✅ `Inspection.status` lifecycle + admin Approve/Reject actions (done — §5.4).
5. ✅ Upload form — rendered from `Category.prefetch_related("subcategories")`, one multi-file input per subcategory, no hardcoded HTML (`templates/datasets/upload.html`).
6. ✅ Upload view — single submit creates one `Inspection` (`status=Submitted`) and fans out N `InspectionImage` rows by subcategory, skipping empty inputs (`datasets/views.py`).
7. ✅ Upload template (§6.2 layout, dynamic loop over categories/subcategories) + Bootstrap `base.html`.
8. ✅ Validation — Pillow image check, required line/location, at least one image.
9. ✅ Auth (login/logout + Bootstrap login page), routing, dashboard "My inspections", dev media serving.

### Milestone 4 task breakdown (complete ✅)

1. ✅ Dashboard search & filters — `q` (line/location `icontains`) + `status`, with `Count("images")` annotation (`dashboard/views.py`, `home.html`).
2. ✅ Inspection detail/preview — `/inspection/<id>/`, images grouped category → subcategory as thumbnails (`datasets/views.py::inspection_detail`, `templates/datasets/detail.html`).
3. ✅ Access control — owners see their own inspections; staff can view any (others get 404).

### Milestone 5 task breakdown (complete ✅)

1. ✅ Staff admin dashboard (`/staff/`) — totals + counts by status / category / line / uploader (`dashboard/views.py::staff_dashboard`).
2. ✅ Upload monitoring — "awaiting review" (Submitted) queue with inline Approve/Reject.
3. ✅ In-portal review endpoint (`/inspection/<id>/review/`, staff-only POST) + Approve/Reject panel on the detail page.
4. ✅ User management via Django admin (linked from the dashboard).

### Milestone 6 task breakdown (complete ✅)

1. ✅ Per-category ZIP export (`/reports/category/<id>/zip/`) — Approved-only images, organized `subcategory_slug/<inspection_id>_<file>` (`reports/views.py`).
2. ✅ Metadata export — CSV (`/reports/metadata.csv`) and Excel (`/reports/metadata.xlsx`, openpyxl), all images with a status column.
3. ✅ Staff-only access (`user_passes_test(is_staff)`) + "Export" nav link for staff.

---

## 13. Decision log

- **D-1 — Upload schema: multi-table.** Use `Inspection` (1) → `InspectionImage`
  (N) instead of a single flat `DatasetImage`. Rationale: groups a location's
  images, supports a clean "My Inspections" view, preserves per-inspection
  relationships for export, and is extensible (approval status, GPS, flight ID,
  AI results) without a schema refactor. Adopted before building M3.

- **D-2 — Location ID: free text for v1.** User types the location ID manually.
  The master CSV already contains per-line tower/location lists (`loc`, `tower`),
  which could later back a dropdown, but parsing the irregular strings is
  deferred. Revisit in a later milestone.

- **D-3 — Superseded approach.** An earlier From-Station → To-Station → Tower
  hierarchy was discarded. The collection workflow is the simpler
  Transmission Line → Location ID → Upload, which matches how APTRANSCO collects
  data.

- **D-4 — Category/subcategory live on the image, not the inspection.** A field
  engineer inspects one location at a time and captures both components and
  defects (many subcategories) before moving on, then submits once. So an
  `Inspection` holds only line/location/remarks/uploader, and each
  `InspectionImage` carries its own `category`/`subcategory`. This replaces the
  earlier idea of one session per category/subcategory and is why the schema is
  multiple tables, not one flat model.

- **D-5 — Taxonomy is data-driven (masterdata app), not code choices.**
  `Category` and `SubCategory` live in DB tables in a dedicated `masterdata` app,
  so admins can add component/defect types (and future kinds like Thermal /
  Drone / Video) without code changes, and the upload form is rendered from the
  database. `InspectionImage.subcategory` is an FK to `masterdata.SubCategory`.
  Initial taxonomy is seeded via the idempotent `seed_masterdata` command. This
  supersedes the earlier `CATEGORY_CHOICES` / `SUBCATEGORY_CHOICES` idea.
  Trade-off accepted: since subcategories double as AI class labels, a subcategory
  added at runtime is a class the trained model won't recognize until retrained —
  so taxonomy changes must be made deliberately and coordinated with the AI team.

- **D-6 — Inspections carry a status lifecycle.** `Inspection.status`
  (`draft → submitted → approved/rejected`, default `draft`) was added *before*
  the upload page so the page is built around it: a new inspection is created as
  a Draft and images are appended incrementally (so a dropped connection loses
  nothing), Submit moves it to Submitted, and an admin Approves/Rejects. Export
  (§10) ships only Approved images, turning the portal into a quality-controlled
  dataset pipeline rather than a raw image dump. Status constants live on the
  model; admin Approve/Reject actions exist today.

- **D-7 — Separate user and admin areas (no mixed UI).** `/` is a role
  dispatcher: regular users land on the upload page and navigate only Upload /
  My Inspections; staff land on the admin dashboard and navigate only Admin /
  Export. After uploading, a user is redirected to "My Inspections" to review
  their own work. The two audiences never share a screen, so the collector
  experience stays simple and the reviewer/export tooling stays out of their way.
```
