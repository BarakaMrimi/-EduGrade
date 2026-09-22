import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edugrade.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("ADMIN_USERNAME")
email = os.environ.get("ADMIN_EMAIL", "")
password = os.environ.get("ADMIN_PASSWORD")

if not username or not password:
    print("ADMIN_USERNAME or ADMIN_PASSWORD is not set.")
else:
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    if created:
        user.set_password(password)
        user.save()
        print(f"Admin '{username}' created successfully.")
    else:
        print(f"Admin '{username}' already exists. No changes made.")
