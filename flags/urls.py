from django.urls import path   
from . import views                 
urlpatterns = [
    path('', views.home, name='home'), 
    path('feature/status/<str:feature_name>/', views.is_feature_active, name='is_feature_active'), 
    path('feature/<str:feature_name>/', views.feature_status, name='feature_status'),
]
