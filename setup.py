from distutils.core import setup

with open('README.md') as file:
    long_description = file.read()

setup(
    name='django-getpaid',
    description='Multi-broker payment processor for django',
    long_description=long_description,
    version='1.0',
    packages=['getpaid',],
    url='https://github.com/cypreess/django-getpaid',
    license='MIT',
    author='Krzysztof Dorosz',
    author_email='cypreess@gmail.com',
    install_requires=['django'],
)
