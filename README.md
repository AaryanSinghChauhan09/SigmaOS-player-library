# SigmaOS Player Library

Python planning and parsing layer shared by SigmaOS media-player components.
It builds an mpv argument vector, parses M3U playlists and key/value metadata,
and validates seek plans.

## Commands

- `sigma-player play-plan PATH...` prints a shell-escaped mpv command plan.
- `playlist FILE` parses M3U entries; `metadata FILE` parses tag dumps.
- `seek-plan --current S --target S --duration S` reports a validated seek.

The CLI does not launch mpv. `play_plan()` returns argv data without touching
the filesystem; no execute path is implemented here. Playlist and metadata
commands read the files named by the caller. A displayed command plan is not
evidence that mpv is installed or playback will succeed.

## Development

`make test` runs the parser and planning tests. The pure planning layer does not
spawn subprocesses or access the network. This component takes inspiration
from [Xplayer's playlist parser](https://github.com/linuxmint/xplayer-plparser)
without claiming compatibility with that project's format or UI.
