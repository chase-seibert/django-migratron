from StringIO import StringIO
from datetime import datetime
from mock import MagicMock
from mock import call
from mock import patch
from django.test import TestCase
from django.test import TransactionTestCase
from django.test.utils import override_settings
from migratron.models import Migration
from migratron.models import MigrationHistory
from migratron.management.commands.migrate import Command


def MigrationFactory(*args, **kwargs):
    migration = Migration(
        filename=kwargs.get('filename'),
        type=(kwargs.get('type')))
    migration.meta = dict(flag_message=False)
    migration.save()
    if kwargs.get('history', True):
        migration_history = MigrationHistory()
        migration_history.migration = migration
        migration_history.meta = {}
        migration_history.save()
        if 'create_date' in kwargs:
            # can't set in initial save, will be over-ridden by current datetime
            migration_history.create_date = kwargs.get('create_date')
            migration_history.save()
    return migration


class MigrateModelTest(TestCase):

    def test_base(self):
        self.assertTrue(MigrationFactory(filename='foobar.sql').id)


def log_to_self(self, message, color=None, newline=True):
    ''' log print calls to a list of messages on self, so we can assert on them
    some trickiness here to emulate print()'s ability to either print a carriage
    return, or not
    '''
    if not hasattr(self, 'messages'):
        self.messages = []
        self._last_newline = True
    if self._last_newline:
        self.messages.append(message)
    else:
        self.messages[-1] += ' ' + message
    self._last_newline = newline


def fake_get_script_author_name(self, script):
    return "username"


def fake_get_script_author_link(self, script):
    return "http://example.com/foobar"


def fake_get_script_author_notes(self, script):
    return "This is a note"


def MigrateCommandFactory(*args, **kwargs):

    # mock out print statements
    Command.console = log_to_self
    Command.output = property(lambda self: '\n'.join(getattr(self, 'messages', [])))

    Command.get_script_author_name = fake_get_script_author_name
    Command.get_script_author_link = fake_get_script_author_link
    Command.get_script_author_notes = fake_get_script_author_notes
    Command.allowed_types = lambda self: True

    import os
    os.path.exists = lambda script: True

    migrate_command = Command()

    for k, v in kwargs.items():
        if k == 'all_scripts':
            # mock out this @property, so we can test w/o hitting disk
            migrate_command.__class__.all_scripts = v
        if k == 'specific_migration':
            migrate_command.specific_migration = Migration.objects.get(filename=v)
        else:
            setattr(migrate_command, k, v)

    return migrate_command


# from: http://java.dzone.com/articles/mocking-open-context-manager
def mock_open(mock=None, data=None):
    if mock is None:
        mock = MagicMock(spec=file)
    handle = MagicMock(spec=file)
    handle.write.return_value = None
    if data is None:
        handle.__enter__.return_value = handle
    else:
        handle.__enter__.return_value = data
    mock.return_value = handle
    return mock


class MigrateCommandTest(TestCase):

    def test_already_run(self):
        migration = MigrationFactory(filename='foobar.sql')
        self.assertTrue(migration in MigrateCommandFactory().already_run)

    def test_already_run_has_all(self):
        for _ in range(100):
            MigrationFactory(filename='foobar.sql')
        self.assertEquals(len(MigrateCommandFactory().already_run), 100)

    def test_pending(self):
        migration = MigrationFactory(filename='foobar.sql', history=False)
        command = MigrateCommandFactory()
        self.assertTrue(migration in command.pending)

    def test_pending_already_run(self):
        MigrationFactory(filename='foobar.sql')
        self.assertFalse(MigrateCommandFactory().pending)

    @override_settings(MIGRATIONS_DIR='/tmp')
    def test_full_script_path(self):
        self.assertEquals(MigrateCommandFactory(type='foo').full_script_path('bar.sql'), '/tmp/foo/bar.sql')

    @override_settings(MIGRATIONS_DIR='/tmp/foobar')
    def test_full_script_path_no_type(self):
        self.assertEquals(MigrateCommandFactory().full_script_path('test.sql'), '/tmp/foobar/test.sql')

    @override_settings(MIGRATIONS_TIMEZONE='UTC')
    def test_list(self):
        MigrationFactory(filename='foo.sql', create_date=datetime(2012, 10, 25, 10, 42))
        command = MigrateCommandFactory()
        command.list()
        self.assertEquals(command.output, '''Migrations:\nThere are no pending migrations\n2012-10-25 10:42  (*)  foo.sql''')

    @override_settings(MIGRATIONS_TIMEZONE='US/Pacific')
    def test_list_timezone(self):
        MigrationFactory(filename='foo.sql', create_date=datetime(2012, 10, 25, 10, 42))
        command = MigrateCommandFactory(all_scripts=['bar.py'])
        command.list()
        self.assertEquals(command.output, '''Migrations:\nThere are no pending migrations\n2012-10-25 03:42  (*)  foo.sql''')

    def test_run_all(self):
        migration1 = MigrationFactory(filename='foo.sql', history=False)
        migration2 = MigrationFactory(filename='bar.py', history=False)
        command = MigrateCommandFactory()
        command.run = MagicMock(return_value=None)
        command.run_all()
        # actual calls are in alphabetical order
        self.assertEquals(command.run.call_args_list,
            [call(migration1), call(migration2)])

    def test_run(self):
        migration = MigrationFactory(filename='bar.py', history=False)
        command = MigrateCommandFactory(specific_migration='bar.py')
        command.run = MagicMock(return_value=None)
        command.run_all()
        command.run.assert_called_with(migration)

    def test_run_not_pending(self):
        migration = MigrationFactory(filename='bar.py')
        command = MigrateCommandFactory(specific_migration='bar.py')
        with self.assertRaises(SystemExit):
            command.run(migration)
        self.assertEquals(command.output, 'That script has already been run.')

    @override_settings(MIGRATIONS_DIR='/tmp/some/path/that/does/not/exist')
    def test_run_bad_path_format(self):
        migration = MigrationFactory(filename='bar.py', history=False)
        command = MigrateCommandFactory()
        command.execfile = MagicMock(return_value=None)
        command.run(migration)
        self.assertEquals(command.output, 'Running bar.py')

    @override_settings(MIGRATIONS_DIR='/tmp')
    def test_run_py(self):
        command = MigrateCommandFactory(all_scripts=['bar.py'])
        command.execfile = MagicMock(return_value=None)
        migration = MigrationFactory(filename='bar.py', history=False)
        command.run(migration)
        command.execfile.assert_called_with('/tmp/bar.py')
        self.assertTrue(migration.history)

    def test_run_py_exception(self):
        command = MigrateCommandFactory(all_scripts=['bar.py'])
        command.execfile = MagicMock(side_effect=Exception)
        with self.assertRaises(Exception):
            command.run('bar.py')
        self.assertFalse(MigrationHistory.objects.all())  # no record was inserted

    @override_settings(MIGRATIONS_DIR='/tmp')
    def test_run_sql(self):
        migration = MigrationFactory(filename='foo.sql', history=False)
        command = MigrateCommandFactory()
        command.execute_sql = MagicMock(return_value=None)
        mocked_open = mock_open(data=StringIO('select 0;'))
        with patch('__builtin__.open', mocked_open, create=True):
            command.run(migration)
        mocked_open.assert_called_with('/tmp/foo.sql', 'r')
        command.execute_sql.assert_called_with('select 0;')
        self.assertTrue(migration.history)

    def test_run_sql_exception(self):
        command = MigrateCommandFactory(all_scripts=['foo.sql'])
        command.execute_sql = MagicMock(side_effect=Exception)
        mocked_open = mock_open(data=StringIO('select * from table_does_not_exist;'))
        with self.assertRaises(Exception):
            with patch('__builtin__.open', mocked_open, create=True):
                command.run('foo.sql')
        self.assertFalse(MigrationHistory.objects.all())

    def test_log_only(self):
        command = MigrateCommandFactory()
        command.execfile = MagicMock(side_effect=Exception)
        command.log_only = True
        command.run(MigrationFactory(filename='foo.sql', history=False))  # no exception thrown
        self.assertTrue(MigrationHistory.objects.all())  # record was inserted

    def test_delete_log(self):
        migration = MigrationFactory(filename='foo.sql')
        command = MigrateCommandFactory(specific_migration='foo.sql')
        command.delete_log()
        self.assertFalse(migration.history)

    def test_delete_log_type(self):
        migration = MigrationFactory(filename='foo.sql', type='pre')
        command = MigrateCommandFactory(specific_migration='foo.sql', type='pre')
        command.delete_log()
        self.assertFalse(MigrationHistory.objects.filter(id=migration.id))

    def test_none_is_pending(self):
        self.assertFalse(MigrateCommandFactory().pending)

    def test_is_pending(self):
        MigrationFactory(filename='foo.sql')
        self.assertFalse(MigrateCommandFactory().pending)


class MigrateCommandTransaction(TransactionTestCase):
    ''' need to inherit from TransactionTestCase if you want to actually
    test the commits. This is pretty slow. BE CAREFUL HERE; because we are
    shelling out, these SQL statements may run against your real database. '''

    def test_execute_sql_multiple_statements(self):
        ''' if you tried to do this in one cursor.execute(), it would fail in mysql '''
        MigrateCommandFactory().execute_sql('CREATE TABLE foobar (col1 int null, col2 varchar(255) null); DROP TABLE foobar;')
