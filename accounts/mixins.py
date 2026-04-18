from .rbac import RBACRequiredMixin, SystemGroup


class RoleRequiredMixin(RBACRequiredMixin):
    allowed_roles = ()


class SuperAdminMixin(RoleRequiredMixin):
    allowed_roles = (SystemGroup.ADMIN,)


class AdminMixin(RoleRequiredMixin):
    allowed_roles = (SystemGroup.ADMIN,)


class ManagerMixin(RoleRequiredMixin):
    allowed_roles = (SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR)


class DriverMixin(RoleRequiredMixin):
    allowed_roles = (SystemGroup.PUMP_ATTENDANT,)


class ClientMixin(RoleRequiredMixin):
    allowed_roles = (SystemGroup.CUSTOMER,)


class OperationsRoleMixin(RBACRequiredMixin):
    """POS, shifts, station equipment visibility, operational APIs."""

    allowed_roles = (
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.PUMP_ATTENDANT,
    )


class OperationsManageMixin(RBACRequiredMixin):
    """Inventory, supplier receiving, tank configuration — supervisor-level and above."""

    allowed_roles = (
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
    )


class FinanceRoleMixin(RBACRequiredMixin):
    allowed_roles = (
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.ACCOUNTANT,
    )


class ReportsRoleMixin(RBACRequiredMixin):
    allowed_roles = (
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.ACCOUNTANT,
    )
