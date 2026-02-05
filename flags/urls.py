from django.urls import path   
from . import views                 
urlpatterns = [
    path('', views.home, name='home'), 
    path('feature/status/<str:feature_name>/', views.is_feature_active, name='is_feature_active'), 
    path('feature/show/<str:feature_name>/', views.feature_status, name='feature_status'),
    path('feature/initialize/<str:feature_name>/', views.initialize_features, name='initialize_features'),
    path('feature/delete/<str:feature_name>/', views.delete_feature, name='delete_feature'),
    path('feature/list/', views.list_all_features, name='list_all_features'),
]
