from django import template

from accounts.rbac import (
    SystemGroup,
    can_access_finance,
    can_access_fuel,
    can_access_operations,
    can_access_reports,
    can_access_settings,
    can_manage_finance,
    can_manage_fuel,
    can_manage_operations,
    user_has_role,
)

register = template.Library()


@register.filter
def has_group(user, group_name):
    return user_has_role(user, group_name)


@register.simple_tag
def is_operations_user(user):
    return user_has_role(user, *SystemGroup.OPERATIONS)


@register.simple_tag
def is_finance_user(user):
    return user_has_role(user, SystemGroup.ACCOUNTANT, SystemGroup.ADMIN)


@register.simple_tag
def can_view_operations(user):
    return can_access_operations(user)


@register.simple_tag
def can_edit_operations(user):
    return can_manage_operations(user)


@register.simple_tag
def can_view_fuel(user):
    return can_access_fuel(user)


@register.simple_tag
def can_edit_fuel(user):
    return can_manage_fuel(user)


@register.simple_tag
def can_view_finance(user):
    return can_access_finance(user)


@register.simple_tag
def can_edit_finance(user):
    return can_manage_finance(user)


@register.simple_tag
def can_view_reports(user):
    return can_access_reports(user)


@register.simple_tag
def can_view_settings(user):
    return can_access_settings(user)
