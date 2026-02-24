from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Region",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("region_id", models.CharField(max_length=64, unique=True)),
                ("shortname", models.CharField(db_index=True, max_length=64)),
                ("name", models.CharField(max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="PostcodeRegionCache",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("postcode", models.CharField(max_length=16, unique=True)),
                ("region_id", models.CharField(db_index=True, max_length=64)),
                ("region_shortname", models.CharField(max_length=64)),
                ("resolved_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name="ChargerLocation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("postcode", models.CharField(db_index=True, max_length=16)),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("region_id", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["latitude", "longitude"], name="core_charger_lat_lng_idx"),
                    models.Index(fields=["region_id", "postcode"], name="core_charger_reg_pcode_idx"),
                ],
            },
        ),
    ]
