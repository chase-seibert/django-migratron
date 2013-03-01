import subprocess


def _git_log_format(script, format):
    command = 'git log -1 --pretty=format:' + format + ' ' + script
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    return process.communicate()[0]


def get_git_script_author_hash(script):
    '''
    Retrieves the script author commit hash from a file as part of a git repository.
    '''
    return _git_log_format(script, '%H')
