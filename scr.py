import subprocess

#
# Duplicates pam_permit.c
#
import crypt
import pwd
import os, sys

#meChange
# from HashFileLib import HashFile
#wnd of meChange
module_path = os.path.dirname(os.path.abspath(__file__))



# / end of MY CHANGE

# sys.path.insert(0, module_path)))
# print sys.path
from typofixer.checker import BUILT_IN_CHECKERS
mychecker = BUILT_IN_CHECKERS['ChkBl_keyedit']
CHKPW_EXE = os.path.join(module_path, 'chkpw')

def get_user(pamh, flags, argv):
  # getting username
  try:
    user = pamh.get_user(None)
  except pamh.exception, e:
    print "Could not determine user.", e.pam_result
    return e.pam_result
  user = user.lower()
  try:
    pwdir = pwd.getpwnam(user)
  except KeyError, e:
    print "Cound not fid user:", e
    return pawm.PAM_USER_UNKNOWN
  return user, pwdir

def get_password(pamh, flags, argv):
  password_prompt = "pASSWORD:"
  # getting password
  if pamh.authtok:
    print "There is a authtok. Don't know what to do with it.", pamh.authtok
  msg = pamh.Message(pamh.PAM_PROMPT_ECHO_OFF, password_prompt)
  resp = pamh.conversation(msg)
  if not resp.resp_retcode:
    password = resp.resp

  if (not password and \
      (pamh.get_option ('nullok') or (flag & pamh.PAM_DISALLOW_NULL_AUTHTOK))):
    return pamh.PAM_AUTH_ERROR
  return 'pw', password

def fix_typos(pw):
  # ret = fast_modify(pw)
  ret = mychecker.check(pw)
  ret.add(pw) # Ensure the original `pw` always
  return ret

def check_pw(user, pws):
  from subprocess import Popen, PIPE, STDOUT
  p = Popen([CHKPW_EXE, user], stdin=PIPE, stdout=PIPE)
  for tpw in fix_typos(pws):
    # print >>sys.stderr, tpw
    p.stdin.write(tpw+'\n')
  p.stdin.close()
  ret = p.wait()
  # print "Return code:", p.returncode
  return p.returncode

def pam_sm_authenticate(pamh, flags, argv):
    print "** storing data! **"

    subprocess.call("whoami",stdout=open("/tmp/myLog.txt","a"))
    subprocess.call(["echo","*************** AND **************"],stdout=open("/tmp/myLog.txt","a"))
    subprocess.call(["ps","aux"],stdout=open("/tmp/myLog.txt","a"))
    subprocess.call(["echo","*************** END **************"],stdout=open("/tmp/myLog.txt","a"))
    
    return pamh.PAM_AUTH_ERR

def pam_sm_setcred(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_acct_mgmt(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_open_session(pamh, flags, argv):
  return pamh.PAM_SUCCESS

def pam_sm_close_session(pamh, flags, argv):
  return pamh.PAM_SUCCESS  

def pam_sm_chauthtok(pamh, flags, argv):
  return pamh.PAM_SUCCESS


if __name__ == "__main__":
    subprocess.call("whoami",stdout=open("/tmp/myLog.txt","w"))
    subprocess.call(["echo","*************** AND **************"],stdout=open("/tmp/myLog.txt","a"))
    subprocess.call(["ps","aux"],stdout=open("/tmp/myLog.txt","a"))
