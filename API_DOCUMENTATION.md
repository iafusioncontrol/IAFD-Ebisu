# API Documentation - POS App Backend

## Descripción

Backend Django + Django REST Framework para aplicación POS offline-first. Diseñado para sincronización incremental basada en `updated_at`.

## Instalación

1. Instalar dependencias:
```bash
pip install django djangorestframework psycopg2-binary
```

2. Crear migraciones:
```bash
python manage.py makemigrations
python manage.py migrate
```

3. Crear superusuario:
```bash
python manage.py createsuperuser
```

4. Ejecutar servidor:
```bash
python manage.py runserver
```

## Endpoints de la API

### Base URL
```
http://localhost:8000/api/
```

---

## Productos

### Listar productos (con sincronización incremental)
```
GET /api/products/
GET /api/products/?updated_after=2024-01-01T00:00:00Z
```

**Query Parameters:**
- `updated_after` (opcional): Timestamp ISO 8601 o Unix timestamp. Filtra productos actualizados después de esta fecha.

**Response:**
```json
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "name": "Producto Ejemplo",
      "description": "Descripción del producto",
      "qr_code": "QR123456",
      "price": "99.99",
      "stock": 50,
      "updated_at": "2024-01-15T10:30:00Z",
      "active": true
    }
  ],
  "sync_timestamp": "2024-01-15T10:35:00Z"
}
```

### Obtener producto específico
```
GET /api/products/{id}/
```

### Crear producto (Admin)
```
POST /api/products/
```

**Body:**
```json
{
  "name": "Nuevo Producto",
  "description": "Descripción",
  "qr_code": "QR789",
  "price": "49.99",
  "stock": 100,
  "active": true
}
```

### Actualizar producto (Admin)
```
PUT /api/products/{id}/
PATCH /api/products/{id}/
```

### Eliminar producto (Soft Delete)
```
DELETE /api/products/{id}/
```

---

## Ventas

### Listar ventas
```
GET /api/sales/
```

**Response:**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "total": "150.00",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z",
      "synced_from_device": false,
      "active": true,
      "items": [
        {
          "product": 1,
          "product_id": 1,
          "product_name": "Producto Ejemplo",
          "quantity": 2,
          "total_price": "99.98"
        }
      ]
    }
  ]
}
```

### Obtener venta específica
```
GET /api/sales/{uuid}/
```

### Crear venta (Admin)
```
POST /api/sales/
```

**Body:**
```json
{
  "total": "150.00",
  "items_data": [
    {
      "product_id": 1,
      "quantity": 2,
      "total_price": "99.98"
    },
    {
      "product_id": 2,
      "quantity": 1,
      "total_price": "50.02"
    }
  ]
}
```

---

## Sincronización

### Sincronizar ventas desde dispositivo
```
POST /api/sync/sales/
```

**Body:**
```json
{
  "sales": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "total": "150.00",
      "items_data": [
        {
          "product_id": 1,
          "quantity": 2,
          "total_price": "99.98"
        }
      ]
    }
  ]
}
```

**Response (Éxito):**
```json
{
  "success": true,
  "synced_count": 1,
  "sales": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "total": "150.00",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z",
      "synced_from_device": true,
      "active": true,
      "items": [...]
    }
  ],
  "sync_timestamp": "2024-01-15T10:35:00Z"
}
```

**Response (Error):**
```json
{
  "success": false,
  "errors": {
    "sales": [
      {
        "total": ["El total debe ser mayor a 0"]
      }
    ]
  }
}
```

**Notas importantes:**
- El endpoint actualiza automáticamente el stock de los productos vendidos
- Las ventas sincronizadas se marcan con `synced_from_device: true`
- Se valida que la suma de `items_data` coincida con el `total`

---

## Modelos de Datos

### Product
- `id` (AutoField): ID único del producto
- `name` (CharField): Nombre del producto
- `description` (TextField): Descripción opcional
- `qr_code` (CharField): Código QR único (opcional)
- `price` (DecimalField): Precio unitario
- `stock` (IntegerField): Cantidad disponible
- `updated_at` (DateTimeField): Última actualización (auto)
- `active` (BooleanField): Soft delete flag

### Sale
- `uuid` (UUIDField): Identificador único de la venta
- `total` (DecimalField): Total de la venta
- `created_at` (DateTimeField): Fecha de creación
- `updated_at` (DateTimeField): Última actualización
- `synced_from_device` (BooleanField): Indica si viene del dispositivo
- `active` (BooleanField): Soft delete flag

### SaleItem
- `sale` (ForeignKey): Venta relacionada
- `product` (ForeignKey): Producto vendido
- `quantity` (PositiveIntegerField): Cantidad vendida
- `total_price` (DecimalField): Precio total del item

---

## Validaciones

### Product
- Precio debe ser > 0
- Stock no puede ser negativo
- QR code debe ser único (si se proporciona)

### Sale
- Total debe ser > 0
- La suma de items debe coincidir con el total

### SaleItem
- Cantidad debe ser > 0
- Precio total debe ser > 0
- Producto debe existir y estar activo

---

## Características Offline-First

1. **Sincronización Incremental**: Usa `updated_after` para obtener solo cambios recientes
2. **Soft Delete**: Los registros se marcan como `active=false` en lugar de eliminarse
3. **Timestamps**: Todos los modelos tienen `updated_at` para tracking de cambios
4. **Batch Sync**: Permite sincronizar múltiples ventas en un solo request
5. **Validación de Stock**: Actualiza automáticamente el stock al sincronizar ventas

---

## Admin Django

Acceder a: `http://localhost:8000/admin/`

- Gestión completa de productos
- Visualización de ventas con items inline
- Filtros y búsquedas avanzadas
- Soft delete visible en el admin

---

## Próximos Pasos Recomendados

1. **Autenticación**: Implementar JWT o Token Authentication
2. **Permisos**: Configurar permisos por roles (admin, vendedor, etc.)
3. **Logging**: Agregar logs de sincronización
4. **Métricas**: Endpoint para estadísticas de sincronización
5. **Rate Limiting**: Limitar requests de sincronización
6. **Compresión**: Comprimir payloads grandes
7. **Webhooks**: Notificaciones cuando hay cambios en productos
