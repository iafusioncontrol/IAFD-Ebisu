from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet,
    SaleViewSet,
    SaleSyncView,
    ProductSyncView,
    LoginView,
    BusinessUsersView,
    PendingSalesView,
    ApproveAllPendingView,
    RejectAllPendingView,
    ApproveSaleView,
    RejectSaleView,
)

# Router para ViewSets
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'sales', SaleViewSet, basename='sale')

app_name = 'posapp'

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('users/', BusinessUsersView.as_view(), name='business-users'),
    path('', include(router.urls)),
    path('sync/products/', ProductSyncView.as_view(), name='sync-products'),
    path('sync/sales/', SaleSyncView.as_view(), name='sync-sales'),
    path('pending-sales/', PendingSalesView.as_view(), name='pending-sales'),
    path('pending-sales/approve-all/', ApproveAllPendingView.as_view(), name='approve-all-pending'),
    path('pending-sales/reject-all/', RejectAllPendingView.as_view(), name='reject-all-pending'),
    path('pending-sales/<uuid:uuid>/approve/', ApproveSaleView.as_view(), name='approve-sale'),
    path('pending-sales/<uuid:uuid>/reject/', RejectSaleView.as_view(), name='reject-sale'),
]
