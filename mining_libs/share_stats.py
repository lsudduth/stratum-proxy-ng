import time
import datetime
import stratum.logger
import subprocess
import threading
log = stratum.logger.get_logger('proxy')
from stratum_control import ShareSubscription


class ShareStats(object):
    shares = {}

    def __init__(self):
        self.accepted_jobs = 0
        self.rejected_jobs = 0
        self.lock = threading.Lock()
        self.last_job_time = datetime.datetime.now()
        self.shares = {}

    def get_last_job_secs(self):
        return int(
            (datetime.datetime.now() -
             self.last_job_time).total_seconds())

    def set_module(self, module):
        try:
            mod_fd = open("%s" % (module), 'r')
            mod_str = mod_fd.read()
            mod_fd.close()
            exec(mod_str)
            self.on_share = on_share
            log.info('Loaded sharenotify module %s' % module)

        except IOError:
            log.error('Cannot load sharenotify snippet')

            def do_nothing(job_id, worker_name, init_time, dif):
                pass
            self.on_share = do_nothing

    def register_job(self, job_id, worker_name, dif, accepted, sharenotify):
        ShareSubscription.emit(job_id, worker_name, dif, accepted)
        log.info("registering job: job_id = %s, worker_name = %s, dif = %s, accepted = %s" % (job_id, worker_name, dif, accepted))
        if self.accepted_jobs + self.rejected_jobs >= 65535:
            self.accepted_jobs = 0
            self.rejected_jobs = 0
            log.info("[Share stats] Reseting statistics")
        self.last_job_time = datetime.datetime.now()
        if accepted:
            self.accepted_jobs += 1
        else:
            self.rejected_jobs += 1

        if not (worker_name in self.shares):
            self.shares[worker_name] = [0, 0]
        if accepted:
            if self.shares[worker_name][0] > 10 ** 16:
                self.shares[worker_name][0] = 0
            self.shares[worker_name][0] += dif
        else:
            if self.shares[worker_name][1] > 10 ** 16:
                self.shares[worker_name][1] = 0
            self.shares[worker_name][1] += dif

        if sharenotify:
            self._execute_snippet(job_id, worker_name, dif, accepted)

    def _execute_snippet(self, job_id, worker_name, dif, accepted):
        log.info("Current active threads: %s" % threading.active_count())
        if threading.active_count() > 10:
            try:
                log.error("Deadlock detected, trying to release it")
                self.lock.release()
            except Exception as e:
                log.error("%s" % e)
        init_time = time.time()
        t = threading.Thread(
            target=self.on_share,
            args=[
                self,
                job_id,
                worker_name,
                init_time,
                dif,
                accepted])
        t.daemon = True
        t.start()
