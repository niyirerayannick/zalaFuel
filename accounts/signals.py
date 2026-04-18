import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver

from .models import User, UserProfile
from .rbac import SystemGroup, ensure_rbac_groups, sync_user_to_system_role

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def sync_user_access_profile(sender, instance, **kwargs):
    if getattr(instance, "_syncing_access", False):
        return
    instance._syncing_access = True
    try:
        _sync_user_groups(instance)
    finally:
        instance._syncing_access = False


@receiver(post_migrate)
def ensure_groups_after_migrate(sender, **kwargs):
    ensure_rbac_groups()


def _sync_user_groups(user):
    role_map = {
        User.Role.SUPERADMIN: SystemGroup.ADMIN,
        User.Role.ADMIN: SystemGroup.ADMIN,
        User.Role.STATION_MANAGER: SystemGroup.STATION_MANAGER,
        User.Role.SUPERVISOR: SystemGroup.SUPERVISOR,
        User.Role.PUMP_ATTENDANT: SystemGroup.PUMP_ATTENDANT,
        User.Role.ACCOUNTANT: SystemGroup.ACCOUNTANT,
        User.Role.CLIENT: SystemGroup.CUSTOMER,
    }
    group_name = role_map.get(user.role)
    if not group_name:
        return
    sync_user_to_system_role(user, group_name)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    logger.info(
        "User logged in: email=%s role=%s ip=%s",
        user.email,
        user.role,
        request.META.get("REMOTE_ADDR"),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user is None:
        return
    logger.info(
        "User logged out: email=%s role=%s ip=%s",
        user.email,
        user.role,
        request.META.get("REMOTE_ADDR") if request else None,
    )
