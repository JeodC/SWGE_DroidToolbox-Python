import subprocess
import threading
import queue
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
        self._stop_event = threading.Event() # Track shutdown
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()

        # Ensure the controller is ready
        self.send("power on")

    def get_info(self, mac: str) -> str:
        """Sends info command and gathers the result from the reader queue."""
        self.drain_output() # Flush old data
        self.send(f"info {mac}")

        # We need to wait long enough for the output to populate the queue
        time.sleep(0.8)

        lines = self.drain_output()
        # Join lines into one big string for the regex parser
        return "\n".join(lines)

    def _reader(self):
        try:
            # Use readline to avoid blocking the whole thread on end-of-stream
            while not self._stop_event.is_set():
                line = self.proc.stdout.readline()
                if not line:
                    break
                self._queue.put(line)
        except Exception:
            pass

    def send(self, cmd: str, delay: float = 0.1): # Increased delay slightly
        if self.proc.poll() is not None:
            return # Process is dead

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