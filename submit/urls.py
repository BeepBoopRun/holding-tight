from django.urls import path

from . import views

app_name = "submit"
urlpatterns = [
    path("", views.index, name="index"),
    path("form", views.form, name="form"),
]
