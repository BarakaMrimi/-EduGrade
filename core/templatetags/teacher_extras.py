from django import template

register = template.Library()


@register.filter
def has_teacher_profile(user):
    """Return True if the user has a linked TeacherProfile."""
    if not user.is_authenticated:
        return False
    try:
        return hasattr(user, 'teacher_profile') and user.teacher_profile is not None
    except Exception:
        return False


@register.filter
def is_class_teacher(user):
    """Return True if the user is an active class teacher."""
    if not user.is_authenticated:
        return False
    try:
        return user.teacher_profile.class_teacher_assignments.filter(is_active=True).exists()
    except Exception:
        return False


@register.filter
def teacher_is_active(user):
    """Return True if the user's teacher profile is active."""
    if not user.is_authenticated:
        return False
    try:
        profile = user.teacher_profile
        return profile.is_active and profile.status == 'ACTIVE'
    except Exception:
        return False
