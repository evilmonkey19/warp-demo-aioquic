# AIOQUIC
# Takens parts from https://github.com/dynamite-bud/webTransport-server/blob/main/wt_server.py
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
class WebTransportProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http : Optional[H3Connection] = None
        self._handler : Optional[CounterHandler] = None

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
            self._handler = CounterHandler(stream_id, self._http)
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

# CounterHandler implements a really simple protocol:
#   - For every incoming bidirectional stream, it counts bytes it receives on
#     that stream until the stream is closed, and then replies with that byte
#     count on the same stream.
#   - For every incoming unidirectional stream, it counts bytes it receives on
#     that stream until the stream is closed, and then replies with that byte
#     count on a new unidirectional stream.
#   - For every incoming datagram, it sends a datagram with the length of
#     datagram that was just received.
class CounterHandler:

    def __init__(self, session_id, http: H3Connection) -> None:
        self._session_id = session_id
        self._http = http
        self._counters = defaultdict(int)
        self._num_messages = 0

    def h3_event_received(self, event: H3Event) -> None:
        if isinstance(event, DatagramReceived):
            payload = str(len(event.data)).encode('ascii')
            self._http.send_datagram(self._session_id, payload)

        if isinstance(event, WebTransportStreamDataReceived):
            self._num_messages += 1
            self._counters[event.stream_id] += len(event.data)
            if event.stream_ended:
                if stream_is_unidirectional(event.stream_id):
                    response_id = self._http.create_webtransport_stream(
                        self._session_id, is_unidirectional=True)
                else:
                    response_id = event.stream_id
                    payload = str(self._counters[event.stream_id]).encode('ascii')
                    self._http._quic.send_stream_data(
                        response_id, payload, end_stream=True)
                    self.stream_closed(event.stream_id)
            else:
                if(self._num_messages==1):
                    print(event.data)
                response_id = event.stream_id

    def stream_closed(self, stream_id: int) -> None:
        try:
            del self._counters[stream_id]
        except KeyError:
            pass
