from django.contrib.auth import views as auth_views
from django.urls import path

from budget import views
from budget import invitation_views
from budget.forms import VerifiedPasswordResetForm

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(form_class=VerifiedPasswordResetForm), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("email/verify/", invitation_views.email_verify, name="email_verify"),
    path("email/verify/<str:token>/", invitation_views.email_verify, name="email_verify_confirm"),
    path("invitations/<str:token>/", invitation_views.invitation_accept, name="invitation_accept"),
    path("invitations/<str:token>/register/", invitation_views.invitation_register, name="invitation_register"),
    path("invitations/<str:token>/register/<str:proof>/", invitation_views.invitation_register, name="invitation_register_confirm"),
    path("workspaces/<int:workspace_id>/invitations/", invitation_views.invitation_create, name="invitation_create"),
    path("workspaces/<int:workspace_id>/invitations/<int:invitation_id>/revoke/", invitation_views.invitation_revoke, name="invitation_revoke"),
    path("health/", views.health),
    path("ready/", views.ready),
    path("robots.txt", views.robots),
    path("accounts/new/", views.account_create, name="account_create"),
    path("groups/new/", views.group_create, name="group_create"),
    path("workspaces/<int:workspace_id>/", views.workspace_detail, name="workspace"),
    path("workspaces/<int:workspace_id>/accounts/<int:account_id>/", views.account_detail, name="account_detail"),
    path("workspaces/<int:workspace_id>/accounts/<int:account_id>/transactions/new/", views.transaction_edit, name="transaction_create"),
    path("workspaces/<int:workspace_id>/accounts/<int:account_id>/transactions/<int:transaction_id>/", views.transaction_edit, name="transaction_edit"),
    path("workspaces/<int:workspace_id>/sharing/", views.sharing, name="sharing"),
    path("workspaces/<int:workspace_id>/members/<int:member_id>/remove/", views.member_remove, name="member_remove"),
]
