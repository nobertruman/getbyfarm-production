from django.urls import path
from .api import LogoutView, MeView, RegisterView, ThrottledLoginView, ThrottledRefreshView

urlpatterns = [
    path("login/", ThrottledLoginView.as_view(), name="token_obtain_pair"),
    path("refresh/", ThrottledRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
]
