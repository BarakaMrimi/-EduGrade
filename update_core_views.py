import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edugrade.settings')
import django
django.setup()

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from students.models import Student
from teachers.models import TeacherProfile
from examinations.models import Examination
from marks.models import MarkEntry
from grading.models import StudentKCSEGrade, StudentCBAAssessment

# Update the core views
views_content = """
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse
from students.models import Student
from teachers.models import TeacherProfile
from examinations.models import Examination
from marks.models import MarkEntry
from grading.models import StudentKCSEGrade, StudentCBAAssessment

@login_required
def dashboard(request):
    \"\"\"Main dashboard view with statistics\"\"\"
    # Get statistics
    total_students = Student.objects.count()
    students_844 = Student.objects.filter(curriculum__code='844').count()
    students_cbc = Student.objects.filter(curriculum__code='CBC').count()
    
    total_teachers = TeacherProfile.objects.count()
    active_teachers = TeacherProfile.objects.filter(status='ACTIVE', is_active=True).count()
    
    total_exams = Examination.objects.count()
    exams_844 = Examination.objects.filter(curriculum__code='844').count()
    exams_cbc = Examination.objects.filter(curriculum__code='CBC').count()
    
    total_marks = MarkEntry.objects.count()
    kcse_grades = StudentKCSEGrade.objects.count()
    cbc_assessments = StudentCBAAssessment.objects.count()
    
    # Recent items
    recent_students = Student.objects.all().order_by('-created_at')[:5]
    recent_exams = Examination.objects.all().order_by('-created_at')[:5]
    
    context = {
        'total_students': total_students,
        'students_844': students_844,
        'students_cbc': students_cbc,
        'total_teachers': total_teachers,
        'active_teachers': active_teachers,
        'total_exams': total_exams,
        'exams_844': exams_844,
        'exams_cbc': exams_cbc,
        'total_marks': total_marks,
        'kcse_grades': kcse_grades,
        'cbc_assessments': cbc_assessments,
        'recent_students': recent_students,
        'recent_exams': recent_exams,
    }
    return render(request, 'core/dashboard.html', context)


class HomeView(TemplateView):
    \"\"\"Home page view\"\"\"
    template_name = 'core/home.html'
"""

# Write the updated views
views_content | Out-File -FilePath core/views.py -Encoding UTF8
Write-Host "✅ Updated core/views.py with statistics" -ForegroundColor Green
