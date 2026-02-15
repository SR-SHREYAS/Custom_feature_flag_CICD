from functools import wraps
from django.http import JsonResponse
from .redis_client import redis_client

RATE_LIMIT = 30          # Max requests
RATE_LIMIT_WINDOW = 60   # Time window in seconds


def admin_rate_limit(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):                 # get the admin API key from request headers and check if it exists 
        admin_key = request.headers.get("X-ADMIN-KEY")
        if not admin_key:
            return JsonResponse(
                {"error": "Missing admin API key"},
                status=400
            )

        redis_key = f"rate_limit:admin:{admin_key}"            # Redis key format to track requests per admin API key 

        try:
            current_requests = redis_client.incr(redis_key)       # Increment the request count

            # If this is the first request, set TTL
            if current_requests == 1: 
                redis_client.expire(redis_key, RATE_LIMIT_WINDOW)      

            if current_requests > RATE_LIMIT:                   
                return JsonResponse(
                    {"error": "Rate limit exceeded"},
                    status=429
                )

        except Exception:
            pass            # In case of Redis failure, we allow the request to go through to avoid blocking admins

        return view_func(request, *args, **kwargs)

    return _wrapped_view
