from django.urls import path

from . import views

app_name = "extractor"

urlpatterns = [
    path("", views.upload_view, name="upload"),
    path("process/<int:pk>/", views.process_view, name="process"),
    path("reprocess/<int:pk>/", views.reprocess_view, name="reprocess"),
    path("report/<int:pk>/", views.detail_view, name="detail"),
]
