from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime
from .models import Examination, ExaminationClass, SubjectScoreConfig
from school.models import AcademicYear, Term, Curriculum, GradeLevel, Stream, Subject
from core.access import is_admin, permitted_student_queryset, class_teacher_assignments

try:
    from grading.models import StudentCBAAssessment, StudentOverallCBA
except ImportError:
    StudentCBAAssessment = None
    StudentOverallCBA = None

@login_required
def exam_list(request):
    """List all examinations"""
    examinations = Examination.objects.select_related(
        'academic_year', 'term', 'curriculum', 'grade_level'
    ).all()
    
    # Filters
    academic_year_id = request.GET.get('academic_year')
    if academic_year_id:
        examinations = examinations.filter(academic_year_id=academic_year_id)
    
    term_id = request.GET.get('term')
    if term_id:
        examinations = examinations.filter(term_id=term_id)
    
    grade_level_id = request.GET.get('grade_level')
    if grade_level_id:
        examinations = examinations.filter(grade_level_id=grade_level_id)
    
    status = request.GET.get('status')
    if status:
        examinations = examinations.filter(status=status)
    
    search_query = request.GET.get('search', '')
    if search_query:
        examinations = examinations.filter(
            Q(code__icontains=search_query) |
            Q(name__icontains=search_query)
        )
    
    paginator = Paginator(examinations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    
    context = {
        'examinations': page_obj,
        'search_query': search_query,
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'terms': Term.objects.all(),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'status_choices': Examination.STATUS_CHOICES,
        'pagination_query': query_params.urlencode(),
    }
    return render(request, 'examinations/list.html', context)


@login_required
def exam_create(request):
    """Create a new examination"""
    if request.method == 'POST':
        try:
            # Get form data
            code = request.POST.get('code')
            name = request.POST.get('name')
            exam_type = request.POST.get('exam_type')
            description = request.POST.get('description', '')
            
            academic_year_id = request.POST.get('academic_year')
            term_id = request.POST.get('term')
            curriculum_id = request.POST.get('curriculum')
            grade_level_id = request.POST.get('grade_level')
            
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            results_date = request.POST.get('results_date') or None
            
            max_score = request.POST.get('max_score', 100)
            pass_mark = request.POST.get('pass_mark', 40)
            status = request.POST.get('status', 'DRAFT')
            
            # Get selected subjects
            subject_ids = request.POST.getlist('subjects')
            
            if not subject_ids:
                messages.error(request, 'Please select at least one subject!')
                return redirect('examinations:create')
            
            # Create examination
            exam = Examination.objects.create(
                code=code,
                name=name,
                exam_type=exam_type,
                description=description,
                academic_year_id=academic_year_id,
                term_id=term_id,
                curriculum_id=curriculum_id,
                grade_level_id=grade_level_id,
                start_date=start_date,
                end_date=end_date,
                results_date=results_date,
                max_score=int(max_score),
                pass_mark=int(pass_mark),
                status=status,
                created_by=request.user
            )
            
            # Add subjects
            exam.subjects.add(*subject_ids)
            
            # Create subject configs
            for subject_id in subject_ids:
                SubjectScoreConfig.objects.create(
                    examination=exam,
                    subject_id=subject_id,
                    max_score=int(max_score),
                    pass_mark=int(pass_mark)
                )
            
            messages.success(request, f'Examination {exam.name} created successfully!')
            return redirect('examinations:detail', exam_id=exam.id)
            
        except Exception as e:
            messages.error(request, f'Error creating examination: {str(e)}')
            return redirect('examinations:create')
    
    context = {
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'terms': Term.objects.all(),
        'curriculums': Curriculum.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'subjects': Subject.objects.filter(is_active=True),
        'exam_types': Examination.EXAM_TYPES,
        'status_choices': Examination.STATUS_CHOICES,
    }
    return render(request, 'examinations/create.html', context)


@login_required
def exam_detail(request, exam_id):
    """View examination details"""
    exam = get_object_or_404(Examination, id=exam_id)
    subjects = exam.subjects.all()
    subject_configs = SubjectScoreConfig.objects.filter(examination=exam)
    
    context = {
        'exam': exam,
        'subjects': subjects,
        'subject_configs': subject_configs,
    }
    return render(request, 'examinations/detail.html', context)


@login_required
def exam_analysis(request, exam_id):
    """Role-scoped CBC assessment analysis for one examination."""
    exam = get_object_or_404(Examination.objects.select_related(
        'academic_year', 'term', 'curriculum', 'grade_level'
    ), id=exam_id)
    if not StudentCBAAssessment or not StudentOverallCBA or exam.curriculum.code != 'CBC':
        return render(request, 'examinations/analysis.html', {
            'exam': exam,
            'analysis_available': False,
            'scope_label': 'School-wide' if is_admin(request.user) else 'Assigned class',
        })

    learners = permitted_student_queryset(request.user).filter(
        current_grade_level=exam.grade_level,
        is_active=True,
    )
    scope_label = f'School-wide · {exam.grade_level.name}'
    if not is_admin(request.user):
        assignments = class_teacher_assignments(request.user).filter(grade_level=exam.grade_level)
        learner_scope = learners.none()
        labels = []
        for assignment in assignments:
            learner_scope |= learners.filter(current_stream=assignment.stream, academic_year=assignment.academic_year)
            labels.append(assignment.stream.name)
        learners = learner_scope
        scope_label = f"{' / '.join(labels) or 'No assigned stream'} · {exam.grade_level.name}"

    expected = learners.count()
    results = list(StudentOverallCBA.objects.filter(
        examination=exam, student__in=learners
    ).select_related('student', 'student__current_stream', 'overall_level').order_by('-total_weighted_score'))
    assessed_ids = set(StudentCBAAssessment.objects.filter(
        examination=exam, student__in=learners
    ).values_list('student_id', flat=True))
    assessed = len(assessed_ids)
    result_ids = {result.student_id for result in results}
    assessed = len(assessed_ids | result_ids)
    levels = {'PL4': 'Exceeding Expectations', 'PL3': 'Meeting Expectations', 'PL2': 'Approaching Expectations', 'PL1': 'Below Expectations'}
    distribution = {code: 0 for code in levels}
    for result in results:
        if result.overall_level:
            distribution[result.overall_level.level_code] += 1

    ranking = []
    for position, result in enumerate(results[:10], 1):
        ranking.append({'position': position, 'student': result.student, 'level': result.overall_level.level_code if result.overall_level else '-', 'score': float(result.total_weighted_score)})
    boys = [result for result in results if result.student.gender == 'M']
    girls = [result for result in results if result.student.gender == 'F']

    area_map = {}
    for item in StudentCBAAssessment.objects.filter(
        examination=exam, student__in=learners
    ).select_related('subject', 'overall_level'):
        area = area_map.setdefault(item.subject_id, {'name': item.subject.name, 'assessed': 0, 'support': 0, 'levels': {code: 0 for code in levels}})
        area['assessed'] += 1
        if item.overall_level:
            area['levels'][item.overall_level.level_code] += 1
            if item.overall_level.level_code in {'PL1', 'PL2'}:
                area['support'] += 1
    learning_areas = []
    for area in area_map.values():
        area['support_rate'] = round(area['support'] / area['assessed'] * 100, 1) if area['assessed'] else 0
        learning_areas.append(area)
    learning_areas.sort(key=lambda item: item['support_rate'])

    stream_map = {}
    for result in results:
        stream = result.student.current_stream
        key = stream.id if stream else 0
        entry = stream_map.setdefault(key, {'name': stream.name if stream else 'Unassigned', 'assessed': 0, 'levels': {code: 0 for code in levels}})
        entry['assessed'] += 1
        if result.overall_level:
            entry['levels'][result.overall_level.level_code] += 1
    streams = list(stream_map.values())
    for stream in streams:
        stream['higher_rate'] = round((stream['levels']['PL3'] + stream['levels']['PL4']) / stream['assessed'] * 100, 1) if stream['assessed'] else 0
    streams.sort(key=lambda item: item['higher_rate'], reverse=True)

    previous = StudentOverallCBA.objects.filter(
        examination__curriculum=exam.curriculum,
        examination__grade_level=exam.grade_level,
        examination__start_date__lt=exam.start_date,
        student__in=learners,
    ).select_related('overall_level').order_by('-examination__start_date')
    previous_by_student = {}
    for item in previous:
        previous_by_student.setdefault(item.student_id, item)
    improvements = []
    for result in results:
        before = previous_by_student.get(result.student_id)
        if before and before.overall_level and result.overall_level:
            order = {'PL1': 1, 'PL2': 2, 'PL3': 3, 'PL4': 4}
            change = order[result.overall_level.level_code] - order[before.overall_level.level_code]
            improvements.append({'student': result.student, 'previous': before.overall_level.level_code, 'current': result.overall_level.level_code, 'change': change})
    improvements.sort(key=lambda item: item['change'], reverse=True)
    improved = [item for item in improvements if item['change'] > 0]
    declined = [item for item in improvements if item['change'] < 0]
    best_area = learning_areas[0]['name'] if learning_areas else '-'
    weakest_area = learning_areas[-1]['name'] if learning_areas else '-'
    insight = f'{best_area} has the lowest PL1/PL2 support rate, while {weakest_area} requires the most intervention.' if learning_areas else 'No learning-area data is available yet.'

    return render(request, 'examinations/analysis.html', {
        'exam': exam, 'analysis_available': True, 'scope_label': scope_label,
        'expected': expected, 'assessed': assessed, 'not_assessed': max(expected - assessed, 0),
        'completion_rate': round(assessed / expected * 100, 1) if expected else 0,
        'distribution': [{'code': code, 'name': name, 'count': distribution[code]} for code, name in levels.items()],
        'ranking': ranking, 'best_boy': boys[0] if boys else None, 'best_girl': girls[0] if girls else None,
        'learning_areas': learning_areas, 'streams': streams, 'improvements': improved[:10], 'declined': declined[:10],
        'intervention_count': sum(item['count'] for item in [{'count': distribution['PL1']}, {'count': distribution['PL2']}]),
        'insight': insight,
    })


@login_required
def exam_edit(request, exam_id):
    """Edit examination"""
    exam = get_object_or_404(Examination, id=exam_id)
    
    if request.method == 'POST':
        try:
            exam.name = request.POST.get('name')
            exam.exam_type = request.POST.get('exam_type')
            exam.description = request.POST.get('description', '')
            exam.academic_year_id = request.POST.get('academic_year')
            exam.term_id = request.POST.get('term')
            exam.curriculum_id = request.POST.get('curriculum')
            exam.grade_level_id = request.POST.get('grade_level')
            exam.start_date = request.POST.get('start_date')
            exam.end_date = request.POST.get('end_date')
            exam.results_date = request.POST.get('results_date') or None
            exam.max_score = int(request.POST.get('max_score', 100))
            exam.pass_mark = int(request.POST.get('pass_mark', 40))
            exam.status = request.POST.get('status', 'DRAFT')
            exam.updated_by = request.user
            
            # Update subjects
            subject_ids = request.POST.getlist('subjects')
            if subject_ids:
                exam.subjects.set(subject_ids)
                
                # Update subject configs
                SubjectScoreConfig.objects.filter(examination=exam).delete()
                for subject_id in subject_ids:
                    SubjectScoreConfig.objects.create(
                        examination=exam,
                        subject_id=subject_id,
                        max_score=exam.max_score,
                        pass_mark=exam.pass_mark
                    )
            
            exam.save()
            messages.success(request, f'Examination {exam.name} updated successfully!')
            return redirect('examinations:detail', exam_id=exam.id)
            
        except Exception as e:
            messages.error(request, f'Error updating examination: {str(e)}')
    
    context = {
        'exam': exam,
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'terms': Term.objects.all(),
        'curriculums': Curriculum.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'subjects': Subject.objects.filter(is_active=True),
        'selected_subjects': exam.subjects.values_list('id', flat=True),
        'exam_types': Examination.EXAM_TYPES,
        'status_choices': Examination.STATUS_CHOICES,
    }
    return render(request, 'examinations/edit.html', context)


@login_required
def exam_delete(request, exam_id):
    """Delete examination"""
    exam = get_object_or_404(Examination, id=exam_id)
    
    if request.method == 'POST':
        exam.delete()
        messages.success(request, f'Examination {exam.name} deleted successfully!')
        return redirect('examinations:list')
    
    context = {'exam': exam}
    return render(request, 'examinations/delete.html', context)


@login_required
def exam_change_status(request, exam_id):
    """Change examination status"""
    exam = get_object_or_404(Examination, id=exam_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Examination.STATUS_CHOICES):
            exam.status = new_status
            exam.updated_by = request.user
            exam.save()
            messages.success(request, f'Examination status changed to {exam.get_status_display()}')
        else:
            messages.error(request, 'Invalid status!')
        
        return redirect('examinations:detail', exam_id=exam.id)
    
    context = {
        'exam': exam,
        'status_choices': Examination.STATUS_CHOICES,
    }
    return render(request, 'examinations/change_status.html', context)


@login_required
def api_get_subjects(request):
    """API endpoint to get subjects by curriculum"""
    curriculum_id = request.GET.get('curriculum_id')
    if curriculum_id:
        subjects = Subject.objects.filter(
            curriculum_id=curriculum_id,
            is_active=True
        ).values('id', 'name', 'code')
        return JsonResponse({'subjects': list(subjects)})
    return JsonResponse({'subjects': []})


@login_required
def api_get_terms(request):
    """API endpoint to get terms by academic year"""
    academic_year_id = request.GET.get('academic_year_id')
    if academic_year_id:
        terms = Term.objects.filter(
            academic_year_id=academic_year_id
        ).values('id', 'name', 'term_number')
        return JsonResponse({'terms': list(terms)})
    return JsonResponse({'terms': []})
