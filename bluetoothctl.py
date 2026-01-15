#!/usr/bin/env python3
"""
bluetoothctl.py - Communication layer for bluetoothctl / BlueZ
"""

import queue
import subprocess
import threading
import time
import select
import os
import signal

class BluetoothCtlError(RuntimeError):
    pass

class BluetoothCtl:
    def __init__(self):
        self.proc = None
        self._queue = queue.Queue(maxsize=500)
        self._stop_event = threading.Event()
        self.current_mfg_payload = None
        self._start_process()

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------
    def _start_process(self):
        if self.proc:
            raise BluetoothCtlError("bluetoothctl already running")

        self.proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0,
        )

        self._stop_event.clear()
        self._reader_thread = threading.Thread(
            target=self._reader, daemon=True
        )
        self._reader_thread.start()

        self._send("power on")
        self._send("agent NoInputNoOutput")
        self._send("default-agent")
        self._send("pairable off")
        self._send("discoverable off")

    def close(self):
        self._stop_event.set()
        if not self.proc:
            return

        try:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
            self.proc.wait(timeout=0.5)
        except Exception:
            try:
                os.kill(self.proc.pid, signal.SIGTERM)
            except Exception:
                pass
        finally:
            self.proc = None
            
    def _is_powered(self) -> bool:
        """Check if Bluetooth is powered."""
        try:
            if not self.proc or self.proc.poll() is not None:
                return False
            output = self.get_info("")
            return "Powered: yes" in output
        except BluetoothCtlError:
            return False

    # ------------------------------------------------------------------
    # Reader thread
    # ------------------------------------------------------------------
    def _reader(self):
        try:
            fd = self.proc.stdout.fileno()
            while not self._stop_event.is_set():
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    continue

                line = self.proc.stdout.readline()
                if not line:
                    break

                try:
                    self._queue.put_nowait(line)
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                        self._queue.put_nowait(line)
                    except queue.Empty:
                        pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Command sending
    # ------------------------------------------------------------------
    def _send(self, cmd: str, delay: float = 0.05):
        try:
            if self.proc.poll() is not None:
                print("[BT] Process died. Restarting...")
                self.proc = None
                self._start_process()
                
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()
            if delay:
                time.sleep(delay)
        except (AttributeError, BrokenPipeError, Exception) as e:
            raise BluetoothCtlError(f"Command failed: {cmd} - {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def power_on(self):
        """Ensure the adapter is powered. Retry once if needed."""
        try:
            print("[BT] Ensuring Bluetooth is powered on...")
            self._send("power on") 
            time.sleep(0.1)
            output = self.get_info("")
            if "Powered: yes" not in output:
                print("[BT] Adapter still not powered, retrying...")
                self._send("power on")
        except BluetoothCtlError as e:
            print(f"[BT] Failed to power on: {e}")

    def start_scanning(self):
        self._send("scan on")

    def stop_scanning(self):
        self._send("scan off")

    def get_info(self, mac: str, timeout: float = 1.0) -> str:
        mac = mac.upper()
        self._send(f"info {mac}", delay=0.0)
    
        end = time.monotonic() + timeout
        output = []
        found_data = False
    
        while time.monotonic() < end:
            try:
                line = self._queue.get(timeout=0.1)
                output.append(line)
                
                # Specifically look for the end of the data block we need
                if "ManufacturerData" in line or "ServiceData" in line:
                    found_data = True
                    
            except queue.Empty:
                # If we haven't seen any data yet, keep waiting. 
                # If we already have some data, give it one last short wait for trailing lines.
                if found_data:
                    time.sleep(0.1)
                    break
                continue
    
        return "".join(output)

    # ------------------------------------------------------------------
    # Advertising (stable, no clear abuse)
    # ------------------------------------------------------------------
    def broadcast_mfg(self, mfg_id: str, mfg_data: str):
        payload = f"{mfg_id}:{mfg_data}"
        if payload == self.current_mfg_payload:
            return
    
        self._send("advertise off", delay=0.1)
        self._send("menu advertise")
        self._send("clear")
        self._send(f"manufacturer {mfg_id} {mfg_data}")
        self._send("back")
        self._send("advertise on")
        self.current_mfg_payload = payload

    def stop_advertising(self):
        self._send("advertise off")
        self.current_mfg_payload = None
