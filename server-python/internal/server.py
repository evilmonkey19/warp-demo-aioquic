import asyncio
# from .media import Media
from .webtransport_server import WebTransportProtocol
from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.h3.connection import H3_ALPN

from .webtransport_server import CounterHandler


class ServerConfig:
    ip : str
    port : int
    cert_file : str
    key_file : str
    log_dir : str

    def __init__(self, *args) -> None:
        self.ip = args[0].ip
        self.port = args[0].port
        self.cert_file = args[0].tls_cert
        self.key_file = args[0].tls_key
        self.log_dir = args[0].log_dir

class Server:
    #inner : WebSocketServerProtocol
    #media : Media
    #socket : socket
    __config : ServerConfig
    __loop : asyncio.AbstractEventLoop

    def __init__(self, 
        config: ServerConfig,
        #media: Media
        ) -> None:
        self.__config = config
        configuration = QuicConfiguration(
            alpn_protocols=H3_ALPN,
            is_client=False,
            max_datagram_frame_size=65536,
        )
        configuration.load_cert_chain(self.__config.cert_file, self.__config.key_file)
        #self.media = media
        #audio = self.media.audio
        #video = self.media.video
        #audio,video = media.start()
        self.__loop = asyncio.get_event_loop()
        self.__loop.run_until_complete(
            serve(
                self.__config.ip,
                self.__config.port,
                configuration=configuration,
                create_protocol=WebTransportProtocol,
            )
        )

    def run(self) -> None:
        try:
            print(f'Listening on https://{self.__config.ip}:{self.__config.port}')
            self.__loop.run_forever()
        except KeyboardInterrupt:
            pass


        



    
        



