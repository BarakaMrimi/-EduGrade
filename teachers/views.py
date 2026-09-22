from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime
from .models import TeacherProfile, TeacherAssignment, TeacherRequest, ClassTeacher, ClassTeacherRequest
from school.models import Subject, GradeLevel, Stream, AcademicYear, Curriculum
from marks.models import MarkEntry, MarkSubmission
from students.models import Student, StudentHistory
from core.permissions import Permission
from core.models import Notification, PermissionAssignment, PermissionCode, Role, UserProfile
from core.access import has_permission, is_admin, send_notification, notify_warning, notify_suspension, notify_request_result


def _is_admin(user):
    return user.is_staff or user.is_superuser

@login_required
def teacher_list(request):
    """List all registered teachers — admin only."""
    if not _is_admin(request.user):
        messages.error(request, 'Only administrators can view all teachers.')
        return redirect('core:dashboard')
    
    # Default to showing only functional teachers (self-registered, active)
    show_all = request.GET.get('show_all') == '1'
    teachers = TeacherProfile.objects.select_related('user').filter(
        created_via='SELF_REGISTER',
        is_active=True,
        status='ACTIVE'
    )
    
    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(staff_number__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if show_all:
        teachers = TeacherProfile.objects.select_related('user').filter(
            created_via='SELF_REGISTER'
        )
        if search_query:
            teachers = teachers.filter(
                Q(staff_number__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )
    
    paginator = Paginator(teachers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop('page', None)
    
    context = {
        'teachers': page_obj,
        'search_query': search_query,
        'status_choices': TeacherProfile.STATUS_CHOICES,
        'selected_status': '',
        'pending_requests': TeacherRequest.objects.filter(status='PENDING').count(),
        'pagination_query': query_params.urlencode(),
        'show_all': show_all,
    }
    return render(request, 'teachers/list.html', context)


@login_required
def teacher_detail(request, teacher_id):
    """View teacher details — admin can view all, teachers can view their own."""
    from core.models import Role, UserProfile, SuspensionRecord, WarningRecord
    
    teacher = get_object_or_404(TeacherProfile, id=teacher_id)
    is_admin = _is_admin(request.user)
    
    if not is_admin and teacher.user_id != request.user.id:
        messages.error(request, 'You can only view your own profile.')
        return redirect('core:dashboard')

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
def teacher_edit(request, teacher_id):
    """Edit teacher details — admin only."""
    if not _is_admin(request.user):
        messages.error(request, 'Only administrators can edit teacher profiles.')
        return redirect('core:dashboard')
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
    """Assign teacher to subject and class — admin only."""
    if not _is_admin(request.user):
        messages.error(request, 'Only administrators can manage teacher assignments.')
        return redirect('core:dashboard')
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
    is_admin = request.user.is_staff or request.user.is_superuser
    
    if is_admin:
        requests_list = TeacherRequest.objects.select_related(
            'teacher', 'subject', 'grade_level', 'stream', 'academic_year'
        ).all()
    else:
        try:
            teacher_profile = TeacherProfile.objects.get(user=request.user)
            requests_list = TeacherRequest.objects.filter(teacher=teacher_profile).select_related(
                'subject', 'grade_level', 'stream', 'academic_year'
            )
        except TeacherProfile.DoesNotExist:
            requests_list = TeacherRequest.objects.none()
    
    if request.method == 'POST' and is_admin:
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '').strip()

        teacher_request = get_object_or_404(TeacherRequest, id=request_id)

        if action in ('approve', 'reapprove'):
            try:
                with transaction.atomic():
                    teacher_request.reviewed_by = request.user
                    teacher_request.reviewed_date = timezone.now()
                    teacher_request.admin_notes = admin_notes
                    _execute_approval(teacher_request, request.user)
                    teacher_request.status = 'APPROVED'
                    teacher_request.save(
                        update_fields=['status', 'reviewed_by', 'reviewed_date', 'admin_notes']
                    )
                notify_request_result(teacher_request, approved=True, admin_notes=admin_notes)
                messages.success(request, f'Request approved for {teacher_request.teacher.full_name}!')
            except ValidationError as exc:
                messages.error(request, f'Request cannot be approved: {exc.message}')
            except Exception as exc:
                messages.error(request, f'Approval could not be completed: {exc}')
            return redirect('teachers:requests')

        if action == 'reject':
            with transaction.atomic():
                teacher_request.status = 'REJECTED'
                teacher_request.reviewed_by = request.user
                teacher_request.reviewed_date = timezone.now()
                teacher_request.admin_notes = admin_notes
                teacher_request.save(
                    update_fields=['status', 'reviewed_by', 'reviewed_date', 'admin_notes']
                )
            notify_request_result(teacher_request, approved=False, admin_notes=admin_notes)
            messages.warning(request, f'Request rejected for {teacher_request.teacher.full_name}!')
            return redirect('teachers:requests')

        messages.error(request, 'Unknown request action.')
        return redirect('teachers:requests')
    
    status_filter = request.GET.get('status', '')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    context = {
        'requests': requests_list,
        'status_choices': TeacherRequest.REQUEST_STATUS,
        'is_admin': is_admin,
    }
    return render(request, 'teachers/requests.html', context)


def _get_or_create_permission(code):
    label, description = Permission.LABELS.get(code, (code, ''))
    permission, _ = PermissionCode.objects.get_or_create(
        code=code,
        defaults={'name': label, 'description': description, 'category': label.split()[0]},
    )
    return permission


def _upsert_permission(profile, permission, granted_by, **scope):
    assignment = PermissionAssignment.objects.filter(
        profile=profile,
        permission=permission,
        **scope,
    ).first()
    if assignment:
        assignment.is_active = True
        assignment.expires_at = None
        assignment.granted_by = granted_by
        assignment.save(
            update_fields=['is_active', 'expires_at', 'granted_by']
        )
        return assignment
    return PermissionAssignment.objects.create(
        profile=profile,
        permission=permission,
        granted_by=granted_by,
        expires_at=None,
        is_active=True,
        **scope,
    )


def _grant_assignment_permissions(profile, teacher_request, granted_by):
    scope = {
        'grade_level': teacher_request.grade_level,
        'stream': teacher_request.stream,
        'academic_year': teacher_request.academic_year,
    }
    if teacher_request.role == 'class_teacher':
        _upsert_permission(profile, _get_or_create_permission(Permission.ENTER_MARKS), granted_by, **scope)
        _upsert_permission(profile, _get_or_create_permission(Permission.VIEW_STUDENT), granted_by, **scope)
        _upsert_permission(profile, _get_or_create_permission(Permission.VIEW_CLASS_ANALYTICS), granted_by, **scope)
        _upsert_permission(profile, _get_or_create_permission(Permission.GENERATE_REPORT), granted_by, **scope)
        return

    subject_scope = {'subject': teacher_request.subject, **scope}
    _upsert_permission(profile, _get_or_create_permission(Permission.ENTER_MARKS), granted_by, **subject_scope)
    _upsert_permission(profile, _get_or_create_permission(Permission.VIEW_STUDENT), granted_by, **scope)
    _upsert_permission(profile, _get_or_create_permission(Permission.VIEW_SUBJECT_ANALYTICS), granted_by, **subject_scope)
    _upsert_permission(profile, _get_or_create_permission(Permission.GENERATE_REPORT), granted_by, **scope)


def _revoke_removed_permissions(profile, teacher_request):
    permissions = PermissionAssignment.objects.filter(
        profile=profile,
        is_active=True,
        grade_level=teacher_request.grade_level,
        stream=teacher_request.stream,
        academic_year=teacher_request.academic_year,
    )
    if teacher_request.role == 'teacher':
        permissions = permissions.filter(subject=teacher_request.subject)
    else:
        permissions = permissions.filter(subject__isnull=True)
    permissions.update(is_active=False)


def _sync_effective_profile(teacher):
    profile, _ = UserProfile.objects.get_or_create(user=teacher.user)
    has_class_role = teacher.class_teacher_assignments.filter(is_active=True).exists()
    has_subject_role = teacher.assignments.filter(status='APPROVED').exists()

    if has_class_role:
        role_name = 'CLASS_TEACHER'
    elif has_subject_role or teacher.status == 'ACTIVE':
        role_name = 'TEACHER'
    else:
        role_name = profile.role.name if profile.role_id else 'TEACHER'

    role, _ = Role.objects.get_or_create(name=role_name)
    profile.role = role
    profile.is_active = teacher.is_active
    profile.save(update_fields=['role', 'is_active', 'updated_at'])
    return profile


def _validate_removal_scope(teacher_request):
    if not teacher_request.grade_level_id or not teacher_request.academic_year_id:
        raise ValidationError('Grade/Form and Academic Year are required.')
    if teacher_request.role == 'class_teacher':
        if not teacher_request.stream_id:
            raise ValidationError('Stream is required for a Class Teacher removal.')
    elif not teacher_request.subject_id or not teacher_request.stream_id:
        raise ValidationError('Subject and Stream are required for a Teacher removal.')


def _execute_approval(teacher_request, granted_by):
    if teacher_request.request_type == 'REMOVE':
        _validate_removal_scope(teacher_request)
        if teacher_request.role == 'class_teacher':
            ClassTeacher.objects.filter(
                teacher=teacher_request.teacher,
                grade_level=teacher_request.grade_level,
                stream=teacher_request.stream,
                academic_year=teacher_request.academic_year,
            ).delete()
        else:
            TeacherAssignment.objects.filter(
                teacher=teacher_request.teacher,
                subject=teacher_request.subject,
                grade_level=teacher_request.grade_level,
                stream=teacher_request.stream,
                academic_year=teacher_request.academic_year,
            ).delete()
        profile, _ = UserProfile.objects.get_or_create(user=teacher_request.teacher.user)
        _revoke_removed_permissions(profile, teacher_request)
        _sync_effective_profile(teacher_request.teacher)
        return

    if not teacher_request.grade_level_id or not teacher_request.academic_year_id:
        raise ValidationError('Grade/Form and Academic Year are required.')
    if not teacher_request.stream_id:
        raise ValidationError('Stream is required for this assignment.')

    if teacher_request.role == 'class_teacher':
        existing_class = ClassTeacher.objects.filter(
            grade_level=teacher_request.grade_level,
            stream=teacher_request.stream,
            academic_year=teacher_request.academic_year,
        ).first()
        if existing_class and existing_class.teacher_id != teacher_request.teacher_id:
            raise ValidationError('This class already has an active class teacher.')
        ClassTeacher.objects.update_or_create(
            teacher=teacher_request.teacher,
            grade_level=teacher_request.grade_level,
            stream=teacher_request.stream,
            academic_year=teacher_request.academic_year,
            defaults={'is_active': True},
        )
    else:
        if not teacher_request.subject_id:
            raise ValidationError('Subject is required for a Teacher assignment.')
        curriculum = (
            teacher_request.grade_level.curriculum
            or teacher_request.subject.curriculum
        )
        if not curriculum:
            raise ValidationError('A curriculum is required for this assignment.')
        TeacherAssignment.objects.update_or_create(
            teacher=teacher_request.teacher,
            subject=teacher_request.subject,
            grade_level=teacher_request.grade_level,
            stream=teacher_request.stream,
            academic_year=teacher_request.academic_year,
            defaults={
                'curriculum': curriculum,
                'status': 'APPROVED',
                'is_class_teacher': False,
                'approved_by': granted_by,
                'approved_date': timezone.now().date(),
                'notes': teacher_request.reason,
            },
        )

    teacher_request.teacher.status = 'ACTIVE'
    teacher_request.teacher.is_active = True
    teacher_request.teacher.save(update_fields=['status', 'is_active', 'updated_at'])
    profile = _sync_effective_profile(teacher_request.teacher)
    _grant_assignment_permissions(profile, teacher_request, granted_by)


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
        role = request.POST.get('role', '').strip()
        request_type = request.POST.get('request_type', '').strip()
        subject_id = request.POST.get('subject', '').strip()
        grade_level_id = request.POST.get('grade_level', '').strip()
        stream_id = request.POST.get('stream', '').strip()
        academic_year_id = request.POST.get('academic_year', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not role or not request_type or not grade_level_id or not stream_id or not academic_year_id or not reason:
            messages.error(request, 'Please fill in all required fields: Role, Request Type, Grade/Form, Stream, Academic Year, and Reason.')
            return redirect('teachers:request_create')

        if role not in dict(TeacherRequest.ROLES):
            messages.error(request, 'Invalid role selected.')
            return redirect('teachers:request_create')

        if role == 'teacher' and not subject_id:
            messages.error(request, 'Subject is required for Teacher role.')
            return redirect('teachers:request_create')

        try:
            teacher_request = TeacherRequest.objects.create(
                teacher=teacher,
                request_type=request_type,
                role=role,
                subject_id=subject_id or None,
                grade_level_id=grade_level_id,
                stream_id=stream_id or None,
                academic_year_id=academic_year_id,
                reason=reason,
                status='PENDING'
            )

            role_label = 'Class Teacher' if role == 'class_teacher' else 'Teacher'

            admin_message = (
                f"{teacher.full_name} is requesting to serve as {role_label}.\n\n"
                f"Request Type: {teacher_request.get_request_type_display()}\n"
                f"Role: {role_label}\n"
            )
            if teacher_request.subject:
                admin_message += f"Subject: {teacher_request.subject.name}\n"
            admin_message += (
                f"Grade/Form: {teacher_request.grade_level.name}\n"
                f"Stream: {teacher_request.stream.name if teacher_request.stream else 'N/A'}\n"
                f"Academic Year: {teacher_request.academic_year.year}\n\n"
                f"Reason: {reason}\n\n"
                f"Please review and approve or reject this request."
            )

            from django.contrib.auth import get_user_model
            admins = get_user_model().objects.filter(is_staff=True, is_active=True)
            for admin in admins:
                send_notification(
                    admin,
                    title=f"New {role_label} Request",
                    message=admin_message,
                    notification_type="APPROVAL_REQUEST",
                    url="/teachers/requests/",
                    related_object_id=str(teacher_request.id),
                    related_object_type="TeacherRequest",
                )

            messages.success(request, 'Your request has been submitted successfully!')
            return redirect('teachers:requests')

        except Exception as e:
            messages.error(request, f'Error submitting request: {str(e)}')
            return redirect('teachers:request_create')

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


@login_required
def teacher_request_approval(request):
    """Allow an unapproved/inactive teacher to remind admin to approve their account."""
    try:
        teacher = TeacherProfile.objects.get(user=request.user)
    except TeacherProfile.DoesNotExist:
        messages.error(request, 'You do not have a teacher profile. Contact the administrator.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        from core.access import send_approval_reminder
        send_approval_reminder(request.user)
        messages.success(request, 'Approval request sent to administrators. You will be notified once your account is approved.')
        return redirect('core:dashboard')

    context = {
        'teacher': teacher,
        'is_pending': not teacher.is_active or teacher.status in ('INACTIVE', 'PENDING'),
    }
    return render(request, 'teachers/request_approval.html', context)


@login_required
def my_status(request):
    admin_user = is_admin(request.user)
    teacher = TeacherProfile.objects.select_related('user').filter(user=request.user).first()
    user_profile = UserProfile.objects.select_related('role').filter(user=request.user).first()
    if user_profile is None:
        user_profile = UserProfile.objects.create(user=request.user)

    if teacher:
        all_assignments = TeacherAssignment.objects.filter(
            teacher=teacher
        ).select_related(
            'subject', 'grade_level', 'stream', 'academic_year', 'curriculum', 'term', 'approved_by'
        ).order_by('-academic_year__year', 'grade_level__order', 'subject__name')
        approved_assignments = all_assignments.filter(status='APPROVED')
        class_teacher_records = ClassTeacher.objects.filter(
            teacher=teacher, is_active=True
        ).select_related('grade_level', 'stream', 'academic_year').order_by('-academic_year__year')
        requests = teacher.requests.select_related(
            'subject', 'grade_level', 'stream', 'academic_year', 'reviewed_by'
        ).order_by('-requested_date')
        class_teacher_requests = teacher.class_teacher_requests.select_related(
            'grade_level', 'stream', 'subject', 'academic_year', 'term', 'reviewed_by'
        ).order_by('-requested_at')
        mark_submissions = MarkSubmission.objects.filter(
            teacher=teacher
        ).select_related(
            'examination', 'examination__academic_year', 'examination__term',
            'subject', 'grade_level', 'stream', 'submitted_by', 'approved_by'
        ).order_by('-submission_date')
        scope_q = Q()
        for assignment in approved_assignments:
            scope_q |= Q(
                current_grade_level_id=assignment.grade_level_id,
                current_stream_id=assignment.stream_id,
                academic_year_id=assignment.academic_year_id,
            )
        for class_assignment in class_teacher_records:
            scope_q |= Q(
                current_grade_level_id=class_assignment.grade_level_id,
                current_stream_id=class_assignment.stream_id,
                academic_year_id=class_assignment.academic_year_id,
            )
        has_scope = bool(scope_q.children)
        if admin_user and not has_scope:
            students_in_scope = Student.objects.filter(is_active=True)
        elif has_scope:
            students_in_scope = Student.objects.filter(scope_q, is_active=True)
        else:
            students_in_scope = Student.objects.none()
        students_in_scope = students_in_scope.select_related(
            'curriculum', 'current_grade_level', 'current_stream', 'academic_year'
        ).distinct()

        students_with_marks = Student.objects.filter(marks__entered_by=request.user)
        if has_scope or admin_user:
            students_with_marks = students_with_marks.filter(scope_q if has_scope else Q(pk__in=students_in_scope.values('pk')))
        students_with_marks = students_with_marks.select_related(
            'current_grade_level', 'current_stream', 'academic_year'
        ).distinct()

        student_progress = students_in_scope.annotate(
            entered_mark_count=Count(
                'marks', filter=Q(marks__entered_by=request.user), distinct=True
            ),
            average_score=Avg('marks__score', filter=Q(marks__entered_by=request.user)),
        ).order_by('admission_number')

        stream_progress = students_in_scope.values(
            'current_grade_level_id', 'current_grade_level__name',
            'current_stream_id', 'current_stream__name',
            'academic_year_id', 'academic_year__year',
        ).annotate(
            enrolled_students=Count('id', distinct=True),
            assessed_students=Count('marks__student_id', filter=Q(marks__isnull=False), distinct=True),
            marks_entered=Count('marks', filter=Q(marks__entered_by=request.user)),
            average_score=Avg('marks__score'),
        ).order_by('-academic_year__year', 'current_grade_level__order', 'current_stream__name')

        reenrolled_streams = StudentHistory.objects.filter(
            student__in=students_in_scope,
        ).exclude(is_current=True).select_related(
            'student', 'student__current_grade_level', 'student__current_stream',
            'academic_year', 'grade_level', 'stream'
        ).order_by('-academic_year__year', '-created_at')[:20]

        try:
            from grading.models import StudentOverallKCSE, StudentOverallCBA
            kcse_progress = StudentOverallKCSE.objects.filter(
                student__in=students_in_scope
            ).select_related('student', 'examination').order_by('-examination__start_date')[:20]
            cbc_progress = StudentOverallCBA.objects.filter(
                student__in=students_in_scope
            ).select_related('student', 'examination', 'overall_level').order_by('-examination__start_date')[:20]
        except Exception:
            kcse_progress = StudentOverallKCSE.objects.none() if 'StudentOverallKCSE' in locals() else Student.objects.none()
            cbc_progress = StudentOverallCBA.objects.none() if 'StudentOverallCBA' in locals() else Student.objects.none()
    else:
        all_assignments = TeacherAssignment.objects.none()
        approved_assignments = TeacherAssignment.objects.none()
        class_teacher_records = ClassTeacher.objects.none()
        requests = TeacherRequest.objects.none()
        class_teacher_requests = ClassTeacherRequest.objects.none()
        mark_submissions = MarkSubmission.objects.none()
        students_in_scope = Student.objects.filter(is_active=True) if admin_user else Student.objects.none()
        students_with_marks = Student.objects.none()
        student_progress = Student.objects.none()
        stream_progress = Student.objects.none()
        reenrolled_streams = StudentHistory.objects.none()
        kcse_progress = Student.objects.none()
        cbc_progress = Student.objects.none()

    marks_entered = MarkEntry.objects.filter(
        entered_by=request.user
    ).select_related(
        'student', 'student__current_grade_level', 'student__current_stream',
        'examination', 'examination__academic_year', 'examination__term',
        'subject', 'grade_level', 'stream'
    ).order_by('-updated_at')
    recent_marks_entered = marks_entered[:20]
    total_marks_count = marks_entered.count()
    active_permissions = user_profile.effective_permissions().select_related(
        'permission', 'subject', 'grade_level', 'stream', 'academic_year', 'term', 'examination'
    ).order_by('-granted_at')
    notifications = request.user.notifications.all().order_by('-created_at')[:10]
    mark_summary = marks_entered.aggregate(average_score=Avg('score'))
    enrolled_students_count = students_in_scope.count()
    assessed_students_count = students_with_marks.count()

    context = {
        'teacher': teacher,
        'user_profile': user_profile,
        'admin_user': admin_user,
        'role_label': user_profile.role.get_name_display() if user_profile.role_id else ('Teacher' if teacher else 'No role assigned'),
        'profile_status': teacher.get_status_display() if teacher else ('Active' if request.user.is_active else 'Inactive'),
        'is_suspended': user_profile.is_suspended,
        'all_assignments': all_assignments,
        'approved_assignments': approved_assignments,
        'active_assignments_count': approved_assignments.count(),
        'class_teacher_records': class_teacher_records,
        'is_class_teacher': class_teacher_records.exists(),
        'requests': requests,
        'pending_requests_count': requests.filter(status='PENDING').count() if teacher else 0,
        'class_teacher_requests': class_teacher_requests,
        'pending_class_teacher_requests_count': class_teacher_requests.filter(status='PENDING').count() if teacher else 0,
        'students_in_scope': students_in_scope,
        'students_with_marks': students_with_marks,
        'student_progress': student_progress,
        'stream_progress': stream_progress,
        'reenrolled_streams': reenrolled_streams,
        'marks_entered': recent_marks_entered,
        'total_marks_count': total_marks_count,
        'mark_submissions': mark_submissions,
        'average_mark_score': mark_summary.get('average_score'),
        'enrolled_students_count': enrolled_students_count,
        'assessed_students_count': assessed_students_count,
        'kcse_progress': kcse_progress,
        'cbc_progress': cbc_progress,
        'active_permissions': active_permissions,
        'notifications': notifications,
    }
    return render(request, 'teachers/my_status.html', context)
