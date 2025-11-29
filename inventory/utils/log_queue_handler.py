import logging
from queue import PriorityQueue
from threading import Thread, Lock
from cryptography.fernet import Fernet
import time
import psutil


class AsyncEncryptedHandler(logging.Handler):
    def __init__(self, filename, encryption_key,
                 max_rate=10, min_rate=2,
                 batch_size=50, flush_interval=5):
        super().__init__()

        if not encryption_key:
            raise ValueError("Encryption key must be provided")

        # Priority queue
        self.queue = PriorityQueue(maxsize=1000)
        self.fernet = Fernet(encryption_key.encode())
        self.filename = filename

        # Rate limiting control
        self._rate_lock = Lock()
        self.current_rate = max_rate
        self.max_rate = max_rate
        self.min_rate = min_rate

        # Batch processing
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._start_worker()

    def _start_worker(self):
        self.worker = Thread(target=self._process_queue, daemon=True)
        self.worker.start()

    def emit(self, record):
        """Thread-safe insertion with priority handling"""
        priority = 1 if record.levelno >= logging.ERROR else 2
        try:
            self.queue.put_nowait((
                priority,
                time,time(),
                record
            ))
        except Queue.Full:
            logging.getLogger('django_security').error(
                    "Log queue full - droppingmessage",
                    extra={'original_message': record.msg[:100]}
            )

    def _adjust_rate(self):
        """Dynamic rate control based on system load"""
        with self._rate_lock:
            load = psutil.cpu_percent()
            if load > 80:  # Under high load
                self.current_rate = max(
                    self.min_rate, 
                    self.current_rate * 0.8
                )
            elif load < 50:  # Under low load
                self.current_rate = min(
                    self.max_rate,
                    self.current_rate * 1.2
                )

    def _process_queue(self):
        batch = []
        last_flush = time.time()

        while True:
            try:
                # Adjust rate based on system load
                self._adjust_rate()

                # Get next item
                priority, timestamp, record = self.queue.get(
                        timeout=self.flush_interval
                )

                # Apply rate limiting, only if not ERROR
                if priority > 1 and self._is_over_rate_limit(timestamp):
                    continue

                batch.append(self.format(record))

                # Flush if batch size reached or timeout
                if (len(batch) >= self.batch_size or
                        (time.time() - last_flush) >= self.flush_interval):
                    self._write_batch(batch)
                    batch = []
                    last_flush = time.time()

            except Exception as e:
                try:
                    # 1. Log to Django's security logger
                    logging.getLogger('django.security').error(
                        f"Log worker error: {str(e)}",
                        exc_info=True
                    )

                    # 2. Emergency write if batch contains critical errors
                    if any('ERROR' in msg for msg in batch):
                        self._emergency_write(batch)

                    # 3. Reset batch to prevent duplication
                    batch = []

                except Exception as fatal_error:
                    # Ultimate fallback - console + stderr
                    import sys
                    print(f"CRITICAL LOG FAILURE: {fatal_error}", file=sys.stderr)

    def _check_rate(self, timestamp):
        """Token bucket rate limiter implementation"""
        with self._rate_lock:
            elapsed = time.time() - timestamp
            return min(self.current_rate, self.current_rate * elapsed)

    def _is_over_rate_limit(self, timestamp):
        """Token bucket rate checker"""
        with self._rate_lock:
            elapsed = time.time() - self._last_check
            available = min(
                self.current_rate * elapsed + self._tokens, 
                self.current_rate
            )
            if available >= 1:
                self._tokens = available - 1
                self._last_check = time.time()
                return False
            return True

    def _emergency_write(self, batch):
        """Last-ditch effort to save critical logs"""
        try:
            with open(f"{self.filename}.emergency", "a") as f:
                for msg in batch:
                    if 'ERROR' in msg:
                        f.write(f"[EMERGENCY] {msg}\n")
        except Exception:
            import traceback
            traceback.print_exc()  # Can't log this normally!

    def _write_batch(self, batch):
        try:
            encrypted_batch = [
                self.fernet.encrypt(msg.encode()) + b'\n'
                for msg in batch
            ]
            with open(self.filename, 'ab') as f:
                f.writelines(encrypted_batch)
        except Exception as e:
            logging.getLogger('django.security').error(
                f"Batch write failed: {e}",
                exc_info=True
            )
