def redis_key_generator(redis_domain_name,feature_name):
    return f"{redis_domain_name}:{feature_name}"

