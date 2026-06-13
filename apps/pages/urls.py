from django.urls import path
from . import views

app_name = "pages"
urlpatterns = [
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("contact/", views.contact, name="contact"),
    path("contact/thanks/", views.contact_thanks, name="contact_thanks"),
    path("share-your-voice/", views.post_review_lp, name="post_review_lp"),
]
