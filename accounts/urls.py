from django.urls import path

from .views import (
    AdminDashboardView,
    ClientDashboardView,
    CustomerLoginView,
    DashboardView,
    DriverDashboardView,
    LoginView,
    LoginVerificationView,
    LogoutView,
    ManagerDashboardView,
    ProfileView,
    SuperAdminDashboardView,
    UserCreateView,
    UserDeleteView,
    UserDetailView,
    UserPasswordResetTriggerView,
    UserListView,
    UserToggleActiveView,
    UserUpdateView,
    RoleManagementView,
    UserRoleUpdateView,
    ActivityLogView,
    PermissionManagementView,
    PasswordResetCompleteStepView,
    PasswordResetNewPasswordView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    ForcePasswordChangeView,
    SecureAccountView,
    SystemSettingsView,
    UserExcelExportView,
    exchange_rates_api,
    UserPdfExportView,
)

app_name = "accounts"

urlpatterns = [
    path("", LoginView.as_view(), name="login"),
    path("login/verify/", LoginVerificationView.as_view(), name="login-verify"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("secure-account/", SecureAccountView.as_view(), name="secure-account"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("portal/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("portal/dashboard/superadmin/", SuperAdminDashboardView.as_view(), name="dashboard-superadmin"),
    path("portal/dashboard/admin/", AdminDashboardView.as_view(), name="dashboard-admin"),
    path("portal/dashboard/manager/", ManagerDashboardView.as_view(), name="dashboard-manager"),
    path("portal/dashboard/driver/", DriverDashboardView.as_view(), name="dashboard-driver"),
    path("portal/dashboard/client/", ClientDashboardView.as_view(), name="dashboard-client"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password/change-required/", ForcePasswordChangeView.as_view(), name="password-change-required"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/export/pdf/", UserPdfExportView.as_view(), name="user-export-pdf"),
    path("users/export/excel/", UserExcelExportView.as_view(), name="user-export-excel"),
    path("users/create/", UserCreateView.as_view(), name="user-create"),
    path("users/<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/edit/", UserUpdateView.as_view(), name="user-update"),
    path("users/<uuid:pk>/toggle-active/", UserToggleActiveView.as_view(), name="user-toggle-active"),
    path("users/<uuid:pk>/reset-password/", UserPasswordResetTriggerView.as_view(), name="user-reset-password"),
    path("users/<uuid:pk>/delete/", UserDeleteView.as_view(), name="user-delete"),
    
    # Role and Permission Management
    path("roles/", RoleManagementView.as_view(), name="role-management"),
    path("users/<uuid:pk>/role/", UserRoleUpdateView.as_view(), name="user-role-update"),
    path("permissions/", PermissionManagementView.as_view(), name="permission-management"),
    
    # Activity Logs
    path("activity-logs/", ActivityLogView.as_view(), name="activity-logs"),
    
    # System Settings
    path("settings/", SystemSettingsView.as_view(), name="system-settings"),
    
    # API
    path("exchange-rates/", exchange_rates_api, name="exchange-rates"),
    
    path("password/reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password/reset/done/", PasswordResetVerifyView.as_view(), name="password_reset_done"),
    path("password/reset/verify/", PasswordResetVerifyView.as_view(), name="password_reset_verify"),
    path("password/reset/confirm/", PasswordResetNewPasswordView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", PasswordResetCompleteStepView.as_view(), name="password_reset_complete"),
]
