import json, os, subprocess, sys, tempfile, unittest

class Check(unittest.TestCase):
    def test_history_class(self):
        from calc.history import History
        h = History()
        h.append("add", 2, 3, 5)
        h.append("mul", 2, 4, 8)
        self.assertEqual(len(h.to_list()), 2)
        self.assertEqual(h.to_list()[0]["op"], "add")
        self.assertEqual(h.to_list()[0]["result"], 5)
        h.undo()
        self.assertEqual(len(h.to_list()), 1)

    def test_save_load_roundtrip(self):
        from calc.history import History
        h = History()
        h.append("sub", 5, 3, 2)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.json")
            h.save(p)
            h2 = History.load(p)
            self.assertEqual(h2.to_list(), h.to_list())

    def test_cli_history_flag(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "h.json")
            for args in (["add", "1", "2"], ["mul", "3", "4"]):
                r = subprocess.run([sys.executable, "-m", "calc.cli", "--history", p, *args], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
            data = json.load(open(p))
            self.assertEqual(len(data), 2)
            self.assertEqual(data[1]["op"], "mul")
            self.assertEqual(data[1]["result"], 12)
