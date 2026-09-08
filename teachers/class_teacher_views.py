from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import ClassTeacher, TeacherProfile, ClassTeacherRequest
from school.models import GradeLevel, Stream, AcademicYear, Curriculum, Term, Subject
from core.access import is_admin, class_teacher_assignments, send_notification

@login_required
def class_teacher_list(request):
    """List all class teachers"""
    class_teachers = ClassTeacher.objects.select_related(
        'teacher', 'grade_level', 'stream', 'academic_year'
    ).all()
    
    # Filters
    grade_level_id = request.GET.get('grade_level')
    if grade_level_id:
        class_teachers = class_teachers.filter(grade_level_id=grade_level_id)
    
    stream_id = request.GET.get('stream')
    if stream_id:
        class_teachers = class_teachers.filter(stream_id=stream_id)
    
    academic_year_id = request.GET.get('academic_year')
    if academic_year_id:
        class_teachers = class_teachers.filter(academic_year_id=academic_year_id)
    
    is_active = request.GET.get('is_active')
    if is_active:
        class_teachers = class_teachers.filter(is_active=is_active == 'true')
    
    context = {
        'class_teachers': class_teachers,
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
    }
    return render(request, 'class_teachers/list.html', context)


@login_required
def class_teacher_create(request):
    """Assign a class teacher"""
    if request.method == 'POST':
        try:
            teacher_id = request.POST.get('teacher')
            grade_level_id = request.POST.get('grade_level')
            stream_id = request.POST.get('stream')
            academic_year_id = request.POST.get('academic_year')
            is_active = request.POST.get('is_active') == 'on'
            
            # Check if class teacher already exists for this class
            existing = ClassTeacher.objects.filter(
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                academic_year_id=academic_year_id
            ).first()
            
            if existing:
                messages.warning(request, 'This class already has a class teacher!')
                return redirect('class_teachers:create')
            
            # Create class teacher assignment
            class_teacher = ClassTeacher.objects.create(
                teacher_id=teacher_id,
                grade_level_id=grade_level_id,
                stream_id=stream_id,
                academic_year_id=academic_year_id,
                is_active=is_active
            )
            
            messages.success(request, f'Class teacher assigned successfully!')
            return redirect('class_teachers:list')
            
        except Exception as e:
            messages.error(request, f'Error assigning class teacher: {str(e)}')
    
    context = {
        'teachers': TeacherProfile.objects.filter(status='ACTIVE', is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
    }
    return render(request, 'class_teachers/create.html', context)


@login_required
def class_teacher_edit(request, class_teacher_id):
    """Edit class teacher assignment"""
    class_teacher = get_object_or_404(ClassTeacher, id=class_teacher_id)
    
    if request.method == 'POST':
        try:
            class_teacher.teacher_id = request.POST.get('teacher')
            class_teacher.grade_level_id = request.POST.get('grade_level')
            class_teacher.stream_id = request.POST.get('stream')
            class_teacher.academic_year_id = request.POST.get('academic_year')
            class_teacher.is_active = request.POST.get('is_active') == 'on'
            class_teacher.save()
            
            messages.success(request, 'Class teacher updated successfully!')
            return redirect('class_teachers:list')
            
        except Exception as e:
            messages.error(request, f'Error updating class teacher: {str(e)}')
    
    context = {
        'class_teacher': class_teacher,
        'teachers': TeacherProfile.objects.filter(status='ACTIVE', is_active=True),
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
    }
    return render(request, 'class_teachers/edit.html', context)


@login_required
def class_teacher_delete(request, class_teacher_id):
    """Remove class teacher assignment"""
    class_teacher = get_object_or_404(ClassTeacher, id=class_teacher_id)
    
    if request.method == 'POST':
        class_teacher.delete()
        messages.success(request, 'Class teacher removed successfully!')
        return redirect('class_teachers:list')
    
    context = {'class_teacher': class_teacher}
    return render(request, 'class_teachers/delete.html', context)


@login_required
def class_teacher_by_class(request):
    """API endpoint to get class teacher by class"""
    grade_level_id = request.GET.get('grade_level_id')
    stream_id = request.GET.get('stream_id')
    academic_year_id = request.GET.get('academic_year_id')
    
    if grade_level_id and stream_id and academic_year_id:
        class_teacher = ClassTeacher.objects.filter(
            grade_level_id=grade_level_id,
            stream_id=stream_id,
            academic_year_id=academic_year_id,
            is_active=True
        ).select_related('teacher').first()
        
        if class_teacher:
            return JsonResponse({
                'exists': True,
                'teacher_id': class_teacher.teacher.id,
                'teacher_name': class_teacher.teacher.full_name,
                'teacher_staff_number': class_teacher.teacher.staff_number
            })
    
    return JsonResponse({'exists': False})


# ========================================================
# Class Teacher Request Workflow
# ========================================================

@login_required
def class_teacher_request_list(request):
    """List class-teacher requests.

    Teachers see their own requests. Admins see pending requests.
    """
    if is_admin(request.user):
        requests = ClassTeacherRequest.objects.select_related(
            'teacher', 'teacher__user', 'grade_level', 'stream',
            'subject', 'academic_year', 'term'
        ).all().order_by('-requested_at')
        requests = requests.filter(status='PENDING')
    else:
        try:
            teacher = TeacherProfile.objects.get(user=request.user, is_active=True)
            requests = ClassTeacherRequest.objects.filter(teacher=teacher).select_related(
                'grade_level', 'stream', 'subject', 'academic_year', 'term'
            ).order_by('-requested_at')
        except TeacherProfile.DoesNotExist:
            requests = ClassTeacherRequest.objects.none()

    context = {
        'requests': requests,
        'is_admin': is_admin(request.user),
    }
    return render(request, 'class_teachers/requests.html', context)


@login_required
def class_teacher_request_create(request):
    """Teacher submits a request for a specific class-teacher function."""
    try:
        teacher = TeacherProfile.objects.get(user=request.user, is_active=True)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'You do not have a teacher profile!')
        return redirect('core:dashboard')

    if request.method == 'POST':
        request_type = request.POST.get('request_type')
        grade_level_id = request.POST.get('grade_level')
        stream_id = request.POST.get('stream')
        subject_id = request.POST.get('subject')
        academic_year_id = request.POST.get('academic_year')
        term_id = request.POST.get('term')
        specific_students = request.POST.get('specific_students', '')
        reason = request.POST.get('reason')
        description = request.POST.get('description', '')
        duration_days = int(request.POST.get('duration_days', 7))

        if not request_type or not reason:
            messages.error(request, 'Please select a request type and provide a reason.')
            return redirect('class_teachers:request_create')

        if not grade_level_id:
            messages.error(request, 'Please select a grade level.')
            return redirect('class_teachers:request_create')

        req = ClassTeacherRequest.objects.create(
            teacher=teacher,
            request_type=request_type,
            grade_level_id=grade_level_id,
            stream_id=stream_id or None,
            subject_id=subject_id or None,
            academic_year_id=academic_year_id or AcademicYear.objects.filter(is_current=True).first().id,
            term_id=term_id or None,
            specific_students=specific_students,
            reason=reason,
            description=description,
            duration_days=duration_days,
            status='PENDING',
        )
        messages.success(request, f'Request #{req.id} submitted. Waiting for admin approval.')
        return redirect('class_teachers:request_list')

    context = {
        'teacher': teacher,
        'request_types': ClassTeacherRequest.REQUEST_TYPES,
        'grade_levels': GradeLevel.objects.filter(is_active=True),
        'streams': Stream.objects.filter(is_active=True),
        'subjects': Subject.objects.filter(is_active=True),
        'academic_years': AcademicYear.objects.all().order_by('-year'),
        'terms': Term.objects.all(),
    }
    return render(request, 'class_teachers/request_create.html', context)


@login_required
def class_teacher_request_review(request, request_id):
    """Admin reviews and approves/rejects a class teacher request."""
    if not is_admin(request.user):
        messages.error(request, 'Only administrators can review requests.')
        return redirect('core:dashboard')

    req = get_object_or_404(ClassTeacherRequest, id=request_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')

        if action == 'approve':
            req.status = 'APPROVED'
            req.reviewed_by = request.user
            req.reviewed_at = __import__('django.utils.timezone', fromlist=['now']).now()
            req.admin_notes = admin_notes

            # Send notification to the teacher
            _send_request_notification(req, approved=True)

            # Create a PermissionAssignment so the teacher can actually perform the action
            _grant_permission_from_request(req, request.user)

        elif action == 'reject':
            req.status = 'REJECTED'
            req.reviewed_by = request.user
            req.reviewed_at = __import__('django.utils.timezone', fromlist=['now']).now()
            req.admin_notes = admin_notes

            _send_request_notification(req, approved=False)

        req.save()
        messages.success(request, f'Request #{req.id} has been {action.lower()}.')
        return redirect('class_teachers:request_list')

    context = {
        'request_obj': req,
        'is_admin': True,
    }
    return render(request, 'class_teachers/request_review.html', context)


def _send_request_notification(req, approved):
    """Send a notification to the teacher about their request result."""
    from core.models import Notification
    from django.utils import timezone
    from datetime import timedelta

    teacher = req.teacher
    req_type_label = req.get_request_type_display

    if approved:
        title = "Request Approved"
        message = (
            f"Your request for '{req.get_request_type_display()}' has been approved.\n\n"
            f"Grade: {req.grade_level.name if req.grade_level else 'N/A'}\n"
            f"Stream: {req.stream.name if req.stream else 'N/A'}\n"
            f"Subject: {req.subject.name if req.subject else 'N/A'}\n"
        )
        if req.admin_notes:
            message += f"\nAdmin notes: {req.admin_notes}\n"
        message += f"\nPermission granted for {req.duration_days} days."
        notif_type = "APPROVAL"
    else:
        title = "Request Rejected"
        message = f"Your request for '{req.get_request_type_display()}' has been rejected.\n\n"
        if req.admin_notes:
            message += f"Admin notes: {req.admin_notes}\n"
        notif_type = "REJECTION"

    Notification.objects.create(
        recipient=teacher.user,
        title=title,
        message=message,
        notification_type=notif_type,
        url='/teachers/class-teachers/requests/',
        related_object_id=req.id,
        related_object_type='ClassTeacherRequest',
    )


def _grant_permission_from_request(req, granted_by):
    """Create a PermissionAssignment based on the approved request."""
    from core.models import PermissionCode, PermissionAssignment
    from django.utils import timezone
    from datetime import timedelta

    # Map request type to permission code
    request_type_to_permission = {
        'ADD_LEARNER':      'CREATE_STUDENT',
        'TRANSFER_LEARNER': 'TRANSFER_STUDENT',
        'ENTER_MARKS':      'ENTER_MARKS',
        'EDIT_MARKS':       'EDIT_MARKS',
        'SCHOOL_WIDE_MARKS': 'ENTER_MARKS',
        'GENERATE_REPORT':  'GENERATE_REPORT',
        'VIEW_ANALYTICS':   'VIEW_CLASS_ANALYTICS',
        'OTHER':            None,
    }

    permission_code = request_type_to_permission.get(req.request_type)
    if not permission_code:
        return

    permission = PermissionCode.objects.filter(code=permission_code).first()
    if not permission:
        return

    try:
        profile = req.teacher.user.profile
    except Exception:
        return

    expires_at = timezone.now() + timedelta(days=req.duration_days)

    PermissionAssignment.objects.create(
        profile=profile,
        permission=permission,
        subject=req.subject,
        grade_level=req.grade_level,
        stream=req.stream,
        academic_year=req.academic_year,
        term=req.term,
        granted_by=granted_by,
        expires_at=expires_at,
        is_active=True,
    )

    req.granted_at = timezone.now()
    req.save(update_fields=['granted_at'])
