# Live Stream Player

This is a lightweight web app for playing live video streams and true VCNR v3 protected video files in the browser.

## Features

- Plays HLS live streams (`.m3u8`)
- Plays VCNR v3 encrypted files after passcode entry
- Accepts shared VCNR links through `?url=...`
- Can show a hosted sample file button through `sample-config.json`
- Uses native browser playback when available
- Falls back to HLS.js for wider compatibility
- Includes a demo stream button
- Responsive layout for desktop and mobile

## Files

- `index.html` - app structure
- `styles.css` - visual design and responsive layout
- `app.js` - stream and VCNR playback logic
- `mp4_segments.js` - fragmented MP4 reconstruction for VCNR playback
- `sample-config.json` - hosted sample VCNR configuration

## How to run

Serve the folder with any static web server, then open `index.html` in the browser through that local server.

Example options:

- VS Code Live Server
- `python -m http.server 4173`
- `npm start`
- any Netlify, Vercel, or static hosting deployment

## How to use

1. Start a static server in this folder.
2. Open the app in your browser.
3. To play a live stream, paste an HLS URL such as `https://example.com/live/stream.m3u8` and click `Play Stream`.
4. To play a VCNR file, switch to `VCNR File`, then either paste a VCNR URL or choose a local `.vcnr` file, enter the passcode, and click `Unlock And Play`.

## GitHub Pages

Recommended layout for hosted VCNR files:

- player page at `/`
- encrypted media under `/media/`

Example:

- player: `https://USERNAME.github.io/REPO/`
- VCNR file: `https://USERNAME.github.io/REPO/media/movie.vcnr`

This app also supports:

- shared links like `?url=https://USERNAME.github.io/REPO/media/movie.vcnr`
- a sample file button driven by `sample-config.json`

If you publish a file at `media/sample.vcnr`, the app can use that as a default hosted sample.

## Railway

This project is also ready for Railway deployment.

Files added for Railway:

- `package.json`
- `server.js`
- `railway.json`
- `.nojekyll`
- `media/.gitkeep`

Deployment shape:

- Railway runs `npm start`
- `server.js` serves the app and VCNR files
- VCNR URLs can be hosted directly from the same Railway app

Recommended Railway file layout:

- app at `/`
- VCNR files in `/media/`

Example after deploy:

- player: `https://your-app.up.railway.app/`
- VCNR file: `https://your-app.up.railway.app/media/movie.vcnr`
- shared link: `https://your-app.up.railway.app/?url=https://your-app.up.railway.app/media/movie.vcnr`

## Notes

- HTTPS streams work best in modern browsers.
- Some browsers may block autoplay until the user presses play.
- If the stream server blocks cross-origin access, playback may fail even if the URL is valid.
- VCNR support now follows the true VCNR v3 browser format:
  `VCNRCMP3`, PBKDF2-HMAC-SHA256, AES-256-GCM, SHA-256 header authentication, and fragmented MP4 reconstruction.
- H.264 VCNR files should be the most reliable. H.265 depends on browser support.
- When playing VCNR from a URL on a different host, that server must allow CORS.
