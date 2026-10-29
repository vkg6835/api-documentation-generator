import argparse
import socket
import threading
import webbrowser
from app.server import serve

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8000)
    parser.add_argument("--no-browser",action="store_true")
    args=parser.parse_args()
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1",args.port))==0:
            raise SystemExit(f"Port {args.port} is occupied. Use --port 8001.")
    if not args.no_browser:
        timer=threading.Timer(1.5,lambda:webbrowser.open(f"http://127.0.0.1:{args.port}"))
        timer.daemon=True
        timer.start()
    serve(args.port)
