import argparse
from internal.server import ServerConfig, Server

def get_args() -> argparse.Namespace:
    
    parser = argparse.ArgumentParser(description ="" \
        "WARP written in Python. Made for educational and testing purposes only. " \
        "Original idea from Luke Curley [Twitch] and re-written in Python by Enric Perpinyà [Aalto University]."
    )
    parser.add_argument("-i", "--ip", type=str, default="127.0.0.1", help="HTTP server IP")
    parser.add_argument("-p", "--port", type=int, default=4443, help="HTTP server port")
    parser.add_argument("-c", "--tls-cert", type=str, default="../cert/localhost.warp.demo.crt", help="TLS certificate file path", required=True)
    parser.add_argument("-k", "--tls-key", type=str, default="../cert/localhost.warp.demo.key", help="TLS key file path", required=True)
    parser.add_argument("--log-dir", type=str, default="", help="logs will be written to the provided directory")
    parser.add_argument("-m", "--hls", type=str, default="../media/hls.m3u8", help="HLS playlist path")
    return parser.parse_args()

if __name__ == '__main__':
    args: argparse.Namespace = get_args()
    config = ServerConfig(args)
    server = Server(config)
    server.run()

