from django.db import models
from django.conf import settings


class BaseTenantModel(models.Model):
    """
    An abstract base class model that provides self-updating
    `created_at` and `updated_at` fields, along with creator/updater
    and mandatory tenant/company IDs.
    """
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    # Using settings.AUTH_USER_MODEL for flexibility with custom user models.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='%(class)s_created',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='%(class)s_updated',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Per requirements, these are mandatory but hardcoded for the initial implementation.
    # `editable=False` ensures they are not changed via model forms/admin.
    company_id = models.IntegerField(default=1, editable=False)
    client_id = models.IntegerField(default=1, editable=False)

    class Meta:
        abstract = True
        ordering = ['-created_at']
