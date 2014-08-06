#!python3
import os
import os.path
import re
import sys
import subprocess
import enum

__version__ = "0.1.0"

CREDENTIALS_FILE = "/var/_xcsbuildd/githubcredentials"
#CREDENTIALS_FILE = "/tmp/removeme"


def set_github_status(repo, sha):
    token = github_auth()
    import github3
    gh = github3.login(token=token)
    (owner, reponame) = repo.split("/")
    r = gh.repository(owner, reponame)
    if not r:
        raise Exception("Trouble getting a repository for %s and %s" % (owner, reponame))

    # these constants are documented on http://faq.sealedabstract.com/xcodeCI/
    xcs_status = os.environ["XCS_INTEGRATION_RESULT"]
    if xcs_status == "unknown":
        gh_state = "pending"
    elif xcs_status == "build-errors":
        gh_state = "error"
    elif xcs_status == "test-failures" or xcs_status == "warnings" or xcs_status == "analyzer-warnings" or xcs_status == "test-failures":
        gh_state = "failure"
    elif xcs_status == "success":
        gh_state = "success"
    else:
        raise Exception("Unknown xcs_status %s.  Please file a bug at http://github.com/drewcrawford/cavejohnson" % xcs_status)

    r.create_status(sha=sha, state=gh_state, target_url=get_integration_url(), description=get_botname())


def github_auth():
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            token = f.read().strip()
            return token

    from github3 import authorize
    from getpass import getpass
    user = ''
    while not user:
        user = input("Username: ")
    password = ''
    while not password:
        password = getpass('Password for {0}: '.format(user))
    note = 'cavejohnson, teaching Xcode 6 CI new tricks'
    note_url = 'http://sealedabstract.com'
    scopes = ['repo:status']
    auth = authorize(user, password, scopes, note, note_url)

    with open(CREDENTIALS_FILE, "w") as f:
        f.write(auth.token)

    return auth.token


# rdar://17923022
def get_sha():
    sourceLogPath = os.path.join(os.environ["XCS_OUTPUT_DIR"], "sourceControl.log")
    with open(sourceLogPath) as sourceFile:
        sourceLog = sourceFile.read()
        match = re.search('"DVTSourceControlLocationRevisionKey"\s*\:\s*"(.*)"', sourceLog)
        if not match:
            raise Exception("No sha match in file.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the contents of %s" % sourceLogPath)
        return match.groups()[0]
    assert False


def get_repo():
    sourceLogPath = os.path.join(os.environ["XCS_OUTPUT_DIR"], "sourceControl.log")
    with open(sourceLogPath) as sourceFile:
        sourceLog = sourceFile.read()
        match = re.search('"DVTSourceControlWorkspaceBlueprintRemoteRepositoryURLKey"\s*\:\s*"(.*)"', sourceLog)
        if not match:
            raise Exception("No repo match in file.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the contents of %s" % sourceLogPath)
        XcodeFunkyRepo = match.groups()[0]  # some funky string like "github.com:drewcrawford\/DCAKit.git"
        assert XcodeFunkyRepo[:11] == "github.com:"
        XcodeFunkyRepo = XcodeFunkyRepo[11:]
        XcodeFunkyRepo = XcodeFunkyRepo.replace("\/", "/")
        assert XcodeFunkyRepo[-4:] == ".git"
        XcodeFunkyRepo = XcodeFunkyRepo[:-4]
        return XcodeFunkyRepo
    assert False


def set_build_number(plistpath):
    if not os.path.exists(plistpath):
        output = subprocess.check_output(["find", ".", "-name", "*.plist"]).decode('utf-8')
        print(output)
        raise Exception("No such plist exists.  Try one of the strings shown in the log.")

    import plistlib
    with open(plistpath, "rb") as f:
        data = plistlib.load(f)
    # see xcdoc://?url=developer.apple.com/library/etc/redirect/xcode/ios/602958/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html
    # but basically this is the only valid format
    # unofficially, however, sometimes a buildno is omitted.
    import re
    match = re.match("(\d+)\.?(\d*)\.?(\d*)", data["CFBundleVersion"])
    if not match:
        raise Exception("Can't figure out CFBundleVersion.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the string %s" % data["CFBundleVersion"])
    (major, minor, build) = match.groups()
    data["CFBundleVersion"] = "%s.%s.%s" % (major, minor, os.environ["XCS_INTEGRATION_NUMBER"])
    with open(plistpath, "wb") as f:
        plistlib.dump(data, f)


def get_integration_url():
    return "https://" + subprocess.check_output(["hostname"]).decode('utf-8').strip() + "/xcode/bots/" + os.environ["XCS_BOT_TINY_ID"] + "/integrations"


def get_botname():
    return os.environ["XCS_BOT_NAME"]


def get_commit_log():
    token = github_auth()
    import github3
    gh = github3.login(token=token)
    (owner, reponame) = get_repo().split("/")
    r = gh.repository(owner, reponame)
    if not r:
        raise Exception("Trouble getting a repository for %s and %s" % (owner, reponame))
    commit = r.git_commit(get_sha())
    return commit.to_json()["message"]


class HockeyAppNotificationType(enum.Enum):
    dont_notify = 0
    notify_testers_who_can_install = 1
    notify_all_testers = 2


class HockeyAppStatusType(enum.Enum):
    dont_allow_to_download_or_install = 0
    allow_to_download_or_install = 1


class HockeyAppMandatoryType(enum.Enum):
    not_mandatory = 0
    mandatory = 1


def upload_hockeyapp(token, appid, notification=None, status=None, mandatory=None, tags=None):
    import requests
    ipa_path = os.path.join(os.environ["XCS_OUTPUT_DIR"], os.environ["XCS_PRODUCT"])
    if not os.path.exists(ipa_path):
        raise Exception("Can't find %s." % ipa_path)
    dsym_path = "/tmp/cavejohnson.dSYM.zip"
    subprocess.check_output("cd %s && zip -r %s dSYMs" % (os.environ["XCS_ARCHIVE"], dsym_path), shell=True)
    if not os.path.exists(dsym_path):
        raise Exception("Error processing dsym %s" % dsym_path)

    with open(dsym_path, "rb") as dsym:
        with open(ipa_path, "rb") as ipa:
            files = {"ipa": ipa, "dsym": dsym}
            data = {"notes": get_commit_log(), "notes_type": "1", "commit_sha": get_sha(), "build_server_url": get_integration_url()}

            if notification:
                data["notify"] = notification.value
            if status:
                data["status"] = status.value
            if mandatory:
                data["mandatory"] = mandatory.value
            if tags:
                data["tags"] = tags

            r = requests.post("https://rink.hockeyapp.net/api/2/apps/%s/app_versions/upload" % appid, data=data, files=files, headers={"X-HockeyAppToken": token})
            if r.status_code != 200:
                print(r.text)
                raise Exception("Hockeyapp returned error code %d" % r.status_code)


def setGithubStatus(args):
    set_github_status(get_repo(), get_sha())


def getGithubRepo(args):
    print(get_repo())


def getSha(args):
    print(get_sha())


def setGithubCredentials(args):
    whoami = subprocess.check_output(["whoami"]).strip().decode("utf-8")
    if whoami != "_xcsbuildd":
        print("%s is not _xcsbuildd" % whoami)
        print("Sorry, you need to call like 'sudo -u _xcsbuildd cavejohnson setGithubCredentials'")
        sys.exit(1)
    github_auth()


def setBuildNumber(args):
    set_build_number(args.plist_path)


def uploadHockeyApp(args):
    notify = None
    if args.notification_settings == "dont_notify":
        notify = HockeyAppNotificationType.dont_notify
    elif args.notification_settings == "notify_testers_who_can_install":
        notify = HockeyAppNotificationType.notify_testers_who_can_install
    elif args.notification_settings == "notify_all_testers":
        notify = HockeyAppNotificationType.notify_all_testers

    availability = None
    if args.availability_settings == "dont_allow_to_download_or_install":
        availability = HockeyAppStatusType.dont_allow_to_download_or_install
    elif args.availability_settings == "allow_to_download_or_install":
        availability = HockeyAppStatusType.allow_to_download_or_install

    if args.mandatory:
        mandatory = HockeyAppMandatoryType.mandatory
    else:
        mandatory = HockeyAppMandatoryType.not_mandatory

    upload_hockeyapp(args.token, args.app_id, notification=notify, status=availability, mandatory=mandatory, tags=args.restrict_to_tag)


def main_func():
    import argparse
    parser = argparse.ArgumentParser(prog='CaveJohnson')
    subparsers = parser.add_subparsers(help='sub-command help')
    # create the parser for the "setGithubStatus" command
    parser_ghstatus = subparsers.add_parser('setGithubStatus', help='Sets the GitHub status to an appropriate value inside a trigger.  Best to run both before and after build.')
    parser_ghstatus.set_defaults(func=setGithubStatus)

    parser_ghrepo = subparsers.add_parser('getGithubRepo', help='Detects the GitHub repo inside a trigger.')
    parser_ghrepo.set_defaults(func=getGithubRepo)

    parser_getsha = subparsers.add_parser('getSha', help="Detects the git sha of what is being integrated")
    parser_getsha.set_defaults(func=getSha)

    parser_authenticate = subparsers.add_parser('setGithubCredentials', help="Sets the credentials that will be used to talk to GitHub.")
    parser_authenticate.set_defaults(func=setGithubCredentials)

    parser_buildnumber = subparsers.add_parser('setBuildNumber', help="Sets the build number (CFBundleVersion) based on the bot integration count to building")
    parser_buildnumber.add_argument('--plist-path', help="path for the plist to edit", required=True)
    parser_buildnumber.set_defaults(func=setBuildNumber)

    parser_hockeyapp = subparsers.add_parser('uploadHockeyApp', help="Uploads an app to HockeyApp")
    parser_hockeyapp.add_argument("--token", required=True, help="Hockeyapp token")
    parser_hockeyapp.add_argument("--app-id", required=True, help="Hockeyapp app ID")
    parser_hockeyapp.add_argument("--notification-settings", choices=["dont_notify", "notify_testers_who_can_install", "notify_all_testers"], default=None)
    parser_hockeyapp.add_argument("--availability-settings", choices=["dont_allow_to_download_or_install", "allow_to_download_or_install"], default=None)
    parser_hockeyapp.add_argument("--mandatory", action='store_true', default=False, help="Makes the build mandatory (users must install)")
    parser_hockeyapp.add_argument("--restrict-to-tag", action='append', default=None, help="Restricts the build's availibility to users with certain tags")
    parser_hockeyapp.set_defaults(func=uploadHockeyApp)

    args = parser.parse_args()
    args.func(args)
