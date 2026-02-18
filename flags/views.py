from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import redis
from redis.exceptions import RedisError

from .redis_client import redis_client
from . import utils
from .local_cache import LOCAL_FEATURE_CACHE
from .auth import admin_required 
from audit.utils import log_audit_event
from .rate_limit import admin_rate_limit
from .auth import require_scope

# Create your views here.
def home(request):
    return HttpResponse("Feature Flag service running")

@csrf_exempt
@admin_required
@admin_rate_limit
@require_scope("read")          # RBAC: only admins with "read" scope can access this view
def is_feature_active(request, feature_name):
    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    try:
        raw_value = redis_client.get(redis_key)           # Redis key format: "feature:{feature_name}" → value can be "1"/"0" (legacy) or JSON (new)

        # feature not found → fail closed
        if raw_value is None:
            return HttpResponse(
                f"Feature '{feature_name}' not found, active: False"
            )

        if raw_value in ("1", "0"):
            is_active = (raw_value == "1")                     
            LOCAL_FEATURE_CACHE[redis_key] = is_active              # update cache for legacy format 
            return HttpResponse(                                   
                f"Feature '{feature_name}' active: {is_active}"
            )

        # NEW FORMAT: JSON
        try:
            data = json.loads(raw_value)           # attempt to parse JSON value → if it fails, we treat it as corrupted and fail closed
        except json.JSONDecodeError:
            # corrupted value → fail closed
            return HttpResponse(
                f"Feature '{feature_name}' active: False"
            )

        # soft delete check
        if data.get("deleted") is True:         
            is_active = False       
        else: 
            is_active = bool(data.get("enabled", False))                    

        LOCAL_FEATURE_CACHE[redis_key] = is_active                     # update cache

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        # Redis down → fallback cache
        is_active = LOCAL_FEATURE_CACHE.get(redis_key, False)

    return HttpResponse(
        f"Feature '{feature_name}' active: {is_active}"
    )

@csrf_exempt
@admin_required
@admin_rate_limit
@require_scope("write")
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

        # state change should not be allowed if feature is soft deleted
        value = redis_client.get(redis_key)
        if value not in ("1", "0"):
            try:
                existing_data = json.loads(value)
                if existing_data.get("deleted") is True:
                    return JsonResponse(
                        {"error": "Cannot change state of a deleted feature"},
                        status=400
                    )
            except json.JSONDecodeError:
                return JsonResponse(
                    {"error": "Corrupted feature data"},
                    status=500
                )

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

        log_audit_event(
            action = "UPDATE",
            feature_name = feature_name,
            new_value = data["enabled"],
            performed_by = request.admin.name,
            performed_by_id = request.admin.id
        )

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
@admin_required           # redirect flow to auth.py -> admin_required -> _wrapped_view -> feature_status and then back to admin_required -> _wrapped_view -> feature_status
@admin_rate_limit
@require_scope("write")
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
        log_audit_event(
            action = "CREATE",
            feature_name = feature_name,
            new_value = False,
            performed_by = request.admin.name,
            performed_by_id = request.admin.id
        )

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
@admin_required
@admin_rate_limit
@require_scope("delete")
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

        # Soft delete: mark as deleted, key is not removed form redis 
        redis_client.set(
            redis_key,
            json.dumps({
                "enabled": False,
                "deleted": True
            })
        )

        log_audit_event(
            action="DELETE",
            feature_name=feature_name,
            new_value=None,
            performed_by=request.admin.name,
            performed_by_id=request.admin.id
        )

        # update cache after Redis success
        LOCAL_FEATURE_CACHE[redis_key] = False

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
@admin_required
@admin_rate_limit
@require_scope("read")
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
    

@csrf_exempt
@admin_required
@admin_rate_limit
@require_scope("write")
def restore_feature(request, feature_name):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Invalid request method"},
            status=405
        )

    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name, feature_name)

    try:
        raw_value = redis_client.get(redis_key)

        if raw_value is None:
            return JsonResponse(
                {"error": "Feature not found"},
                status=404
            )

        # Handle legacy format
        if raw_value in ("1", "0"):
            data = {
                "enabled": False,
                "deleted": False
            }
        else:
            try:
                data = json.loads(raw_value)
            except json.JSONDecodeError:
                return JsonResponse(
                    {"error": "Corrupted feature data"},
                    status=500
                )

        if data.get("deleted") is not True:
            return JsonResponse(
                {"error": "Feature is not deleted"},
                status=400
            )

        # Restore safely
        data["deleted"] = False
        data["enabled"] = False

        redis_client.set(redis_key, json.dumps(data))

        log_audit_event(
            action="UPDATE",   # keep enum consistent for now
            feature_name=feature_name,
            new_value=False,
            performed_by=request.admin.name,
            performed_by_id=request.admin.id
        )

        LOCAL_FEATURE_CACHE[redis_key] = False

        return JsonResponse(
            {
                "feature": feature_name,
                "enabled": False,
                "message": f"Feature '{feature_name}' restored successfully"
            }
        )

    except (redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            RedisError):
        return JsonResponse(
            {"error": "Feature service temporarily unavailable"},
            status=503
        )
