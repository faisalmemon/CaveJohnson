#!python3
import os
import os.path
import re
import sys
import subprocess
import enum

__version__ = "1.1"

CREDENTIALS_FILE = "/var/_xcsbuildd/githubcredentials"


def warning(*objs):
    with open("/tmp/cavejohnson.log", "a") as file:
        file.write(" ".join(objs))
        file.write("\n")


def reSignIPAArgs(args):
    reSignIPA(args.new_mobileprovision_path, args.certificate_name, args.out_ipa_name, args.ipa_path)


def zipdir(path, zip_path):
    import zipfile
    with zipfile.ZipFile(zip_path, 'w') as zip:
        for root, dirs, files in os.walk(path):
            for file in files:
                full_path = os.path.join(root, file)
                correct_path = full_path[len(path):]
                zip.write(full_path, arcname=correct_path, compress_type=zipfile.ZIP_DEFLATED)


def reSignIPA(new_mobileprovision_path, certificate_name, out_ipa_name, ipa_path=None):
    if not ipa_path:
        ipa_path = os.environ["XCS_OUTPUT_DIR"] + "/" + os.environ["XCS_PRODUCT"]

    import plistlib
    # extract from mobileprovision
    entitlements = subprocess.check_output(["security", "cms", "-D", "-i", new_mobileprovision_path])
    entitlements = plistlib.loads(entitlements)

    info_plist = load_plist_ipa(ipa_path)

    if not entitlements["Entitlements"]["application-identifier"].endswith(info_plist["CFBundleIdentifier"]):
        print("Entitlements application-identifier %s doesn't match info_plist identifier %s" % (entitlements["Entitlements"]["application-identifier"], info_plist["CFBundleIdentifier"]))

    # todo: resign frameworks

    import tempfile
    import zipfile
    tempdir = tempfile.mkdtemp()
    zip_file = zipfile.ZipFile(ipa_path)
    zip_file.extractall(tempdir)
    warning("Working in", tempdir)

    # calculate appname
    import re
    not_app = list(filter(lambda x: re.match("Payload/.*.app/$", x), zip_file.namelist()))[0]  # like 'Payload/MyiOSApp.app/'
    appname = re.match("Payload/(.*).app/$", not_app).groups()[0] + ".app"
    payload_path = tempdir + "/Payload"

    app_path = payload_path + "/" + appname

    import shutil
    shutil.copyfile(new_mobileprovision_path, app_path + "/embedded.mobileprovision")

    # write entitlements to tempfile
    with open(tempdir + "/entitlements.plist", "wb") as fp:
        plistlib.dump(entitlements["Entitlements"], fp)
    warning("codesign begin")
    subprocess.check_call(["codesign", "--entitlements", tempdir + "/entitlements.plist", "-f", "-s", certificate_name, app_path])
    warning("codesign end")

    zipdir(payload_path, out_ipa_name)
    shutil.rmtree(tempdir)
    warning("done signing")


def xcodeGUITricksArgs(args):
    xcodeGUITricks(args.archive_path, args.new_ipa_path)


def xcodeGUITricks(archive_path, new_ipa_path):
    if not archive_path:
        archive_path = os.environ["XCS_ARCHIVE"]

    import tempfile
    tempdir = tempfile.mkdtemp()

    # First we copy the payload
    import shutil
    # There's only 1 app, right?
    appname = os.listdir(archive_path + "/Products/Applications")
    assert len(appname) == 1
    appname = appname[0]

    shutil.copytree(archive_path + "/Products/Applications/", tempdir + "/Payload")

    # next, we copy the swiftsupport
    shutil.copytree(archive_path + "/SwiftSupport", tempdir + "/SwiftSupport")

    # finally, we fix up the symbols
    # we need the app binary
    appbinary = archive_path + "/Products/Applications/" + appname + "/" + appname[:-4]  # .app, like MyAppName.app/MyAppName
    os.mkdir(tempdir + "/Symbols")
    # This was reverse-engineered by running a GUI export and poking in a file called IDEDistribustion.standard.log
    subprocess.check_call(["/Applications/Xcode.app/Contents/Developer/usr/bin/symbols", "-noTextInSOD",
                           "-noDaemon", "-arch", "all", "-symbolsPackageDir", tempdir + "/Symbols", appbinary])

    # finally, let's call it a day
    zipdir(tempdir, new_ipa_path)
    shutil.rmtree(tempdir)


def uploadITMS(args):
    upload_itunesconnect(args.itunes_app_id, args.itunes_username, args.itunes_password, args.ipa_path)


def upload_itunesconnect(itunes_app_id, itunes_username, itunes_password, ipa_path=None):
    if not ipa_path:
        ipa_path = os.environ["XCS_OUTPUT_DIR"] + "/" + os.environ["XCS_PRODUCT"]

    data = load_plist_ipa(ipa_path)

    # first, we compute a path to the IPA
    # now we get a temp path to work in
    new_ipa_basename = "payload.ipa"
    import tempfile
    tpath = tempfile.mkdtemp()
    print("Working in path", tpath)
    packagepath = tpath + "/package.itmsp"
    new_ipa_path = packagepath + "/" + new_ipa_basename
    os.mkdir(packagepath)

    # copy the IPA to our temp path
    import shutil
    shutil.copyfile(ipa_path, new_ipa_path)

    # compute MD5
    import hashlib
    md5 = hashlib.md5()
    with open(new_ipa_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    checksum = md5.hexdigest()

    # calculate filesize
    filesize = os.path.getsize(new_ipa_path)

    # Ok, here we go

    metadata_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package version="software5.2" xmlns="http://apple.com/itunes/importer">
    <software_assets apple_id="{APP_ID}"
        bundle_short_version_string="{SHORT_VERSION_STRING}"
        bundle_version="{BUNDLE_VERSION}"
        bundle_identifier="{BUNDLE_IDENTIFIER}">
        <asset type="bundle">
            <data_file>
                <file_name>{IPA_NAME}</file_name>
                <checksum type="md5">{MD5}</checksum>
                <size>{FILESIZE}</size>
            </data_file>
        </asset>
    </software_assets>
</package>""".format(APP_ID=itunes_app_id, SHORT_VERSION_STRING=data["CFBundleShortVersionString"], BUNDLE_VERSION=data["CFBundleVersion"],
                     BUNDLE_IDENTIFIER=data["CFBundleIdentifier"], IPA_NAME=new_ipa_basename, MD5=checksum, FILESIZE=filesize)

    with open(packagepath + "/metadata.xml", "w") as f:
        f.write(metadata_xml)

    # run iTMSUploader
    subprocess.check_call(["/Applications/Xcode.app/Contents/Applications/Application Loader.app/Contents/MacOS/itms/bin/iTMSTransporter",
                           "-m", "upload", "-apple_id", itunes_app_id, "-u", itunes_username, "-p", itunes_password, "-f", packagepath])

    shutil.rmtree(tpath)


def set_github_status(repo, sha, token=None, integration_result=None, url=None, botname=None):
    import github3
    if not token:
        token = github_auth()
    gh = github3.login(token=token)
    repo = repo.strip("/")
    (owner, reponame) = repo.split("/")
    r = gh.repository(owner, reponame)
    if not r:
        raise Exception("Trouble getting a repository for %s and %s" % (owner, reponame))

    # these constants are documented on http://faq.sealedabstract.com/xcodeCI/
    if not integration_result:
        xcs_status = os.environ["XCS_INTEGRATION_RESULT"]
    else:
        xcs_status = integration_result
    if xcs_status == "unknown":
        gh_state = "pending"
    elif xcs_status == "build-errors":
        gh_state = "error"
    elif xcs_status == "test-failures" or xcs_status == "warnings" or xcs_status == "analyzer-warnings" or xcs_status == "test-failures":
        gh_state = "failure"
    elif xcs_status == "succeeded":
        gh_state = "success"
    else:
        raise Exception("Unknown xcs_status %s.  Please file a bug at http://github.com/drewcrawford/cavejohnson" % xcs_status)
    if not url:
        url = get_integration_url()
    if not botname:
        botname = get_botname()
    r.create_status(sha=sha, state=gh_state, target_url=url, description=botname)


def install_mobileprovision_args(args):
    install_mobileprovision(args.provisioning_profile)


def install_mobileprovision(mobileprovision_path):
    import shutil
    basename = os.path.basename(mobileprovision_path)
    shutil.copyfile(mobileprovision_path, "/Library/Developer/XcodeServer/ProvisioningProfiles/" + basename)


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
    scopes = ['repo:status', 'repo']
    auth = authorize(user, password, scopes, note, note_url)

    with open(CREDENTIALS_FILE, "w") as f:
        f.write(auth.token)

    return auth.token


# rdar://17923022
def get_sha():
    return get_repo_sha(get_git_directory())

def get_git_directory():
    for subdir in os.listdir('.'):
        if is_git_directory(subdir):
            return subdir
    assert False

def is_git_directory(path = '.'):
    return subprocess.call(['git', '-C', path, 'status'], stderr=subprocess.STDOUT, stdout = open(os.devnull, 'w')) == 0    

def get_repo_sha(repo):
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode('ascii').strip()
    return sha

def update_git_submodules(repo):
    subprocess.call(['git', 'submodule', 'update', '--init', '--recursive'], cwd=repo)

def get_sha_from_log():
    sourceLogPath = os.path.join(os.environ["XCS_OUTPUT_DIR"], "sourceControl.log")
    with open(sourceLogPath) as sourceFile:
        sourceLog = sourceFile.read()
        match = re.search('"DVTSourceControlLocationRevisionKey"\s*\:\s*"(.*)"', sourceLog)
        if not match:
            raise Exception("No sha match in file.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the contents of %s" % sourceLogPath)
        return match.groups()[0]
    assert False

def get_origin(repo):
    origin = subprocess.check_output(['git', 'ls-remote', '--get-url'], cwd=repo).decode('ascii').strip()
    return origin

def get_repo():
    origin = get_origin(get_git_directory())
    if not origin:
        raise Exception("Unable to find repo.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the contents of %s" % sourceLogPath)
    githubRegex = re.compile('github.com(:)?', re.IGNORECASE)
    match = githubRegex.search(origin)
    assert match
    repo = origin[match.end():]
    repo = repo.replace("\/", "/")
    assert repo[-4:] == ".git"
    repo = repo[:-4]
    return repo

def get_repo_from_log():
    sourceLogPath = os.path.join(os.environ["XCS_OUTPUT_DIR"], "sourceControl.log")
    with open(sourceLogPath) as sourceFile:
        sourceLog = sourceFile.read()
        match = re.search('"DVTSourceControlWorkspaceBlueprintRemoteRepositoryURLKey"\s*\:\s*"(.*)"', sourceLog)
        if not match:
            raise Exception("No repo match in file.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the contents of %s" % sourceLogPath)
        XcodeFunkyRepo = match.groups()[0]  # some funky string like "github.com:drewcrawford\/DCAKit.git"
        githubRegex = re.compile('github.com(:)?', re.IGNORECASE)
        match = githubRegex.search(XcodeFunkyRepo)
        assert match
        XcodeFunkyRepo = XcodeFunkyRepo[match.end():]
        XcodeFunkyRepo = XcodeFunkyRepo.replace("\/", "/")
        assert XcodeFunkyRepo[-4:] == ".git"
        XcodeFunkyRepo = XcodeFunkyRepo[:-4]
        return XcodeFunkyRepo
    assert False


def load_plist_ipa(ipa_path):
    # we have to read the plist inside the IPA
    import zipfile
    zip_file = zipfile.ZipFile(ipa_path)
    import re
    # search for info plist inside IPA
    info_plists = list(filter(lambda x: re.match("Payload/[^/]*/Info.plist", x), zip_file.namelist()))
    assert len(info_plists) == 1

    with zip_file.open(info_plists[0]) as plistfile:
        # some hackery to read into RAM because zip_file doesn't support 'seek' as plistlib requires
        plistdata = plistfile.read()

    import plistlib
    data = plistlib.loads(plistdata)
    return data


def load_plist(plistpath):
    if not os.path.exists(plistpath):
        output = subprocess.check_output(["find", ".", "-name", "*.plist"]).decode('utf-8')
        print(output)
        raise Exception("No such plist exists.  Try one of the strings shown in the log.")

    import plistlib
    with open(plistpath, "rb") as f:
        data = plistlib.load(f)
    return data


def set_build_number(plistpath):
    data = load_plist(plistpath)
    # see xcdoc://?url=developer.apple.com/library/etc/redirect/xcode/ios/602958/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html
    # but basically this is the only valid format
    # unofficially, however, sometimes a buildno (and minor) is omitted.
    import re
    match = re.match("(\d+)\.?(\d*)\.?(\d*)", data["CFBundleVersion"])
    if not match:
        raise Exception("Can't figure out CFBundleVersion.  Please file a bug at http://github.com/drewcrawford/cavejohnson and include the string %s" % data["CFBundleVersion"])
    (major, minor, build) = match.groups()
    if minor == "":
        minor = "0"

    data["CFBundleVersion"] = "%s.%s.%s" % (major, minor, os.environ["XCS_INTEGRATION_NUMBER"])
    import plistlib
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


def upload_hockeyapp(token, appid, notification=None, status=None, mandatory=None, tags=None, profile=None):
    import requests
    old_ipa_path = os.path.join(os.environ["XCS_OUTPUT_DIR"], os.environ["XCS_PRODUCT"])
    if not os.path.exists(old_ipa_path):
        raise Exception("Can't find %s." % old_ipa_path)
    dsym_path = "/tmp/cavejohnson.dSYM.zip"
    subprocess.check_output("cd %s && zip -r %s dSYMs" % (os.environ["XCS_ARCHIVE"], dsym_path), shell=True)
    if not os.path.exists(dsym_path):
        raise Exception("Error processing dsym %s" % dsym_path)
    # resign IPA
    new_ipa_path = os.path.join(os.environ["XCS_OUTPUT_DIR"], "resigned.ipa")
    f = open("/tmp/xcodebuildlog", "w")
    data = ["Signing", "xcodebuild", "-exportArchive", "-exportFormat", "IPA", "-archivePath", os.environ["XCS_ARCHIVE"], "-exportPath", new_ipa_path, "-exportProvisioningProfile", profile]
    f.write("".join(data))
    f.close()

    output = subprocess.check_output(["xcodebuild", "-exportArchive", "-exportFormat", "IPA", "-archivePath", os.environ["XCS_ARCHIVE"], "-exportPath", new_ipa_path, "-exportProvisioningProfile", profile])
    print(output)
    with open(dsym_path, "rb") as dsym:
        with open(new_ipa_path, "rb") as ipa:
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
            if r.status_code != 201:
                print(r.text)
                raise Exception("Hockeyapp returned error code %d" % r.status_code)


def setGithubStatus(args):
    if not args.sha:
        args.sha = get_sha()
    if not args.repo:
        args.repo = get_repo()
    set_github_status(args.repo, args.sha, token=args.token, integration_result=args.integration_result, url=args.url, botname=args.bot_name)


def getGithubRepo(args):
    print(get_repo())


def getSha(args):
    print(get_sha())

def setGithubAuthToken(args):
    whoami = subprocess.check_output(["whoami"]).strip().decode("utf-8")
    if whoami != "_xcsbuildd":
        print("%s is not _xcsbuildd" % whoami)
        print("Sorry, you need to call like 'sudo -u _xcsbuildd cavejohnson setGithubAuthToken --token github_auth_token'")
        sys.exit(1)
    with open(CREDENTIALS_FILE, "w") as f:
        f.write(args.token)

def setGithubCredentials(args):
    whoami = subprocess.check_output(["whoami"]).strip().decode("utf-8")
    if whoami != "_xcsbuildd":
        print("%s is not _xcsbuildd" % whoami)
        print("Sorry, you need to call like 'sudo -u _xcsbuildd cavejohnson setGithubCredentials'")
        sys.exit(1)
    github_auth()

def updateGitSubmodules(args):
    update_git_submodules(get_git_directory())

def setBuildNumber(args):
    set_build_number(args.plist_path)


def uploadHockeyApp(args):
    notify = None
    if args.notification_settings == "dont_notify":
        notify = HockeyAppNotificationType.dont_notify
    elif args.notification_settings == "notify_testers_who_can_install":
        notify = HockeyAppNotificationType.notify_testers_who_can_install
    elif args.nltification_settings == "notify_all_testers":
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

    upload_hockeyapp(args.token, args.app_id, notification=notify, status=availability, mandatory=mandatory, tags=args.restrict_to_tag, profile=args.resign_with_profile)


def main_func():
    import argparse
    parser = argparse.ArgumentParser(prog='CaveJohnson')
    subparsers = parser.add_subparsers(help='sub-command help')
    # create the parser for the "setGithubStatus" command
    parser_ghstatus = subparsers.add_parser('setGithubStatus', help='Sets the GitHub status to an appropriate value inside a trigger.  Best to run both before and after build.')
    parser_ghstatus.add_argument("--token", default=None, help="GitHub token (by default, we pull it out of storage with setGithubCredentials)")
    parser_ghstatus.add_argument("--sha", default=None, help="SHA to set status for.  By default, we work this out from XCS. See getSha for details.")
    parser_ghstatus.add_argument("--repo", default=None, help="Repo to set status for.  By default, we work this out from XCS.  See getGithubRepo for details.")
    parser_ghstatus.add_argument("--integration-result", default=None, help="XCS_INTEGRATION_RESULT to parse.  See http://faq.sealedabstract.com/xcodeCI/ for valid values.")
    parser_ghstatus.add_argument("--bot-name", default=None, help="Name of bot.")
    parser_ghstatus.add_argument("--url", default=None, help="URL for more details about this integration.")

    parser_ghstatus.set_defaults(func=setGithubStatus)

    parser_ghrepo = subparsers.add_parser('getGithubRepo', help='Detects the GitHub repo inside a trigger.')
    parser_ghrepo.set_defaults(func=getGithubRepo)

    parser_getsha = subparsers.add_parser('getSha', help="Detects the git sha of what is being integrated")
    parser_getsha.set_defaults(func=getSha)

    parser_authenticate = subparsers.add_parser('setGithubCredentials', help="Sets the credentials that will be used to talk to GitHub.")
    parser_authenticate.set_defaults(func=setGithubCredentials)

    parser_token = subparsers.add_parser('setGithubAuthToken', help="Sets an application access token used to communicate with GitHub. Generate this token via your application settings on github.com.")
    parser_token.add_argument('--token', help="GitHub application access token.", required=True)
    parser_token.set_defaults(func=setGithubAuthToken)

    parser_updategitsubmodules = subparsers.add_parser('updateGitSubmodules', help="Update the repo's git submodules. Xcode Bots may not do so automatically.")
    parser_updategitsubmodules.set_defaults(func=updateGitSubmodules)

    parser_buildnumber = subparsers.add_parser('setBuildNumber', help="Sets the build number (CFBundleVersion) based on the bot integration count to building")
    parser_buildnumber.add_argument('--plist-path', help="path for the plist to edit", required=True)
    parser_buildnumber.set_defaults(func=setBuildNumber)

    parser_hockeyapp = subparsers.add_parser('uploadHockeyApp', help="Uploads an app to HockeyApp")
    parser_hockeyapp.add_argument("--token", required=True, help="Hockeyapp token")
    parser_hockeyapp.add_argument("--app-id", required=True, help="Hockeyapp app ID")
    parser_hockeyapp.add_argument("--notification-settings", choices=["dont_notify", "notify_testers_who_can_install", "notify_all_testers"], default=None)
    parser_hockeyapp.add_argument("--availability-settings", choices=["dont_allow_to_download_or_install", "allow_to_download_or_install"], default=None)
    parser_hockeyapp.add_argument("--mandatory", action='store_true', default=False, help="Makes the build mandatory (users must install)")
    parser_hockeyapp.add_argument("--restrict-to-tag", action='append', default=None, help="Restricts the build's availability to users with certain tags")
    parser_hockeyapp.add_argument("--resign-with-profile", default=None, help="Resign the archive with the specified provisioning profile name.")
    parser_hockeyapp.set_defaults(func=uploadHockeyApp)

    parser_uploadipa = subparsers.add_parser('uploadiTunesConnect', help="Upload the IPA to iTunesConnect (e.g. new TestFlight)")
    parser_uploadipa.add_argument("--itunes-app-id", required=True, help="iTunes app ID")
    parser_uploadipa.add_argument("--itunes-username", required=True, help="iTunes username (technical role or better)")
    parser_uploadipa.add_argument("--itunes-password", required=True, help="iTunes password")
    parser_uploadipa.add_argument("--ipa-path", default=None, help="IPA path.  If unspecified, guesses based on XCS settings.  Note that if reSignIPA is used, this should not be left blank.")
    parser_uploadipa.set_defaults(func=uploadITMS)

    parser_resignipa = subparsers.add_parser('reSignIPA', help="Resign IPA with given provisioning profile")
    parser_resignipa.add_argument("--ipa-path", default=None, help="IPA path.  If unspecified, guesses based on XCS settings.")
    parser_resignipa.add_argument("--new-mobileprovision-path", required=True, help="Path to the mobileprovision to resign with.")
    parser_resignipa.add_argument("--certificate-name", required=True, help="Full name of the certificate to resign with (like 'iPhone Distribution: DrewCrawfordApps LLC (P5GM95Q9VV)')")
    parser_resignipa.add_argument("--out-ipa-name", required=True, help="Name (path) of the resigned IPA file")
    parser_resignipa.set_defaults(func=reSignIPAArgs)

    parser_installmobileprovision = subparsers.add_parser('installMobileProvision', help="Installs the provisioning profile for XCS use")
    parser_installmobileprovision.add_argument("--provisioning-profile", required=True, help="Path to the provisioning profile.")
    parser_installmobileprovision.set_defaults(func=install_mobileprovision_args)

    parser_xcodeGUITricks = subparsers.add_parser('xcodeGUITricks', help="Converts Xcode Archives into IPAs in the way that the Xcode GUI does (swiftsupport + symbols).  Works around rdar://19432441 and rdar://19432725.")
    parser_xcodeGUITricks.add_argument("--archive-path", default=None, help="Path to the Xcode Archive.  If none, guesses based on XCS settings.")
    parser_xcodeGUITricks.add_argument("--new-ipa-path", required=True, help="Path to the output IPA file")
    parser_xcodeGUITricks.set_defaults(func=xcodeGUITricksArgs)

    def usage(args):
        parser.print_help()
    # parser.set_defaults(func=usage)
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        usage(args)
