from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Student, StudentHistory
from school.models import AcademicYear, Curriculum, GradeLevel, Stream
from django.contrib.auth.models import User
from datetime import datetime
from core.access import can_manage_student, can_use_class, permitted_student_queryset, can_edit_student
from teachers.models import ClassTeacher, TeacherProfile

try:
    from grading.models import (
        StudentKCSEGrade,
        StudentOverallKCSE,
        StudentCBAAssessment,
        StudentOverallCBA,
    )
except ImportError:
    StudentKCSEGrade = None
    StudentOverallKCSE = None
    StudentCBAAssessment = None
    StudentOverallCBA = None


def _student_exam_history(student):
    """Build a normalized performance history for both supported curricula."""
    exam_ids = set()
    if StudentOverallKCSE:
        exam_ids.update(StudentOverallKCSE.objects.filter(student=student).values_list('examination_id', flat=True))
    if StudentKCSEGrade:
        exam_ids.update(StudentKCSEGrade.objects.filter(student=student).values_list('examination_id', flat=True))
    if StudentOverallCBA:
        exam_ids.update(StudentOverallCBA.objects.filter(student=student).values_list('examination_id', flat=True))
    if StudentCBAAssessment:
        exam_ids.update(StudentCBAAssessment.objects.filter(student=student).values_list('examination_id', flat=True))

    from examinations.models import Examination
    exams = Examination.objects.filter(id__in=exam_ids).select_related(
        'academic_year', 'term', 'curriculum'
    ).order_by('start_date', 'id')
    history = []

    for exam in exams:
        score = None
        grade = '-'
        position = None
        subject_count = 0

        if exam.curriculum.code == '844' and StudentOverallKCSE:
            overall = StudentOverallKCSE.objects.filter(student=student, examination=exam).first()
            if overall:
                score = float(overall.mean_score)
                grade = overall.mean_grade
                position = overall.position
            if StudentKCSEGrade:
                subject_count = StudentKCSEGrade.objects.filter(student=student, examination=exam).count()
        elif exam.curriculum.code == 'CBC' and StudentOverallCBA:
            overall = StudentOverallCBA.objects.filter(student=student, examination=exam).select_related('overall_level').first()
            if overall:
                score = float(overall.total_weighted_score)
                grade = overall.overall_level.level_code if overall.overall_level else (overall.grade_equivalent or '-')
                position = overall.position
            if StudentCBAAssessment:
                subject_count = StudentCBAAssessment.objects.filter(student=student, examination=exam).values('subject').distinct().count()

        if score is None and exam.curriculum.code == '844' and StudentKCSEGrade:
            marks = StudentKCSEGrade.objects.filter(student=student, examination=exam)
            if marks.exists():
                score = sum(float(mark.raw_mark) for mark in marks) / marks.count()
                subject_count = marks.count()
                grade = 'Pending overall grade'
        elif score is None and exam.curriculum.code == 'CBC' and StudentCBAAssessment:
            assessments = StudentCBAAssessment.objects.filter(student=student, examination=exam).exclude(score__isnull=True)
            if assessments.exists():
                score = sum(float(item.score) for item in assessments) / assessments.count()
                subject_count = assessments.values('subject').distinct().count()
                grade = 'Pending overall level'

        if score is not None:
            history.append({
                'id': exam.id,
                'name': exam.name,
                'code': exam.code,
                'date_label': exam.start_date.strftime('%b %Y'),
                'year': exam.academic_year.year,
                'term': exam.term.name,
                'curriculum': exam.curriculum.code,
                'score': round(score, 1),
                'grade': grade,
                'position': position,
                'subject_count': subject_count,
            })

    return history


def _student_selected_exam(student, exam_id):
    """Return subject-level details for one exam selected from the profile."""
    from examinations.models import Examination
    exam = Examination.objects.filter(id=exam_id).select_related('academic_year', 'term', 'curriculum').first()
    if not exam:
        return None

    subjects = []
    overall = None
    if exam.curriculum.code == '844' and StudentKCSEGrade:
        subjects = [
            {'name': item.subject.name, 'score': float(item.raw_mark), 'grade': item.grade, 'points': float(item.points)}
            for item in StudentKCSEGrade.objects.filter(student=student, examination=exam).select_related('subject').order_by('subject__name')
        ]
        if StudentOverallKCSE:
            result = StudentOverallKCSE.objects.filter(student=student, examination=exam).first()
            if result:
                overall = {'score': float(result.mean_score), 'grade': result.mean_grade, 'position': result.position, 'total': float(result.total_points)}
    elif exam.curriculum.code == 'CBC' and StudentCBAAssessment:
        subjects = [
            {
                'name': item.subject.name,
                'score': float(item.score) if item.score is not None else None,
                'grade': item.overall_level.level_code if item.overall_level else '-',
                'points': item.overall_level.numeric_value if item.overall_level and item.overall_level.numeric_value is not None else '-',
            }
            for item in StudentCBAAssessment.objects.filter(student=student, examination=exam).select_related('subject', 'overall_level').order_by('subject__name')
        ]
        if StudentOverallCBA:
            result = StudentOverallCBA.objects.filter(student=student, examination=exam).select_related('overall_level').first()
            if result:
                overall = {
                    'score': float(result.total_weighted_score),
                    'grade': result.overall_level.level_code if result.overall_level else (result.grade_equivalent or '-'),
                    'position': result.position,
                    'total': float(result.total_score),
                }

    return {'exam': exam, 'subjects': subjects, 'overall': overall}

@login_required
def student_list(request):
    """List all students"""
    students = permitted_student_queryset(request.user).select_related('current_grade_level', 'current_stream', 'academic_year')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(admission_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Filter by grade level
    grade_level_id = request.GET.get('grade_level')
    if grade_level_id:
        students = students.filter(current_grade_level_id=grade_level_id)
    
    # Filter by stream
    stream_id = request.GET.get('stream')
    if stream_id:
        students = students.filter(current_stream_id=stream_id)
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        students = students.filter(status=status)
    
    # Pagination
    paginator = Paginator(students, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    
    context = {
        'students': page_obj,
        'search_query': search_query,
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'status_choices': Student.STATUS_CHOICES,
        'selected_grade_level': grade_level_id or '',
        'selected_stream': stream_id or '',
        'selected_status': status or '',
        'students_844': Student.objects.filter(curriculum__code='844').count(),
        'students_cbc': Student.objects.filter(curriculum__code='CBC').count(),
        'pagination_query': query_params.urlencode(),
    }
    return render(request, 'students/list.html', context)


@login_required
def student_detail(request, student_id):
    """View student details"""
    student = get_object_or_404(permitted_student_queryset(request.user), id=student_id)
    exam_history = _student_exam_history(student)
    selected_exam_id = request.GET.get('exam_id')
    if selected_exam_id and not selected_exam_id.isdigit():
        selected_exam_id = None
    selected_exam = _student_selected_exam(student, selected_exam_id) if selected_exam_id else None
    if selected_exam is None and exam_history:
        selected_exam_id = str(exam_history[-1]['id'])
        selected_exam = _student_selected_exam(student, selected_exam_id)

    scores = [item['score'] for item in exam_history]
    average_score = round(sum(scores) / len(scores), 1) if scores else None
    change = round(scores[-1] - scores[0], 1) if len(scores) > 1 else None
    slope = (scores[-1] - scores[0]) / (len(scores) - 1) if len(scores) > 1 else 0
    predicted_score = round(max(0, min(100, scores[-1] + slope)), 1) if scores else None
    trend = 'Improving' if slope > 0.5 else 'Declining' if slope < -0.5 else 'Stable'
    cbc_learning_areas = []
    strengths = []
    improvement_areas = []
    interventions = []
    if selected_exam and StudentCBAAssessment:
        current_exam = selected_exam['exam']
        previous_exam_id = None
        exam_ids = [item['id'] for item in exam_history]
        if current_exam.id in exam_ids:
            index = exam_ids.index(current_exam.id)
            if index > 0:
                previous_exam_id = exam_ids[index - 1]
        current = StudentCBAAssessment.objects.filter(
            student=student, examination=current_exam
        ).select_related('subject', 'overall_level')
        previous = {}
        if previous_exam_id:
            previous = {
                item.subject_id: item.overall_level.level_code
                for item in StudentCBAAssessment.objects.filter(
                    student=student, examination_id=previous_exam_id
                ).select_related('overall_level')
                if item.overall_level
            }
        level_order = {'PL1': 1, 'PL2': 2, 'PL3': 3, 'PL4': 4}
        for item in current:
            current_level = item.overall_level.level_code if item.overall_level else '-'
            previous_level = previous.get(item.subject_id, '-')
            if current_level in {'PL3', 'PL4'}:
                strengths.append(item.subject.name)
            if current_level in {'PL1', 'PL2'}:
                improvement_areas.append(item.subject.name)
                interventions.append(f'Provide targeted support and practical activities in {item.subject.name}.')
            if current_level != '-' and previous_level != '-':
                direction = 'Improving' if level_order[current_level] > level_order[previous_level] else 'Declining' if level_order[current_level] < level_order[previous_level] else 'Stable'
            else:
                direction = 'New'
            cbc_learning_areas.append({
                'name': item.subject.name,
                'current': current_level,
                'previous': previous_level,
                'trend': direction,
                'note': item.teacher_notes,
            })

    context = {
        'student': student,
        'history': student.history.all().order_by('-academic_year'),
        'exam_history': exam_history,
        'selected_exam': selected_exam,
        'selected_exam_id': int(selected_exam_id) if selected_exam_id else None,
        'exam_scores': scores,
        'average_exam_score': average_score,
        'score_change': change,
        'predicted_score': predicted_score,
        'performance_trend': trend,
        'cbc_learning_areas': cbc_learning_areas,
        'strengths': list(dict.fromkeys(strengths)),
        'improvement_areas': list(dict.fromkeys(improvement_areas)),
        'interventions': list(dict.fromkeys(interventions)),
    }
    return render(request, 'students/detail.html', context)


@login_required
def student_create(request):
    """Create a new student — admin and class teachers only."""
    if not is_admin(request.user):
        try:
            teacher = TeacherProfile.objects.get(user=request.user)
            if not ClassTeacher.objects.filter(teacher=teacher, is_active=True).exists():
                messages.error(request, 'Only administrators and class teachers can register learners.')
                return redirect('core:dashboard')
        except TeacherProfile.DoesNotExist:
            messages.error(request, 'You do not have a teacher profile.')
            return redirect('core:dashboard')
    if request.method == 'POST':
        try:
            # Get form data
            admission_number = request.POST.get('admission_number')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            middle_name = request.POST.get('middle_name', '')
            date_of_birth = request.POST.get('date_of_birth')
            gender = request.POST.get('gender')
            nationality = request.POST.get('nationality', 'Kenyan')
            religion = request.POST.get('religion', '')
            
            email = request.POST.get('email', '')
            phone_number = request.POST.get('phone_number', '')
            address = request.POST.get('address', '')
            
            admission_date = request.POST.get('admission_date')
            curriculum_id = request.POST.get('curriculum')
            grade_level_id = request.POST.get('grade_level')
            stream_id = request.POST.get('stream')
            academic_year_id = request.POST.get('academic_year')

            if not can_use_class(request.user, grade_level_id, stream_id, academic_year_id):
                messages.error(request, 'You can only add learners to your assigned class and stream.')
                return redirect('students:create')
            
            guardian_name = request.POST.get('guardian_name', '')
            guardian_phone = request.POST.get('guardian_phone', '')
            guardian_email = request.POST.get('guardian_email', '')
            guardian_relationship = request.POST.get('guardian_relationship', '')
            
            status = request.POST.get('status', 'ACTIVE')
            
            # Validate admission number uniqueness
            if Student.objects.filter(admission_number=admission_number).exists():
                messages.error(request, f'Student with admission number {admission_number} already exists!')
                return redirect('students:create')
            
            # Create student
            student = Student.objects.create(
                admission_number=admission_number,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                date_of_birth=date_of_birth,
                gender=gender,
                nationality=nationality,
                religion=religion,
                email=email,
                phone_number=phone_number,
                address=address,
                admission_date=admission_date,
                curriculum_id=curriculum_id,
                current_grade_level_id=grade_level_id,
                current_stream_id=stream_id,
                academic_year_id=academic_year_id,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                guardian_email=guardian_email,
                guardian_relationship=guardian_relationship,
                status=status,
                created_by=request.user
            )
            
            # Create history entry
            StudentHistory.objects.create(
                student=student,
                academic_year_id=academic_year_id,
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                is_current=True
            )
            
            messages.success(request, f'Student {student.full_name} registered successfully!')
            return redirect('students:detail', student_id=student.id)
            
        except Exception as e:
            messages.error(request, f'Error creating student: {str(e)}')
            return redirect('students:create')
    
    context = {
        'curriculums': Curriculum.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'gender_choices': Student.GENDER_CHOICES,
        'status_choices': Student.STATUS_CHOICES,
        'today': datetime.now().date(),
    }
    return render(request, 'students/create.html', context)


@login_required
def student_edit(request, student_id):
    """Edit student details — admin and class teachers only."""
    student = get_object_or_404(permitted_student_queryset(request.user), id=student_id)
    
    if not is_admin(request.user) and not can_edit_student(request.user, student):
        messages.error(request, 'Only administrators and class teachers can edit learner details.')
        return redirect('students:detail', student_id=student.id)
    
    if request.method == 'POST':
        try:
            admission_number = request.POST.get('admission_number', '').strip()
            if not admission_number:
                messages.error(request, 'Admission number is required.')
                return redirect('students:edit', student_id=student.id)
            if Student.objects.filter(admission_number=admission_number).exclude(id=student.id).exists():
                messages.error(request, f'Admission number {admission_number} is already in use.')
                return redirect('students:edit', student_id=student.id)
            student.admission_number = admission_number
            # Update student fields
            student.first_name = request.POST.get('first_name')
            student.last_name = request.POST.get('last_name')
            student.middle_name = request.POST.get('middle_name', '')
            student.date_of_birth = request.POST.get('date_of_birth')
            student.gender = request.POST.get('gender')
            student.nationality = request.POST.get('nationality', 'Kenyan')
            student.religion = request.POST.get('religion', '')
            
            student.email = request.POST.get('email', '')
            student.phone_number = request.POST.get('phone_number', '')
            student.address = request.POST.get('address', '')
            
            student.admission_date = request.POST.get('admission_date')
            student.curriculum_id = request.POST.get('curriculum')
            student.current_grade_level_id = request.POST.get('grade_level')
            student.current_stream_id = request.POST.get('stream')
            student.academic_year_id = request.POST.get('academic_year')

            if not can_use_class(request.user, student.current_grade_level_id, student.current_stream_id, student.academic_year_id):
                messages.error(request, 'You can only manage learners in your assigned class and stream.')
                return redirect('students:edit', student_id=student.id)
            
            student.guardian_name = request.POST.get('guardian_name', '')
            student.guardian_phone = request.POST.get('guardian_phone', '')
            student.guardian_email = request.POST.get('guardian_email', '')
            student.guardian_relationship = request.POST.get('guardian_relationship', '')
            
            student.status = request.POST.get('status', 'ACTIVE')
            student.updated_by = request.user
            
            student.save()
            
            messages.success(request, f'Student {student.full_name} updated successfully!')
            return redirect('students:detail', student_id=student.id)
            
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
    
    context = {
        'student': student,
        'curriculums': Curriculum.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'gender_choices': Student.GENDER_CHOICES,
        'status_choices': Student.STATUS_CHOICES,
    }
    return render(request, 'students/edit.html', context)


@login_required
def student_delete(request, student_id):
    """Delete/Deactivate a student — admin and class teachers only."""
    student = get_object_or_404(permitted_student_queryset(request.user), id=student_id)
    
    if not is_admin(request.user) and not can_edit_student(request.user, student):
        messages.error(request, 'Only administrators and class teachers can delete or deactivate learners.')
        return redirect('students:detail', student_id=student.id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            student.delete()
            messages.success(request, f'Student {student.full_name} deleted successfully!')
        elif action == 'deactivate':
            student.is_active = False
            student.status = 'INACTIVE'
            student.save()
            messages.success(request, f'Student {student.full_name} deactivated successfully!')
        
        return redirect('students:list')
    
    context = {'student': student}
    return render(request, 'students/delete.html', context)


@login_required
def student_transfer(request, student_id):
    """Transfer student to another class — admin and class teachers only."""
    student = get_object_or_404(permitted_student_queryset(request.user), id=student_id)
    
    if not is_admin(request.user) and not can_edit_student(request.user, student):
        messages.error(request, 'Only administrators and class teachers can transfer learners.')
        return redirect('students:detail', student_id=student.id)
    
    if request.method == 'POST':
        new_grade_level_id = request.POST.get('grade_level')
        new_stream_id = request.POST.get('stream')
        academic_year_id = request.POST.get('academic_year')

        if not can_use_class(request.user, new_grade_level_id, new_stream_id, academic_year_id):
            messages.error(request, 'You can only transfer learners within your assigned class scope.')
            return redirect('students:transfer', student_id=student.id)
        
        # Update current class
        student.current_grade_level_id = new_grade_level_id
        student.current_stream_id = new_stream_id
        student.academic_year_id = academic_year_id
        student.save()
        
        # Add history entry
        StudentHistory.objects.create(
            student=student,
            academic_year_id=academic_year_id,
            grade_level_id=new_grade_level_id,
            stream_id=new_stream_id,
            is_current=True
        )
        
        messages.success(request, f'Student {student.full_name} transferred successfully!')
        return redirect('students:detail', student_id=student.id)
    
    context = {
        'student': student,
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
    }
    return render(request, 'students/transfer.html', context)


@login_required
def api_students_search(request):
    """API endpoint for student search (autocomplete)"""
    query = request.GET.get('q', '')
    if len(query) >= 2:
        students = permitted_student_queryset(request.user).filter(
            Q(admission_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).values('id', 'admission_number', 'first_name', 'last_name')[:10]
        return JsonResponse({'students': list(students)})
    return JsonResponse({'students': []})
