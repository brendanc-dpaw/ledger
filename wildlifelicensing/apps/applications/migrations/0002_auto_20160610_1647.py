# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-06-10 08:47
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0002_fixtures'),
        ('wl_applications', '0001_initial'),
        ('wl_main', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentcondition',
            name='condition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_main.Condition'),
        ),
        migrations.AddField(
            model_name='applicationlogentry',
            name='application',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_applications.Application'),
        ),
        migrations.AddField(
            model_name='applicationlogentry',
            name='document',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='accounts.Document'),
        ),
        migrations.AddField(
            model_name='applicationlogentry',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='applicationcondition',
            name='application',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_applications.Application'),
        ),
        migrations.AddField(
            model_name='applicationcondition',
            name='condition',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_main.Condition'),
        ),
        migrations.AddField(
            model_name='application',
            name='applicant_profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.Profile'),
        ),
        migrations.AddField(
            model_name='application',
            name='assigned_officer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignee', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='application',
            name='conditions',
            field=models.ManyToManyField(through='wl_applications.ApplicationCondition', to='wl_main.Condition'),
        ),
        migrations.AddField(
            model_name='application',
            name='documents',
            field=models.ManyToManyField(to='accounts.Document'),
        ),
        migrations.AddField(
            model_name='application',
            name='hard_copy',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='hard_copy', to='accounts.Document'),
        ),
        migrations.AddField(
            model_name='application',
            name='licence',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='wl_main.WildlifeLicence'),
        ),
        migrations.AddField(
            model_name='application',
            name='licence_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_main.WildlifeLicenceType'),
        ),
        migrations.AddField(
            model_name='application',
            name='previous_application',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='wl_applications.Application'),
        ),
        migrations.AddField(
            model_name='application',
            name='proxy_applicant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='proxy', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='assessmentcondition',
            name='assessment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_applications.Assessment'),
        ),
        migrations.AddField(
            model_name='assessment',
            name='assessor_group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wl_main.AssessorGroup'),
        ),
        migrations.AddField(
            model_name='assessment',
            name='conditions',
            field=models.ManyToManyField(through='wl_applications.AssessmentCondition', to='wl_main.Condition'),
        ),
        migrations.AlterUniqueTogether(
            name='applicationcondition',
            unique_together=set([('condition', 'application', 'order')]),
        ),
        migrations.AlterUniqueTogether(
            name='assessmentcondition',
            unique_together=set([('condition', 'assessment', 'order')]),
        ),
    ]