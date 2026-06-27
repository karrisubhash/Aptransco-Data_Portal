from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="reports"),
    path("category/<int:category_id>/zip/", views.export_category_zip, name="export_category_zip"),
    path("metadata.csv", views.export_metadata_csv, name="export_metadata_csv"),
    path("metadata.xlsx", views.export_metadata_xlsx, name="export_metadata_xlsx"),
]
