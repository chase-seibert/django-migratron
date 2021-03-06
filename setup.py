from distutils.core import setup

setup(
    name='django-migratron',
    version='0.1.3',
    author='Chase Seibert',
    author_email='chase.seibert@gmail.com',
    packages=[
        'migratron',
        'migratron.management',
        'migratron.management.commands',
        'migratron.templates',
    ],
    url='https://github.com/chase-seibert/django-migratron',
    download_url='https://github.com/chase-seibert/django-migratron/tarball/master',
    license='LICENSE.txt',
    description='Create and run different buckets of unordered schema and data migrations.',
    requires=[
        'yaml',
        'yamlfield',
        'termcolor',
    ],
)
