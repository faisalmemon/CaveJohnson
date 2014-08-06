#!python3
import os
import os.path
import re

__version__ = "0.1.0"

CREDENTIALS_FILE = "/var/_xcsbuildd/githubcredentials"


def set_github_status(repo, sha):
    (ident, token) = github_auth()
    import github3
    gh = github3.login(token=token)
    (owner, reponame) = repo.split("/")
    r = gh.repository(owner, reponame)
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
    import keyring
    if keyring.get_password("cavejohnson", "github"):
        (ident, token) = keyring.get_password("cavejohnson", "github").split("::")
        return (int(ident), token)

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

    keyring.set_password("cavejohnson", "github", str(auth.id) + "::" + auth.token)
    return (auth.id, auth.token)


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
        return XcodeFunkyRepo
    assert False


def get_integration_url():
    return "https://" + os.system("hostname") + "/xcode/bots/" + os.environ["XCS_BOT_TINY_ID"] + "/integrations"


def get_botname():
    return os.environ["XCS_BOT_NAME"]
