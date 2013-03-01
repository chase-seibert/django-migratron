import os
import subprocess
import sys
import traceback
import StringIO

from optparse import make_option
from django.conf import settings
from django.template import defaultfilters
from textwrap import TextWrapper
from migratron.models import Migration
from migratron.models import MigrationHistory
from migratron.editor import raw_input_editor
from migratron import MigratronCommand


class Command(MigratronCommand):

    help = 'Run schema and data migration scripts'
    args = []
    type = None
    run_all = False
    log_only = False
    specific_migration = None
    run_again = False
    verbose = False
    pager = 'less'
    continue_on_errors = False

    handled_migratron_option_list = (
        make_option('--type',
                    action='store',
                    dest='type',
                    default=None,
                    help='What type of migrations to work with. Corresponds to sub-directories under MIGRATIONS_DIR. If no type is specified, look at ALL sub-directories.'),
        make_option('--log-only',
                    action='store_const',
                    dest='log_only',
                    const=True,
                    help="Don't run the scripts, just create a fake log entry for them."),
        make_option('--again',
                    action='store_const',
                    dest='run_again',
                    const=True,
                    help='Allow specific previously run migrations to be run again. Does not work with --all.'),
        make_option('--verbose',
                    action='store_const',
                    dest='verbose',
                    const=True,
                    help='Adds verbose output to the --list action.'),
        make_option('--pager',
                    action='store',
                    dest='pager',
                    default='less',
                    help='Changes the default pager. Can use "cat", "less", etc.'),
        make_option('--continue',  # option parser treats this the same as --continue-on-errors
                    action='store_const',
                    dest='continue_on_errors',
                    const=True,
                    help='If a migration script fails, continue to the next one.'))

    migratron_option_list = (
        make_option('--list',
                    action='store_const',
                    dest='action',
                    const='list',
                    help='List the most recently run migrations, as well as the pending migrations.'),
        make_option('--all',
                    action='store_const',
                    dest='action',
                    const='run_all',
                    help='Run all pending migration scripts.'),
        make_option('--delete-log',
                    action='store_const',
                    dest='action',
                    const='delete_log',
                    help='Manually remove a log entry.'),
        make_option('--pending',
                    action='store_const',
                    dest='action',
                    const='is_pending',
                    help='Exits with status code 1 if there are pending migrations.'),
        make_option('--history',
                    action='store_const',
                    dest='action',
                    const='history',
                    help='List all previously run migrations, in the order they were run.'),
        make_option('--info',
                    action='store_const',
                    dest='action',
                    const='info',
                    help='Print out all information on a specific migration.'),
        make_option('--notes',
                    action='store_const',
                    dest='action',
                    const='add_note',
                    help='Create or update notes from the script runner for a specific script. Set the environment variable EDITOR to change the note editor.'),
        make_option('--flag',
                    action='store_const',
                    dest='action',
                    const='flag',
                    help='Toggle the flag bit on a specific migration. Flags are just informational for script runners.'),
        make_option('--clear',
                    action='store_const',
                    dest='action',
                    const='clear',
                    help='Delete all migraton history in the database.'))

    option_list = MigratronCommand.option_list + handled_migratron_option_list + migratron_option_list

    def get_directory_listing(self):
        walk_dir = self.full_script_path()
        for dirname, dirnames, filenames in os.walk(walk_dir):
            return filenames
        return []

    def sync_filesystem_and_db(self):
        ''' for performance, we sync the migrations/type dir on every run w/ the database '''
        for migration in Migration.objects.filter(type=self.type):
            if not os.path.exists(self.full_script_path(migration.filename)):
                migration.is_deleted = True
                migration.save()
        # TODO: md5/timestamps?
        for filename in self.get_directory_listing():
            try:
                migration = Migration.objects.get(type=self.type, filename=filename)
            except Migration.DoesNotExist:
                self.console('Getting initial meta-data for %s' % filename)
                meta = self.metadata(filename)
                Migration(filename=filename, type=self.type, meta=meta).save()

    @property
    def already_run(self):
        return Migration.objects.filter(migrationhistory__isnull=False, type=self.type).order_by('-create_date')

    @property
    def pending(self):
        return Migration.objects.filter(migrationhistory__isnull=True, type=self.type).order_by('-filename')

    def _list_filename(self, migration):
        ''' filename for a migration in the --list view '''
        message = migration.meta.get('flag_message')
        if migration.flagged and message and not self.verbose:
            return '%s <--- %s' % (migration.filename, message)
        return migration.filename

    def _list_non_verbose_line(self, migration, symbol):
        self.console(' (%s) ' % symbol, newline=False)
        color = None
        if migration.flagged:
            color = 'red'
        if self.verbose:
            color = 'yellow'
        self.console(self._list_filename(migration), color)

    def list(self, do_pending=True, migrations=None):

        if self.pager == 'less':
            self._pager = subprocess.Popen([self.pager, '-F', '-R', '-S', '-X', '-K'], stdin=subprocess.PIPE, stdout=sys.stdout)

        try:

            self.console('Migrations:')

            if do_pending:
                if self.pending:
                    for migration in self.pending:
                        if not self.verbose:
                            self.console(' ' * 16, newline=False)
                        self._list_non_verbose_line(migration, ' ')
                        self._list_verbose(migration)
                else:
                    self.console('There are no pending migrations')

            if not migrations:
                migrations = list(self.already_run.order_by('create_date'))

            for migration in migrations:
                if not self.verbose:
                    self.console('%s' % self._local_datetime(migration.last_run.create_date), newline=False)
                self._list_non_verbose_line(migration, '*')
                self._list_verbose(migration)

            if self._pager:
                self._pager.stdin.close()
                self._pager.wait()

        except KeyboardInterrupt:
            # let less handle this, -K will exit cleanly
            pass

        finally:
            self._pager = None

    def _list_verbose(self, migration):
        if self.verbose:
            lead = ' ' * 5
            wrap = TextWrapper(width=80, initial_indent=lead, subsequent_indent=lead)
            meta = migration.meta
            if meta:
                self.console()
                for field in ('Author', 'link', 'Description'):
                    value = meta.get(field)
                    if value:
                        self.console(lead + defaultfilters.title(field) + ': ' + value)
                if migration.flagged:
                    self.console()
                    self.console(lead + 'Flagged: True', 'red')
                    message = meta.get('flag_message')
                    if message:
                        self.console(wrap.fill(message))
            last_run = migration.last_run
            if last_run:
                meta = last_run.meta
                if last_run.meta:
                    self.console()
                    meta['date'] = self._local_datetime(last_run.create_date)
                    for field in ('runner', 'date'):
                        value = last_run.meta.get(field)
                        if value:
                            self.console(lead + defaultfilters.title(field) + ': ' + value)
                    notes = meta.get('notes')
                    if notes:
                        self.console(wrap.fill(notes))

            if meta or last_run:
                self.console()

    def run_all(self):
        for migration in self.pending:
            self.run(migration)

    def run(self, migration):

        # needs to be before pending check, in case no type is passed
        script = self.full_script_path(migration.filename)
        if not os.path.exists(script):
            self.failfast('Cannot locate script "%s".' % migration)

        if migration not in self.pending and not self.run_again:
            self.failfast('That script has already been run.')

        file_path, ext = os.path.splitext(script)
        if ext not in ('.py', '.sql'):
            self.failfast('Cannot run scripts of type: "%s"' % ext)

        if self.log_only:
            self.console('Logging %s' % migration)
        else:
            self.console('Running %s' % migration)

            if ext == '.py':
                result = self.execfile(script)
            elif ext == '.sql':
                with open(script, 'r') as raw_sql_file:
                    result = self.execute_sql(raw_sql_file.read())

        if not result:
            if not self.continue_on_errors:
                self.failfast("Aborting the rest of the migrations.")

            self.console("Skipping migration...")

        if result:
            self.log_migration(migration)
        else:
            self.console("Result of script: %s..skipping migration" % result)

    def execfile(self, filename):
        ''' abstracted so we can mock it out for tests '''
        # execute the file using the built-in execfile method, passing
        # a __name__ of __main__, so that any main function in the file will run
        try:
            return execfile(filename, {'__name__': '__main__'})
        except:  # We can get Django DoesNotExist errors.
            output = StringIO.StringIO()
            traceback.print_exc(file=output)
            self.console("Error running %s\nStack trace: %s" % (filename, output.getvalue()))
            return False

        return True

    def execute_sql(self, raw_sql):
        ''' abstracted so we can mock it out for tests '''
        cwd = os.getcwd()
        dbshell_cmds = getattr(settings, 'MIGRATIONS_DBSHELL_CMD', 'manage.py dbshell').split(' ')
        cmd_list = [os.path.join(cwd, dbshell_cmds[0])] + dbshell_cmds[1:]
        dbshell = subprocess.Popen(cmd_list, cwd=cwd, stdin=subprocess.PIPE)
        (stdout, stderr) = dbshell.communicate(raw_sql)
        for output in (stdout, stderr):
            if output:
                self.console(output.read())

        return (dbshell.returncode == 0)

    def log_migration(self, migration):
        MigrationHistory(
            migration=migration,
            meta=dict(runner=os.environ.get("USER"))).save()

    def delete_log(self):
        if not self.specific_migration:
            self.failfast('Must specify a specific script to delete the logs for.')
        # can delete more than one script if you ran them multiple times w/ --again
        migrations = self.specific_migration.history
        if not migrations:
            self.failfast('No such migration found.')
        migrations.delete()
        self.console('Removed migration log(s) for "%s".' % self.specific_migration)

    def is_pending(self):
        ''' useful for aborting hudson/jenkins/fab jobs '''
        if self.pending:
            self.failfast('There are %s pending migrations' % len(self.pending))

    def history(self):
        migrations = [h.migration for h in MigrationHistory.objects.all().order_by('-create_date')]
        if self.verbose:
            self.list(do_pending=False, migrations=migrations)
        else:
            for migration in migrations:
                print migration.filename

    def info(self):
        if not self.specific_migration:
            self.failfast('Must specify a specific script to show info for.')
        self.verbose = True
        self._list_verbose(self.specific_migration)

    def flag(self):
        if not self.specific_migration:
            self.failfast('Must specify a specific script to flag.')
        migration = self.specific_migration
        if migration.flagged:
            migration.flagged = False
            try:
                del migration.meta['flag_message']
            except KeyError:
                pass
        else:
            migration.flagged = True
            migration.meta['flag_message'] = self.args[1] if len(self.args) >= 2 else None
        migration.save()
        self.console('Flag SET' if migration.flagged else 'Flag UNSET')

    def add_note(self):
        if not self.specific_migration:
            self.failfast('Must specify a specific script to add a note for.')
        migrations = self.specific_migration.history
        if not migrations:
            self.failfast('That script has not been run yet.')
        migration = migrations[0]
        migration.meta['notes'] = raw_input_editor(migration.meta.get('notes', ''))
        migration.save()

    def clear(self):
        if raw_input('Are you SURE you want to delete all migration history of ALL TYPES? [y/n] ').lower() == 'y':
            MigrationHistory.objects.all().delete()
            Migration.objects.all().delete()

    def handle(self, *args, **options):

        self.args = args
        for option in self.handled_migratron_option_list:
            arg = option.dest
            setattr(self, arg, options.get(arg))
        self.failfast_bad_type()
        self.specific_script_name = args[0] if args else None
        action = options.get('action', None)

        self.sync_filesystem_and_db()

        if self.specific_script_name:
            self.specific_migration = Migration.objects.get(type=self.type, filename=self.specific_script_name)

        if self.specific_migration and not action:
            self.run(self.specific_migration)
        elif not action:
            self.print_help('migrate', 'help')
        else:
            getattr(self, action)()
