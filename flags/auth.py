# auth decorators for admin views

# flags/auth.py

from audit.models import AdminUser
from django.http import JsonResponse

def admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        api_key = request.headers.get("X-ADMIN-KEY")

        if not api_key:
            return JsonResponse({"error": "Missing admin API key"}, status=401)

        try:
            admin = AdminUser.objects.get(api_key=api_key, is_active=True)                          # Check if the API key exists and is active in the AdminUser model
        except AdminUser.DoesNotExist:
            return JsonResponse({"error": "Invalid or inactive admin key"}, status=403)

        # attach admin to request 
        request.admin = admin

        return view_func(request, *args, **kwargs)

    return _wrapped_view



# RBAC decorator to check if the admin has the required scope for the view 
# RBAC : Role-Based Access Control 
def require_scope(required_scope: str):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            admin = getattr(request, "admin", None)

            if not admin:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            if not admin.has_scope(required_scope):
                return JsonResponse(
                    {"error": f"Missing required scope: {required_scope}"},
                    status=403
                )

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

