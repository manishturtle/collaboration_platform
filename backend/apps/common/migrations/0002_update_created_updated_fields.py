"""
Migration to convert created_by and updated_by fields from ForeignKey to IntegerField
This allows cross-schema references in a multi-tenant environment
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # No dependencies - this is effectively the initial migration
    ]

    operations = [
        migrations.RunSQL(
            # Convert created_by_id and updated_by_id to integer fields without constraints
            """
            BEGIN;
            
            -- For each table inheriting from BaseTenantModel
            -- Drop foreign key constraints first (if they exist)
            DO $$
            DECLARE
                tables RECORD;
            BEGIN
                -- Find tables with created_by_id column that might have FK constraints
                FOR tables IN
                    SELECT table_name FROM information_schema.columns 
                    WHERE column_name IN ('created_by_id', 'updated_by_id')
                      AND table_schema = current_schema()
                LOOP
                    -- Try to drop FK constraints safely (ignore if they don't exist)
                    EXECUTE format('
                        DO $$ 
                        BEGIN 
                            BEGIN
                                ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I_created_by_id_fkey;
                            EXCEPTION WHEN undefined_object THEN
                                NULL;
                            END;
                            
                            BEGIN
                                ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I_updated_by_id_fkey;
                            EXCEPTION WHEN undefined_object THEN
                                NULL;
                            END;
                        END $$;
                    ', tables.table_name, tables.table_name, tables.table_name, tables.table_name);
                END LOOP;
            END;
            $$;
            
            COMMIT;
            """,
            # Reverse SQL (empty as this is not easily reversible)
            """
            -- No reverse operation provided - this is a one-way migration
            """
        ),
    ]
