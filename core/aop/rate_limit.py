from threading import BoundedSemaphore


checkout_semaphore = BoundedSemaphore(value=10)
