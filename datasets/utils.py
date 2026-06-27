import hashlib
import posixpath
import re
import uuid


# OS-illegal / path-breaking characters:  < > : " / \ | ? *
_UNSAFE_RE = re.compile(r'[<>:"/\\|?*]')


def sha256_of_file(f):
    """Return the hex SHA-256 of an uploaded file's content.

    Reads in chunks (works for large images without loading them whole) and
    rewinds the file pointer to 0 afterwards so the file stays usable for
    saving. This hash is the basis of upload deduplication: two files with the
    same content produce the same digest, so we never store one image twice.
    """
    f.seek(0)
    digest = hashlib.sha256()
    for chunk in f.chunks():
        digest.update(chunk)
    f.seek(0)
    return digest.hexdigest()

# Keep the stored filename short enough that the full
# "<line>/<location>/<Category>/<SubCategory>/<filename>" path stays well under
# the ImageField's max_length (255), even for long line names.
_MAX_STEM_LEN = 60


def safe_folder_name(name):
    """Convert any string into a single, safe folder name.

    Replaces OS-illegal characters (< > : " / \\ | ? *) and whitespace with
    underscores, then collapses repeats. Case is preserved.

        "132KV Line A/B"             -> "132KV_Line_A_B"
        "132KV Vemagiri-Rajahmundry" -> "132KV_Vemagiri-Rajahmundry"

    Without this, the 476 line names containing "/" would fork into extra
    nested directories.
    """
    name = str(name).strip()
    name = _UNSAFE_RE.sub("_", name)
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def safe_file_name(filename):
    """Return a safe, length-bounded, unique name for an uploaded file.

    Keeps a readable, sanitized stem and the real extension, but:
      * drops the inner dots so Django treats only the true suffix as the
        extension (a multi-dot name like "img.44.12 PM.jpeg" otherwise makes
        Django's file_ext swallow most of the name),
      * truncates the stem, and
      * appends a short unique token so every stored name is distinct.

    The uniqueness matters: without it, two files with the same name force
    Django to append its own random suffix and, combined with the long folder
    path, overflow max_length — which is what raised SuspiciousFileOperation.

        "WhatsApp Image 2026-06-03 at 6.44.12 PM. - X.jpeg"
            -> "WhatsApp_Image_2026-06-03_at_6_44_12_PM_-_X_1a2b3c4d.jpeg"
    """
    stem, ext = posixpath.splitext(filename)
    ext = "." + re.sub(r"[^A-Za-z0-9]", "", ext).lower() if ext.strip(".") else ""
    stem = safe_folder_name(stem).replace(".", "_")
    stem = re.sub(r"_+", "_", stem).strip("_")[:_MAX_STEM_LEN] or "image"
    return f"{stem}_{uuid.uuid4().hex[:8]}{ext}"


def upload_path(instance, filename):
    """Build media/<line>/<location>/<Category>/<SubCategory>/<filename>.

    Uses posixpath (forward slashes): Django's upload_to should return "/"
    separators on every OS — os.path.join would emit "\\" on Windows and
    corrupt the stored path / media URL. The category folder comes from
    subcategory.category, so no category is stored on the image row.
    """
    inspection = instance.inspection
    subcategory = instance.subcategory
    return posixpath.join(
        safe_folder_name(inspection.transmission_line.line_name),
        safe_folder_name(inspection.location_id),
        safe_folder_name(subcategory.category.name),
        safe_folder_name(subcategory.name),
        safe_file_name(filename),
    )
