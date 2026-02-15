from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import redis
from redis.exceptions import RedisError

from .redis_client import redis_client
from . import utils
from .local_cache import LOCAL_FEATURE_CACHE
from .auth import admin_api_key_required


# Create your views here.
def home(request):
    return HttpResponse("Feature Flag service running")


def is_feature_active(request, feature_name):
    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    if redis_client.exists(redis_key) == 0:
        return HttpResponse(
            f"Feature '{feature_name}' not found"
        )

    try:
        value = redis_client.get(redis_key)

        if value is None:
            is_active = False  # fail-closed
        else:
            is_active = (value == "1")

        # update local cache ONLY on Redis success
        LOCAL_FEATURE_CACHE[redis_key] = is_active

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        # fallback to local cache
        is_active = LOCAL_FEATURE_CACHE.get(redis_key, False)

    return HttpResponse(
        f"Feature '{feature_name}' active: {is_active}"
    )


@csrf_exempt
@admin_api_key_required
def feature_status_change(request, feature_name):
    if request.method != "PATCH":
        return JsonResponse(
            {"error": "Invalid request method"},
            status=405
        )

    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    try:
        if not redis_client.exists(redis_key):
            return JsonResponse(
                {"error": "Feature not found"},
                status=404
            )

        body = request.body.decode("utf-8")
        data = json.loads(body)

        if "enabled" not in data:
            return JsonResponse(
                {"error": 'Missing "enabled" field'},
                status=400
            )

        if not isinstance(data["enabled"], bool):
            return JsonResponse(
                {"error": '"enabled" field must be a boolean'},
                status=400
            )

        redis_value = "1" if data["enabled"] else "0"
        redis_client.set(redis_key, redis_value)

        # update cache ONLY after Redis success
        LOCAL_FEATURE_CACHE[redis_key] = data["enabled"]

        return JsonResponse({
            "feature": feature_name,
            "enabled": data["enabled"]
        })

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        return JsonResponse(
            {"error": "Feature service temporarily unavailable"},
            status=503
        )


@csrf_exempt
@admin_api_key_required              # redirect flow to auth.py -> admin_api_key_required -> _wrapped_view -> feature_status and then back to admin_api_key_required -> _wrapped_view -> feature_status
def initialize_features(request, feature_name):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Invalid request method"},
            status=405
        )

    # validate feature name
    if not feature_name or not isinstance(feature_name, str):
        return JsonResponse(
            {"error": "Feature name is required"},
            status=400
        )

    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    try:
        if redis_client.exists(redis_key):
            return JsonResponse(
                {"error": "Feature already exists"},
                status=409
            )

        # future metadata support (ignored for now)
        if request.body:
            try:
                json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse(
                    {"error": "Invalid JSON body"},
                    status=400
                )

        # always start disabled (A)
        redis_client.set(redis_key, "0")

        # update cache after Redis success
        LOCAL_FEATURE_CACHE[redis_key] = False

        return JsonResponse(
            {
                "feature": feature_name,
                "enabled": False
            },
            status=201
        )

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        return JsonResponse(
            {"error": "Feature service temporarily unavailable"},
            status=503
        )
    

@csrf_exempt
@admin_api_key_required
def delete_feature(request, feature_name):
    if request.method != "DELETE":
        return JsonResponse(
            {"error": "Invalid request method"},
            status=405
        )

    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    try:
        if not redis_client.exists(redis_key):
            return JsonResponse(
                {"error": "Feature not found"},
                status=404
            )

        redis_client.delete(redis_key)

        # update cache ONLY after Redis success
        if redis_key in LOCAL_FEATURE_CACHE:
            del LOCAL_FEATURE_CACHE[redis_key]

        return JsonResponse(
            {"message": f"Feature '{feature_name}' deleted successfully"}
        )

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        return JsonResponse(
            {"error": "Feature service temporarily unavailable"},
            status=503
        )

@csrf_exempt
def list_all_features(request):

    if request.method != "GET":
        return JsonResponse(
            {"error": "Invalid request method"},
            status=405
        )
    
    redis_domain_name = "feature"
    pattern_key = utils.redis_key_generator(redis_domain_name, "*")

    features = {}

    try:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor,
                match=pattern_key,
                count=100
            )

            for key in keys:
                feature_name = key.split(":", 1)[1]
                value = redis_client.get(key)
                is_active = (value == "1")

                # store in response
                features[feature_name] = {
                    "enabled": is_active
                }

                # update local cache
                LOCAL_FEATURE_CACHE[key] = is_active

            if cursor == 0:
                break

        return JsonResponse(
            {"features": features}
        )

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):

        # fallback to local cache
        for key, is_active in LOCAL_FEATURE_CACHE.items():
            if key.startswith(f"{redis_domain_name}:"):
                feature_name = key.split(":", 1)[1]
                features[feature_name] = {
                    "enabled": is_active
                }

        return JsonResponse(
            {
                "features": features,
                "source": "local_cache"
            },
            status=200
        )