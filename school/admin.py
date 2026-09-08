from django.contrib import admin
from .models import (
    AcademicYear, Term, Curriculum, GradeLevel, 
    Stream, Subject, SchoolInfo
)

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'name', 'is_current', 'start_date', 'end_date']
    list_filter = ['is_current']
    search_fields = ['year', 'name']
    ordering = ['-year']

@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'term_number', 'is_active', 'start_date', 'end_date']
    list_filter = ['academic_year', 'is_active']
    search_fields = ['name']
    ordering = ['academic_year', 'term_number']

@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']

@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'curriculum', 'level_type', 'level_number', 'order', 'is_active']
    list_filter = ['curriculum', 'level_type', 'is_active']
    search_fields = ['name']

@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'grade_level', 'capacity', 'is_active']
    list_filter = ['grade_level', 'is_active']
    search_fields = ['name', 'code']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'short_name', 'curriculum', 'subject_type', 'is_active']
    list_filter = ['curriculum', 'subject_type', 'is_active']
    search_fields = ['code', 'name']
    filter_horizontal = ['grade_levels']

@admin.register(SchoolInfo)
class SchoolInfoAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'current_academic_year']
