# About

Why write another schema migration tool? Here is how we stack up against other tools.

### Similarities

- Migrations are defined as scripts in a configurable directory
- There are commands to list, run and fake one or more migrations
- Migrations side effects can include schema changes, data updates or anything you can do from python script
- Migration history is stored in the same database that the migrations are run against

### Differences

- Migrations can be either python or sql files
- Migrations can be placed in a sub directory by type, and you can run/list a single type at a time
- Migrations are not ordered
- Schema migrations cannot be automatically generated
- Schema updates are only as database-independent as you make them
- Migration history includes who ran the migration, when it was run, who authored the script, and any notes either person has entered.

# Install

Just run `pip install pytz PyYAML django-yamlfield termcolor django-migratron`.

### Add to INSTALLED_APPS

In your `settings.py`, add `migratron` to the INSTALLED_APPS setting:

```python
INSTALLED_APPS = (
    ...
    'migratron',
    )
```

### Create database tables

```bash
./manage.py syncdb
```

### Settings

You can configure the following settings in your `settings.py`. All of these are optional, if you don't specify them, they will use defaults.

- `MIGRATIONS_DIR` - The directory where migrations will be stored either at the top level, or in top-level directories corresponding to migration types.

Different migration types might be things like "pre", "post", "delayed", etc.

You can use an absolute path, or build one dynamically like so:

```python
import os
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')
```

- `MIGRATIONS_ALLOWED_TYPES` - A tuple of allowed migration types. If not specified, any type is allowed, including no type.
To explicitly allow no type (ie, migrations in the root directory), add None to the tuple.

Example:

```python
MIGRATIONS_ALLOWED_TYPES = (None, 'pre', 'post')
```

- `MIGRATIONS_SCRIPT_AUTHOR_LINK_FUNCTION` - The function to run on a file path to get the script commit link (ie, github, bitbucket, etc).

Example:

```python
from migratron.authors import get_git_script_author_link
MIGRATIONS_SCRIPT_AUTHOR_LINK_FUNCTION = get_git_script_author_link
```


- `MIGRATIONS_TIMEZONE` - The timezone used to calculate the display value of the script run datetimes in --list.

Example:

```python
MIGRATIONS_TIMEZONE = 'US/Pacific'
```

- `MIGRATIONS_DBSHELL_CMD` - The command to run to exclude `dbshell`. Typically `manage.py dbshell`, but you may use an
alternate shell, or an alternate python intepreter.

# Usage

### Creating Migrations

Migrations are created based on python/sql templates. The body of the script must be implemented manually. The templates have standard meta-data slots in them, in the form of a leading comment block.

- `./manage.py createmigration "Add date_added and user columns to the Foobar model` - Create a new python migration
- `./manage.py createmigration --type pre "Add date_added and user columns to the Foobar model` - Create a new python migration of type "pre"
- `./manage.py createmigration --template sql "Add date_added and user columns to the Foobar model` - Create a new sql migration

### Listing and Running Migrations

- `./manage.py migrate --list` - List the migrations under the root `MIGRATIONS_DIR`.


```bash
Migrations:
2012-10-24 18:06 (*) test.sql
2012-10-25 11:31 (*) dedupe_sso.py
2012-10-25 12:47 (*) run_jsunit.py
2012-10-25 13:43 (*) suggestions_add_org_backfill_cleanup.sql
2012-10-25 18:41 (*) mail_message_allow_null.sql
2012-10-25 19:02 (*) test.py
                 ( ) activities_slave_index.sql
                 ( ) add_group_is_corporate_column.sql
                 ( ) add_org_sharing_preferences_column.sql
                 ( ) add_org_to_subscription.sql
```

- `./manage.py migrate --type pre --list` - List the migrations under the `MIGRATIONS_DIR/pre`.
- `./manage.py migrate foobar.py` - Run the migration `MIGRATIONS_DIR/foobar.py`.
- `./manage.py migrate --type pre foobar.py` - Run the migration `MIGRATIONS_DIR/pre/foobar.py`.
- `./manage.py migrate --all` - Run ALL migrations in `MIGRATIONS_DIR`.
- `./manage.py migrate foobar.py --log-only` - Don't really run the migration, but add it to the migration history as successfully run
- `./manage.py migrate foobar.py --delete-log` - Delete the migration history for this file
- `./manage.py migrate foobar.py --pending` - Exit with status code 1 if there are pending migrations
- `./manage.py migrate foobar.py --info` - Print all meta-data, migration history and notes for a migration.
- `./manage.py migrate foobar.py --notes` - Create or edit the migration runner's note for the latest migration using $EDITOR.
- `./manage.py migrate --list --verbose` - List migrations with extra meta-data, like runner's notes.
- `./manage.py migrate test.py --flag "Need to run this again after the next deploy"` - Flag a migration as needing further attention, with an optional note.
- `./manage.py migrate test.py --flag` - Toggle the flag on an existing migration.
- `./manage.py migrate test.py --clear` - Delete all migration history from the database.


### Migration History

If you need to play back sql migrations run on one database against another one, you may find it useful to list migrations in the order they were actually run, optionally with runner comments. For history commands, types do not matter; all run migrations are output.

- `./manage.py migrate --history` - List just the file names in the order they were run.
- `./manage.py migrate --history --verbose` - List file names and runner comments.

## Confirmation Inside Migrations

If you want to require manual confirmation for a particular migration, just make sure you exit
with an error code, or raise an exception, if the script does not run. That way, the script will
not be marked as having run successfully.

```python
char = raw_input('Nuke all the things? (Y/N): ')
if char.upper() == 'Y':
    print "Nuking!"
else:
    exit(1)
```

