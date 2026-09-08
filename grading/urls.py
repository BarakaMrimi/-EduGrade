from django.urls import path
from . import views

app_name = 'grading'

urlpatterns = [
    path('process/', views.process_marks, name='process'),
    path('class-report/', views.class_report, name='class_report'),
    path('student-report/<int:student_id>/', views.student_report, name='student_report'),
    path('systems/', views.grading_system_list, name='systems'),
]
