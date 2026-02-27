import base64
import uuid
from io import BytesIO
from django.core.files.base import ContentFile
from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from datetime import datetime
from .models import Business, Product, Sale, SaleItem


class ProductSyncItemSerializer(serializers.Serializer):
    """
    Serializer para sincronización de productos desde el dispositivo.
    Acepta id del cliente (local), que se mapea a local_id en el modelo.
    business_id viene del usuario autenticado.
    """
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    qr_code = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    stock = serializers.IntegerField(min_value=0)
    updated_at = serializers.DateTimeField()
    active = serializers.BooleanField(default=True, required=False)
    image_base64 = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value


class ProductSyncSerializer(serializers.Serializer):
    """Serializer para sincronización de productos (push desde dispositivo)."""
    products = ProductSyncItemSerializer(many=True)

    def validate_products(self, value):
        if not value:
            raise serializers.ValidationError("Debe enviar al menos un producto")
        return value

    def create(self, validated_data):
        request = self.context['request']
        business_id = request.user.profile.business_id
        if not business_id:
            raise serializers.ValidationError("Usuario sin negocio asignado")

        synced = []
        for item in validated_data['products']:
            image_base64 = item.pop('image_base64', None)
            # id recibido desde el dispositivo es el id local; lo usamos como local_id
            local_id = item.pop('id')
            qr_val = item.get('qr_code')
            qr_final = (qr_val or '').strip() or None
            product, created = Product.objects.update_or_create(
                business_id=business_id,
                local_id=local_id,
                defaults={
                    'name': item['name'],
                    'description': (item.get('description') or '').strip() or None,
                    'qr_code': qr_final,
                    'price': item['price'],
                    'stock': item['stock'],
                    'updated_at': item['updated_at'],
                    'active': item.get('active', True),
                }
            )
            if image_base64 and image_base64.strip():
                try:
                    data = base64.b64decode(image_base64)
                    if data:
                        ext = 'jpg'
                        product.image.save(f'{uuid.uuid4().hex}.{ext}', ContentFile(data), save=True)
                except Exception:
                    pass
            synced.append(product)
        return {'products': synced}


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer para Product. Incluye negocio, imagen (URL) y campos de sync.
    """
    image_url = serializers.SerializerMethodField()
    business_id = serializers.IntegerField(read_only=True)
    local_id = serializers.IntegerField()

    class Meta:
        model = Product
        fields = [
            'id',
            'local_id',
            'business_id',
            'name',
            'description',
            'qr_code',
            'image',
            'image_url',
            'price',
            'stock',
            'updated_at',
            'active',
        ]
        read_only_fields = ['id', 'updated_at', 'business_id']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("El stock no puede ser negativo")
        return value

    def create(self, validated_data):
        validated_data['business_id'] = self.context['request'].user.profile.business_id
        return super().create(validated_data)


class SaleItemSerializer(serializers.ModelSerializer):
    """
    Serializer para SaleItem.
    Incluye información del producto relacionado.
    """
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            'product',
            'product_id',
            'product_name',
            'quantity',
            'total_price'
        ]

    def validate_quantity(self, value):
        """Valida que la cantidad sea mayor a 0"""
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor a 0")
        return value

    def validate_total_price(self, value):
        """Valida que el precio total sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El precio total debe ser mayor a 0")
        return value


class SaleItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear SaleItem. Valida que el producto pertenezca al negocio.
    """
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = SaleItem
        fields = ['product_id', 'quantity', 'total_price']

    def validate_product_id(self, value):
        request = self.context.get('request')
        business_id = request and getattr(request.user.profile, 'business_id', None)
        if not business_id:
            raise serializers.ValidationError("Usuario sin negocio asignado")
        try:
            # value viene desde el dispositivo y representa el ID local del producto.
            # En el servidor se mapea contra Product.local_id, no contra el UUID (PK).
            product = Product.objects.get(local_id=value, active=True, business_id=business_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError(
                f"Producto con local_id {value} no existe, está inactivo o no pertenece a su negocio"
            )
        return value


class SaleSerializer(serializers.ModelSerializer):
    """
    Serializer para Sale. Incluye negocio (solo lectura) e items.
    """
    items = SaleItemSerializer(many=True, read_only=True)
    items_data = SaleItemCreateSerializer(many=True, write_only=True, required=False)
    business_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'uuid',
            'business_id',
            'total',
            'created_at',
            'updated_at',
            'synced_from_device',
            'active',
            'items',
            'items_data',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at', 'business_id']

    def validate_total(self, value):
        """Valida que el total sea positivo"""
        if value <= 0:
            raise serializers.ValidationError("El total debe ser mayor a 0")
        return value

    def validate(self, attrs):
        """Valida que la suma de items coincida con el total"""
        items_data = attrs.get('items_data', [])
        if items_data:
            calculated_total = sum(item['total_price'] for item in items_data)
            if abs(calculated_total - attrs['total']) > 0.01:  # Tolerancia para decimales
                raise serializers.ValidationError(
                    f"El total ({attrs['total']}) no coincide con la suma de items ({calculated_total})"
                )
        return attrs

    def create(self, validated_data):
        """Crea la venta con sus items. business se setea desde el contexto."""
        items_data = validated_data.pop('items_data', [])
        request = self.context.get('request')
        business_id = request and request.user.profile.business_id
        if not business_id:
            raise serializers.ValidationError("Usuario sin negocio asignado")
        validated_data['business_id'] = business_id
        sale = Sale.objects.create(**validated_data)

        for item_data in items_data:
            product_id = item_data.pop('product_id')
            # product_id viene del dispositivo y representa el ID local;
            # lo mapeamos contra Product.local_id.
            product = Product.objects.get(local_id=product_id, business_id=business_id)
            SaleItem.objects.create(sale=sale, product=product, **item_data)

        return sale


class SaleSyncItemSerializer(serializers.Serializer):
    """
    Item de venta para sync. Acepta uuid del dispositivo para evitar duplicados.
    """
    uuid = serializers.UUIDField()
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    items_data = SaleItemCreateSerializer(many=True)

    def validate_total(self, value):
        if value <= 0:
            raise serializers.ValidationError("El total debe ser mayor a 0")
        return value


class SaleSyncSerializer(serializers.Serializer):
    """
    Serializer para sincronización de ventas desde el dispositivo.
    Usa el uuid del cliente para evitar duplicados (update_or_create).
    """
    sales = SaleSyncItemSerializer(many=True)

    def validate_sales(self, value):
        if not value:
            raise serializers.ValidationError("Debe enviar al menos una venta")
        return value

    def create(self, validated_data):
        import uuid as uuid_module
        sales_data = validated_data['sales']
        request = self.context['request']
        business_id = request.user.profile.business_id
        if not business_id:
            raise serializers.ValidationError("Usuario sin negocio asignado")

        synced_sales = []
        is_worker = request.user.profile.role == 'worker'
        for sale_data in sales_data:
            sale_uuid = uuid_module.UUID(str(sale_data['uuid']))
            items_data = sale_data['items_data']
            sale, created = Sale.objects.update_or_create(
                uuid=sale_uuid,
                business_id=business_id,
                defaults={
                    'total': sale_data['total'],
                    'synced_from_device': True,
                    'active': True,
                    'created_by': request.user,
                    'pending_approval': is_worker,
                }
            )
            if created:
                for item_data in items_data:
                    product_id = item_data.pop('product_id')
                    # product_id viene del dispositivo y es el ID local;
                    # en el servidor usamos Product.local_id como mediador.
                    product = Product.objects.get(local_id=product_id, business_id=business_id)
                    SaleItem.objects.create(sale=sale, product=product, **item_data)
                # Solo reducir stock si es admin (venta aprobada directamente)
                if not is_worker:
                    for item in sale.items.all():
                        p = item.product
                        if p.stock >= item.quantity:
                            p.stock -= item.quantity
                            p.save()
            synced_sales.append(sale)
        return {'sales': synced_sales}
