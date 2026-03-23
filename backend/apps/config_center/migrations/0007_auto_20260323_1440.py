from django.db import migrations, models


def _has_index(schema_editor, table_name, index_name):
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)
    constraint = constraints.get(index_name)
    return bool(constraint and constraint.get('index'))


def _rename_indexes(apps, schema_editor, forward=True):
    policy_model = apps.get_model('config_center', 'StructuredDriftPolicy')
    audit_model = apps.get_model('config_center', 'StructuredDriftPolicyAudit')

    index_specs = [
        (
            policy_model,
            models.Index(fields=['is_active'], name='structured__is_acti_3d559e_idx'),
            models.Index(fields=['is_active'], name='structured__is_acti_a78f90_idx'),
        ),
        (
            policy_model,
            models.Index(fields=['name', 'updated_at'], name='structured__name_a23e5f_idx'),
            models.Index(fields=['name', 'updated_at'], name='structured__name_3763af_idx'),
        ),
        (
            audit_model,
            models.Index(fields=['action', 'created_at'], name='structured__action__1f25d0_idx'),
            models.Index(fields=['action', 'created_at'], name='structured__action_8a087a_idx'),
        ),
        (
            audit_model,
            models.Index(fields=['policy', 'created_at'], name='structured__policy__043778_idx'),
            models.Index(fields=['policy', 'created_at'], name='structured__policy__5dca63_idx'),
        ),
    ]

    for model, old_index, new_index in index_specs:
        source_index = old_index if forward else new_index
        target_index = new_index if forward else old_index

        if not _has_index(schema_editor, model._meta.db_table, target_index.name):
            schema_editor.add_index(model, target_index)

        if _has_index(schema_editor, model._meta.db_table, source_index.name):
            schema_editor.remove_index(model, source_index)


def rename_indexes_forward(apps, schema_editor):
    _rename_indexes(apps, schema_editor, forward=True)


def rename_indexes_backward(apps, schema_editor):
    _rename_indexes(apps, schema_editor, forward=False)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('config_center', '0006_structureddriftpolicyaudit'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(rename_indexes_forward, rename_indexes_backward),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='structureddriftpolicy',
                    name='structured__is_acti_3d559e_idx',
                ),
                migrations.RemoveIndex(
                    model_name='structureddriftpolicy',
                    name='structured__name_a23e5f_idx',
                ),
                migrations.RemoveIndex(
                    model_name='structureddriftpolicyaudit',
                    name='structured__action__1f25d0_idx',
                ),
                migrations.RemoveIndex(
                    model_name='structureddriftpolicyaudit',
                    name='structured__policy__043778_idx',
                ),
                migrations.AddIndex(
                    model_name='structureddriftpolicy',
                    index=models.Index(fields=['is_active'], name='structured__is_acti_a78f90_idx'),
                ),
                migrations.AddIndex(
                    model_name='structureddriftpolicy',
                    index=models.Index(fields=['name', 'updated_at'], name='structured__name_3763af_idx'),
                ),
                migrations.AddIndex(
                    model_name='structureddriftpolicyaudit',
                    index=models.Index(fields=['action', 'created_at'], name='structured__action_8a087a_idx'),
                ),
                migrations.AddIndex(
                    model_name='structureddriftpolicyaudit',
                    index=models.Index(fields=['policy', 'created_at'], name='structured__policy__5dca63_idx'),
                ),
            ],
        ),
    ]
