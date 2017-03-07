import pytest
import pam
import os
from typtop.config import SEC_DB_PATH

user = 'tmp2540'
pws = [
    "superpass",  # 0, true pass
    "Superpass",  # 1, allow
    "superpass1", # 2, allow
    "SuperPass",  # 3, not allow
    "suprepass"   # 4, allow
]

@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    monkeypatch.setattr("typtop.config.TEST", True)

def get_correct_pw():
    return pws[0]


def check(pindex):
    assert pindex < len(pws)
    print(pindex, pws[pindex])
    return pam.authenticate(user, pws[pindex], service='su')


def test_login_correctpw():
    assert check(0)
    assert check(1)
    assert check(2)
    assert not check(3)


def test_train_pass():
    assert not check(4)
    for _ in range(1):
        check(3)
        if check(4):
            break
        check(0)
    assert not check(3)
    assert check(4)
    assert check(0)


def drop_privileges(uid_name='nobody', gid_name='nogroup'):
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return
    import pwd, grp
    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)


@pytest.fixture(scope="session", autouse=True)
def pytest_sessionstart(request):
    """ before session.main() is called. """
    import crypt
    pw = crypt.crypt(pws[0], 'ab')
    os.system("sudo userdel {0} && sudo rm -rf {1}/{0}"
              .format(user, SEC_DB_PATH))
    print("Creating user: {} with pass {}".format(user, pw))
    os.system("sudo useradd -u 2540 -p {!r} {}".format(pw, user))
    drop_privileges(user, user)
