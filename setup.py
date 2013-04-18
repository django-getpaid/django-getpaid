from setuptools import find_packages, setup

with open('README.rst') as file:
    long_description = file.read()

setup(
    name='django-getpaid',
    description='Multi-broker payment processor for django',
    long_description=long_description,
    version='1.4.0',
    packages=find_packages(),
    url='https://github.com/cypreess/django-getpaid',
    license='MIT',
    author='Krzysztof Dorosz',
    author_email='cypreess@gmail.com',
    extras_require = {
        'payu': [
            'django-celery>=3.0.11',
        ],
        'moip': [
        	'requests',
        ],
    },

    package_data={
        'getpaid': [
            'templates/getpaid/*.html',
            'locale/pl/LC_MESSAGES/*',
            'locale/pt_BR/LC_MESSAGES/*',
        ],
        'getpaid.backends.dummy': [
            'templates/getpaid_dummy_backend/*.html',
        ],

        'getpaid.backends.dotpay': [
            'static/getpaid/backends/dotpay/*',
        ],

        'getpaid.backends.payu': [
            'static/getpaid/backends/payu/*',
        ],

        'getpaid.backends.transferuj': [
            'static/getpaid/backends/transferuj/*',
        ],
        'getpaid.backends.moip': [
            'static/getpaid/backends/moip/*',
            ],
    },
)
