#!python3
from setuptools import setup, find_packages
import cavejohnson  # detect cj version
setup(
    name="cavejohnson",
    version=cavejohnson.__version__,
    packages=find_packages(),
    install_requires=["github3.py"],
    entry_points={
        'console_scripts': [
            'cavejohnson = cavejohnson:main_func',
        ],
    }
)
