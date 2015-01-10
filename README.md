CaveJohnson is a program to teach XCode6 Server new tricks.  It's a set of commands that perform various commonly-used tasks in a continuous build system.  While designed primarily for use inside an XCS trigger script, many of the commands are useful to other build systems (Jenkins, TeamCity, etc.) because the author is unusually good at reverse-engineering and duplicating weird Xcode behavior.

In true Unix style, these commands can all be used separately:

* Build status reporting to GitHub
* Detecting the GitHub repo and git sha of the current XCS integration
* Set the CFBundleVersion based on the XCS integration number
* Re-sign an IPA with a new provisioning profile and certificate
* Install a mobile provisioning profile to XCS
* Resolve missing SwiftSupport that prevent builds from being processed correctly in iTunesConnect
* Generate `.symbols` files so iTunesConnect symbolicates your crash reports
* Submit to iTunesConnect (new TestFlight) so you can get fully automatic deployments
* Submit to HockeyApp

#Examples

Report status to GitHub inside trigger

First configure GitHub credentials

```bash
sudo -u _xcsbuildd cavejohnson setGithubCredentials
```

Now from inside trigger we can do

```bash
#!/bin/bash
PATH=/Library/Frameworks/Python.framework/Versions/3.4/bin:$PATH
cavejohnson setGithubStatus
```

Figure out what SHA or repo is being integrated

```bash
$ cavejohnson getGithubRepo
drewcrawford/DCAKit
$ cavejohnson getSha
25ab291bf606f8ed9b5eb612553329b622882e15
```

Set minor build number (CFBundleVersion) to XCS integration id

```bash
cavejohnson setBuildNumber --plist-path ./path/to/Info.plist
```

# Very quick guide to automating New TestFlight:

1.  First, you need to copy your distribution certificate and key into the System keychain
2.  Make sure the key's Access Control is set to "Allow all applications to access the item" or you will [get a hang](http://faq.sealedabstract.com/xcodeCI/#signing-for-distribution).
3.  Check your provisioning profile into source control
4.  In build settings, ensure your Code Signing for Release is set to **distribution**, and your provisioning profile for release is **Not automatic**.  More detail on the why can be found in my [Xcode CI missing manual](http://faq.sealedabstract.com/xcodeCI/#signing-for-distribution)
5.  Set up a pre-integration trigger

```bash
#!/bin/bash
PATH=/Library/Frameworks/Python.framework/Versions/3.4/bin:$PATH
cavejohnson setBuildNumber --plist-path ./MyiOSApp/MyiOSApp/Info.plist
cavejohnson installMobileProvision --provisioning-profile ./MyiOSApp/myIosApp.mobileprovision
```

This installs the provisioning profile from source control and creates a unique build number for the app.

Now you need a post-integration trigger:

```bash
PATH=/Library/Frameworks/Python.framework/Versions/3.4/bin:$PATH
cavejohnson xcodeGUITricks --new-ipa-path myapp.ipa
cavejohnson uploadiTunesConnect --itunes-app-id 12345678 --itunes-username me@me.com --itunes-password mypassword --ipa-path myapp.ipa
```

This works around some [Xcode CLI bugs](http://faq.sealedabstract.com/xcodeCI/#the-case-of-the-missing-swiftsupport) and sends the fixed IPA to iTunesConnect.

#install

Requires Python 3

```bash
pip3.4 install git+https://github.com/drewcrawford/CaveJohnson.git
```

# Notes

You may also find my [Xcode CI missing manual](http://faq.sealedabstract.com/xcodeCI/) helpful, which explains the rationale for some things in this program.
