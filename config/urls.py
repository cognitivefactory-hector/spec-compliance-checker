from django.urls import path

from app import views

urlpatterns = [
    path("", views.index, name="index"),
    path("healthz", views.healthz, name="healthz"),
    path("sample/<str:sample_id>/requirements", views.requirements, name="requirements"),
    path("sample/<str:sample_id>/results", views.results, name="results"),
    path("sample/<str:sample_id>/report", views.report, name="report"),
]
