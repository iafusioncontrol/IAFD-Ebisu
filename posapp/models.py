from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
import os

def product_image_upload_to(instance, filename):
    # Obtener extensión
    ext = filename.split('.')[-1]

    # Limpiar nombre del negocio (opcional pero recomendado)
    business_name = instance.business.name.replace(" ", "_")

    # Crear nombre final
    filename = f"{instance.name}.{ext}"

    return os.path.join('products', business_name, filename)


class Business(models.Model):
    """
    Negocio / tienda. Cada negocio tiene sus propios productos y ventas.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name="Nombre del negocio")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'businesses'
        verbose_name = 'Negocio'
        verbose_name_plural = 'Negocios'

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Perfil de usuario: vincula User de Django con un negocio y un rol.
    """
    ROLE_ADMIN = 'admin'
    ROLE_WORKER = 'worker'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrador'),
        (ROLE_WORKER, 'Trabajador'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        primary_key=True,
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='users',
        verbose_name="Negocio",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_WORKER,
        db_index=True,
    )

    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f"{self.user.username} ({self.business.name})"

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN


class Product(models.Model):
    """
    Modelo para productos del inventario.
    Pertenece a un negocio. Incluye imagen y campos de sincronización.
    """
    server_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        primary_key=True,
        verbose_name="ID del servidor",
        help_text="Identificador único del producto en el servidor",
    )
    id = models.PositiveIntegerField()
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Negocio",
        db_index=True,
    )
    name = models.CharField(max_length=255, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    qr_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Código QR",
        help_text="Código QR del producto (único por negocio)",
    )
    image = models.ImageField(
        upload_to=product_image_upload_to,
        blank=True,
        null=True,
        verbose_name="Imagen",
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Precio",
        help_text="Precio unitario del producto"
    )
    stock = models.IntegerField(
        default=0,
        verbose_name="Stock",
        help_text="Cantidad disponible en inventario"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
        db_index=True,
        help_text="Fecha y hora de última actualización"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        db_index=True,
        help_text="Indica si el producto está activo (soft delete)"
    )

    class Meta:
        db_table = 'products'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['business', 'updated_at']),
            models.Index(fields=['business', 'qr_code']),
            models.Index(fields=['active']),
        ]
        unique_together = [['business', 'qr_code'],['business', 'id']]

    def __str__(self):
        return f"{self.name} - ${self.price}"

    def save(self, *args, **kwargs):
        """Actualiza updated_at al guardar"""
        self.updated_at = timezone.now()
        
        if not self.id:
            last_product = Product.objects.filter(
                business=self.business
            ).order_by('-id').first()

            self.id = 1 if not last_product else last_product.id + 1
            
        super().save(*args, **kwargs)


class Sale(models.Model):
    """
    Modelo para ventas. Pertenece a un negocio.
    Las ventas pueden venir del dispositivo (synced_from_device=True) o del backend.
    """
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="UUID",
        help_text="Identificador único de la venta"
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='sales',
        verbose_name="Negocio",
        db_index=True,
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Total",
        help_text="Total de la venta"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Creado en",
        db_index=True,
        help_text="Fecha y hora de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Actualizado en",
        db_index=True,
        help_text="Fecha y hora de última actualización"
    )
    synced_from_device = models.BooleanField(
        default=False,
        verbose_name="Sincronizado desde dispositivo",
        db_index=True,
        help_text="Indica si la venta fue creada en un dispositivo y sincronizada"
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        db_index=True,
        help_text="Indica si la venta está activa (soft delete)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_created',
        verbose_name="Creado por",
        help_text="Usuario que realizó la venta",
    )
    pending_approval = models.BooleanField(
        default=False,
        verbose_name="Pendiente de aprobación",
        db_index=True,
        help_text="True si fue enviada por trabajador y admin aún no la aprobó",
    )

    class Meta:
        db_table = 'sales'
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['updated_at', 'active']),
            models.Index(fields=['synced_from_device']),
            models.Index(fields=['active']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"Venta {self.uuid} - ${self.total}"

    def save(self, *args, **kwargs):
        """Actualiza updated_at al guardar"""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    """
    Modelo para items de venta.
    Relaciona productos con ventas y almacena cantidad y precio total.
    """
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Venta",
        help_text="Venta a la que pertenece este item"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sale_items',
        verbose_name="Producto",
        help_text="Producto vendido"
    )
    quantity = models.PositiveIntegerField(
        verbose_name="Cantidad",
        help_text="Cantidad de productos vendidos"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Precio Total",
        help_text="Precio total del item (quantity * product.price)"
    )

    class Meta:
        db_table = 'sale_items'
        verbose_name = 'Item de Venta'
        verbose_name_plural = 'Items de Venta'
        ordering = ['sale', 'id']
        indexes = [
            models.Index(fields=['sale']),
            models.Index(fields=['product']),
        ]
        unique_together = [['sale', 'product']]

    def __str__(self):
        return f"{self.product.name} x{self.quantity} - ${self.total_price}"

    def clean(self):
        """Valida que la cantidad sea mayor a 0"""
        from django.core.exceptions import ValidationError
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'La cantidad debe ser mayor a 0'})
        if self.total_price <= 0:
            raise ValidationError({'total_price': 'El precio total debe ser mayor a 0'})

    def save(self, *args, **kwargs):
        """Valida antes de guardar"""
        self.full_clean()
        super().save(*args, **kwargs)
