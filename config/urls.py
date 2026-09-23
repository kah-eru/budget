from django.contrib.auth import views as auth_views
from django.urls import path

from budget import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("health/", views.health),
    path("ready/", views.ready),
    path("robots.txt", views.robots),
    path("accounts/new/", views.account_create, name="account_create"),
    path("groups/new/", views.group_create, name="group_create"),
    path("workspaces/<int:workspace_id>/", views.workspace_detail, name="workspace"),
    path("workspaces/<int:workspace_id>/accounts/<int:account_id>/", views.account_detail, name="account_detail"),
    path("workspaces/<int:workspace_id>/sharing/", views.sharing, name="sharing"),
    path("workspaces/<int:workspace_id>/members/<int:member_id>/remove/", views.member_remove, name="member_remove"),
]
