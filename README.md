CaveJohnson is a program to teach XCode6 CI new tricks.

#Examples

Report status to GitHub inside trigger

First configure GitHub credentials

```bash
sudo -u _xcsbuildd cavejohnson setGithubCredentials
```

Now from inside trigger we can do

```bash
cavejohnson setGithubStatus
```

Figure out what SHA or repo is being integrated

```bash
cavejohnson getGithubRepo
cavejohnson getSha
```


#install

Requires Python 3

```bash
pip3.4 install git+https://github.com/drewcrawford/CaveJohnson.git
```

