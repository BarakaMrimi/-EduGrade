from django.urls import path
from . import views

app_name = 'examinations'

urlpatterns = [
    path('', views.exam_list, name='list'),
    path('create/', views.exam_create, name='create'),
    path('<int:exam_id>/', views.exam_detail, name='detail'),
    path('<int:exam_id>/analysis/', views.exam_analysis, name='analysis'),
    path('<int:exam_id>/edit/', views.exam_edit, name='edit'),
    path('<int:exam_id>/delete/', views.exam_delete, name='delete'),
    path('<int:exam_id>/change-status/', views.exam_change_status, name='change_status'),
    path('api/subjects/', views.api_get_subjects, name='api_subjects'),
    path('api/terms/', views.api_get_terms, name='api_terms'),
]
