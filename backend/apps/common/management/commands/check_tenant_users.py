from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = 'Check users in a specific tenant schema'

    def add_arguments(self, parser):
        parser.add_argument('tenant_schema', type=str, help='The tenant schema to check')

    def handle(self, *args, **options):
        tenant_schema = options['tenant_schema']
        
        self.stdout.write(f"Checking users in schema: {tenant_schema}")
        
        with schema_context(tenant_schema):
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, email, first_name, last_name, is_active FROM ecomm_tenant_admins_tenantuser ORDER BY id ASC")
                rows = cursor.fetchall()
                
                if not rows:
                    self.stdout.write(self.style.WARNING(f"No users found in schema {tenant_schema}"))
                    return
                
                self.stdout.write(self.style.SUCCESS(f"Found {len(rows)} users in schema {tenant_schema}:"))
                self.stdout.write("=" * 80)
                self.stdout.write(f"{'ID':<5} {'Email':<40} {'Name':<30} {'Active'}")
                self.stdout.write("=" * 80)
                
                for row in rows:
                    user_id, email, first_name, last_name, is_active = row
                    name = f"{first_name} {last_name}".strip()
                    self.stdout.write(f"{user_id:<5} {email:<40} {name:<30} {'Yes' if is_active else 'No'}")
