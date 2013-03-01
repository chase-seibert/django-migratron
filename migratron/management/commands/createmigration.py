import os
from optparse import make_option
import datetime
from django.conf import settings
from django.template.defaultfilters import slugify
from django.template import loader
from migratron import MigratronCommand


class Command(MigratronCommand):

    help = 'Create empty schema and data migration scripts'
    type = None
    name = None
    template = None

    option_list = MigratronCommand.option_list + (
        make_option('--type',
            action='store',
            dest='type',
            default=None,
            help='What type of migrations to work with. Corresponds to sub-directories under MIGRATIONS_DIR.'),
        make_option('--template',
            action='store',
            dest='template',
            default='python',
            help='What type of migration to create. Either sql or python.'),
        make_option('--name',
            action='store',
            dest='name',
            default=None,
            help='Single sentence description of the migration.'))

    def generate_file_name(self, ext):
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        slug = slugify(self.name)
        return '%s_%s.%s' % (timestamp, slug, ext)

    def get_template_path(self, filename):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../templates', filename))

    def create_migration(self, ext):
        file_path = self.full_script_path(self.generate_file_name(ext))
        if os.path.isfile(file_path):
            self.fastfail('Migration already exists at %s' % file_path)
        try:
            os.mkdir(os.path.join(settings.MIGRATIONS_DIR, self.type or ''))
        except OSError:
            pass
        with open(file_path, 'w') as file:
            file.write(loader.render_to_string(
                self.get_template_path('template.' + ext),
                dict(
                    author=os.environ.get('USER'),
                    create_date=self._local_datetime(),
                    description=self.name,
                )))
        self.console('Created new migration at %s' % file_path)

    def handle(self, *args, **options):

        for attr in ('type', 'name', 'template'):
            setattr(self, attr, options.get(attr))

        if not self.name and args:
            self.name = args[0]

        if not self.name:
            self.print_help('migrate', 'help')
        self.failfast_bad_type()

        template = self.template.lower()
        if template in ('sql', '.sql'):
            self.create_migration('sql')
        elif template in ('python', '.py', 'py'):
            self.create_migration('py')
        else:
            print 'Invalid template: %s' % template
