from django.urls import path   
from . import views                 
urlpatterns = [
    path('', views.home, name='home'), 
    path('feature/status/<str:feature_name>/', views.is_feature_active, name='is_feature_active'), 
    path('feature/change-state/<str:feature_name>/', views.feature_status_change, name='feature_status'),
    path('feature/initialize/<str:feature_name>/', views.initialize_features, name='initialize_features'),
    path('feature/delete/<str:feature_name>/', views.delete_feature, name='delete_feature'),
    path('feature/list/', views.list_all_features, name='list_all_features'),
    path('feature/restore/<str:feature_name>/' , views.restore_feature, name='restore_feature'),
]
