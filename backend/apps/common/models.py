from django.db import models
from django.conf import settings

from django_tenants.models import TenantMixin


class Tenant(TenantMixin):
    """
    Tenant model that maps to the existing ecomm_superadmin_tenants table
    created by the Platform Admin application.
    """
    # These fields should match the existing table structure
    # Adjust field names and types to match your existing table
    name = models.CharField(max_length=100)
    
    # Schema name - required by TenantMixin
    schema_name = models.CharField(max_length=63, db_index=True)
    
    # Don't auto-create schema as they should already exist
    auto_create_schema = False
    
    def __str__(self):
        return self.name
    
    class Meta:
        # Link to the existing tenant table
        db_table = 'ecomm_superadmin_tenants'
        managed = False  # Django won't try to create/modify this table


class Domain(models.Model):
    """
    Domain model for tenant URL mapping.
    Maps to the existing domains table created by the Platform Admin.
    """
    domain = models.CharField(max_length=253, db_index=True)
    # Use tenant_id instead of a ForeignKey to avoid model validation issues
    tenant_id = models.IntegerField()
    is_primary = models.BooleanField(default=True)
    
    def __str__(self):
        return self.domain
        
    class Meta:
        db_table = 'ecomm_superadmin_domains'  # Adjust this to your actual domains table
        managed = False  # Django won't try to create/modify this table


class BaseTenantModel(models.Model):
    """
    An abstract base class model that provides self-updating
    `created_at` and `updated_at` fields, along with creator/updater
    and mandatory tenant/company IDs.
    """
    # These fields are now defined in child classes to ensure proper db_column names
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
