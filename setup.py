from distutils.core import setup

setup(
    name='django-migratron',
    version='0.1',
    author='Chase Seibert',
    author_email='chase.seibert@gmail.com',
    packages=['migratron'],
    url='https://github.com/chase-seibert/migratron',
    license='LICENSE.txt',
    description='Create and run different buckets of unordered schema and data migrations.',
    long_description=open('README.md').read(),
)
