#!/usr/local/bin/python
from __future__ import print_function
import os, sys
import pwd
import argparse
from typtop.dbaccess import (
    UserTypoDB,
    on_correct_password,
    on_wrong_password,
    VERSION, call_check
)
from typtop.config import (
    set_distro, SEC_DB_PATH, NUMBER_OF_ENTRIES_TO_ALLOW_TYPO_LOGIN,
    WARM_UP_CACHE
)
from typtop.dbutils import logger
from typtop.validate_parent import is_valid_parent
import subprocess
# import getpass


USER = ""
ALLOW_TYPO_LOGIN = True
GITHUB_URL = 'https://github.com/rchatterjee/pam-typopw' # URL in github repo
first_msg = """\n\n
  /  |                          /  |
 _$$ |_    __    __   ______   _$$ |_     ______    ______
/ $$   |  /  |  /  | /      \ / $$   |   /      \  /      \\
$$$$$$/   $$ |  $$ |/$$$$$$  |$$$$$$/   /$$$$$$  |/$$$$$$  |
  $$ | __ $$ |  $$ |$$ |  $$ |  $$ | __ $$ |  $$ |$$ |  $$ |
  $$ |/  |$$ \__$$ |$$ |__$$ |  $$ |/  |$$ \__$$ |$$ |__$$ |
  $$  $$/ $$    $$ |$$    $$/   $$  $$/ $$    $$/ $$    $$/
   $$$$/   $$$$$$$ |$$$$$$$/     $$$$/   $$$$$$/  $$$$$$$/
          /  \__$$ |$$ |                          $$ |
          $$    $$/ $$ |                          $$ |
           $$$$$$/  $$/                           $$/
Hello!

Thanks for installing TypToP (version: {version}).  This software
attaches a new pluggable authentication module (PAM) to almost all of
your common authentication processes, and observes your password
typing mistakes. It records your frequent typing mistakes, and enable
logging in with frequent but slight vairations of your actual login
password that are safe to do so.

This is a research prototype, and we are collecting some anonymous
non-sensitive data about your password typing patterns to verify our
design. The details of what we collect, how we collect and store, and
the security blueprint of this software can be found in the GitHub
page: {url}.  The participation in the study is completely voluntary,
and you can opt out at any time while still keep using the software.

Checkout other options (such as opting out of the study) of the
utility script typtop by running:

$ typtop --help

Note, You have to initiate this for each user who intend to use the
benefit of adaptive typo-tolerant password login.
""".format


class AbortSettings(RuntimeError):
    pass

def _get_login_user():
    # gets the username of the logging user
    pp = subprocess.Popen('who', stdout=subprocess.PIPE)
    output = pp.stdout.read()
    first_line = output.splitlines()[0]
    user = first_line.split()[0]
    return user

def _get_username():
    # trying to go over the problem of
    if USER:
        print("Designated user: {}".format(USER))
        return USER
    uid = os.getuid()
    is_root = uid == 0
    user = _get_login_user()
    if is_root:
        r = raw_input("Setting will be done for login user: {}.\n"
              "Please confirm. (Yn) ".format(user))
        abort = r and r.lower() == 'n'
        if abort:
            raise AbortSettings()
    else:
        print("Designated user: {}".format(user))
    return user

def _get_typoDB():
    user = _get_username()
    try:
        typoDB = UserTypoDB(user)
    except Exception as e:
        print(
            "It seems you have not initialized the db. Try running"\
            " \"sudo {} --init\" to initialize the db.\nThe error "\
            "I ran into is the following:\n{}"\
            .format(sys.argv[0], e)
        )
        return None
    if not typoDB.is_typotoler_init():
        raise Exception("{}:{} not initiated".format(
            str(typoDB),
            typoDB.get_db_path())
        )
    return typoDB

def root_only_operation():
    if os.getuid() != 0:
        print("ERROR!! You need root priviledge to run this operation")
        raise AbortSettings

def initiate_typodb(RE_INIT=False):
    # ValueError(
    #     "You should not require to call this. "
    #     "Something is wrong!! Try re-installing the whole system"
    # )
    root_only_operation()
    user = _get_username()
    try:
        # checks that such a user exists:
        _ = pwd.getpwnam(user).pw_dir
    except KeyError as e:
        print("Error: {}".format(e.message))
        print("Hint: The user ({}) must have an account in this computer."\
              .format(user))
        print("Hint 2: It's not a registration. User the username for "\
              "your account in the computer.")
    else:
        branch = "master"
        subdir = 'osx/pam_opendirectory' if DISTRO == 'darwin'\
                 else 'linux/myunix_chkpwd' if DISTRO in ('debian', 'fedora')\
                      else ''
        cmd = """
        cd /tmp/ && curl -LOk https://github.com/rchatterjee/pam-typopw/archive/{0}.zip && unzip {0}.zip \
        && cd pam-typopw-{0}/{1} && make && make install && cd /tmp && rm -rf {0}.zip pam-typopw*
        """.format(branch, subdir)
        os.system(cmd)

        # right_pw = False
        # for _ in range(3):
        #     pw = getpass.getpass()
        #     right_pw = (check_pw(user, pw) == 0)
        #     if right_pw:
        #         stub = "RE-" if RE_INIT else ""
        #         print("{}Initiating the database...".format(stub),)
        #         tb = UserTypoDB(user)
        #         if RE_INIT:
        #             tb.update_after_pw_change(pw)
        #         else: # Normal Init
        #             tb.init_typotoler(pw, typoTolerOn=ALLOW_TYPO_LOGIN)
        #         print("Done!")
        #         return 0
        #     else:
        #         print("Doesn't look like a correct password. Please try again.")
        # print("Failed to enter a correct password 3 times.")
        # to stop the installation process
        # raise ValueError("incorrect pw given 3 times")

DISTRO = set_distro()
common_auth = {
    'debian': '/etc/pam.d/common-auth',
    'fedora': '/etc/pam.d/system-auth',
    'darwin': ''
}[DISTRO]

def uninstall_pam_typtop():
    # Last try to send logs
    os.system("nohup python -u /usr/local/bin/send_typo_log.py >/dev/null 2>&1 &")
    print(DISTRO)
    if DISTRO == 'darwin':
        cmd = '''
#!/bin/bash
set -e
set -u
for f in /etc/pam.d/{{screensaver,su}} ; do
    if [ ! -e $f.bak ]; then continue ; fi ;
    if [ "$(grep pam_opendirectory_typo $f.bak)" != "" ] ; then
        echo "Backup file is wrong. Removing all pam_opendirectory_typo with pam_opendirectory. Checkout the webpage" ;
        sudo sed -i '' 's/^auth\(.*\)\/usr\/local\/lib\/security\/pam_opendirectory_typo.so/auth\1pam_opendirectory.so/g' $f ;
    else
        sudo mv $f.bak $f;
    fi ;
done
rm -rf /var/log/typtop.log {} /tmp/typtop* /usr/local/etc/typtop.d
rm -rf /usr/local/bin/typtop* /usr/local/bin/send_typo_log.py
pip -q uninstall --yes typtop
        '''.format(SEC_DB_PATH)
        os.system(cmd)
    elif DISTRO in ('debian', 'fedora'):
        raise ValueError("Not implemented yet!!!")
        cmd = '''
#!/bin/bash
set -e
set -u
user=$(who am i| awk '{{print $1}}')

rm -rf /etc/pam.d/typo_auth
        '''.format()
        os.system(cmd)

parser = argparse.ArgumentParser("typtop ")

parser.add_argument(
    "--user",
    help="To set the username. Otherwise login user will be the target"
)
parser.add_argument(
    "--init", action="store_true",
    help="To initialize the DB. You have to run this once you install pam_typtop"
)

parser.add_argument(
    "--allowtypo", type=str.lower, choices=['yes','no'],
    help='Allow login with typos of the password'
)

parser.add_argument(
    "--allowupload", type=str.lower, choices=['yes', 'no'],
    help="Allow uploading the non-sensive annonymous "\
    "data into the server for research purposes."
)

parser.add_argument(
    "--installid", action="store_true",
    help="Prints the installation id, which you have to submit while filling up the google form"
)

parser.add_argument(
    "--status", action="store", nargs="*",
    help='Prints current states of the typotolerance. Needs a username as argument.'
)

parser.add_argument(
    "--uninstall", action="store_true",
    help="Uninstall TypToP from your machine. Will delete all the data related to TypTop too."
)

parser.add_argument(
    "--reinit", action="store_true",
    help="To re-initiate the DB, especially after the user's pw has changed"
)

parser.add_argument(
    "--update", action="store_true",
    help="Updates TypTop to the latest released version"
)

parser.add_argument(
    "--check", action="store", nargs=3,
    help="(INTERNAL FUNCTION). Please don't call this."
)

args = parser.parse_args()
if len(sys.argv) <=1:
    print(parser.print_help())
    exit(0)

# ITS IMPORTENT THIS ONE WILL BE FIRST
if args.user:
    USER = args.user
    # print("User settings have been set to {}".format(USER))

SEND_LOGS = '/usr/local/bin/send_typo_log.py'

try:
    # root_only_operation()
    if args.allowtypo:
        typoDB = _get_typoDB()
        if args.allowtypo == "no":
            typoDB.allow_login(False)
            print(
                "Turning OFF login with typos. The software will still monitor\n"\
                "your typos and build cache of popular typos. You can switch on this\n"\
                "whenever you want")# :{}".format(typoDB.is_allowed_login())
        elif args.allowtypo == "yes":
            print("Turning ON login with typos...",)
            typoDB.allow_login(True)

    if args.allowupload:
        typoDB = _get_typoDB()
        if args.allowupload == "yes":
            typoDB.allow_upload(True)
            print("Uploading data is enabled. You are awesome. Thanks!!")
        elif args.allowupload == "no":
            typoDB.allow_upload(False)
            print("Uploading data is disabled.  :( :'( :-(!")
            print("Thanks for using the software anyway.")

    if args.init:
        print(first_msg(url=GITHUB_URL, version=VERSION), file=sys.stderr)
        print("Initializing the typo database..")
        initiate_typodb()

    if args.reinit:
        print("RE-initiating pam_typtop")
        initiate_typodb(RE_INIT=True)

    if args.status:
        users = args.status
        if not users:
            users.add(_get_username)
        for user in users:
            typoDB = UserTypoDB(user)
            print("\n** TYPO-TOLERANCE STATUS **\n")
            print(">> User: {}".format(user))
            print("\tLogin with typos: {}".format(typoDB.is_allowed_login()))
            print("\tParticipate in the study: {}"\
                  .format(typoDB.is_allowed_upload()))
            print("\tIs enough logins to allow typos: {}"\
                  .format(typoDB.check_login_count(update=False)))
            print("\tInstall Id: {}".format(typoDB.get_installation_id().strip()))
            print("\tSoftware Version: {}".format(VERSION))
            print("\tNum entries before typo-login allowed: {}".format(NUMBER_OF_ENTRIES_TO_ALLOW_TYPO_LOGIN))
            print("\tWarmup cache: {}".format(WARM_UP_CACHE))

    if args.uninstall:
        r = raw_input("Uninstalling pam_typtop. Will delete all the "\
                      "databases.\nPlease confirm. (yN)")
        if r and r.lower() == 'y':
            uninstall_pam_typtop()

    if args.update:
        subprocess.call(
            "pip install -U typtop && sudo typtop --init",
            shell=True
        )

    if args.check:
        # ensure the parent is pam_opendirectory_typo.so
        assert is_valid_parent()
        failed, user, pw =  args.check
        ret = call_check(failed, user, pw)
        sys.stdout.write(str(ret))
        if ret==0:
            p = subprocess.Popen('nohup /usr/local/bin/send_typo_log.py {}'.format(user).split())


except AbortSettings as abort:
    print("Settings' change had been aborted.")