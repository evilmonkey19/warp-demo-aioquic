package warp

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"time"

	"github.com/adriancable/webtransport-go"
	"github.com/kixelated/invoker"
)

// A single WebTransport session
type Session struct {
	inner  *webtransport.Session
	media  *Media
	socket *Socket
	audio  *MediaStream
	video  *MediaStream

	streams invoker.Tasks
}

func NewSession(session *webtransport.Session, media *Media, socket *Socket, audio *MediaStream, video *MediaStream) (s *Session, err error) {
	s = new(Session)
	s.inner = session
	s.media = media
	s.socket = socket
	s.audio = audio
	s.video = video
	return s, nil
}

func (s *Session) Run(ctx context.Context) (err error) {
	// TODO validate the session before accepting it
	s.inner.AcceptSession()
	defer s.inner.CloseSession()

	/*
		s.audio, s.video, err = s.media.Start()
		if err != nil {
			return fmt.Errorf("failed to start media: %w", err)
		}*/

	// Once we've validated the session, now we can start accessing the streams
	return invoker.Run(ctx, s.runAccept, s.runAcceptUni, s.runAudio, s.runVideo, s.streams.Repeat)
}

func (s *Session) runAccept(ctx context.Context) (err error) {
	for {
		// TODO context support :(
		stream, err := s.inner.AcceptStream()
		if err != nil {
			return fmt.Errorf("failed to accept bidirectional stream: %w", err)
		}

		// Warp doesn't utilize bidirectional streams so just close them immediately.
		// We might use them in the future so don't close the connection with an error.
		stream.CancelRead(1)
	}
}

func (s *Session) runAcceptUni(ctx context.Context) (err error) {
	for {
		stream, err := s.inner.AcceptUniStream(ctx)
		if err != nil {
			return fmt.Errorf("failed to accept unidirectional stream: %w", err)
		}

		s.streams.Add(func(ctx context.Context) (err error) {
			return s.handleStream(ctx, &stream)
		})
	}
}

func (s *Session) handleStream(ctx context.Context, stream *webtransport.ReceiveStream) (err error) {
	defer func() {
		if err != nil {
			stream.CancelRead(1)
		}
	}()

	var header [8]byte
	for {
		_, err = io.ReadFull(stream, header[:])
		if errors.Is(io.EOF, err) {
			return nil
		} else if err != nil {
			return fmt.Errorf("failed to read atom header: %w", err)
		}

		size := binary.BigEndian.Uint32(header[0:4])
		name := string(header[4:8])

		if size < 8 {
			return fmt.Errorf("atom size is too small")
		} else if size > 42069 { // arbitrary limit
			return fmt.Errorf("atom size is too large")
		} else if name != "warp" {
			return fmt.Errorf("only warp atoms are supported")
		}

		payload := make([]byte, size-8)

		_, err = io.ReadFull(stream, payload)
		if err != nil {
			return fmt.Errorf("failed to read atom payload: %w", err)
		}

		msg := Message{}

		err = json.Unmarshal(payload, &msg)
		if err != nil {
			return fmt.Errorf("failed to decode json payload: %w", err)
		}

		if msg.Throttle != nil {
			s.setThrottle(msg.Throttle)
		}
	}
}

func (s *Session) runAudio(ctx context.Context) (err error) {
	init, err := s.audio.Init(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch init segment: %w", err)
	}

	// NOTE: Assumes a single init segment
	err = s.writeInit(ctx, init, 1)
	if err != nil {
		return fmt.Errorf("failed to write init stream: %w", err)
	}

	for {
		segment, err := s.audio.Segment(ctx)
		if err != nil {
			return fmt.Errorf("failed to get next segment: %w", err)
		}

		if segment == nil {
			return nil
		}

		err = s.writeSegment(ctx, segment, 1)
		if err != nil {
			return fmt.Errorf("failed to write segment stream: %w", err)
		}
	}
}

func (s *Session) runVideo(ctx context.Context) (err error) {
	init, err := s.video.Init(ctx)
	if err != nil {
		return fmt.Errorf("failed to fetch init segment: %w", err)
	}

	// NOTE: Assumes a single init segment
	err = s.writeInit(ctx, init, 2)
	if err != nil {
		return fmt.Errorf("failed to write init stream: %w", err)
	}

	for {
		segment, err := s.video.Segment(ctx)
		if err != nil {
			return fmt.Errorf("failed to get next segment: %w", err)
		}

		if segment == nil {
			return nil
		}

		err = s.writeSegment(ctx, segment, 2)
		if err != nil {
			return fmt.Errorf("failed to write segment stream: %w", err)
		}
	}
}

// Create a stream for an INIT segment and write the container.
func (s *Session) writeInit(ctx context.Context, init *MediaInit, id int) (err error) {
	temp, err := s.inner.OpenUniStreamSync(ctx)
	if err != nil {
		return fmt.Errorf("failed to create stream: %w", err)
	}

	// Wrap the stream in an object that buffers writes instead of blocking.
	stream := NewStream(temp)
	s.streams.Add(stream.Run)

	defer func() {
		if err != nil {
			stream.WriteCancel(1)
		}
	}()

	stream.SetPriority(math.MaxInt)

	err = stream.WriteMessage(Message{
		Init: &MessageInit{Id: id},
	})
	if err != nil {
		return fmt.Errorf("failed to write init header: %w", err)
	}

	_, err = stream.Write(init.Raw)
	if err != nil {
		return fmt.Errorf("failed to write init data: %w", err)
	}

	return nil
}

// Create a stream for a segment and write the contents, chunk by chunk.
func (s *Session) writeSegment(ctx context.Context, segment *MediaSegment, init int) (err error) {
	temp, err := s.inner.OpenUniStreamSync(ctx)
	if err != nil {
		return fmt.Errorf("failed to create stream: %w", err)
	}

	// Wrap the stream in an object that buffers writes instead of blocking.
	stream := NewStream(temp)
	s.streams.Add(stream.Run)

	defer func() {
		if err != nil {
			stream.WriteCancel(1)
		}
	}()

	ms := int(segment.timestamp / time.Millisecond)

	// newer segments take priority
	stream.SetPriority(ms)

	err = stream.WriteMessage(Message{
		Segment: &MessageSegment{
			Init:      init,
			Timestamp: ms,
		},
	})
	if err != nil {
		return fmt.Errorf("failed to write segment header: %w", err)
	}

	for {
		// Get the next fragment
		buf, err := segment.Read(ctx)
		if errors.Is(err, io.EOF) {
			break
		} else if err != nil {
			return fmt.Errorf("failed to read segment data: %w", err)
		}

		// NOTE: This won't block because of our wrapper
		_, err = stream.Write(buf)
		if err != nil {
			return fmt.Errorf("failed to write segment data: %w", err)
		}
	}

	err = stream.Close()
	if err != nil {
		return fmt.Errorf("failed to close segemnt stream: %w", err)
	}

	return nil
}

func (s *Session) setThrottle(msg *MessageThrottle) {
	s.socket.SetWriteRate(msg.Rate)
	s.socket.SetWriteBuffer(msg.Buffer)
	s.socket.SetWriteLoss(msg.Loss)
}
