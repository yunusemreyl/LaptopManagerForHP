import os
import json
import urllib.request
import threading
import subprocess
import tarfile
import shutil
import tempfile
import re
from gi.repository import GLib

GITHUB_API_URL = "https://api.github.com/repos/yunusemreyl/OmenCtl/releases/latest"
GITHUB_RELEASES_URL = "https://github.com/yunusemreyl/OmenCtl/releases/latest"

class OmenUpdater:
    def __init__(self, current_version, T):
        """
        :param current_version: string, e.g. "1.6.6"
        :param T: translation function for UI strings
        """
        self.current_version = current_version
        self.T = T
        self._latest_tarball_url = None

    @staticmethod
    def version_compare(v1, v2):
        def parse(v):
            v = str(v).strip()
            m = re.match(r'^([\d.]+)', v)
            if not m:
                return [0]
            return [int(x) for x in m.group(1).split('.') if x]
        
        n1 = parse(v1)
        n2 = parse(v2)
        maxlen = max(len(n1), len(n2))
        n1.extend([0] * (maxlen - len(n1)))
        n2.extend([0] * (maxlen - len(n2)))
        
        for a, b in zip(n1, n2):
            if a > b: return 1
            if a < b: return -1
        return 0

    def check_update_async(self, on_result, on_error):
        """
        on_result(has_update: bool, latest_ver: str)
        on_error(error_msg: str)
        """
        def _worker():
            try:
                req = urllib.request.Request(GITHUB_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    latest = data.get("tag_name", "").lstrip("v").strip()
                    tarball_url = data.get("tarball_url", "")
                    if latest and self.version_compare(latest, self.current_version) > 0:
                        self._latest_tarball_url = tarball_url
                        GLib.idle_add(on_result, True, latest)
                    else:
                        GLib.idle_add(on_result, False, latest or self.current_version)
            except Exception as e:
                GLib.idle_add(on_error, str(e))
                
        threading.Thread(target=_worker, daemon=True).start()

    def open_releases_page(self):
        subprocess.Popen(["xdg-open", GITHUB_RELEASES_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def install_update_async(self, on_progress, on_done):
        """
        on_progress(fraction: float, status_text: str)
        on_done(success: bool, error_msg: str)
        """
        if not self._latest_tarball_url:
            on_done(False, "No URL available")
            return
            
        def _worker():
            tmp_dir = None
            try:
                GLib.idle_add(on_progress, 0.1, self.T("downloading_update"))
                tmp_dir = tempfile.mkdtemp(prefix="hp-manager-update-")
                tarball_path = os.path.join(tmp_dir, "update.tar.gz")

                req = urllib.request.Request(self._latest_tarball_url, headers={"Accept": "application/vnd.github.v3+json"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get('Content-Length', 0))
                    downloaded = 0
                    with open(tarball_path, 'wb') as f:
                        while True:
                            chunk = resp.read(8192)
                            if not chunk: break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = min(downloaded / total, 0.5)
                                GLib.idle_add(on_progress, pct, self.T("downloading_update"))

                GLib.idle_add(on_progress, 0.5, self.T("installing_update"))

                with tarfile.open(tarball_path, 'r:gz') as tar:
                    abs_tmp = os.path.realpath(tmp_dir)
                    for member in tar.getmembers():
                        member_path = os.path.realpath(os.path.join(tmp_dir, member.name))
                        if not member_path.startswith(abs_tmp + os.sep) and member_path != abs_tmp:
                            raise ValueError(f"Path traversal detected in archive member: {member.name}")
                    tar.extractall(path=tmp_dir)

                extracted_dirs = [d for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d))]
                if not extracted_dirs:
                    raise RuntimeError("No directory found in tarball")
                src_dir = os.path.join(tmp_dir, extracted_dirs[0])

                setup_script = os.path.join(src_dir, "setup.sh")
                if os.path.exists(setup_script):
                    os.chmod(setup_script, 0o755)
                    cmd = ["pkexec", "bash", "-c", f"cd '{src_dir}' && bash setup.sh update"]
                else:
                    install_script = os.path.join(src_dir, "update.sh")
                    if not os.path.exists(install_script):
                        install_script = os.path.join(src_dir, "install.sh")
                        if not os.path.exists(install_script):
                            raise RuntimeError(f"setup.sh or update.sh not found in {src_dir}")
                    os.chmod(install_script, 0o755)
                    cmd = ["pkexec", "bash", "-c", f"cd '{src_dir}' && bash '{os.path.basename(install_script)}'"]

                GLib.idle_add(on_progress, 0.6, self.T("installing_update"))

                result = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True, timeout=300)

                GLib.idle_add(on_progress, 0.95, self.T("installing_update"))

                if result.returncode == 0:
                    GLib.idle_add(on_done, True, "")
                else:
                    err = result.stderr.strip() or result.stdout.strip() or f"Exit code: {result.returncode}"
                    GLib.idle_add(on_done, False, err)

            except Exception as e:
                GLib.idle_add(on_done, False, str(e))
            finally:
                if tmp_dir and os.path.exists(tmp_dir):
                    try: shutil.rmtree(tmp_dir)
                    except Exception: pass

        threading.Thread(target=_worker, daemon=True).start()

    def restart_app(self):
        import sys
        python = sys.executable
        script = os.path.abspath(sys.argv[0]) if sys.argv else ""
        if script and os.path.exists(script):
            subprocess.Popen([python, script])
        sys.exit(0)
