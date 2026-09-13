from django.urls import path

from . import views

app_name = "surveys"

urlpatterns = [
    path("<slug:slug>/submit/", views.submit, name="submit"),
]
