from django.db import models
from yamlfield.fields import YAMLField


class Migration(models.Model):
    """
    Any migration that the system knows about, cleaned up on every run
    """
    filename = models.CharField(max_length=255)
    type = models.CharField(max_length=255, null=True)
    meta = YAMLField(null=True)
    is_deleted = models.BooleanField(default=False)
    flagged = models.BooleanField(default=False)
    create_date = models.DateTimeField("date added", auto_now_add=True)

    def __unicode__(self):
        return self.filename

    @property
    def last_run(self):
        try:
            return MigrationHistory.objects.filter(migration=self).order_by('-create_date')[0]
        except IndexError:
            return None

    @property
    def history(self):
        return MigrationHistory.objects.filter(migration=self).order_by('-create_date')


class MigrationHistory(models.Model):
    """
    Successful migration runs
    """
    migration = models.ForeignKey(Migration)
    meta = YAMLField(null=True)
    create_date = models.DateTimeField("date added", auto_now_add=True)

    def __unicode__(self):
        return '%s on %s' % (self.migration.filename, self.create_date)

    @property
    def author_name(self):
        return self.author
