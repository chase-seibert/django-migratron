import os
import datetime
import re
import sys
from pytz import timezone
import yaml
from termcolor import colored
from django.core.management.base import BaseCommand
from django.conf import settings


class MigratronCommand(BaseCommand):

    color = True
    _pager = None

    def full_script_path(self, script=""):  # empty str == migrations dir
        migrations_dir = os.path.abspath(settings.MIGRATIONS_DIR)  # simplfies '../' parts
        if self.type:
            return os.path.join(migrations_dir, self.type, script)
        return os.path.join(migrations_dir, script)

    def _local_datetime(self, date_time=None):
        if not date_time:
            date_time = datetime.datetime.now()
        utc, local = timezone('UTC'), timezone(getattr(settings, 'MIGRATIONS_TIMEZONE', 'UTC'))
        return str(utc.localize(date_time).astimezone(local))[:16]  # cut off at minutes

    def failfast(self, message):
        self.console(message)
        exit(1)

    def console(self, message='', color=None, newline=True):  # passing None == newline
        ''' abstracted so we can mock it out for tests '''
        output = self._pager.stdin if self._pager else sys.stdout
        message = colored(message, color) if message else message
        output.write(message + ('\n' if newline else ''))

    def allowed_types(self):
        return getattr(settings, 'MIGRATIONS_ALLOWED_TYPES', None)

    def type_allowed(self, type):
        if self.allowed_types():
            return type in self.allowed_types()
        return True

    def failfast_bad_type(self):
        if not self.type_allowed(self.type):
            if not self.type:
                self.failfast('Your MIGRATIONS_ALLOWED_TYPES setting requires that you pass a --type for every migratron command.')
            else:
                self.failfast('Type %s is not allowed by your MIGRATIONS_ALLOWED_TYPES setting of %s' % (
                    self.type, settings.MIGRATIONS_ALLOWED_TYPES))

    def get_script_author_link(self, script):
        func = getattr(settings, 'MIGRATIONS_SCRIPT_AUTHOR_LINK_FUNCTION', None)
        if func:
            try:
                return func(self.full_script_path(script))
            except:
                return None

    def metadata(self, _script):

        script = self.full_script_path(_script)

        # don't just read doc string; may execute file if code is outside __main__
        result = {}
        try:
            with open(script, 'r') as file:
                file_contents = file.read()
                comment = re.findall(r'^(?:"""|/\*)(.*?)(?:"""|\*/)', file_contents, re.DOTALL)[0]
                _result = yaml.load(comment)
                if isinstance(_result, dict):  # can return a str for regular comments
                    result = _result
        except IndexError:
            pass
        except yaml.scanner.ScannerError:
            pass
        except IOError:
            pass

        # author meta-data from source control
        result['link'] = self.get_script_author_link(_script)

        return result
