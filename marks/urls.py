from django.urls import path
from . import views

app_name = 'marks'

urlpatterns = [
    path('entry/', views.mark_entry, name='entry'),
    path('view/', views.mark_view, name='view'),
    path('correction/', views.mark_correction, name='correction'),
    path('api/classes/', views.api_get_classes, name='api_classes'),
]
