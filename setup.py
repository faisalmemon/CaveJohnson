#!python3
from setuptools import setup, find_packages
import cavejohnson  # detect cj version
setup(
    name="cavejohnson",
    version=cavejohnson.__version__,
    packages=find_packages(),
    install_requires=["github3.py", "requests"],
    entry_points={
        'console_scripts': [
            'cavejohnson = cavejohnson:main_func',
        ],
    },
    author="Drew Crawford",
    author_email="drew@sealedabstract.com",
    url="http://github.com/drewcrawford/cavejohnson",
    description="Teach Xcode 6 CI new tricks",
    long_description="""CaveJohnson is a program to teach XCode6 Server new tricks. It's a set of commands that perform various commonly-used tasks in a continuous build system. While designed primarily for use inside an XCS trigger script, many of the commands are useful to other build systems (Jenkins, TeamCity, etc.) because the author is unusually good at reverse-engineering and duplicating weird Xcode behavior.

In true Unix style, these commands can all be used separately:

* Build status reporting to GitHub
* Detecting the GitHub repo and git sha of the current XCS integration
* Set the CFBundleVersion based on the XCS integration number
* Re-sign an IPA with a new provisioning profile and certificate
* Install a mobile provisioning profile to XCS
* Resolve missing SwiftSupport that prevent builds from being processed correctly in iTunesConnect
* Generate .symbols files so iTunesConnect symbolicates your crash reports
* Submit to iTunesConnect (new TestFlight) so you can get fully automatic deployments
* Submit to HockeyApp""",
    classifiers=["Development Status :: 5 - Production/Stable",
                 "Environment :: Console",
                 "Environment :: MacOS X",
                 "Intended Audience :: Developers",
                 "Intended Audience :: Information Technology",
                 "Intended Audience :: System Administrators",
                 "License :: OSI Approved :: MIT License",
                 "Operating System :: MacOS :: MacOS X",
                 "Programming Language :: Python :: 3 :: Only",
                 "Programming Language :: Python :: 3.4",
                 "Topic :: Software Development :: Build Tools",
                 "Topic :: Software Development :: Testing",
                 ],
)
