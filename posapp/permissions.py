from rest_framework import permissions


def get_business_for_request(request):
    """Obtiene el negocio del usuario autenticado. None si no tiene perfil."""
    if not request.user or not request.user.is_authenticated:
        return None
    try:
        return request.user.profile.business
    except Exception:
        return None


class IsInBusiness(permissions.BasePermission):
    """
    Solo permite acceso a usuarios autenticados con perfil en un negocio.
    Las vistas deben filtrar el queryset por request.user.profile.business.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return hasattr(request.user, 'profile') and request.user.profile.business_id is not None
        except Exception:
            return False


class IsAdmin(permissions.BasePermission):
    """Solo administradores del negocio."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            return (
                hasattr(request.user, 'profile')
                and request.user.profile.role == 'admin'
            )
        except Exception:
            return False
