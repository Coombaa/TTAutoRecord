import threading

class SharedDataStore:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def set_value(self, key, value):
        with self.lock:
            self.data[key] = value

    def get_value(self, key):
        with self.lock:
            return self.data.get(key)

    def remove_value(self, key):
        with self.lock:
            if key in self.data:
                del self.data[key]

shared_stream_links_store = SharedDataStore()
