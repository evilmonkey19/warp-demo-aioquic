import mpd_parser
from mpd_parser.parser import Parser
from fsspec.implementations.local import LocalFileSystem
import time

class Media:
    dash_path : str
    audio : mpd_parser.tags.Representation
    video : mpd_parser.tags.Representation

    def __init__(self, dash_path: str):
        self.dash_path = dash_path
        mpd = Parser.from_file(dash_path)
        if len(mpd.periods) > 1 : raise Exception("Multiple periods are not supported")
        period = mpd.periods[0]
        for adaption in period.adaptation_sets:
            representation = adaption.representations[0]

            if not representation.mime_type : raise Exception("No mime type")

            if representation.mime_type == 'video/mp4': self.video = representation
            elif representation.mime_type == 'audio/mp4': self.audio = representation
        
        if not self.video : raise Exception("No video representation found")
        elif not self.audio : raise Exception("No audio representation found")        

    def start(self) -> None:
        start = time.now()
        audio = MediaStream(self, audio, start)
        video = MediaStream(self, video, start)


class MediaStream:
    media : Media
    init : 
    representation : mpd_parser.tags.Representation
    start : time

    def __init__(self, media: Media, representation: mpd_parser.tags.Representation, start: time) -> None:
        self.media = media
        self.representation = representation
        self.start = start

class MediaInit:
    raw : bytes
    timescale : int

    def __init__(self, raw: bytes, timescale: int) -> None:
        self.raw = raw
        self._findTimescale(self, raw)

    def _findTimescale(self, raw: bytes) -> int:
        
'''   
class MediaHandler:
        def __init__(self, session_id : int, http : H3Connection) -> None:
        self._session_id = session_id
        self._http = http
'''