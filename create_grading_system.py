import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edugrade.settings')
import django
django.setup()

from grading.models import GradingSystem, GradeRule
from school.models import Curriculum, GradeLevel

print("Creating default grading systems...")

# Get 8-4-4 curriculum
try:
    curriculum_844 = Curriculum.objects.get(code='844')
    
    # Create 8-4-4 grading system
    grading_system, created = GradingSystem.objects.get_or_create(
        name='8-4-4 Standard Grading',
        system_type='844',
        curriculum=curriculum_844,
        defaults={'is_active': True, 'description': 'Standard 8-4-4 grading system'}
    )
    
    if created:
        print(f"✅ Created grading system: {grading_system.name}")
        
        # Create grade rules
        grade_rules = [
            {'grade': 'A', 'grade_name': 'Excellent', 'min_score': 80, 'max_score': 100, 'points': 12, 'order': 1},
            {'grade': 'A-', 'grade_name': 'Very Good', 'min_score': 75, 'max_score': 79, 'points': 11, 'order': 2},
            {'grade': 'B+', 'grade_name': 'Good', 'min_score': 70, 'max_score': 74, 'points': 10, 'order': 3},
            {'grade': 'B', 'grade_name': 'Above Average', 'min_score': 65, 'max_score': 69, 'points': 9, 'order': 4},
            {'grade': 'B-', 'grade_name': 'Average', 'min_score': 60, 'max_score': 64, 'points': 8, 'order': 5},
            {'grade': 'C+', 'grade_name': 'Satisfactory', 'min_score': 55, 'max_score': 59, 'points': 7, 'order': 6},
            {'grade': 'C', 'grade_name': 'Pass', 'min_score': 45, 'max_score': 54, 'points': 6, 'order': 7},
            {'grade': 'C-', 'grade_name': 'Below Average', 'min_score': 40, 'max_score': 44, 'points': 5, 'order': 8},
            {'grade': 'D+', 'grade_name': 'Poor', 'min_score': 35, 'max_score': 39, 'points': 4, 'order': 9},
            {'grade': 'D', 'grade_name': 'Very Poor', 'min_score': 30, 'max_score': 34, 'points': 3, 'order': 10},
            {'grade': 'D-', 'grade_name': 'Extremely Poor', 'min_score': 25, 'max_score': 29, 'points': 2, 'order': 11},
            {'grade': 'E', 'grade_name': 'Fail', 'min_score': 0, 'max_score': 24, 'points': 1, 'order': 12},
        ]
        
        for rule_data in grade_rules:
            rule, created = GradeRule.objects.get_or_create(
                grading_system=grading_system,
                grade=rule_data['grade'],
                defaults={
                    'grade_name': rule_data['grade_name'],
                    'min_score': rule_data['min_score'],
                    'max_score': rule_data['max_score'],
                    'points': rule_data['points'],
                    'order': rule_data['order'],
                    'subject_type': 'ALL'
                }
            )
            if created:
                print(f"   ✅ Created grade rule: {rule.grade} ({rule.min_score}-{rule.max_score})")
    
    print("✅ Default grading system created successfully!")

except Curriculum.DoesNotExist:
    print("❌ 8-4-4 curriculum not found. Please run Phase 2 setup first.")
