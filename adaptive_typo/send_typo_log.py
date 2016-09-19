from adaptive.typo_db_access import UserTypoDB,LastSent
import time
import dataset
import urllib2


user =  pwd.getpwuid(os.getuid()).pw_name
t_db = UserTypoDB(user)
t_db.update_last_log_sent_time(0)
need_to_send,iter_data = t_db.get_last_unsent_logs_iter(self)
last_time = 0
list_of_logs = []
if need_to_send:
    for row in iter_data:
        list_of_logs.append(row)
        last_time = min(last_time,row['timestamp'])
        print row
    t_db.update_last_log_sent_time(last_time)

else:
    print "nothing to send"

