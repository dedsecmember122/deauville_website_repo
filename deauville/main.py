"""uv run python main.py  ->  starts the server and opens the website."""
import threading
import webbrowser

import uvicorn

URL = "http://127.0.0.1:8000"

if __name__ == "__main__":
    threading.Timer(1.2, webbrowser.open, args=[URL]).start()
    print(f"Deauville Festival du Rire -> {URL}  (Ctrl+C to stop)")
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
