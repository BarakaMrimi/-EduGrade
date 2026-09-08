from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_dashboard, name='dashboard'),
    path('list/', views.report_list, name='list'),
    path('student/<int:student_id>/', views.generate_student_report, name='student_report'),
    path('class/', views.generate_class_report, name='class_report'),
    path('school/', views.school_report, name='school_report'),
    path('<int:report_id>/', views.report_detail, name='detail'),
    path('<int:report_id>/word/', views.generate_word_report, name='word_report'),
    path('<int:report_id>/approve/', views.report_approve, name='approve'),
    path('<int:report_id>/publish/', views.report_publish, name='publish'),
]