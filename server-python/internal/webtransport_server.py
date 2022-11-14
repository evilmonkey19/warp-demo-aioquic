# AIOQUIC
# Takens parts from https://github.com/dynamite-bud/webTransport-server/blob/main/wt_server.py
import asyncio
from typing import Dict, Optional, List, Tuple
from collections import defaultdict

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3Connection, H3_ALPN
from aioquic.h3.events import H3Event, HeadersReceived, WebTransportStreamDataReceived, DatagramReceived
from aioquic.quic.connection import stream_is_unidirectional

from aioquic.quic.events import (
    ProtocolNegotiated, 
    StreamReset, 
    QuicEvent, 
)

import random

from .config import App

class WebTransportProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http : Optional[H3Connection] = None
        self._handler : Optional[ChunkHandler] = None


    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated):
            self._http = H3Connection(self._quic, enable_webtransport=True)
        elif isinstance(event, StreamReset) and self._handler is not None:
            # Streams in QUIC can be closed in two ways: normal (FIN) and
            # abnormal (resets). FIN is handled by the handler; the code
            # below handles resets.
            self._handler.stream_closed(event.stream_id)
        if self._http is not None:
            for h3_event in self._http.handle_event(event):
                self._h3_event_received(h3_event)

    def _h3_event_received(self, event: H3Event) -> None:
        if isinstance(event, HeadersReceived):
            headers : dict = {}
            for header, value in event.headers:
                headers[header] = value
            if (
                headers.get(b':method') == b'CONNECT' 
                and headers.get(b':protocol') == b'webtransport'
            ):
                self._handshake_webtransport(event.stream_id, headers)
            else:
                self._send_response(event.stream_id, 400, end_stream=True)
        if self._handler:
            self._handler.h3_event_received(event)
            
    
    def _handshake_webtransport(
        self, 
        stream_id: int, 
        headers: Dict[bytes, bytes]
    ) -> None:
        authority : bytes = headers.get(b':authority')
        path : bytes = headers.get(b':path')
        if authority is None or path is None:
            # ':authority' and ':path' are required for WebTransport.
            self._send_response(stream_id, 400, end_stream=True)
            return
        if path == b'/':
            assert(self._handler is None)
            self._handler = ChunkHandler(stream_id, self)
            self._send_response(stream_id, 200)
        else:
            self._send_response(stream_id, 404, end_stream=True)

    def _send_response(
        self,
        stream_id: int,
        status_code: int,
        end_stream: bool = False
    ) -> None:
        headers : List[Tuple[bytes, bytes]] = [
            (b':status',
            str(status_code).encode()),
        ]
        if status_code == 200:
            headers.append((b'sec-webtransport-http3-draft', b'draft02'))
        self._http.send_headers(
            stream_id=stream_id,
            headers=headers,
            end_stream=end_stream
        )

# ChunkHandler implements a really simple protocol:
#   - Pushes the stream segmets read from the HLS playlist as datagrams
class ChunkHandler:

    def __init__(self, session_id, protocol: QuicConnectionProtocol) -> None:
        self._session_id = session_id
        self._http = protocol._http
        self.protocol = protocol
        self._counters = defaultdict(int)
        

    def h3_event_received(self, event: H3Event) -> None:
        # DATAGRAM
        if isinstance(event, DatagramReceived):
            print('received datagram')
            asyncio.create_task(datagram_m3u8_handler(self, self._session_id))

        # STREAM
        if isinstance(event, WebTransportStreamDataReceived):
            self._counters[event.stream_id] += len(event.data)
            if event.stream_ended:  
                if stream_is_unidirectional(event.stream_id):
                    response_id = self._http.create_webtransport_stream(
                        self._session_id, is_unidirectional=True)
            else:
                response_id = event.stream_id
                
            asyncio.create_task(stream_m3u8_handler(self, response_id))

    def stream_closed(self, stream_id: int) -> None:
        try:
            del self._counters[stream_id]
        except KeyError:
            pass

    def create_payload(self):
        with open('test.m4s', 'rb') as f:
            return f.read()

    def sendChunks(self):
        response_id = self._http.create_webtransport_stream(
            self._session_id, is_unidirectional=True
        )
        asyncio.create_task(stream_chunk_handler(self, response_id))

async def datagram_m3u8_handler(self, stream_id):
    payload = genPayload()
    self._http.send_datagram(stream_id, payload)
    self.protocol.transmit()

async def datagram_chunk_handler(self, stream_id):
    print('datagram_chunk_handler')
    for i in range(10):
        payload = self.create_payload()
        print(f'sending datagram {i}')
        self._http.send_datagram(stream_id, payload)
        self.protocol.transmit()
        await asyncio.sleep(1)

    payload = f'end of stream'.encode('ascii')
    self._http.send_datagram(stream_id, payload)

async def stream_m3u8_handler(self, stream_id):
    payload = genPayload()
    self._http._quic.send_stream_data(stream_id, payload, end_stream=True)
    self.protocol.transmit()

async def stream_chunk_handler(self, stream_id):
    print('stream_chunk_handler')
    for i in range(10):
        payload = self.create_payload()
        print(f'sending chunk {i}')
        self._http._quic.send_stream_data(
            stream_id, payload, end_stream=False)
        self.protocol.transmit()
        await asyncio.sleep(1)

    payload = f'end of stream'.encode('ascii')
    self._http._quic.send_stream_data(stream_id, payload, end_stream=True)



def genPayload():
    urls = App.config('urls')
    random_num = random.randint(0, len(urls) - 1)
    if len(urls) > 1 :
        if (App.config('current_stream') == random_num):
            random_num = (random_num + 1) % len(urls)
        App.set('current_stream', random_num)
    return f'{urls[random_num]}'.encode('ascii')
    