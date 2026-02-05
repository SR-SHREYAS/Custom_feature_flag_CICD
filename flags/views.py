from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from .redis_client import redis_client
from . import utils


# Create your views here.
def home(request):
    return HttpResponse("Feature Flag service running")

def is_feature_active(request, feature_name):
    redis_domain_name = "feature";
    redis_key = utils.redis_key_generator(redis_domain_name,feature_name)  # generate redis key
    value =  redis_client.get(redis_key)  # get value from redis

    if value is None:
        #fail closed       is_active = False
        is_active = False
    else:
        is_active = (value == '1')  # convert string to boolean

    return HttpResponse(
        f"Feature '{feature_name}' active: {is_active}"
    )

@csrf_exempt
def feature_status(request, feature_name):
    
    # allow only PATCH method
    if(request.method != 'PATCH'):
        return JsonResponse(
            {'error': 'Invalid request method'},
            status=400
        )
    
    redis_domain_name = "feature"
    redis_key = utils.redis_key_generator(redis_domain_name,feature_name)  # generate redis key
    
    # check if feature exists
    if not redis_client.exists(redis_key):
        return JsonResponse(
            {'error': 'Feature not found'},
            status=404
        )
    
    # parse JSON body : string to dictionary
    # decode bytes to string , utf-8 stands for unicode transformation format 
    try:
        body = request.body.decode('utf-8')         
        data = json.loads(body)                     

    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON'},
            status=400
        )
    
    # valid input 
    # expected input is enabled as a key 
    if 'enabled' not in data:                        
        return JsonResponse(
            {'error': 'Missing "enabled" field'},
            status=400
        )

    # expected input enabled has a boolean value
    if not isinstance(data['enabled'], bool):  
        return JsonResponse(
            {'error': '"enabled" field must be a boolean'},
            status=400
        )
    
    # update feature flag status
    redis_value = "1" if data['enabled'] else "0"  # convert boolean to string
    redis_client.set(redis_key, redis_value)  # set value in redis


    # return response
    return JsonResponse({
        'feature': feature_name,
        'enabled': data["enabled"]
    })
