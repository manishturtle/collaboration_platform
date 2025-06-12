from threading import local
from django.db import connection

_thread_locals = local()

def get_current_schema():
    return getattr(_thread_locals, 'schema', None)

class TenantRouter:
    """
    Database router that routes queries to the correct tenant schema
    """
    def db_for_read(self, model, **hints):
        schema = get_current_schema()
        if schema:
            with connection.cursor() as cursor:
                # Use proper quoting for schema name
                cursor.execute('SET search_path TO "%s", public' % schema)
        return None

    def db_for_write(self, model, **hints):
        schema = get_current_schema()
        if schema:
            with connection.cursor() as cursor:
                # Use proper quoting for schema name
                cursor.execute('SET search_path TO "%s", public' % schema)
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return None
