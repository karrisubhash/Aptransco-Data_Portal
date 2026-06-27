from django.contrib import admin

from .models import Inspection, InspectionImage


class InspectionImageInline(admin.TabularInline):
    model = InspectionImage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transmission_line",
        "location_id",
        "status",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("status", "transmission_line__voltage", "created_at")
    search_fields = (
        "location_id",
        "transmission_line__line_name",
        "remarks",
    )
    inlines = [InspectionImageInline]
    actions = ["mark_approved", "mark_rejected"]

    @admin.action(description="Mark selected inspections as Approved")
    def mark_approved(self, request, queryset):
        updated = queryset.update(status=Inspection.APPROVED)
        self.message_user(request, f"{updated} inspection(s) marked Approved.")

    @admin.action(description="Mark selected inspections as Rejected")
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status=Inspection.REJECTED)
        self.message_user(request, f"{updated} inspection(s) marked Rejected.")


@admin.register(InspectionImage)
class InspectionImageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "inspection",
        "subcategory",
        "category",
        "image",
        "created_at",
    )
    # 'category' is filterable even though it's not a column — proof the
    # normalization works (it filters through subcategory.category).
    list_filter = ("subcategory__category", "subcategory")
    search_fields = (
        "inspection__location_id",
        "inspection__transmission_line__line_name",
    )
