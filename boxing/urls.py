"""URL patterns for the boxing app."""

from django.urls import path

from boxing.views import RecommendBoxView

urlpatterns = [
    path("orders/recommend-box/", RecommendBoxView.as_view(), name="recommend-box"),
]
