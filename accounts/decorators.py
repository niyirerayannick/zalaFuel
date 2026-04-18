from .rbac import SystemGroup, roles_required


def role_required(roles_list, permission=None):
    return roles_required(*roles_list, permission=permission)


def superadmin_required(view_func):
    return roles_required(SystemGroup.ADMIN)(view_func)


def admin_required(view_func):
    return roles_required(SystemGroup.ADMIN)(view_func)


def manager_required(view_func):
    return roles_required(SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR)(view_func)


def driver_required(view_func):
    return roles_required(SystemGroup.PUMP_ATTENDANT)(view_func)


def client_required(view_func):
    return roles_required(SystemGroup.CUSTOMER)(view_func)


def staff_required(view_func):
    return roles_required(*SystemGroup.STAFF)(view_func)
