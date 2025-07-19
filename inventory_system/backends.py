from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)

            if user.check_password(password):
                # Check is user is admin
                if not user.is_staff and not user.is_superuser:
                    return user
        except User.DoesNotExist:
            return None

        return None
