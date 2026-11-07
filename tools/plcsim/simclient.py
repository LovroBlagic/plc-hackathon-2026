"""simclient.py - tiny client for SimHost.exe (tools/plcsim). Usage as module or CLI:
    python tools/plcsim/simclient.py STATE
    python tools/plcsim/simclient.py R '"HMI_IF".State'
"""
import socket
import sys


class Sim:
    def __init__(self, port=50123):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=120)
        self.f = self.s.makefile("rw", encoding="utf-8", newline="\n")

    def cmd(self, line):
        self.f.write(line + "\n")
        self.f.flush()
        ans = self.f.readline().rstrip("\n")
        if not ans.startswith("OK"):
            raise RuntimeError("%s -> %s" % (line, ans))
        return ans[3:]

    def r(self, tag):
        return self.cmd("R " + tag)

    def ri(self, tag):
        return int(float(self.r(tag)))

    def rf(self, tag):
        return float(self.r(tag))

    def rb(self, tags):
        out = []
        for i in range(0, len(tags), 200):
            out += self.cmd("RB " + "|".join(tags[i:i + 200])).split("|")
        return out

    def w(self, tag, val):
        if isinstance(val, bool):
            val = 1 if val else 0
        return self.cmd("W %s %s" % (tag, val))

    def wb(self, pairs):
        items = ["%s=%s" % (k, (1 if v else 0) if isinstance(v, bool) else v) for k, v in pairs]
        for i in range(0, len(items), 100):
            self.cmd("WB " + "|".join(items[i:i + 100]))

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


if __name__ == "__main__":
    s = Sim()
    print(s.cmd(" ".join(sys.argv[1:])))
