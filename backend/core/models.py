from django.db import models


class CoreModel(models.Model):
    """
    Base model that provides common fields and functionality across all models.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.IntegerField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.IntegerField(blank=True, null=True)
    company_id = models.IntegerField(blank=True, null=True)
    client_id = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    app_id = models.IntegerField(required=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']
