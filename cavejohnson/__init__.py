#!python3
import os
import os.path
import re
import sys
import subprocess

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


def get_integration_url():
    return "https://" + subprocess.check_output(["hostname"]) + "/xcode/bots/" + os.environ["XCS_BOT_TINY_ID"].decode("utf-8") + "/integrations"


def get_botname():
    return os.environ["XCS_BOT_NAME"]
    #!python3


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

    args = parser.parse_args()
    args.func(args)
