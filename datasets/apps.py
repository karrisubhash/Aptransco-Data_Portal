from django.apps import AppConfig


class DatasetsConfig(AppConfig):
    name = 'datasets'

    def ready(self):
        # Wire up the post_delete receiver that removes image files from disk.
        from . import signals  # noqa: F401
