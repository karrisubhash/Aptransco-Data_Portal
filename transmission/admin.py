from django.contrib import admin
from .models import TransmissionLine


@admin.register(TransmissionLine)
class TransmissionLineAdmin(admin.ModelAdmin):
    list_display = (
        "line_name",
        "voltage",
    )

    search_fields = (
        "line_name",
        "voltage",
    )

    list_filter = (
        "voltage",
    )

    ordering = (
        "line_name",
    )