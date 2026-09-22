import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edugrade.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("ADMIN_USERNAME", "baraka")
email = os.environ.get("ADMIN_EMAIL", "")
password = os.environ.get("ADMIN_PASSWORD", "10203040")

user, created = User.objects.get_or_create(
    username=username,
    defaults={"email": email}
)

user.email = email
user.is_active = True
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

if created:
    print(f"Admin '{username}' created successfully.")
else:
    print(f"Admin '{username}' updated successfully.")
