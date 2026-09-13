from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.list_all, name="list"),
    path("new/<uslug:slug>/", views.create, name="create"),
    path("guest/<uslug:slug>/", views.guest_create, name="guest_create"),
    path("<int:review_id>/helpful/", views.helpful_toggle, name="helpful_toggle"),
    path("<int:review_id>/report/", views.report, name="report"),
    path("<int:review_id>/delete/", views.delete, name="delete"),
    # 使用記録（ProductUseLog）。投稿は商品 slug、削除/通報は use_log の id。
    path("use-logs/new/<uslug:slug>/", views.use_log_create, name="use_log_create"),
    path("use-logs/<int:use_log_id>/delete/", views.use_log_delete, name="use_log_delete"),
    path("use-logs/<int:use_log_id>/report/", views.use_log_report, name="use_log_report"),
]
