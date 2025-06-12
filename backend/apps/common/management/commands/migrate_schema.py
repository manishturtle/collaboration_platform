#!/usr/bin/env python
"""
Tenant Migration Management Command

This Django management command allows running migrations for specific tenants.
It provides a simpler interface than the standalone script and integrates 
with Django's command framework.

Usage:
    python manage.py migrate_schema --tenant=tenant1
    python manage.py migrate_schema --tenant=tenant1 --app=chat
    python manage.py migrate_schema --list --tenant=tenant1
    python manage.py migrate_schema --shared
    python manage.py migrate_schema --all
"""

from typing import Any
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_tenants.utils import get_tenant_model, get_public_schema_name
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run migrations for a specific tenant or all tenants'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--tenant', 
            help='Tenant schema name to run migrations for'
        )
        parser.add_argument(
            '--shared', 
            action='store_true', 
            help='Run migrations for shared apps'
        )
        parser.add_argument(
            '--all', 
            action='store_true',
            help='Run migrations for all tenants'
        )
        parser.add_argument(
            '--list', 
            action='store_true', 
            help='List pending migrations instead of running them'
        )
        parser.add_argument(
            '--fake', 
            action='store_true', 
            help='Mark migrations as done without executing them'
        )
        parser.add_argument(
            '--app', 
            help='Specify an app to migrate'
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command"""
        tenant_id = options.get('tenant')
        shared = options.get('shared')
        all_tenants = options.get('all')
        list_mode = options.get('list')
        app_label = options.get('app')
        fake = options.get('fake')

        # Check for mutually exclusive options
        exclusive_count = sum([bool(tenant_id), bool(shared), bool(all_tenants)])
        if exclusive_count != 1:
            raise CommandError(
                "You must specify exactly one of --tenant, --shared, or --all"
            )

        # Prepare command options
        command_name = 'showmigrations' if list_mode else 'migrate'
        command_options = {
            'verbosity': options.get('verbosity', 1),
            'interactive': False,
        }
        
        if app_label:
            command_options['app_label'] = app_label
        
        if not list_mode:
            command_options['fake'] = fake

        if shared:
            self._run_shared_command(command_name, **command_options)
        elif all_tenants:
            self._run_command_for_all_tenants(command_name, **command_options)
        else:
            self._run_command_for_tenant(tenant_id, command_name, **command_options)

    def get_tenant(self, tenant_id):
        """Get tenant by schema name using the configured tenant model"""
        TenantModel = get_tenant_model()
        
        try:
            # First try to get by schema_name exactly matching tenant_id
            return TenantModel.objects.get(schema_name=tenant_id)
        except TenantModel.DoesNotExist:
            try:
                # If that fails, try case-insensitive match
                tenant = TenantModel.objects.filter(schema_name__iexact=tenant_id).first()
                if tenant:
                    return tenant
                    
                # If that fails, try to get by name field
                tenant = TenantModel.objects.filter(name__iexact=tenant_id).first()
                if tenant:
                    return tenant
                    
                # If all fails, raise error
                raise TenantModel.DoesNotExist()
                
            except TenantModel.DoesNotExist:
                try:
                    # Query all tenants to show available options
                    available_tenants = TenantModel.objects.all()
                    if available_tenants.exists():
                        tenant_list = "\n".join([
                            f" - {t.schema_name} ({t.name})" 
                            for t in available_tenants
                        ])
                        raise CommandError(
                            f"Tenant '{tenant_id}' not found.\n"
                            f"Available tenants:\n{tenant_list}"
                        )
                    else:
                        raise CommandError(
                            f"No tenants found in the database. "
                            f"Please ensure the ecomm_superadmin_tenants table exists and has data."
                        )
                except Exception as e:
                    # If even the query for all tenants fails, it could be a db table issue
                    raise CommandError(
                        f"Error accessing tenant data: {str(e)}\n"
                        f"Please ensure the ecomm_superadmin_tenants table exists."
                    )

    def _run_command_for_tenant(self, tenant_id, command, **options) -> None:
        """Run a command for a specific tenant"""
        tenant = self.get_tenant(tenant_id)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Running '{command}' for tenant '{tenant.schema_name}' ({tenant.name})"
            )
        )
        
        # First verify the schema exists in PostgreSQL
        self.stdout.write(f"Checking if schema '{tenant.schema_name}' exists")
        
        # Use raw connection to check schema existence
        cursor = connection.cursor()
        cursor.execute(
            """SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = %s
            )""", 
            [tenant.schema_name]
        )
        schema_exists = cursor.fetchone()[0]
        
        if not schema_exists:
            self.stdout.write(
                self.style.WARNING(
                    f"Schema '{tenant.schema_name}' does not exist in the database. "
                    f"Creating it now..."
                )
            )
            # Create the schema
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{tenant.schema_name}"')
        
        # Switch to tenant schema
        self.stdout.write(f"Switching to schema '{tenant.schema_name}'")
        connection.set_tenant(tenant)
        
        # Confirm schema switch worked
        self.stdout.write(f"Current schema: {connection.schema_name}")
        
        # Add schema parameter for django-tenants
        if command == 'migrate':
            options['schema'] = tenant.schema_name
        
        # Run the command
        try:
            call_command(command, **options)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error running {command} for tenant {tenant.schema_name}: {str(e)}")
            )
        
        # Reset to public schema
        connection.set_schema_to_public = True

    def _run_shared_command(self, command, **options) -> None:
        """Run a command for shared apps only"""
        self.stdout.write(
            self.style.SUCCESS(f"Running '{command}' for shared apps in public schema")
        )
        
        # Ensure we're in the public schema using the django-tenants approach
        public_schema_name = get_public_schema_name()
        self.stdout.write(f"Setting connection to public schema '{public_schema_name}'")
        
        # Explicitly set schema using connection.schema_name
        connection.set_schema_to_public()
        
        # Double-check the schema is set
        self.stdout.write(f"Current schema: {connection.schema_name}")
        
        # Add schema parameter for django-tenants
        if command == 'migrate':
            # Explicitly set the schema parameter
            options['schema'] = public_schema_name
            
        # Run the command
        try:
            call_command(command, **options)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error running {command} on public schema: {str(e)}")
            )

    def _run_command_for_all_tenants(self, command, **options) -> None:
        """Run a command for all tenants"""
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name=get_public_schema_name())
        
        if not tenants.exists():
            raise CommandError("No tenants found in the database (excluding public schema)")
        
        # First run for shared apps
        self._run_shared_command(command, **options)
        
        # Then for each tenant
        for tenant in tenants:
            self._run_command_for_tenant(tenant.schema_name, command, **options)
