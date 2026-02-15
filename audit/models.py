from django.db import models


# Create your models here.
class AuditLog(models.Model):                     # AuditLog model to store feature flag changes and admin actions 
    ACTION_CHOICES = [
        ("CREATE", "Create Feature"),
        ("UPDATE", "Update Feature"),
        ("DELETE", "Delete Feature"),
    ]

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    feature_name = models.CharField(max_length=255)
    new_value = models.BooleanField(null=True, blank=True)

    # For now: store admin identity as string (API key label / name later)
    performed_by = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} {self.feature_name} at {self.created_at}"
