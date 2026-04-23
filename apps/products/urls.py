from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.list_view, name="list"),
    path("type/<uslug:type_slug>/", views.type_detail, name="type_detail"),
    path("articles/", views.article_list, name="article_list"),
    path("articles/<uslug:slug>/", views.article_detail, name="article_detail"),
    path("products/<uslug:slug>/", views.detail, name="detail"),
]
