import queue
import subprocess
import threading
import time

class BluetoothCtl:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self.reader_thread = threading.Thread(target=self.reader, daemon=True)
        self.reader_thread.start()
        self.send("power on")

    def get_info(self, mac: str) -> str:
        """Sends info command and gathers the result from the reader queue."""
        self.drain_output()
        self.send(f"info {mac}")
        time.sleep(0.8)
        lines = self.drain_output()
        return "\n".join(lines)

    def reader(self):
        try:
            # Use readline to avoid blocking the whole thread on end-of-stream
            while not self._stop_event.is_set():
                line = self.proc.stdout.readline()
                if not line:
                    break
                self._queue.put(line)
        except Exception:
            pass

    def send(self, cmd: str, delay: float = 0.1):
        if self.proc.poll() is not None:
            return

        try:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
            time.sleep(delay)
        except (BrokenPipeError, OSError):
            pass

    def broadcast_mfg(self, mfg_id: str, mfg_data: str):
        self.send("advertise off")
        self.send("menu advertise")
        self.send("clear")
        self.send(f"manufacturer {mfg_id} {mfg_data}")
        self.send("name on")
        self.send("back")
        self.send("advertise on")

    def stop_advertising(self):
        self.send("advertise off")

    def close(self):
        self._stop_event.set()
        self.send("advertise off")
        self.send("quit")
        try:
            self.proc.wait(timeout=1.5)
        except:
            self.proc.kill()

    def drain_output(self) -> list[str]:
        lines = []
        while not self._queue.empty():
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return lines

    def close(self):
        self._stop_event.set()
        self.stop_advertising()
        self.send("quit")
        try:
            self.proc.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        except Exception:
            self.proc.kill()