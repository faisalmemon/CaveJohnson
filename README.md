CaveJohnson is a program to teach XCode6 CI new tricks.

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

Upload to HockeyApp

```bash
cavejohnson uploadHockeyApp --token [token] --app-id [app id] --notification-settings dont_notify --resign-with-profile 'My provisioning profile name'
```




#install

Requires Python 3

```bash
pip3.4 install git+https://github.com/drewcrawford/CaveJohnson.git
```

