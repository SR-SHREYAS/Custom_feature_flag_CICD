# auth decorators for admin views

# flags/auth.py

from django.conf import settings
from django.http import JsonResponse
from functools import wraps


def admin_api_key_required(view_func):                          # view_func is the view being decorated from views.py
    @wraps(view_func)                                           # wraps to preserve original view function metadata 
    def _wrapped_view(request, *args, **kwargs):                # inner function to handle the request , *args and **kwargs to pass any additional arguments
        api_key = request.headers.get("X-ADMIN-KEY")            # get the API key from request headers

        if api_key != settings.ADMIN_API_KEY:                   
            return JsonResponse(
                {"error": "Forbidden"},
                status=403
            )

        return view_func(request, *args, **kwargs)              # call the original view function if API key is valid

    return _wrapped_view                                        # return the inner function as the decorated view 


