from django.db import transaction

from core.models import AuditLog
from students.models import Student, StudentHistory
from teachers.models import ClassTeacher, TeacherAssignment


def _move_class_teacher_assignments(source_grade, source_stream, destination_grade, destination_stream):
    assignments = ClassTeacher.objects.filter(
        grade_level=source_grade,
        **({'stream': source_stream} if source_stream else {}),
    )
    for assignment in assignments:
        duplicate = ClassTeacher.objects.filter(
            grade_level=destination_grade,
            stream=destination_stream,
            academic_year=assignment.academic_year,
        ).exclude(pk=assignment.pk).exists()
        if duplicate:
            assignment.delete()
            continue
        assignment.grade_level = destination_grade
        assignment.stream = destination_stream
        assignment.save(update_fields=['grade_level', 'stream', 'updated_at'])


def _move_teacher_assignments(source_grade, source_stream, destination_grade, destination_stream):
    assignments = TeacherAssignment.objects.filter(
        grade_level=source_grade,
        **({'stream': source_stream} if source_stream else {}),
    )
    for assignment in assignments:
        duplicate = TeacherAssignment.objects.filter(
            teacher=assignment.teacher,
            subject=assignment.subject,
            grade_level=destination_grade,
            stream=destination_stream,
            academic_year=assignment.academic_year,
        ).exclude(pk=assignment.pk).exists()
        if duplicate:
            assignment.delete()
            continue
        assignment.grade_level = destination_grade
        assignment.stream = destination_stream
        assignment.curriculum = destination_grade.curriculum
        assignment.save(update_fields=['grade_level', 'stream', 'curriculum', 'updated_at'])


@transaction.atomic
def bulk_reallocate_students(source_grade, source_stream, destination_grade, destination_stream, actor):
    """Move all students and assignments from a grade/stream to a new destination."""
    students = Student.objects.filter(
        current_grade_level=source_grade,
        **({'current_stream': source_stream} if source_stream else {}),
    )

    for student in students.select_for_update():
        StudentHistory.objects.filter(student=student, is_current=True).update(is_current=False)
        StudentHistory.objects.create(
            student=student,
            academic_year=student.academic_year,
            grade_level=destination_grade,
            stream=destination_stream,
            is_current=True,
        )
        old_placement = {
            'grade_level': student.current_grade_level_id,
            'stream': student.current_stream_id,
            'academic_year': student.academic_year_id,
        }
        student.current_grade_level = destination_grade
        student.current_stream = destination_stream
        student.updated_by = actor
        student.save(update_fields=['current_grade_level', 'current_stream', 'updated_by', 'updated_at'])
        AuditLog.objects.create(
            user=actor,
            action='UPDATE',
            model_name='Student',
            object_id=str(student.pk),
            object_repr=str(student),
            changes={'placement_from': old_placement, 'placement_to': {
                'grade_level': destination_grade.pk,
                'stream': destination_stream.pk,
                'academic_year': student.academic_year_id,
            }},
        )

    _move_class_teacher_assignments(source_grade, source_stream, destination_grade, destination_stream)
    _move_teacher_assignments(source_grade, source_stream, destination_grade, destination_stream)
    return students.count()


@transaction.atomic
def reallocate_and_delete(source, destination_grade, destination_stream, actor):
    """Move all dependants of a grade or stream before deleting it."""
    source_stream = source if source.__class__.__name__ == 'Stream' else None
    source_grade = source.grade_level if source_stream else source
    bulk_reallocate_students(source_grade, source_stream, destination_grade, destination_stream, actor)

    AuditLog.objects.create(
        user=actor,
        action='DELETE',
        model_name=source.__class__.__name__,
        object_id=str(source.pk),
        object_repr=str(source),
        changes={'reallocated_to_grade': destination_grade.pk, 'reallocated_to_stream': destination_stream.pk},
    )
    source.delete()