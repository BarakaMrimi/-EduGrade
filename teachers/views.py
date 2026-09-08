from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from datetime import datetime
from .models import TeacherProfile, TeacherAssignment, TeacherRequest, ClassTeacher, ClassTeacherRequest
from school.models import Subject, GradeLevel, Stream, AcademicYear, Curriculum
from core.permissions import Permission
from core.access import has_permission, is_admin, send_notification, notify_warning, notify_suspension


def _is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
def teacher_list(request):
    """List all teachers"""
    teachers = TeacherProfile.objects.select_related('user').all()
    
    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(staff_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        teachers = teachers.filter(status=status_filter)
    
    paginator = Paginator(teachers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    
    context = {
        'teachers': page_obj,
        'search_query': search_query,
        'status_choices': TeacherProfile.STATUS_CHOICES,
        'selected_status': status_filter,
        'pending_requests': TeacherRequest.objects.filter(status='PENDING').count(),
        'pagination_query': query_params.urlencode(),
    }
    return render(request, 'teachers/list.html', context)


@login_required
def teacher_detail(request, teacher_id):
    """View teacher details"""
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    is_admin = _is_admin(request.user)

    if request.method == 'POST':
        if not is_admin:
            messages.error(request, 'Only administrators can manage teacher status.')
            return redirect('teachers:detail', teacher_id=teacher.id)

        action = request.POST.get('action')
        if action == 'update_role':
            from core.models import Role, UserProfile
            role = get_object_or_404(Role, id=request.POST.get('role_id'))
            profile, _ = UserProfile.objects.get_or_create(user=teacher.user)
            profile.role = role
            profile.save(update_fields=['role', 'updated_at'])
            messages.success(request, f'{teacher.full_name} is now assigned the {role.get_name_display()} role.')
        if action == 'suspend':
            from core.models import SuspensionRecord, WarningRecord
            from datetime import date, timedelta
            teacher.status = 'INACTIVE'
            teacher.is_active = False
            teacher.save(update_fields=['status', 'is_active', 'updated_at'])
            messages.warning(request, f'{teacher.full_name} has been suspended.')
            suspension = SuspensionRecord.objects.create(
                teacher_profile=teacher.user.profile,
                reason=request.POST.get('reason', 'Administrative suspension.'),
                start_date=date.today(),
                end_date=date.today() + timedelta(days=7),
                status='ACTIVE',
                issued_by=request.user,
            )
            notify_suspension(teacher.user.profile, suspension)
        elif action == 'activate':
            teacher.status = 'ACTIVE'
            teacher.is_active = True
            teacher.save(update_fields=['status', 'is_active', 'updated_at'])
            SuspensionRecord.objects.filter(
                teacher_profile=teacher.user.profile,
                status='ACTIVE',
            ).update(status='REVOKED')
            messages.success(request, f'{teacher.full_name} has been reactivated.')
        elif action == 'warn':
            from core.models import WarningRecord
            warning = WarningRecord.objects.create(
                teacher_profile=teacher.user.profile,
                reason=request.POST.get('reason', 'Administrative warning.'),
                description=request.POST.get('warning_reason', 'Administrative warning'),
                severity=request.POST.get('severity', 'MEDIUM'),
                issued_by=request.user,
            )
            notify_warning(teacher.user.profile, warning)
            messages.warning(request, f'Warning recorded for {teacher.full_name}.')
        elif action == 'delete':
            teacher_name = teacher.full_name
            user = teacher.user
            teacher.delete()
            if user:
                user.delete()
            messages.success(request, f'{teacher_name} has been deleted.')
            return redirect('teachers:list')
        return redirect('teachers:detail', teacher_id=teacher.id)

    assignments = teacher.assignments.select_related(
        'subject', 'grade_level', 'stream', 'academic_year', 'curriculum'
    ).order_by('-academic_year__year', 'grade_level__order', 'subject__name')
    requests = teacher.requests.all().order_by('-requested_date')
    class_teacher = ClassTeacher.objects.filter(
        teacher=teacher, is_active=True
    ).select_related('grade_level', 'stream', 'academic_year')
    
    context = {
        'teacher': teacher,
        'assignments': assignments,
        'requests': requests,
        'class_teacher': class_teacher,
        'is_admin': is_admin,
        'roles': __import__('core.models', fromlist=['Role']).Role.objects.all() if is_admin else [],
    }
    return render(request, 'teachers/detail.html', context)


@login_required
def teacher_assignment_delete(request, assignment_id):
    """Remove a teacher's subject/class assignment."""
    if not _is_admin(request.user):
        messages.error(request, 'Only administrators can remove assignments.')
        return redirect('core:dashboard')
    assignment = get_object_or_404(TeacherAssignment, id=assignment_id)
    teacher_id = assignment.teacher_id
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Teacher assignment removed.')
    return redirect('teachers:detail', teacher_id=teacher_id)


@login_required
def teacher_create(request):
    """Create a new teacher — admin only."""
    if not is_admin(request.user):
        messages.error(request, 'Only administrators can create teacher accounts.')
        return redirect('core:dashboard')
    if request.method == 'POST':
        try:
            # Get form data
            staff_number = request.POST.get('staff_number')
            tsc_number = request.POST.get('tsc_number') or None
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            middle_name = request.POST.get('middle_name', '')
            gender = request.POST.get('gender')
            date_of_birth = request.POST.get('date_of_birth')
            phone_number = request.POST.get('phone_number')
            email = request.POST.get('email')
            address = request.POST.get('address', '')
            employment_date = request.POST.get('employment_date')
            qualification = request.POST.get('qualification')
            specialization = request.POST.get('specialization', '')
            status = request.POST.get('status', 'ACTIVE')
            
            # Create user account
            username = staff_number.lower()
            password = request.POST.get('password')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username {username} already exists!')
                return redirect('teachers:create')
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create teacher profile
            teacher = TeacherProfile.objects.create(
                user=user,
                staff_number=staff_number,
                tsc_number=tsc_number,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                gender=gender,
                date_of_birth=date_of_birth,
                phone_number=phone_number,
                email=email,
                address=address,
                employment_date=employment_date,
                qualification=qualification,
                specialization=specialization,
                status=status,
                created_by=request.user
            )
            
            messages.success(request, f'Teacher {teacher.full_name} created successfully!')
            return redirect('teachers:detail', teacher_id=teacher.id)
            
        except Exception as e:
            messages.error(request, f'Error creating teacher: {str(e)}')
            return redirect('teachers:create')
    
    context = {
        'gender_choices': TeacherProfile.GENDER_CHOICES,
        'status_choices': TeacherProfile.STATUS_CHOICES,
    }
    return render(request, 'teachers/create.html', context)


@login_required
def teacher_edit(request, teacher_id):
    """Edit teacher details"""
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    
    if request.method == 'POST':
        try:
            old_tsc_number = teacher.tsc_number
            teacher.tsc_number = request.POST.get('tsc_number') or None
            teacher.first_name = request.POST.get('first_name')
            teacher.last_name = request.POST.get('last_name')
            teacher.middle_name = request.POST.get('middle_name', '')
            teacher.gender = request.POST.get('gender')
            teacher.date_of_birth = request.POST.get('date_of_birth')
            teacher.phone_number = request.POST.get('phone_number')
            teacher.email = request.POST.get('email')
            teacher.address = request.POST.get('address', '')
            teacher.employment_date = request.POST.get('employment_date')
            teacher.qualification = request.POST.get('qualification')
            teacher.specialization = request.POST.get('specialization', '')
            teacher.status = request.POST.get('status', 'ACTIVE')
            teacher.updated_by = request.user
            
            teacher.save()

            if old_tsc_number != teacher.tsc_number:
                from core.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='UPDATE',
                    model_name='TeacherProfile',
                    object_id=str(teacher.id),
                    object_repr=teacher.full_name,
                    changes={'tsc_number': {'old': old_tsc_number, 'new': teacher.tsc_number}},
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            
            messages.success(request, f'Teacher {teacher.full_name} updated successfully!')
            return redirect('teachers:detail', teacher_id=teacher.id)
            
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')
    
    context = {
        'teacher': teacher,
        'gender_choices': TeacherProfile.GENDER_CHOICES,
        'status_choices': TeacherProfile.STATUS_CHOICES,
    }
    return render(request, 'teachers/edit.html', context)


@login_required
def teacher_assign(request, teacher_id):
    """Assign teacher to subject and class"""
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    
    if request.method == 'POST':
        try:
            subject_id = request.POST.get('subject')
            grade_level_id = request.POST.get('grade_level')
            stream_id = request.POST.get('stream')
            academic_year_id = request.POST.get('academic_year')
            curriculum_id = request.POST.get('curriculum')
            is_class_teacher = request.POST.get('is_class_teacher') == 'on'
            
            # Check if assignment already exists
            existing = TeacherAssignment.objects.filter(
                teacher=teacher,
                subject_id=subject_id,
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                academic_year_id=academic_year_id
            ).first()
            
            if existing:
                messages.warning(request, 'This assignment already exists!')
                return redirect('teachers:assign', teacher_id=teacher.id)
            
            # Create assignment
            assignment = TeacherAssignment.objects.create(
                teacher=teacher,
                subject_id=subject_id,
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                academic_year_id=academic_year_id,
                curriculum_id=curriculum_id,
                is_class_teacher=is_class_teacher,
                status='APPROVED',
                approved_by=request.user,
                approved_date=datetime.now().date()
            )
            
            # If class teacher, also create class teacher record
            if is_class_teacher:
                ClassTeacher.objects.get_or_create(
                    teacher=teacher,
                    grade_level_id=grade_level_id,
                    stream_id=stream_id,
                    academic_year_id=academic_year_id,
                    defaults={'is_active': True}
                )
            
            messages.success(request, f'Teacher assigned to {assignment.subject.name} successfully!')
            send_notification(
                teacher.user,
                title="New Assignment",
                message=(
                    f"You have been assigned as a Subject Teacher for {assignment.subject.name}.\n\n"
                    f"Grade: {assignment.grade_level.name}\n"
                    f"Stream: {assignment.stream.name}\n"
                    f"Academic Year: {assignment.academic_year.year}\n\n"
                    f"Permissions: View assigned learners, Enter marks, View analytics.\n"
                ),
                notification_type="ASSIGNMENT",
                url="/marks/entry/",
            )
            return redirect('teachers:detail', teacher_id=teacher.id)
            
        except Exception as e:
            messages.error(request, f'Error assigning teacher: {str(e)}')
    
    context = {
        'teacher': teacher,
        'subjects': Subject.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'curriculums': Curriculum.objects.filter(is_active=True),
    }
    return render(request, 'teachers/assign.html', context)


@login_required
def teacher_requests(request):
    """View and manage teacher requests"""
    # Check if user is admin or teacher
    is_admin = request.user.is_staff or request.user.is_superuser
    
    if is_admin:
        # Admin sees all requests
        requests_list = TeacherRequest.objects.select_related(
            'teacher', 'subject', 'grade_level', 'stream', 'academic_year'
        ).all()
    else:
        # Teacher sees only their own requests
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            requests_list = TeacherRequest.objects.filter(teacher=teacher_profile).select_related(
                'subject', 'grade_level', 'stream', 'academic_year'
            )
        except TeacherProfile.DoesNotExist:
            requests_list = TeacherRequest.objects.none()
    
    # Handle request actions (admin only)
    if request.method == 'POST' and is_admin:
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        teacher_request = get_object_or_404(TeacherRequest, id=request_id)
        
        if action == 'approve':
            teacher_request.status = 'APPROVED'
            teacher_request.reviewed_by = request.user
            teacher_request.reviewed_date = timezone.now()
            teacher_request.admin_notes = admin_notes

            if teacher_request.request_type == 'REMOVE':
                TeacherAssignment.objects.filter(
                    teacher=teacher_request.teacher,
                    subject=teacher_request.subject,
                    grade_level=teacher_request.grade_level,
                    stream=teacher_request.stream,
                    academic_year=teacher_request.academic_year,
                ).delete()
                messages.success(request, f'Assignment removed for {teacher_request.teacher.full_name}')
            elif not all([teacher_request.subject, teacher_request.grade_level, teacher_request.stream, teacher_request.academic_year]):
                teacher_request.status = 'REJECTED'
                teacher_request.admin_notes = 'Request is missing subject, grade, stream, or academic year.'
                messages.error(request, 'Request could not be approved because required assignment details are missing.')
            else:
                curriculum = teacher_request.grade_level.curriculum or teacher_request.subject.curriculum
                try:
                    TeacherAssignment.objects.get_or_create(
                        teacher=teacher_request.teacher,
                        subject=teacher_request.subject,
                        grade_level=teacher_request.grade_level,
                        stream=teacher_request.stream,
                        academic_year=teacher_request.academic_year,
                        defaults={
                            'curriculum': curriculum,
                            'status': 'APPROVED',
                            'approved_by': request.user,
                            'approved_date': datetime.now().date(),
                        },
                    )
                    messages.success(request, f'Request approved for {teacher_request.teacher.full_name}')
                except IntegrityError:
                    teacher_request.status = 'REJECTED'
                    teacher_request.admin_notes = 'An identical assignment already exists or the request data is invalid.'
                    messages.error(request, 'Request could not be approved because the assignment already exists or is invalid.')
            
        elif action == 'reject':
            teacher_request.status = 'REJECTED'
            teacher_request.reviewed_by = request.user
            teacher_request.reviewed_date = timezone.now()
            teacher_request.admin_notes = admin_notes
            messages.warning(request, f'Request rejected for {teacher_request.teacher.full_name}')
        
        teacher_request.save()
        return redirect('teachers:requests')
    
    # Filtering
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    context = {
        'requests': requests_list,
        'status_choices': TeacherRequest.REQUEST_STATUS,
        'is_admin': is_admin,
    }
    return render(request, 'teachers/requests.html', context)


@login_required
def teacher_request_create(request):
    """Create a new teacher request"""
    # Get the teacher profile for the logged-in user
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'You do not have a teacher profile!')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            # Get form data
            request_type = request.POST.get('request_type')
            subject_id = request.POST.get('subject')
            grade_level_id = request.POST.get('grade_level')
            stream_id = request.POST.get('stream')
            academic_year_id = request.POST.get('academic_year')
            reason = request.POST.get('reason')
            
            # Validate that all required fields are provided
            if not all([request_type, subject_id, grade_level_id, stream_id, academic_year_id, reason]):
                messages.error(request, 'All fields are required!')
                return redirect('teachers:request_create')
            
            # Create the request
            teacher_request = TeacherRequest.objects.create(
                teacher=teacher,
                request_type=request_type,
                subject_id=subject_id,
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                academic_year_id=academic_year_id,
                reason=reason,
                status='PENDING'
            )
            
            messages.success(request, 'Your request has been submitted successfully!')
            return redirect('teachers:requests')
            
        except Exception as e:
            messages.error(request, f'Error submitting request: {str(e)}')
            return redirect('teachers:request_create')
    
    # GET request - show form
    context = {
        'teacher': teacher,
        'request_types': TeacherRequest.REQUEST_TYPES,
        'subjects': Subject.objects.filter(is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
    }
    return render(request, 'teachers/request_create.html', context)


@login_required
def api_teachers_search(request):
    """API endpoint for teacher search"""
    query = request.GET.get('q', '')
    if len(query) >= 2:
        teachers = TeacherProfile.objects.filter(
            Q(staff_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).values('id', 'staff_number', 'first_name', 'last_name')[:10]
        return JsonResponse({'teachers': list(teachers)})
    return JsonResponse({'teachers': []})
