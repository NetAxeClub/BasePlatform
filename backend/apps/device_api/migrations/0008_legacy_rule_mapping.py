from django.db import migrations, models


def backfill_legacy_rule_mapping(apps, schema_editor):
    DeviceCollectionRule = apps.get_model("device_api", "DeviceCollectionRule")
    DeviceCollectionMatchRule = apps.get_model("device_api", "DeviceCollectionMatchRule")

    for rule in DeviceCollectionRule.objects.filter(legacy_rule_id__isnull=True).iterator():
        rule.legacy_rule_id = rule.id
        rule.save(update_fields=["legacy_rule_id"])

    for match_rule in DeviceCollectionMatchRule.objects.filter(legacy_match_rule_id__isnull=True).iterator():
        match_rule.legacy_match_rule_id = match_rule.id
        match_rule.save(update_fields=["legacy_match_rule_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("device_api", "0007_collection_rule_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="devicecollectionrule",
            name="legacy_rule_id",
            field=models.IntegerField(blank=True, db_index=True, null=True, verbose_name="legacy规则ID"),
        ),
        migrations.AddField(
            model_name="devicecollectionmatchrule",
            name="legacy_match_rule_id",
            field=models.IntegerField(blank=True, db_index=True, null=True, verbose_name="legacy匹配规则ID"),
        ),
        migrations.RunPython(backfill_legacy_rule_mapping, migrations.RunPython.noop),
    ]
