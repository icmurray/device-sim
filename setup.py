from setuptools import setup

install_requires = [
        'Twisted==12.3.0',
        'pyasn1==0.1.4',
        'pycrypto==2.6',
        'pymodbus==1.2.0',
        'docopt==0.6.1',
        'mosquitto==1.2',
    ]

tests_require = [
        'nose==1.1.2',
    ]

setup(
    name='device-simulator',
    version='0.1.0',
    author='Ian Murray',
    author_email='ian@sprily.co.uk',
    packages=['device_simulator'],
    scripts=[],
    license='LICENSE.txt',
    long_description=open('README.md').read(),
    install_requires=install_requires,
    tests_require=tests_require,
)
