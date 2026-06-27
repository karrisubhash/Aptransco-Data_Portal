from django.urls import path

from . import views

urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("inspection/<int:pk>/", views.inspection_detail, name="inspection_detail"),
    path("inspection/<int:pk>/review/", views.review_inspection, name="review_inspection"),
]
