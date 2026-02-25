from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Business, UserProfile, Product, Sale, SaleItem

User = get_user_model()


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['name']


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil (negocio y rol)'


class UserAdminWithProfile(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = BaseUserAdmin.list_display + ('get_business', 'get_role')
    list_filter = BaseUserAdmin.list_filter + ('profile__business', 'profile__role')

    @admin.display(description='Empresa')
    def get_business(self, obj):
        try:
            return obj.profile.business.name
        except UserProfile.DoesNotExist:
            return '—'

    @admin.display(description='Rol')
    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return '—'


# Re-register User con inline de perfil
admin.site.unregister(User)
admin.site.register(User, UserAdminWithProfile)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'business', 'name', 'qr_code', 'price', 'stock',
        'active', 'updated_at'
    ]
    list_filter = ['active', 'business', 'updated_at']
    search_fields = ['name', 'description', 'qr_code']
    readonly_fields = ['id', 'updated_at']
    fieldsets = (
        ('Negocio', {'fields': ('business',)}),
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'qr_code', 'image')
        }),
        ('Precio e Inventario', {'fields': ('price', 'stock')}),
        ('Sincronización', {'fields': ('updated_at', 'active')}),
    )
    
    def get_queryset(self, request):
        """Muestra todos los productos, incluso los inactivos"""
        return super().get_queryset(request)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = [
        'uuid', 'business', 'total', 'synced_from_device',
        'active', 'created_at', 'updated_at'
    ]
    list_filter = ['synced_from_device', 'active', 'business', 'created_at']
    search_fields = ['uuid']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Negocio', {'fields': ('business',)}),
        ('Información de Venta', {
            'fields': ('uuid', 'total', 'synced_from_device')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Estado', {
            'fields': ('active',)
        }),
    )
    
    def get_queryset(self, request):
        """Muestra todas las ventas, incluso las inactivas"""
        return super().get_queryset(request)


class SaleItemInline(admin.TabularInline):
    """
    Inline admin para SaleItem dentro de Sale.
    """
    model = SaleItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'total_price']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        """No permite agregar items desde el admin"""
        return False


# Agregar inline a SaleAdmin
SaleAdmin.inlines = [SaleItemInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    """
    Configuración del admin para SaleItem (vista independiente).
    """
    list_display = [
        'id',
        'sale',
        'product',
        'quantity',
        'total_price'
    ]
    list_filter = ['sale__created_at', 'product']
    search_fields = ['sale__uuid', 'product__name']
    readonly_fields = ['sale', 'product', 'quantity', 'total_price']
