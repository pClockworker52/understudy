"""
Query GIMP state via Script-Fu TCP server.
Provides structured context that is invisible to Layer 1.

Start server in GIMP: Filters > Script-Fu > Start Server (port 10008)
"""

import socket
import time
from typing import Optional, Dict


class GimpBridge:
    """
    Communicates with GIMP's Script-Fu server.

    Start server in GIMP: Filters > Script-Fu > Start Server (port 10008)
    """

    def __init__(self, host: str = "localhost", port: int = 10008):
        self.host = host
        self.port = port

    def _query(self, script_fu_code: str) -> Optional[str]:
        """Send Script-Fu command, return response.

        GIMP Script-Fu server protocol:
          Send:    'G' (1 byte) + length (2 bytes big-endian) + command
          Receive: status (1 byte, 0=OK) + length (2 bytes big-endian) + response
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((self.host, self.port))
            cmd = script_fu_code.encode('utf-8')
            # GIMP Script-Fu server protocol (verified for GIMP 2.10):
            #   Send:    'G' (1 byte) + 2-byte big-endian length + command
            #   Receive: 'G' (1 byte) + status (1 byte, 0=OK) + 2-byte big-endian length + response
            header = b'G' + len(cmd).to_bytes(2, 'big')
            s.sendall(header + cmd)
            time.sleep(0.1)  # Give GIMP time to process
            # Read 4-byte response header: G + status + 2-byte length
            resp_header = b""
            while len(resp_header) < 4:
                chunk = s.recv(4 - len(resp_header))
                if not chunk:
                    break
                resp_header += chunk
            if len(resp_header) < 4:
                s.close()
                return None
            status = resp_header[1]  # byte 0='G', byte 1=status
            length = int.from_bytes(resp_header[2:4], 'big')
            data = b""
            while len(data) < length:
                chunk = s.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
            s.close()
            result = data.decode('utf-8').strip().split('#<EOF>')[0].strip()
            if status != 0:
                print(f"[bridge] Script-Fu error: {result}")
                return None
            return result
        except Exception as e:
            print(f"[bridge] Query failed: {e}")
            return None

    def is_connected(self) -> bool:
        result = self._query('(car (gimp-version))')
        return result is not None

    def get_state(self) -> Optional[Dict]:
        """Get comprehensive GIMP state as structured data."""

        # Active image info
        image_info = self._query('''
            (let* ((image (car (gimp-image-list))))
              (list
                (car (gimp-image-get-name image))
                (car (gimp-image-width image))
                (car (gimp-image-height image))
                (car (gimp-image-get-active-layer image))
                (car (gimp-selection-is-empty image))
              ))
        ''')

        # Foreground/background colors
        fg_color = self._query('(gimp-context-get-foreground)')

        # Number of layers
        num_layers = self._query(
            '(car (gimp-image-get-layers (car (gimp-image-list))))'
        )

        if not image_info:
            return None

        return {
            "image_info": image_info,
            "foreground_color": fg_color,
            "num_layers": num_layers,
        }

    def get_state_as_text(self) -> str:
        """Format state for Gemini context."""
        state = self.get_state()
        if not state:
            return "[GIMP state unavailable]"

        lines = [
            f"Image: {state['image_info']}",
            f"Foreground color: {state['foreground_color']}",
            f"Layers: {state['num_layers']}",
        ]
        return "\n".join(lines)

    # Action execution methods

    def execute(self, script_fu_code: str) -> bool:
        """Execute arbitrary Script-Fu in GIMP."""
        print(f"[bridge] Executing: {script_fu_code[:80]}...")
        result = self._query(script_fu_code)
        if result is not None:
            print(f"[bridge] Success: {result[:50] if result else '(empty)'}")
            return True
        print("[bridge] Execution failed")
        return False

    def feather_selection(self, radius: float = 5.0) -> bool:
        return self.execute(
            f'(gimp-selection-feather (car (gimp-image-list)) {radius})'
        )

    def invert_selection(self) -> bool:
        return self.execute(
            '(gimp-selection-invert (car (gimp-image-list)))'
        )

    def select_all(self) -> bool:
        return self.execute(
            '(gimp-selection-all (car (gimp-image-list)))'
        )


if __name__ == "__main__":
    # Standalone test
    bridge = GimpBridge()
    if bridge.is_connected():
        print("GIMP Script-Fu server connected!")
        print(bridge.get_state_as_text())
    else:
        print("Could not connect to GIMP Script-Fu server.")
        print("Start it in GIMP: Filters > Script-Fu > Start Server (port 10008)")
