"""Keep the media/ tree in sync with the database.

Django does NOT delete the underlying file when an ``InspectionImage`` row is
removed — whether deleted directly, cascaded from its ``Inspection``, or removed
in the admin. Without this, every deletion leaves an orphan image on disk (the
exact DB/disk drift seen during the dataset wipe). This ``post_delete`` receiver
removes the file and prunes any folders left empty by the removal.

Registering this receiver also stops Django from "fast-deleting" images during a
cascade, so the signal reliably fires for ``Inspection.objects.all().delete()``.
"""
import os

from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import InspectionImage


@receiver(post_delete, sender=InspectionImage)
def delete_image_file(sender, instance, **kwargs):
    """Delete the image file (and now-empty parent folders) for a removed row."""
    image = instance.image
    if not image:
        return

    # Resolve the on-disk path before the file is removed; remote/abstract
    # storages may not expose one, in which case we just delete and skip pruning.
    try:
        file_dir = os.path.dirname(image.path)
    except (NotImplementedError, ValueError):
        file_dir = None

    # storage.delete() is a no-op if the file is already gone, so this is safe
    # even when disk and DB had previously drifted apart.
    image.delete(save=False)

    if file_dir:
        _prune_empty_dirs(file_dir)


def _prune_empty_dirs(directory):
    """Remove ``directory`` and empty ancestors up to (not including) MEDIA_ROOT."""
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    directory = os.path.abspath(directory)
    while directory.startswith(media_root) and directory != media_root:
        try:
            os.rmdir(directory)  # only succeeds if the folder is empty
        except OSError:
            break  # non-empty or already gone — stop climbing
        directory = os.path.dirname(directory)
