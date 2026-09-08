from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/read/<int:notification_id>/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/read-all/', views.notification_mark_all_read, name='notification_mark_all_read'),
]
