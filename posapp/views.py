from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth import authenticate
from datetime import datetime
from .models import Product, Sale, SaleItem, UserProfile
from .serializers import (
    ProductSerializer,
    ProductSyncSerializer,
    SaleSerializer,
    SaleSyncSerializer
)
from .permissions import get_business_for_request, IsInBusiness, IsAdmin


class BusinessUsersView(APIView):
    """
    GET /api/users/
    Lista usuarios del negocio (para filtro por trabajador).
    """
    permission_classes = [IsInBusiness]

    def get(self, request):
        business = get_business_for_request(request)
        if not business:
            return Response([])
        profiles = UserProfile.objects.filter(business=business).select_related('user')
        users = [
            {'id': p.user_id, 'username': p.user.username, 'role': p.role}
            for p in profiles
        ]
        return Response(users)


class LoginView(APIView):
    """
    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    Response: { "token": "...", "user": { "id", "username", "business_id", "business_name", "role" } }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response(
                {'error': 'username y password son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response(
                {'error': 'Credenciales inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        try:
            profile = user.profile
        except Exception:
            return Response(
                {'error': 'Usuario sin perfil de negocio asignado'},
                status=status.HTTP_403_FORBIDDEN
            )
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': {
                'id': user.id,
                'username': user.username,
                'business_id': profile.business_id,
                'business_name': profile.business.name,
                'role': profile.role,
            },
        })


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Product. Solo productos del negocio del usuario.
    """
    serializer_class = ProductSerializer
    lookup_field = 'id'
    permission_classes = [IsInBusiness]

    def get_queryset(self):
        business = get_business_for_request(self.request)
        if not business:
            return Product.objects.none()
        queryset = Product.objects.filter(active=True, business=business)

        updated_after = self.request.query_params.get('updated_after', None)
        if updated_after:
            try:
                # Intenta parsear como timestamp ISO 8601
                if 'T' in updated_after or '+' in updated_after:
                    updated_after_dt = datetime.fromisoformat(updated_after.replace('Z', '+00:00'))
                else:
                    # Intenta parsear como timestamp Unix
                    updated_after_dt = datetime.fromtimestamp(float(updated_after))
                    updated_after_dt = timezone.make_aware(updated_after_dt)
                
                queryset = queryset.filter(updated_at__gte=updated_after_dt)
            except (ValueError, TypeError) as e:
                # Si falla el parseo, retorna todos los productos activos
                pass
        
        return queryset.order_by('-updated_at')

    def list(self, request, *args, **kwargs):
        """
        Lista productos con soporte para sincronización incremental.
        
        Query params:
        - updated_after: Timestamp ISO 8601 o Unix timestamp
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        response_data = {
            'count': queryset.count(),
            'results': serializer.data,
            'sync_timestamp': timezone.now().isoformat()
        }
        
        return Response(response_data)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: marca el producto como inactivo en lugar de eliminarlo.
        """
        instance = self.get_object()
        instance.active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SaleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Sale. Solo ventas del negocio del usuario.
    Admin puede ver inactivas con ?include_inactive=true
    """
    serializer_class = SaleSerializer
    lookup_field = 'uuid'
    permission_classes = [IsInBusiness]

    def get_queryset(self):
        business = get_business_for_request(self.request)
        if not business:
            return Sale.objects.none()
        qs = Sale.objects.filter(business=business, pending_approval=False)
        include_inactive = self.request.query_params.get('include_inactive', '').lower() == 'true'
        is_admin = hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'admin'
        if not (include_inactive and is_admin):
            qs = qs.filter(active=True)
        if hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'worker':
            qs = qs.filter(created_by=self.request.user)
        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, uuid=None):
        """Reactivar venta inactiva (solo admin)."""
        if not (hasattr(request.user, 'profile') and request.user.profile.role == 'admin'):
            return Response({'error': 'Solo administradores pueden reactivar ventas'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            sale = Sale.objects.get(uuid=uuid, business=get_business_for_request(request))
        except Sale.DoesNotExist:
            return Response({'error': 'Venta no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        if sale.active:
            return Response({'message': 'La venta ya está activa'}, status=status.HTTP_200_OK)
        sale.active = True
        sale.save()
        serializer = SaleSerializer(sale)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: marca la venta como inactiva y restaura el stock.
        """
        instance = self.get_object()
        for item in instance.items.all():
            product = item.product
            product.stock += item.quantity
            product.save()
        instance.active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PendingSalesView(APIView):
    """
    GET /api/pending-sales/
    Resumen agregado por producto: cantidad inicial, vendida y final.
    Agrupa todas las ventas pendientes y suma cantidades por producto.
    """
    permission_classes = [IsInBusiness, IsAdmin]

    def get(self, request):
        business = get_business_for_request(request)
        if not business:
            return Response({'products': [], 'total': 0})
        sales = Sale.objects.filter(
            active=True,
            business=business,
            pending_approval=True
        ).prefetch_related('items__product')
        # Agregar por producto: { product_id: { product, quantity_sold, partial_amount } }
        agg = {}
        total_amount = 0
        for sale in sales:
            total_amount += float(sale.total)
            for item in sale.items.all():
                p = item.product
                pid = p.local_id
                if pid not in agg:
                    agg[pid] = {
                        'product': p,
                        'quantity_sold': 0,
                        'partial_amount': 0,
                    }
                agg[pid]['quantity_sold'] += item.quantity
                agg[pid]['partial_amount'] += float(item.total_price)
        products = []
        for pid, data in agg.items():
            p = data['product']
            products.append({
                'product_id': p.local_id,
                'product_name': p.name,
                'quantity_sold': data['quantity_sold'],
                'partial_amount': data['partial_amount'],
            })
        return Response({'products': products, 'total': total_amount})


class ApproveAllPendingView(APIView):
    """
    POST /api/pending-sales/approve-all/
    Aprueba todas las ventas pendientes. El stock se gestiona en el dispositivo (SQLite).
    """
    permission_classes = [IsInBusiness, IsAdmin]

    def post(self, request):
        business = get_business_for_request(request)
        if not business:
            return Response(
                {'error': 'Sin negocio'},
                status=status.HTTP_403_FORBIDDEN,
            )
        sales = list(Sale.objects.filter(
            active=True,
            business=business,
            pending_approval=True,
        ))
        # Al aprobar, ahora sí aplicamos el descuento de stock en el servidor.
        for sale in sales:
            for item in sale.items.all():
                product = item.product
                if product.stock >= item.quantity:
                    product.stock -= item.quantity
                    product.save()
                else:
                    return Response(
                        {'error': f'Stock insuficiente para {product.name}'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        for sale in sales:
            sale.pending_approval = False
            sale.save()
        return Response({'success': True, 'approved_count': len(sales)})


class RejectAllPendingView(APIView):
    """
    POST /api/pending-sales/reject-all/
    Rechaza todas las ventas pendientes (soft delete). El stock se restaura en el dispositivo (SQLite).
    """
    permission_classes = [IsInBusiness, IsAdmin]

    def post(self, request):
        business = get_business_for_request(request)
        if not business:
            return Response(
                {'error': 'Sin negocio'},
                status=status.HTTP_403_FORBIDDEN,
            )
        sales = list(Sale.objects.filter(
            active=True,
            business=business,
            pending_approval=True,
        ))
        uuids = [str(s.uuid) for s in sales]
        Sale.objects.filter(
            active=True,
            business=business,
            pending_approval=True,
        ).update(active=False)
        return Response({
            'success': True,
            'rejected_count': len(sales),
            'rejected_uuids': uuids,
        })


class ApproveSaleView(APIView):
    """
    POST /api/pending-sales/<uuid>/approve/
    Aprueba una venta pendiente: reduce stock y quita pending_approval.
    Solo admin.
    """
    permission_classes = [IsInBusiness, IsAdmin]

    def post(self, request, uuid):
        business = get_business_for_request(request)
        if not business:
            return Response(
                {'error': 'Sin negocio'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            sale = Sale.objects.get(
                uuid=uuid,
                business=business,
                pending_approval=True,
                active=True,
            )
        except Sale.DoesNotExist:
            return Response(
                {'error': 'Venta no encontrada o ya aprobada'},
                status=status.HTTP_404_NOT_FOUND,
            )
        for item in sale.items.all():
            product = item.product
            if product.stock >= item.quantity:
                product.stock -= item.quantity
                product.save()
            else:
                return Response(
                    {'error': f'Stock insuficiente para {product.name}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        sale.pending_approval = False
        sale.save()
        return Response({'success': True}, status=status.HTTP_200_OK)


class RejectSaleView(APIView):
    """
    POST /api/pending-sales/<uuid>/reject/
    Rechaza una venta pendiente (soft delete). Solo admin.
    """
    permission_classes = [IsInBusiness, IsAdmin]

    def post(self, request, uuid):
        business = get_business_for_request(request)
        if not business:
            return Response(
                {'error': 'Sin negocio'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            sale = Sale.objects.get(
                uuid=uuid,
                business=business,
                pending_approval=True,
                active=True,
            )
        except Sale.DoesNotExist:
            return Response(
                {'error': 'Venta no encontrada o ya procesada'},
                status=status.HTTP_404_NOT_FOUND,
            )
        sale.active = False
        sale.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductSyncView(APIView):
    """
    Vista para sincronizar productos desde el dispositivo (push).
    POST /api/sync/products/
    Body: { "products": [{ "id": 1, "name": "...", "price": 10, "stock": 5, "updated_at": "...", ... }] }
    El id es el id local del dispositivo. Se usa (business_id, id) como clave única.
    """
    permission_classes = [IsInBusiness]

    def post(self, request):
        serializer = ProductSyncSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = serializer.save()
            return Response(
                {
                    'success': True,
                    'synced_count': len(result['products']),
                    'sync_timestamp': timezone.now().isoformat(),
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SaleSyncView(APIView):
    """
    Vista para sincronizar ventas desde el dispositivo. Asigna al negocio del usuario.
    POST /api/sync/sales/
    
    Body:
    {
        "sales": [
            {
                "uuid": "uuid-de-la-venta",
                "total": 100.00,
                "items_data": [
                    {
                        "product_id": 1,
                        "quantity": 2,
                        "total_price": 50.00
                    }
                ]
            }
        ]
    }
    
    Response:
    {
        "success": true,
        "synced_count": 1,
        "sales": [...]
    }
    """
    
    permission_classes = [IsInBusiness]

    def post(self, request):
        """
        Recibe ventas desde el dispositivo y las sincroniza al negocio del usuario.
        """
        serializer = SaleSyncSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'errors': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = serializer.save()
            synced_sales = result['sales']
            # Importante:
            # - Si la venta viene de un trabajador, queda pending_approval=True y NO descuenta stock aquí.
            # - Si la venta viene de un admin, el descuento se aplica en el serializer (venta aprobada).
            return Response(
                {
                    'success': True,
                    'synced_count': len(synced_sales),
                    'sales': SaleSerializer(synced_sales, many=True).data,
                    'sync_timestamp': timezone.now().isoformat()
                },
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'error': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
