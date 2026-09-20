import threading
import time
import webview

from app import app


def start_flask():
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":

    flask_thread = threading.Thread(
        target=start_flask,
        daemon=True
    )

    flask_thread.start()

    time.sleep(1)

    webview.create_window(
        "HORA Bookshop Management System",
        "http://127.0.0.1:5000",
        width=1200,
        height=800,
        resizable=True
    )

    webview.start()