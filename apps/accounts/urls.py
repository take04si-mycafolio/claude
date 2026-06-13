from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("users/<int:pk>/", views.user_detail, name="user_detail"),
    path("missions/", views.missions, name="missions"),
    path("missions/seen/", views.mission_alerts_seen, name="mission_alerts_seen"),
    path("verify/<str:uidb64>/<str:token>/", views.verify_email, name="verify_email"),
    path("verify/resend/", views.resend_verification, name="resend_verification"),
]
