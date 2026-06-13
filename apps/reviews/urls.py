from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.list_all, name="list"),
    path("new/<uslug:slug>/", views.create, name="create"),
    path("<int:review_id>/helpful/", views.helpful_toggle, name="helpful_toggle"),
]
