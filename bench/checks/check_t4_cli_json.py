import json, subprocess, sys, unittest

class Check(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "calc.cli", *args], capture_output=True, text=True)

    def test_json_flag(self):
        r = self.run_cli("--json", "add", "2", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["result"], 5)

    def test_json_flag_after_positionals(self):
        r = self.run_cli("mul", "2", "4", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["result"], 8)

    def test_plain_still_works(self):
        r = self.run_cli("add", "2", "3")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "5.0")
