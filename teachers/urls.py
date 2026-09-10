from django.urls import path
from . import views
from . import class_teacher_views

app_name = 'teachers'

urlpatterns = [
    # Teacher URLs
    path('', views.teacher_list, name='list'),
    path('<int:teacher_id>/', views.teacher_detail, name='detail'),
    path('<int:teacher_id>/edit/', views.teacher_edit, name='edit'),
    path('<int:teacher_id>/assign/', views.teacher_assign, name='assign'),
    path('assignments/<int:assignment_id>/delete/', views.teacher_assignment_delete, name='assignment_delete'),
    path('requests/', views.teacher_requests, name='requests'),
    path('requests/create/', views.teacher_request_create, name='request_create'),
    path('api/search/', views.api_teachers_search, name='api_search'),
    
    # Class Teacher URLs
    path('class-teachers/', class_teacher_views.class_teacher_list, name='class_teacher_list'),
    path('class-teachers/create/', class_teacher_views.class_teacher_create, name='class_teacher_create'),
    path('class-teachers/<int:class_teacher_id>/edit/', class_teacher_views.class_teacher_edit, name='class_teacher_edit'),
    path('class-teachers/<int:class_teacher_id>/delete/', class_teacher_views.class_teacher_delete, name='class_teacher_delete'),
    path('api/class-teacher/', class_teacher_views.class_teacher_by_class, name='api_class_teacher'),

    # Class Teacher Request Workflow
    path('class-teachers/requests/', class_teacher_views.class_teacher_request_list, name='class_teacher_requests'),
    path('class-teachers/requests/create/', class_teacher_views.class_teacher_request_create, name='class_teacher_request_create'),
    path('class-teachers/requests/<int:request_id>/review/', class_teacher_views.class_teacher_request_review, name='class_teacher_request_review'),

    # Teacher self-service
    path('request-approval/', views.teacher_request_approval, name='request_approval'),
]
