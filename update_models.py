import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edugrade.settings')
import django
django.setup()

from django.db import connection

print("=" * 60)
print("  UPDATING MODEL DEFINITIONS")
print("=" * 60)

# Rename columns in the database
with connection.cursor() as cursor:
    try:
        # For kcse_grade_rules
        cursor.execute("ALTER TABLE kcse_grade_rules RENAME COLUMN sort_order TO `order`")
        print("  ✅ Renamed sort_order to order in kcse_grade_rules")
    except:
        print("  ⚠️ Column already named order")
    
    try:
        # For performance_levels
        cursor.execute("ALTER TABLE performance_levels RENAME COLUMN sort_order TO `order`")
        print("  ✅ Renamed sort_order to order in performance_levels")
    except:
        print("  ⚠️ Column already named order")
    
    try:
        # For rubric_criteria
        cursor.execute("ALTER TABLE rubric_criteria RENAME COLUMN sort_order TO `order`")
        print("  ✅ Renamed sort_order to order in rubric_criteria")
    except:
        print("  ⚠️ Column already named order")

print("\n" + "=" * 60)
print("  ✅ MODEL UPDATES COMPLETE")
print("=" * 60)
