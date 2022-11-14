# Warp
Segmented live media delivery protocol utilizing QUIC streams. See the [Warp draft](https://datatracker.ietf.org/doc/draft-lcurley-warp/).

Warp works by delivering each audio and video segment as a separate QUIC stream. These streams are assigned a priority such that old video will arrive last and can be dropped. This avoids buffering in many cases, offering the viewer a potentially better experience.

# Limitations
## Browser Support
This demo currently only works on Chrome for two reasons:

1. WebTransport support.
2. [Media underflow behavior](https://github.com/whatwg/html/issues/6359).

The ability to skip video abuses the fact that Chrome can play audio without video for up to 3 seconds (hardcoded!) when using MSE. It is possible to use something like WebCodecs instead... but that's still Chrome only at the moment.

## Streaming
This demo works by reading pre-encoded media and sleeping based on media timestamps. Obviously this is not a live stream; you should plug in your own encoder or source. (The code have been modified to generate real live-streaming from ffmpeg just intended for testing purposes).

The media is encoded on disk as a LL-DASH playlist. There's a crude parser and I haven't used DASH before so don't expect it to work with arbitrary inputs.

## QUIC Implementation
This demo uses a fork of [quic-go](https://github.com/lucas-clemente/quic-go). There are two critical features missing upstream:

1. [WebTransport](https://github.com/lucas-clemente/quic-go/issues/3191)
2. [Prioritization](https://github.com/lucas-clemente/quic-go/pull/3442)

## Congestion Control
This demo uses a single rendition. A production implementation will want to:

1. Change the rendition bitrate to match the estimated bitrate.
2. Switch renditions at segment boundaries based on the estimated bitrate.
3. or both!

Also, quic-go ships with the default New Reno congestion control. Something like [BBRv2](https://github.com/lucas-clemente/quic-go/issues/341) will work much better for live video as it limits RTT growth.

## Congestion Simulation
This demo will artificially limit the socket to 4Mb/s and 250ms RTT using a crude throttling mechanism. Each time you click the "Throttle" button, the bitrate is cut in half for a short duration to simulate congestion.

This is NOT how congestion works on real networks. It is meant to demonstrate how prioritizing streams allows playback to recover without buffering. Do not make any conclusions on how Warp or any other network protocol behaves under such crude simulations.

This limit applies to the entire socket so multiple connections will fight for limited bandwidth. You'll want to raise or remove the default limit if you want to test multiple simultaneous connections.


# Setup
## Requirements
* Go
* ffmpeg
* openssl
* Chrome Canary
* caddy

## Media
This demo simulates a live stream by reading a file from disk and sleeping based on media timestamps. Obviously you should hook this up to a real live stream to do anything useful.

Download your favorite media file:
```
wget http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4 -O media/stream1.mp4
```

Use ffmpeg to create a HLS playlist. This creates a segment every 2s and MPEG-TS2 fragment every 4s in an infinite loop.
```
sh ./media/gen_stream.sh stream1
```

In order to serve the files we use caddy:
```
cd media
caddy run
```

## TLS
Unfortunately, QUIC mandates TLS and makes local development difficult.

If you have a valid certificate you can use it instead of self-signing. The go binaries take a `-cert` and `-key` argument. Skip the remaining steps in this section and use your hostname instead of `localhost.demo`.

### Self-Sign
Generate a self-signed certificate for local testing:
```
./cert/generate
```

This creates `cert/localhost.demo.crt` and `cert/localhost.demo.key`.

### Origin
To have the browser accept our self-signed certificate, you'll need to add an entry to `/etc/hosts`.

```
echo '127.0.0.1 localhost.demo' | sudo tee -a /etc/hosts
```

### Chrome
Now we need to make Chrome accept these certificates, which normally would involve trusting a root CA but this was not working with WebTransport when I last tried.

Instead, we need to run a *fresh instance* of Chrome, instructing it to allow our self-signed certificate. This command will not work if Chrome is already running, so it's easier to use Chrome Canary instead. This command also needs to be executed in the project root because it invokes `./cert/fingerprint`.

Launch a new instance of Chrome Canary:
```
/Applications/Google\ Chrome\ Canary.app/Contents/MacOS/Google\ Chrome\ Canary --origin-to-force-quic-on="localhost.demo:4443" --ignore-certificate-errors-spki-list="`./cert/fingerprint`" https://localhost.demo:4444
```

Note that this will open our web server on `localhost.demo:4444`, which is started in the next section.

## Server
The Warp server defaults to listening on UDP 4443. It supports HTTP/3 and WebTransport, pushing media over WebTransport streams once a connection has been established. A more refined implementation would load content based on the WebTransport URL or some other messaging scheme.

```
cd server-python
python main.py -c ../cert/localhost.demo.crt -k ../cert/localhost.demo.key -p 4441 -i localhost.demo -u https://localhost:2015/stream1/stream.m3u8
```

## Web Player
The web assets need to be hosted with a HTTPS server. If you're using a self-signed certificate, you will need to ignore the security warning in Chrome (Advanced -> proceed to localhost.warp.demo). This can be avoided by adding your certificate to the root CA but I'm too lazy to do that.

```
cd player
yarn install
yarn serve
```

These can be accessed on `https://localhost.demo:4444` by default.
