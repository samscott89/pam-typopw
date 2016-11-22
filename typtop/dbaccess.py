
import os
import re
import time
import json
import yaml
import pwd
import random
import dataset
from zxcvbn import password_strength
from typtop.pw_pkcrypto2 import (
    encrypt, decrypt, generate_key_pair, compute_id,
    pkencrypt, pkdecrypt, pwencrypt, pwdecrypt,
    serialize_pk, deserialize_pk, serialize_sk, deserialize_sk,
    verify_pk_sk, SALT_LENGTH
)
from collections import defaultdict
from base64 import urlsafe_b64encode, urlsafe_b64decode
from word2keypress import distance
from config import *
from operator import itemgetter
from dbutils import find_one, logger, setup_logger

# GENERAL TODO:
# - improve computation speed
#   - joint hashes/salt computations
#   - more efficent SQL actions

def is_in_top5_fixes(orig_pw, typo):
    return orig_pw in (
        typo.capitalize(), typo.swapcase(), typo.lower(),
        typo.upper(), typo[1:], typo[:-1]
    )

def get_logging_path(username):
    homedir = pwd.getpwnam(username).pw_dir
    return "{}/{}.log".format(homedir, DB_NAME)

def get_time():
    """
    Returns the timestamp in a string, in a consistent format
    which works in linux and can be stored in the DB
    (unlike datetime.datetime, for example)
    """
    return str(time.time())

_entropy_cache = {}
def entropy(typo):
    global _entropy_cache
    if typo not in _entropy_cache:
        _entropy_cache[typo] = password_strength(typo)['entropy']
    return _entropy_cache[typo]

class UserTypoDB(object):
    class TypoDBError(Exception):
        # all errors that have to do with the typoDB state
        pass
    class NoneInitiatedDB(TypoDBError):
        pass
    class CorruptedDB(TypoDBError):
        pass

    def __str__(self):
        return "UserTypoDB ({})".format(self._user)

    def __init__(self, user, debug_mode=False): # TODO CHANGE to False
        self._user = user  # this is a real user.
        # homedir = pwd.getpwnam(self._user).pw_dir
        typo_dir = os.path.join(SEC_DB_PATH, user)
        if not os.path.exists(typo_dir): # creating dir only if it doesn't exist
            # this directory needs root permission, and should be created as
            # part of the installation process
            try:
                os.makedirs(typo_dir)
            except OSError as error:
                logger.error("Trying to create: {}, but seems like the database "
                      "is not initialized.".format(typo_dir))
                raise UserTypoDB.NoneInitiatedDB(error)

        self._db_path = os.path.join(typo_dir, DB_NAME + '.db')
        self._log_path = os.path.join(LOG_DIR, DB_NAME + '.log')
        self._db = dataset.connect('sqlite:///{}'.format(self._db_path))
        self._aux_tab = self._db.get_table(
            auxT,
            primary_id='desc',
            primary_type='String(100)'
        )

        # always contains the serialized versino of sk, pk
        self._sk, self._pk = None, None
        # the global salt for the hmac-id only will be available if
        # correct pw is provided.
        self._hmac_salt, self._pw, self._pwent = None, None, None
        self._aux_tab_cache = {}  # For caching results from auxtab
        # setting the logger object
        setup_logger(self._log_path, debug_mode, user)
        isON = self.get_from_auxtdb(ALLOWED_TYPO_LOGIN, bool)
        logger.info("typoToler is ON? {}".format(isON))

    def init_typotoler(self, pw, allow_typo_login=False):
        """Create the 'typotoler' database in user's home-directory.  Changes
        the DB permission to ensure its only readable by the user.
        Also, it intializes the required tables as well as the reuired
        variables, such as, the typocache size, the global salt etc.

        """
        logger.info("Initiating typoToler db with {}".format(
            dict(pw=pw, allow_typo_login=allow_typo_login)
        ))
        u_data = pwd.getpwnam(self._user)
        u_id, g_id = u_data.pw_uid, u_data.pw_gid
        db_path = self._db_path
        log_path = self._log_path
        os.chown(log_path, u_id, g_id)  # change owner to user
        os.chmod(log_path, 0600)  # RW only for owner

        db = self._db
        db[auxT].delete()         # make sure there's no old unrelevent data
        # doesn't delete log because it will also be used
        # whenever a password is changed

        # *************** Initializing Aux Data *************************
        self._aux_tab = self._db.get_table(
            auxT, primary_id='desc', primary_type='String(100)'
        )
        self._aux_tab_cache = {}

        # *************** add org password, its' pks && global salt: ********
        # 1. derive public_key from the original password
        # 2. encrypt the global salt with the enc pk
        install_id = urlsafe_b64encode(os.urandom(8))
        install_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        last_sent_time = get_time()
        self._hmac_salt = os.urandom(SALT_LENGTH) # global salt
        self._pk, self._sk = generate_key_pair()  # ECC key pair
        self._sk = serialize_sk(self._sk)
        self._pw = pw
        pwid = compute_id(self._hmac_salt, pw) # Do we need it?
        perm_index = self._fill_cache_w_garbage()
        if WARM_UP_CACHE:
            freq_counts = range(CACHE_SIZE, 0, -1)
            for i, f in enumerate(range(CACHE_SIZE)):
                freq_counts[perm_index[i]] = freq_counts[i]
        else:
            freq_counts = [0 for _ in xrange(WAITLIST_SIZE)]
        header_ctx = pkencrypt(self._pk, json.dumps({
            REAL_PW: self._pw,
            HMAC_SALT: urlsafe_b64encode(self._hmac_salt),
            FREQ_COUNTS: freq_counts
        }))

        logger.info("Initializing the auxiliary data base ({})".format(auxT))
        db[auxT].insert_many([
            dict(desc=INSTALLATION_ID, data=install_id),
            dict(desc=INSTALLATION_DATE, data=install_time),
            dict(desc=LOG_LAST_SENTTIME, data=str(last_sent_time)),
            dict(desc=LOG_SENT_PERIOD, data=str(UPDATE_GAPS)),
            dict(desc=SYSTEM_STATUS, data=SYSTEM_STATUS_NOT_INITIALIZED),
            dict(desc=LOGIN_COUNT, data=str(0)),
            dict(desc=ALLOWED_TYPO_LOGIN, data=str(allow_typo_login)),
            dict(desc=ALLOWED_LOGGING, data='True'),

            dict(desc=ENC_PK, data=serialize_pk(self._pk)),
            dict(desc=INDEX_J, data=str(random.randint(0, WAITLIST_SIZE-1))),

            dict(desc=HEADER_CTX, data=str(header_ctx))
        ])
        self._aux_tab.create_index(['desc'])
        self._aux_tab_cache = {}
        self.set_status(SYSTEM_STATUS_ALL_GOOD)
        # 3. Filling the Typocache with garbage
        self._fill_waitlist_w_garbage()
        logger.debug("Initialization Complete")

    def is_typotoler_init(self):
        """
        Returns whether the typotoler has been set (might be installed
        but not active)
        """
        if not os.path.exists(self._db_path):
            return False
        if self.get_from_auxtdb(HEADER_CTX):
            return True
        else:
            return False

    def getdb(self):
        return self._db

    def get_db_path(self):
        return self._db_path

    def _hmac_id(self, typo):
        """
        Calculates the typo_id required for logging.
        @typo (string) : the typo
        @sk_dict (dict) : is a dictionar from t_h_id -> ECC secret_key,
        """
        assert self._hmac_salt
        return compute_id(self._hmac_salt, bytes(typo))

    def assert_initialized(self):
        if not self.is_typotoler_init():
            raise UserTypoDB.NoneInitiatedDB(
                "is_allowed_login: Typotoler DB wasn't initiated yet!"
            )

    def is_allowed_login(self):
        self.assert_initialized()
        is_on = self.get_from_auxtdb(ALLOWED_TYPO_LOGIN, bool)
        assert is_on in (True, False), \
            'Corrupted data in {}: {}={} ({})'.format(
                auxT, ALLOWED_TYPO_LOGIN, is_on, type(is_on)
            )
        return is_on

    def allow_login(self, allow=True):
        self.assert_initialized()
        assert allow in (True, False, 0, 1), "Expects a boolean"
        allow = True if allow else False
        self.set_in_auxtdb(ALLOWED_TYPO_LOGIN, allow)
        state = "ON" if allow else "OFF"
        logger.info("typoToler set to {}".format(state))

    def _fill_waitlist_w_garbage(self):
        waitlist = [
            pkencrypt(self._pk, os.urandom(16)) for _ in xrange(WAITLIST_SIZE)
        ]
        self.set_in_auxtdb(WAIT_LIST, waitlist)
        self._db.commit()

    def _fill_cache_w_garbage(self):
        logger.debug("Filling Typocache with garbage")
        perm_index = range(CACHE_SIZE)
        random.shuffle(perm_index)
        pw = self._pw
        popular_typos = [os.urandom(16) for _ in xrange(CACHE_SIZE)]
        if WARM_UP_CACHE:
            i = 0
            for tpw in [
                pw.swapcase(), pw[0].swapcase()+pw[1:],
                pw + '1', pw + '`', '1' + pw,
                pw[:-1] + pw[-1] + pw[-1]
            ]:
                if i>=CACHE_SIZE: break
                if (pw != tpw and tpw in popular_typos):
                    popular_typos[perm_index[i]] = tpw
                    i += 1
        popular_typos = [pw] + popular_typos
        garbage_list = [
            pwencrypt(tpw, self._sk) for tpw in popular_typos
        ]
        self.set_in_auxtdb(TYPO_CACHE, garbage_list)
        return perm_index

    def update_after_pw_change(self, newPw):
        """
        Re-initiate the DB after a pw change.
        Most peripherial system settings don't change, including installID
        generates a new hmac salt,
        and encrypts the new pw, pw_ent, and the hmac salt
        """
        # Mostly a simple copy-paste of steps 1 to 2.5
        logger.info("Re-intializing after a pw change")
        # 1. derive public_key from the original password
        # 2. encrypt the global salt with the enc pk
        self._hmac_salt = os.urandom(16) # global salt
        pk, sk = generate_key_pair()  # ECC key pair
        self._pk, self._sk = pk, serialize_sk(sk)
        self._pw = newPw
        perm_index = self._fill_cache_w_garbage()
        if WARM_UP_CACHE:
            freq_counts = range(CACHE_SIZE, 0, -1)
            for i, f in enumerate(range(CACHE_SIZE)):
                freq_counts[perm_index[i]] = freq_counts[i]
        else:
            freq_counts = [0 for _ in xrange(WAITLIST_SIZE)]
        header_ctx = pkencrypt(self._pk, json.dumps({
            REAL_PW: self._pw,
            HMAC_SALT: urlsafe_b64encode(self._hmac_salt),
            FREQ_COUNTS: freq_counts
        }))
        self.set_in_auxtdb(HEADER_CTX, header_ctx)

        # 3 sending logs and deleting tables:
        logger.debug('Sending logs')
        self.update_last_log_sent_time(get_time(), True)

        logger.debug("Deleting tables")
        db[logT].delete()
        db.commit()
        # Filling the Typocache with garbage
        self._fill_waitlist_w_garbage()
        self.set_status(SYSTEM_STATUS_ALL_GOOD)
        logger.info("RE-Initialization Complete")

    def get_installation_id(self):
        self.assert_initialized()
        return self.get_from_auxtdb(InstallationID)

    def get_last_unsent_logs_iter(self):
        """
        Check what was the last time the log has been sent,
        And returns whether the log should be sent
        """
        logger.debug("Getting last unsent logs")
        if not self.is_typotoler_init():
            logger.debug("Could not send. Typotoler not initiated")
            return False, iter([])
        upload_status = self.get_from_auxtdb(AllowUpload)
        if not upload_status:
            raise UserTypoDB.CorruptedDB(
                "Missing {} in {}".format(AllowUpload, auxT)
            )
        if upload_status != 'True':
            logger.info("Not sending logs because send status set to {}".format(
                upload_status))
            return False, iter([])
        last_sending = self.get_from_auxtdb(LastSent, float)
        update_gap = self.get_from_auxtdb(SendEvery, float)
        time_now = time.time()
        passed_enough_time = ((time_now - last_sending) >= update_gap)
        if not passed_enough_time:
            logger.debug("Last sent time:{}".format(str(last_sending)))
            logger.debug("Not enought time has passed to send new logs")
            return False, iter([])
        log_t = self._db[logT]
        new_logs = log_t.find(log_t.table.columns.ts >= last_sending)
        logger.info("Prepared new logs to be sent, from {} to {}".format(
            str(last_sending), str(time_now))
        )
        return True, new_logs

    def update_last_log_sent_time(self, sent_time=0, delete_old_logs=False):
        logger.debug("updating log sent time")
        if not sent_time:
            sent_time = get_time()
            logger.debug("generating new timestamp={} ".format(sent_time))
        self._db[auxT].update(dict(
            desc=LastSent, data=float(sent_time)), ['desc']
        )
        if delete_old_logs:
            logger.debug("deleting old logs")
            log_t = self._db[logT]
            log_t.table.delete().where(
                log_t.table.columns.ts <= float(sent_time)
            ).execute()

    def allow_upload(self, allow):
        if allow in (0, 1):
            allow = bool(allow)
        assert isinstance(allow, bool)
        self.set_in_auxtdb(desc=ALLOWED_LOGGING, data=allow)

    def is_allowed_upload(self):
        send_stat_row = self.get_from_auxtdb(ALLOWED_LOGGING, bool)
        return send_stat_row

    def update_log(self, typo, incache, ts=None):
        """Updates the log with information about typo. Remember, if sk_dict is
        not provided it will insert @typo as typo_id and 0 as relative_entropy.
        Note the default values used in other_info, which is basically what
        is expected for the original password.
        """
        assert self._pw and self._hmac_salt
        # Only log columns:
        log_columns = {'tid', 'edit_dist', 'rel_entropy', 'ts',
                       'istop5fixable', 'in_cache'}
        log_info = {
            'tid': compute_id(self._hmac_salt, typo),
            'edit_dist': distance(str(self._pw), str(typo)),
            'rel_entropy': self._pwent - entropy(typo),
            'ts': ts if ts else get_time(),
            'istop5fixable': is_in_top5_fixes(self._pw, typo),
            'in_cache': incache
        }
        self._db[logT].insert(log_info)

    def log_message(self, msg):
        ts = get_time()
        self._db[logT].insert(dict(t_id=msg, timestamp=ts))

    def _add_typo_to_waitlist(self, typo):
        """Adds the typo to the waitlist.
        @typo (string) : typo of the user's passwrod
        """
        logger.debug("Adding a new typo to waitlist")
        waitlist = self.get_from_auxtdb(WAIT_LIST, yaml.load)
        indexj = int(self.get_from_auxtdb(INDEX_J, int))
        ts = get_time()
        assert indexj < len(waitlist), "Indexj={}, waitlist={}".format(indexj, waitlist)
        waitlist[indexj] = pkencrypt(self.get_pk(), json.dumps([typo, ts]))
        indexj = (indexj + 1) % WAITLIST_SIZE
        self.set_in_auxtdb(WAIT_LIST, waitlist)
        self.set_in_auxtdb(INDEX_J, indexj)
        logger.debug("Typo encrpted.")

    def _decrypt_filter_waitlist(self):
        '''
        Returns a list of the typos in waitlist, unsorted,
        Key = typo (string)
        Value = (typo, t_count, ts_list, typo_hs, t_pk, t_pk_salt)
        '''
        filtered_typos = defaultdict(int)
        sk = deserialize_sk(self._sk)
        assert self._pwent, "PW is not initialized: {}".format(self._pwent)
        ignore = set()
        for typo_ctx in self.get_from_auxtdb(WAIT_LIST, yaml.load):
            typo_txt = pkdecrypt(sk, typo_ctx)
            if re.match(r'\[".*", ".*"\]', typo_txt):
                typo, ts = yaml.safe_load(typo_txt)
            else:
                print("Did not match: {!r}".format(typo_txt))
                continue
            self.update_log(typo, incache=False, ts=ts)
            if typo in ignore: continue
            if self.validate(self._pw, typo):
                filtered_typos[typo] += 1
            else:
                print("Ignoring: {}".format(typo))
                ignore.add(typo)
        logger.info("Waitlist decrypted successfully")
        return sorted(
            filtered_typos.items(), key=lambda a: a[1], reverse=True
        )

    def get_table_size(self, tableName):
        return self._db[tableName].count()

    def get_typo_cache_size(self):
        return CACHE_SIZE

    def get_pk(self):
        """Returns the public key"""
        if not self._pk:
            self._pk = deserialize_pk(self.get_from_auxtdb(ENC_PK))
        return self._pk

    def get_hmac_salt(self, sk):
        """
        Returns the global salt ctx used for computing ID for each typo
        """
        assert False
        if not self._hmac_salt:
            try:
                salt_ctx = self.get_from_auxtdb(HMAC_SALT_CTX)
                self._hmac_salt = pkdecrypt(sk,  salt_ctx)
            except ValueError as e:
                logging.debug(
                    "Sorry wrong id-sk pair ({}). Couldn't decrypt the salt"\
                    .format(sk)
                )
        return self._hmac_salt

    # TODO: More policies
    @staticmethod
    def cache_insert_policy(old_t_c, new_t_c):
        if old_t_c < 0: # for garbage rows in cache
            return True
        d = old_t_c + new_t_c
        assert d>0
        rnd = random.randint(0, d-1)
        return rnd <= new_t_c

    def clear_waitlist(self):
        self._fill_waitlist_w_garbage()
        logger.info("Waitlist is deleted.")

    def check_login_count(self, update=False):
        """Keeps track of how many times the user has successfully logged in."""
        count_entry = self.get_from_auxtdb(LOGIN_COUNT, int) + 1
        if update:
            self.set_in_auxtdb(LOGIN_COUNT, count_entry)
        return count_entry > NUMBER_OF_ENTRIES_BEFORE_TYPOTOLER_CAN_BE_USED

    def check(self, pw):
        logger.info("Original password had been entered by user")
        pk = self.get_pk()   # cannot be tampered
        typo_cache = self.get_from_auxtdb(TYPO_CACHE, yaml.load)
        match_found = False
        freq_counts = []
        for i, sk_ctx in enumerate(typo_cache):
            try:
                sk = pwdecrypt(pw, sk_ctx)
                if not verify_pk_sk(pk, sk):  #  Somehow the hash matched !!
                    continue
                self._sk = sk
            except (TypeError, ValueError) as e: # Decryption Failed
                # print("Failed for {}.{} ({})".format(pw, i, e))
                # that means password did not match.
                continue
            header = yaml.safe_load(pkdecrypt(sk, self.get_from_auxtdb(HEADER_CTX)))
            self._hmac_salt = header[HMAC_SALT]
            freq_counts = header[FREQ_COUNTS]
            if i>0: freq_counts[i-1] += 1
            self._pw = header[REAL_PW]
            self._pwent = entropy(self._pw)
            self.update_log(pw, incache=True, ts=get_time())
            match_found = True
            break
        if match_found:
            assert self._pwent, "PW is not initialized: {}".format(self._pwent)
            self._update_typo_cache_by_waitlist(typo_cache, freq_counts)
            return (
                self.check_login_count(update=False) and self.is_allowed_login()
            )
        else:
            self._add_typo_to_waitlist(pw)
            return False

    def get_from_auxtdb(self, key, apply_type=str):
        if key not in self._aux_tab_cache:
            self._aux_tab_cache[key] = find_one(self._aux_tab, key, apply_type)
        if key == INDEX_J:
            assert isinstance(self._aux_tab_cache[key], int)
        return self._aux_tab_cache[key]

    def set_in_auxtdb(self, key, value):
        if key == INDEX_J:
            assert isinstance(value, int)
        self._aux_tab_cache[key] = value
        val_str = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
        self._db[auxT].upsert(
            dict(desc=key, data=val_str),
            ['desc']
        )

    def validate(self, orig_pw, typo):
        editDist = distance(str(orig_pw), str(typo))
        typo_ent = entropy(typo)
        # rel_bound = self.get_from_auxtdb(REL_ENT_CUTOFF, int)
        # strict_bound = self.get_from_auxtdb(LOWER_ENT_CUTOFF, int)
        # edist_bound = self.get_from_auxtdb(EDIT_DIST_CUTOFF, int)

        notMuchWeaker = (typo_ent >= self._pwent - REL_ENT_CUTOFF)
        notTooWeak = (typo_ent >= LOWER_ENT_CUTOFF)
        closeEdit = (editDist <= EDIT_DIST_CUTOFF)
        return (notTooWeak and notMuchWeaker and closeEdit)

    def _update_typo_cache_by_waitlist(self, typo_cache, freq_counts):
        """
        Updates the hash cache according to waitlist.
        It also updates the log accordingly (if updateLog is set)
        and clears waitlist
        sk: the secrete key found in previous function
        orig_pw: retrieved original password,
        """
        logger.info("Updating TypoCache by Waitlist")
        good_typo_list = self._decrypt_filter_waitlist()
        mini, minf = min(enumerate(freq_counts), key=itemgetter(1))
        print(good_typo_list)
        for typo, f in good_typo_list:
            if UserTypoDB.cache_insert_policy(minf, f):
                print("Inserting: {} @ {}".format(typo, mini))
                typo_cache[mini] = pwencrypt(typo, self._sk)
                freq_counts[mini] = max(minf + 1, f) # TODO: Check
                mini, minf = min(enumerate(freq_counts), key=itemgetter(1))
            else:
                print("I miss you: {} ({} <-> {})".format(typo, minf, f))
        # write the new typo_cache and freq_list
        # TODO: Apply permutation
        header_ctx = pkencrypt(self._pk, json.dumps({
            REAL_PW: self._pw,
            HMAC_SALT: self._hmac_salt,
            FREQ_COUNTS: freq_counts
        }))
        self.set_in_auxtdb(HEADER_CTX, header_ctx)
        self.set_in_auxtdb(TYPO_CACHE, typo_cache)
        self.clear_waitlist()

    def get_prompt(self):
        # Password promts
        return {
            SYSTEM_STATUS_ALL_GOOD: 'aDAPTIVE pASSWORD',
            SYSTEM_STATUS_NOT_INITIALIZED: 'Please Initialized',
            SYSTEM_STATUS_PW_CHANGED: 'Please Re-initialize',
            SYSTEM_STATUS_CORRUPTED_DB: 'Corrupted DB!'
        }.get(self.get_from_auxtdb(SYSTEM_STATUS), 'Error! Password')

    def set_status(self, status):
        self.set_in_auxtdb(key=SYSTEM_STATUS, value=status)

def check_system_status(typo_db):
    sysStatVal = typo_db.get_from_auxtdb(SYSTEM_STATUS)
    # if reached here - db should be initiated updating the entry count
    if not sysStatVal: # if not found in table
        raise UserTypoDB.CorruptedDB(
            "ERROR: (on_correct_password) Typotoler DB is Corrupted."
        )
    if sysStatVal == SYSTEM_STATUS_PW_CHANGED:  # pasword_changed
        raise ValueError(SYSTEM_STATUS_PW_CHANGED)
    if sysStatVal == SYSTEM_STATUS_CORRUPTED_DB:  # corrupted_db
        raise ValueError(SYSTEM_STATUS_CORRUPTED_DB)


def on_correct_password(typo_db, password):
    logger.info("sm_auth: it's the right password")
    # log the entry of the original pwd
    try:
        if not typo_db.is_typotoler_init():
            logger.error("ERROR: (on_correct_pass) Typotoler DB wasn't initiated yet!")
            typo_db.init_typotoler(password)
            # the initialization is now part of the installation process
        check_system_status(typo_db)
        if not typo_db.check(password):  # correct password but db fails to see it
            typo_db.set_status(SYSTEM_STATUS_PW_CHANGED)
        return True
    except (ValueError, KeyError) as e:
        # most probably - an error of decryption as a result of pw change
        typo_db.set_status(SYSTEM_STATUS_PW_CHANGED)
        logger.error("Key error raised. Probably a failure in decryption.")
        logger.exception("Exception in on_correct_password:")
    except Exception as e:
        logger.exception(
            "Unexpected error while on_correct_password:\n{}\n"\
            .format(e)
        )
    # In order to avoid locking out - always return true for correct password
    return True

def on_wrong_password(typo_db, password):
    try:
        check_system_status(typo_db)
        return typo_db.check(password)
    except (ValueError, KeyError) as e:
        # probably  failure in decryption
        logger.exception("ValueError: {}".format(e))
    except Exception as e:
        logger.exception("Unexpected error while on_wrong_password:\n{}\n"\
              .format(e))
        print("TypToP is not initialized.\n $ sudo typtop --init")
    return False # previously inside "finally"


if __name__ == "__main__":
    import getpass
    usage = '{} <1 or 0> <username> <password'.format(sys.argv[0])
    if len(sys.argv)==3: # 0/1 username, password
        typo_db = UserTypoDB(sys.argv[2])
        if sys.argv[1] == '1':
            on_correct_password(typo_db, sys.argv[2])
        elif sys.argv[1] == '0':
            on_wrong_password(typo_db, sys.argv[2])
        else:
            print(usage)
    else:
        print(usage)
