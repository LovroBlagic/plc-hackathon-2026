# -*- coding: utf-8 -*-
# Lists controller device types available in the Machine Expert device repository.
from __future__ import print_function
import sys
print("python", sys.version)
print("globals:", [g for g in ("projects","device_repository","system","librarymanager","online") if g in globals()])
devs = device_repository.get_all_devices()
print("device count:", len(devs))
for d in devs:
    n = d.device_info.name
    if any(k in n for k in ("TM241","TM251","TM262","M241","M251","M262","TM221","Logic Controller")):
        i = d.device_id
        print("%s | type=%s id=%s ver=%s" % (n, i.type, i.id, i.version))
