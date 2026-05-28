from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'jobs', views.IngestionJobViewSet)
router.register(r'records', views.EmissionRecordViewSet)
router.register(r'organizations', views.OrganizationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('ingest/', views.IngestFileView.as_view(), name='ingest-file'),
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
]
