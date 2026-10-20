"""One in-flight detection; the caller never waits or queues old frames."""
from concurrent.futures import ThreadPoolExecutor


class LatestDetection:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='monster-scan')
        self.future = None

    def poll(self):
        if self.future is None or not self.future.done():
            return None
        future, self.future = self.future, None
        return future.result()

    def submit(self, function, *args):
        if self.future is not None:
            return False
        self.future = self.executor.submit(function, *args)
        return True

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
