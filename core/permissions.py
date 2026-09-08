"""
EduGrade Permission System
===========================

Defines granular permission constants and a decorator / helper for
checking whether a user has a given permission at a specific scope.

Usage in views:

    from core.permissions import require_permission, Permission

    @login_required
    @require_permission(Permission.ENTER_MARKS)
    def mark_entry(request):
        ...

    # Scoped check (subject + grade + stream + year + term)
    if has_permission(request.user, Permission.ENTER_MARKS, scope={
        'subject': subject, 'grade_level': grade_level,
        'stream': stream, 'academic_year': academic_year,
    }):
        ...
"""

# ========================================================
# Permission Code Constants
# ========================================================

class Permission:
    """Flat list of all permission codes used across the system.

    Each code follows the pattern <ACTION>_<OBJECT>.
    Admin / staff users automatically have every permission.
    """

    # --- User management ---
    CREATE_USER          = "CREATE_USER"
    EDIT_USER            = "EDIT_USER"
    ARCHIVE_USER         = "ARCHIVE_USER"
    DELETE_USER          = "DELETE_USER"
    SUSPEND_USER         = "SUSPEND_USER"
    ACTIVATE_USER        = "ACTIVATE_USER"

    # --- Teacher management ---
    CREATE_TEACHER       = "CREATE_TEACHER"
    EDIT_TEACHER         = "EDIT_TEACHER"
    ASSIGN_TEACHER       = "ASSIGN_TEACHER"
    REMOVE_TEACHER_ASSIGNMENT = "REMOVE_TEACHER_ASSIGNMENT"
    APPROVE_TEACHER_REQUEST   = "APPROVE_TEACHER_REQUEST"
    WARN_TEACHER         = "WARN_TEACHER"
    SUSPEND_TEACHER      = "SUSPEND_TEACHER"
    ACTIVATE_TEACHER     = "ACTIVATE_TEACHER"
    ARCHIVE_TEACHER      = "ARCHIVE_TEACHER"

    # --- Student management ---
    CREATE_STUDENT       = "CREATE_STUDENT"
    EDIT_STUDENT         = "EDIT_STUDENT"
    VIEW_STUDENT         = "VIEW_STUDENT"
    TRANSFER_STUDENT     = "TRANSFER_STUDENT"
    ARCHIVE_STUDENT      = "ARCHIVE_STUDENT"

    # --- Assessment management ---
    CREATE_ASSESSMENT    = "CREATE_ASSESSMENT"
    EDIT_ASSESSMENT      = "EDIT_ASSESSMENT"
    VIEW_ASSESSMENT      = "VIEW_ASSESSMENT"
    LOCK_ASSESSMENT      = "LOCK_ASSESSMENT"
    UNLOCK_ASSESSMENT    = "UNLOCK_ASSESSMENT"

    # --- Mark management ---
    ENTER_MARKS          = "ENTER_MARKS"
    EDIT_MARKS           = "EDIT_MARKS"
    REQUEST_MARK_EDIT    = "REQUEST_MARK_EDIT"
    APPROVE_MARK_EDIT    = "APPROVE_MARK_EDIT"
    FINALIZE_MARKS       = "FINALIZE_MARKS"

    # --- Analytics / Reporting ---
    VIEW_SCHOOL_ANALYTICS    = "VIEW_SCHOOL_ANALYTICS"
    VIEW_CLASS_ANALYTICS     = "VIEW_CLASS_ANALYTICS"
    VIEW_STREAM_ANALYTICS    = "VIEW_STREAM_ANALYTICS"
    VIEW_SUBJECT_ANALYTICS   = "VIEW_SUBJECT_ANALYTICS"
    VIEW_LEARNER_ANALYTICS   = "VIEW_LEARNER_ANALYTICS"
    GENERATE_REPORT          = "GENERATE_REPORT"
    REVIEW_REPORT            = "REVIEW_REPORT"
    APPROVE_REPORT           = "APPROVE_REPORT"
    PUBLISH_REPORT           = "PUBLISH_REPORT"
    EXPORT_PDF               = "EXPORT_PDF"
    EXPORT_WORD              = "EXPORT_WORD"

    # --- Grading system configuration ---
    CONFIGURE_ASSESSMENT_SCHEME  = "CONFIGURE_ASSESSMENT_SCHEME"
    CONFIGURE_LEARNING_AREAS     = "CONFIGURE_LEARNING_AREAS"
    CONFIGURE_ASSESSMENT_TYPES   = "CONFIGURE_ASSESSMENT_TYPES"
    CONFIGURE_GRADE_RULES        = "CONFIGURE_GRADE_RULES"

    # --- School settings ---
    MANAGE_SCHOOL_SETTINGS = "MANAGE_SCHOOL_SETTINGS"
    VIEW_AUDIT_LOGS      = "VIEW_AUDIT_LOGS"

    # --- Notifications ---
    VIEW_NOTIFICATIONS   = "VIEW_NOTIFICATIONS"
    MANAGE_NOTIFICATIONS = "MANAGE_NOTIFICATIONS"

    # --- Request management ---
    SUBMIT_TEACHER_REQUEST      = "SUBMIT_TEACHER_REQUEST"
    SUBMIT_CLASS_TEACHER_REQUEST = "SUBMIT_CLASS_TEACHER_REQUEST"
    VIEW_PENDING_REQUESTS         = "VIEW_PENDING_REQUESTS"

    # Master list for iteration
    ALL = (
        CREATE_USER, EDIT_USER, ARCHIVE_USER, DELETE_USER,
        SUSPEND_USER, ACTIVATE_USER,
        CREATE_TEACHER, EDIT_TEACHER, ASSIGN_TEACHER,
        REMOVE_TEACHER_ASSIGNMENT, APPROVE_TEACHER_REQUEST,
        WARN_TEACHER, SUSPEND_TEACHER, ACTIVATE_TEACHER, ARCHIVE_TEACHER,
        CREATE_STUDENT, EDIT_STUDENT, VIEW_STUDENT, TRANSFER_STUDENT,
        ARCHIVE_STUDENT,
        CREATE_ASSESSMENT, EDIT_ASSESSMENT, VIEW_ASSESSMENT,
        LOCK_ASSESSMENT, UNLOCK_ASSESSMENT,
        ENTER_MARKS, EDIT_MARKS, REQUEST_MARK_EDIT, APPROVE_MARK_EDIT,
        FINALIZE_MARKS,
        VIEW_SCHOOL_ANALYTICS, VIEW_CLASS_ANALYTICS, VIEW_STREAM_ANALYTICS,
        VIEW_SUBJECT_ANALYTICS, VIEW_LEARNER_ANALYTICS,
        GENERATE_REPORT, REVIEW_REPORT, APPROVE_REPORT, PUBLISH_REPORT,
        EXPORT_PDF, EXPORT_WORD,
        CONFIGURE_ASSESSMENT_SCHEME, CONFIGURE_LEARNING_AREAS,
        CONFIGURE_ASSESSMENT_TYPES, CONFIGURE_GRADE_RULES,
        MANAGE_SCHOOL_SETTINGS, VIEW_AUDIT_LOGS,
        VIEW_NOTIFICATIONS, MANAGE_NOTIFICATIONS,
        SUBMIT_TEACHER_REQUEST, SUBMIT_CLASS_TEACHER_REQUEST,
        VIEW_PENDING_REQUESTS,
    )

    # Human-readable names and categories for admin display
    LABELS = {
        CREATE_USER:          ("User Management",    "Create new user accounts"),
        EDIT_USER:            ("User Management",    "Edit existing users"),
        ARCHIVE_USER:         ("User Management",    "Archive (soft-delete) users"),
        DELETE_USER:          ("User Management",    "Permanently delete users"),
        SUSPEND_USER:         ("User Management",    "Suspend user accounts"),
        ACTIVATE_USER:        ("User Management",    "Re-activate suspended users"),

        CREATE_TEACHER:       ("Teacher Management", "Create teacher accounts"),
        EDIT_TEACHER:         ("Teacher Management", "Edit teacher profiles"),
        ASSIGN_TEACHER:       ("Teacher Management", "Assign teachers to classes/subjects"),
        REMOVE_TEACHER_ASSIGNMENT: ("Teacher Management", "Remove teacher assignments"),
        APPROVE_TEACHER_REQUEST: ("Teacher Management", "Approve/reject teacher requests"),
        WARN_TEACHER:         ("Teacher Management", "Issue warnings to teachers"),
        SUSPEND_TEACHER:      ("Teacher Management", "Suspend teachers"),
        ACTIVATE_TEACHER:     ("Teacher Management", "Re-activate teachers"),
        ARCHIVE_TEACHER:      ("Teacher Management", "Archive departed teachers"),

        CREATE_STUDENT:       ("Student Management", "Create new learners"),
        EDIT_STUDENT:         ("Student Management", "Edit learner details"),
        VIEW_STUDENT:         ("Student Management", "View learner records"),
        TRANSFER_STUDENT:     ("Student Management", "Transfer learners between classes"),
        ARCHIVE_STUDENT:      ("Student Management", "Archive learners (graduated/transferred)"),

        CREATE_ASSESSMENT:    ("Assessment", "Create examinations / assessments"),
        EDIT_ASSESSMENT:      ("Assessment", "Edit examination details"),
        VIEW_ASSESSMENT:      ("Assessment", "View examination information"),
        LOCK_ASSESSMENT:      ("Assessment", "Lock assessments (prevent mark entry)"),
        UNLOCK_ASSESSMENT:    ("Assessment", "Unlock assessments for further editing"),

        ENTER_MARKS:          ("Marks", "Enter assessment marks for assigned subjects/classes"),
        EDIT_MARKS:           ("Marks", "Edit already-entered marks (with approval)"),
        REQUEST_MARK_EDIT:    ("Marks", "Request a mark correction"),
        APPROVE_MARK_EDIT:    ("Marks", "Approve/reject mark correction requests"),
        FINALIZE_MARKS:       ("Marks", "Lock / finalize marks after entry"),

        VIEW_SCHOOL_ANALYTICS:("Analytics",    "View school-wide analytics"),
        VIEW_CLASS_ANALYTICS: ("Analytics",    "View class-level analytics"),
        VIEW_STREAM_ANALYTICS:("Analytics",    "View stream-level analytics"),
        VIEW_SUBJECT_ANALYTICS:("Analytics",   "View subject-level analytics"),
        VIEW_LEARNER_ANALYTICS:("Analytics",   "View individual learner analytics"),

        GENERATE_REPORT:      ("Reports", "Generate student/class/school reports"),
        REVIEW_REPORT:        ("Reports", "Review generated reports"),
        APPROVE_REPORT:       ("Reports", "Approve reports before publishing"),
        PUBLISH_REPORT:       ("Reports", "Publish reports for viewing"),
        EXPORT_PDF:           ("Reports", "Export reports as PDF"),
        EXPORT_WORD:          ("Reports", "Export reports as Word"),

        CONFIGURE_ASSESSMENT_SCHEME: ("Grading Config", "Configure assessment schemes"),
        CONFIGURE_LEARNING_AREAS:    ("Grading Config", "Configure CBC learning areas / performance levels"),
        CONFIGURE_ASSESSMENT_TYPES:  ("Grading Config", "Configure assessment types (SBA, Summative, etc.)"),
        CONFIGURE_GRADE_RULES:       ("Grading Config", "Configure KCSE grade boundaries"),

        MANAGE_SCHOOL_SETTINGS: ("Settings", "Manage school information and configuration"),
        VIEW_AUDIT_LOGS:        ("Settings", "View audit log records"),

        VIEW_NOTIFICATIONS:     ("Notifications", "View in-system notifications"),
        MANAGE_NOTIFICATIONS:   ("Notifications", "Manage notification settings"),

        SUBMIT_TEACHER_REQUEST:      ("Requests", "Submit teacher assignment requests"),
        SUBMIT_CLASS_TEACHER_REQUEST:("Requests", "Submit class-teacher function requests"),
        VIEW_PENDING_REQUESTS:       ("Requests", "View pending teacher/class-teacher requests"),
    }

    # Permissions that should only ever be granted globally (not scoped)
    GLOBAL_ONLY = frozenset({
        CREATE_USER, EDIT_USER, ARCHIVE_USER, DELETE_USER,
        SUSPEND_USER, ACTIVATE_USER,
        CREATE_TEACHER, EDIT_TEACHER, ASSIGN_TEACHER,
        REMOVE_TEACHER_ASSIGNMENT, APPROVE_TEACHER_REQUEST,
        WARN_TEACHER, SUSPEND_TEACHER, ACTIVATE_TEACHER, ARCHIVE_TEACHER,
        MANAGE_SCHOOL_SETTINGS, VIEW_AUDIT_LOGS,
        CONFIGURE_ASSESSMENT_SCHEME, CONFIGURE_LEARNING_AREAS,
        CONFIGURE_ASSESSMENT_TYPES, CONFIGURE_GRADE_RULES,
        VIEW_SCHOOL_ANALYTICS,
    })


def get_permission_label(code):
    """Return (category, description) for a permission code."""
    return Permission.LABELS.get(code, ("Other", ""))


# Scope helper
SCOPE_FIELDS = (
    "subject", "grade_level", "stream",
    "academic_year", "term", "examination",
)
