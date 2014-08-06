#!python3
from setuptools import setup, find_packages

import caffeine  # detect caffeine's version
setup(
    name="cavejohnson",
    version=caffeine.__version__,
    packages=find_packages(),
    install_requires=["github3.py","keyring"],
    scripts=[],
)
