from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from school.models import AcademicYear, Term, Curriculum, GradeLevel, Stream, Subject
from django.contrib.auth.models import User

@login_required
def school_setup_dashboard(request):
    "School setup main dashboard"
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Only administrators can access school setup!')
        return redirect('core:dashboard')
    
    context = {
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'terms': Term.objects.select_related('academic_year').all(),
        'curriculums': Curriculum.objects.all(),
        'grade_levels': GradeLevel.objects.select_related('curriculum').all(),
        'streams': Stream.objects.select_related('grade_level').all(),
        'subjects': Subject.objects.select_related('curriculum').all(),
        'total_years': AcademicYear.objects.count(),
        'total_terms': Term.objects.count(),
        'total_curriculums': Curriculum.objects.count(),
        'total_grades': GradeLevel.objects.count(),
        'total_streams': Stream.objects.count(),
        'total_subjects': Subject.objects.count(),
    }
    return render(request, 'school/setup_dashboard.html', context)


# ============================================
# ACADEMIC YEAR CRUD
# ============================================
@login_required
def academic_year_list(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    years = AcademicYear.objects.all().order_by('-year')
    data = [{
        'id': y.id,
        'year': y.year,
        'name': y.name,
        'start_date': y.start_date.strftime('%Y-%m-%d'),
        'end_date': y.end_date.strftime('%Y-%m-%d'),
        'is_current': y.is_current
    } for y in years]
    return JsonResponse({'years': data})


@login_required
def academic_year_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    if request.method == 'POST':
        try:
            year = request.POST.get('year')
            name = request.POST.get('name')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            is_current = request.POST.get('is_current') == 'on'
            
            if is_current:
                AcademicYear.objects.filter(is_current=True).update(is_current=False)
            
            academic_year = AcademicYear.objects.create(
                year=year,
                name=name,
                start_date=start_date,
                end_date=end_date,
                is_current=is_current
            )
            
            messages.success(request, f'Academic Year {year} created successfully!')
            return redirect('school:setup_dashboard')
        except Exception as e:
            messages.error(request, f'Error creating academic year: {str(e)}')
            return redirect('school:setup_dashboard')
    
    return redirect('school:setup_dashboard')


@login_required
def academic_year_edit(request, year_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    
    if request.method == 'POST':
        try:
            academic_year.year = request.POST.get('year')
            academic_year.name = request.POST.get('name')
            academic_year.start_date = request.POST.get('start_date')
            academic_year.end_date = request.POST.get('end_date')
            is_current = request.POST.get('is_current') == 'on'
            
            if is_current:
                AcademicYear.objects.filter(is_current=True).update(is_current=False)
                academic_year.is_current = True
            else:
                academic_year.is_current = False
            
            academic_year.save()
            messages.success(request, 'Academic Year updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating academic year: {str(e)}')
        
        return redirect('school:setup_dashboard')
    
    context = {'year': academic_year}
    return render(request, 'school/setup_dashboard.html', context)


@login_required
def academic_year_delete(request, year_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    academic_year = get_object_or_404(AcademicYear, id=year_id)
    
    if request.method == 'POST':
        year_name = str(academic_year.year)
        academic_year.delete()
        messages.success(request, f'Academic Year {year_name} deleted successfully!')
        return redirect('school:setup_dashboard')
    
    context = {'year': academic_year}
    return render(request, 'school/setup_dashboard.html', context)


# ============================================
# GRADE LEVEL CRUD
# ============================================
@login_required
def grade_level_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    if request.method == 'POST':
        try:
            curriculum_id = request.POST.get('curriculum')
            level_type = request.POST.get('level_type')
            level_number = request.POST.get('level_number')
            name = request.POST.get('name')
            order = request.POST.get('order', 0)
            
            curriculum = get_object_or_404(Curriculum, id=curriculum_id)
            
            grade_level = GradeLevel.objects.create(
                curriculum=curriculum,
                level_type=level_type,
                level_number=level_number,
                name=name,
                order=order,
                is_active=True
            )
            
            messages.success(request, f'Grade Level {name} created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating grade level: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def grade_level_edit(request, grade_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    grade = get_object_or_404(GradeLevel, id=grade_id)
    
    if request.method == 'POST':
        try:
            grade.curriculum_id = request.POST.get('curriculum')
            grade.level_type = request.POST.get('level_type')
            grade.level_number = request.POST.get('level_number')
            grade.name = request.POST.get('name')
            grade.order = request.POST.get('order', 0)
            grade.is_active = request.POST.get('is_active') == 'on'
            grade.save()
            
            messages.success(request, 'Grade Level updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating grade level: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def grade_level_delete(request, grade_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    grade = get_object_or_404(GradeLevel, id=grade_id)
    
    if request.method == 'POST':
        grade_name = grade.name
        grade.delete()
        messages.success(request, f'Grade Level {grade_name} deleted successfully!')
        return redirect('school:setup_dashboard')


# ============================================
# STREAM CRUD
# ============================================
@login_required
def stream_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    if request.method == 'POST':
        try:
            grade_level_id = request.POST.get('grade_level')
            name = request.POST.get('name')
            code = request.POST.get('code')
            capacity = request.POST.get('capacity', 40)
            
            grade_level = get_object_or_404(GradeLevel, id=grade_level_id)
            
            stream = Stream.objects.create(
                grade_level=grade_level,
                name=name,
                code=code,
                capacity=capacity,
                is_active=True
            )
            
            messages.success(request, f'Stream {name} created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating stream: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def stream_edit(request, stream_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    stream = get_object_or_404(Stream, id=stream_id)
    
    if request.method == 'POST':
        try:
            stream.grade_level_id = request.POST.get('grade_level')
            stream.name = request.POST.get('name')
            stream.code = request.POST.get('code')
            stream.capacity = request.POST.get('capacity', 40)
            stream.is_active = request.POST.get('is_active') == 'on'
            stream.save()
            
            messages.success(request, 'Stream updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating stream: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def stream_delete(request, stream_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    stream = get_object_or_404(Stream, id=stream_id)
    
    if request.method == 'POST':
        stream_name = stream.name
        stream.delete()
        messages.success(request, f'Stream {stream_name} deleted successfully!')
        return redirect('school:setup_dashboard')


# ============================================
# SUBJECT CRUD
# ============================================
@login_required
def subject_create(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    if request.method == 'POST':
        try:
            curriculum_id = request.POST.get('curriculum')
            code = request.POST.get('code')
            name = request.POST.get('name')
            short_name = request.POST.get('short_name')
            subject_type = request.POST.get('subject_type', 'CORE')
            
            curriculum = get_object_or_404(Curriculum, id=curriculum_id)
            
            subject = Subject.objects.create(
                curriculum=curriculum,
                code=code,
                name=name,
                short_name=short_name,
                subject_type=subject_type,
                max_score=100,
                min_score=0,
                is_active=True
            )
            
            messages.success(request, f'Subject {name} created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating subject: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def subject_edit(request, subject_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id)
    
    if request.method == 'POST':
        try:
            subject.curriculum_id = request.POST.get('curriculum')
            subject.code = request.POST.get('code')
            subject.name = request.POST.get('name')
            subject.short_name = request.POST.get('short_name')
            subject.subject_type = request.POST.get('subject_type')
            subject.is_active = request.POST.get('is_active') == 'on'
            subject.save()
            
            messages.success(request, 'Subject updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating subject: {str(e)}')
        
        return redirect('school:setup_dashboard')


@login_required
def subject_delete(request, subject_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Unauthorized!')
        return redirect('school:setup_dashboard')
    
    subject = get_object_or_404(Subject, id=subject_id)
    
    if request.method == 'POST':
        subject_name = subject.name
        subject.delete()
        messages.success(request, f'Subject {subject_name} deleted successfully!')
        return redirect('school:setup_dashboard')


# ============================================
# API ENDPOINTS FOR DYNAMIC LOADING
# ============================================
@login_required
def api_get_grade_levels(request):
    "Get grade levels by curriculum"
    curriculum_id = request.GET.get('curriculum_id')
    if curriculum_id:
        grades = GradeLevel.objects.filter(
            curriculum_id=curriculum_id,
            is_active=True
        ).values('id', 'name', 'level_number')
        return JsonResponse({'grades': list(grades)})
    return JsonResponse({'grades': []})


@login_required
def api_get_streams(request):
    "Get streams by grade level"
    grade_level_id = request.GET.get('grade_level_id')
    if grade_level_id:
        streams = Stream.objects.filter(
            grade_level_id=grade_level_id,
            is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse({'streams': list(streams)})
    return JsonResponse({'streams': []})
