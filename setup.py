from setuptools import find_packages, setup

setup(
    name='tg-keyword-trends',
    version='1',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    package_data={'tg_keyword_trends': ['report_template_text.txt']},
    url='',
    license='',
    author='tomja',
    author_email='',
    description='Telegram keyword trend analysis tool',
    python_requires='>=3.11',
    entry_points={
        'console_scripts': [
            'tg-keyword-trends=tg_keyword_trends.app:main',
        ],
    },
)
