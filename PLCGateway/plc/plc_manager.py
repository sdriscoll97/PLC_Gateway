from __future__ import annotations
import re, threading
from .pylogix_wrapper import PylogixWrapper

class PLCManager:
    def __init__(self, config, wrapper_factory=PylogixWrapper):
        self.config = config
        self._wrappers = {name: wrapper_factory(defn, timeout=config.request_timeout_s)
                          for name, defn in config.plcs.items()}
        self._gates = {name: threading.BoundedSemaphore(config.max_concurrent_per_plc)
                       for name in config.plcs}

    def definition(self, name): return self.config.plc(name)
    def names(self): return sorted(self._wrappers)

    def wrapper(self, name):
        self.definition(name)
        return self._wrappers[name]

    def allowed_write(self, name, tag):
        patterns = self.definition(name).writable_tag_patterns
        return bool(patterns) and any(re.fullmatch(pattern, tag) for pattern in patterns)

    def read(self, name, tags):
        if len(tags) > self.config.max_batch_tags:
            raise ValueError(f"Batch exceeds {self.config.max_batch_tags} tags")
        with self._gates[name]: return self.wrapper(name).read(tags)

    def write(self, name, tag, value):
        with self._gates[name]: return self.wrapper(name).write(tag, value)

    def tag_list(self, name):
        with self._gates[name]: return self.wrapper(name).tag_list()

    def diagnostics(self, name):
        with self._gates[name]: return self.wrapper(name).diagnostics()

    def close(self):
        for wrapper in self._wrappers.values(): wrapper.close()
