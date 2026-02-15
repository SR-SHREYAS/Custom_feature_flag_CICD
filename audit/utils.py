from audit.models import AuditLog

def log_audit_event(action, feature_name, new_value, performed_by):
    """
    Utility function to log an audit event.
    
    Parameters:
    - action: The type of action performed (CREATE, UPDATE, DELETE)
    - feature_name: The name of the feature flag affected
    - new_value: The new value of the feature flag (if applicable)
    - performed_by: The identity of the admin performing the action
    """
    try:
        AuditLog.objects.create(
            action=action,
            feature_name=feature_name,
            new_value=new_value,
            performed_by=performed_by
        )
    except Exception: 
        # audit must NEVER break main flow 
        pass
    