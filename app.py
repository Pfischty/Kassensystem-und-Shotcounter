"""Entrypoint shim that forwards to the Shotcounter application package."""

from Shotcounter.app import app, socketio


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
