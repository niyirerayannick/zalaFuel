from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.rbac import SystemGroup, ensure_rbac_groups


class Command(BaseCommand):
    help = "Create RBAC groups, assign permissions, and sync legacy users into the new role groups."

    def handle(self, *args, **options):
        User = get_user_model()
        ensure_rbac_groups()

        legacy_role_map = {
            User.Role.SUPERADMIN: SystemGroup.ADMIN,
            User.Role.ADMIN: SystemGroup.ADMIN,
            User.Role.MANAGER: SystemGroup.OPERATIONS_MANAGER,
            User.Role.CLIENT: SystemGroup.CUSTOMER,
        }

        synced = 0
        for user in User.objects.all():
            group_name = legacy_role_map.get(user.role)
            if not group_name:
                continue
            group = Group.objects.filter(name=group_name).first()
            if group:
                user.groups.add(group)
            synced += 1

        self.stdout.write(self.style.SUCCESS(f"RBAC groups ready. Synced {synced} users."))
