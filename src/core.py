"""mpv-backed media planner for SigmaOS-player / photo-viewer / player-library.

A PURE plan & parse layer (build the mpv argv, parse an M3U playlist or a
tag dump, validate a seek range) is fully unit-tested; the thin execute layer
that would spawn mpv is never run by self_test() (no subprocess).
Principles: Separation of Concerns, Defensive Programming, Fail-Fast, KISS,
Deterministic Testing.
"""
import argparse, os, shlex, sys

ENGINE = {
    "name": "sigma-player",
    "summary": "Plan mpv playback, parse playlists and media metadata",
    "language": "python",
    "verbs": ["play-plan", "playlist", "metadata", "seek-plan"],
    "principles": ["Separation of Concerns", "Defensive Programming",
                   "Fail-Fast", "KISS", "Deterministic Testing"],
}

cli_doc = """\
$ sigma-player play-plan movie.mkv --fullscreen --loop
mpv --really-quiet --fullscreen --loop-playlist=inf -- movie.mkv
$ sigma-player playlist show.m3u
1. Sunrise Over the Ridge (612.3s) https://cdn.example.com/ridge.mp4
$ sigma-player metadata tags.txt
title = Sunrise Over the Ridge
$ sigma-player seek-plan --current 12 --target 90 --duration 600
seek-forward +78.000s (15% of 600s)
"""


class PlayerError(Exception):
    pass


# --------------------------------------------------------------------------- #
#  PURE plan layer
# --------------------------------------------------------------------------- #
def play_plan(paths, fullscreen=False, loop=False, paused=False, extra=()):
    """Return the mpv argv for `paths` without touching the filesystem."""
    if not paths:
        raise PlayerError("no media path given")
    argv = ["mpv", "--really-quiet"]
    if fullscreen:
        argv.append("--fullscreen")
    if loop:
        argv.append("--loop-playlist=inf")
    if paused:
        argv.append("--pause")
    for opt in extra:
        if not isinstance(opt, str) or not opt:
            raise PlayerError(f"bad extra option: {opt!r}")
        argv.append(opt)
    argv.append("--")
    argv.extend(os.path.expanduser(p) for p in paths)
    return argv


def _split_unquoted(text, sep):
    """Split `text` on `sep` ignoring separators inside double quotes."""
    out, buf, quoted = [], [], False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == sep and not quoted:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def parse_playlist(text):
    """Parse an (S)M3U playlist into an ordered list of dicts."""
    items, pending = [], None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            parts = _split_unquoted(line[len("#EXTINF:"):], ",")
            left = parts[0].strip()
            title = ",".join(parts[1:]).strip()
            token = left.split()[0] if left.split() else ""
            if token in ("", "-1"):
                dur = None
            else:
                try:
                    dur = float(token)
                except ValueError:
                    raise PlayerError(f"line {lineno}: bad #EXTINF duration")
            pending = {"duration": dur, "title": title}
            continue
        if line.startswith("#"):
            continue
        base = os.path.basename(line.split("?")[0])
        items.append({
            "duration": pending["duration"] if pending else None,
            "title": (pending["title"] if pending else "") or base,
            "url": line,
        })
        pending = None
    if pending is not None:
        raise PlayerError("dangling #EXTINF without a media URL")
    if not items:
        raise PlayerError("playlist contains no entries")
    return items


def parse_metadata(text):
    """Parse a 'key: value' / 'key=value' tag dump into a dict."""
    meta = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cand = sorted((line.find(s), s) for s in (":", "=") if s in line)
        if not cand:
            raise PlayerError(f"line {lineno}: expected 'key: value', got {line!r}")
        idx = cand[0][0]
        key = line[:idx].strip().lower().replace(" ", "-")
        if not key:
            raise PlayerError(f"line {lineno}: empty metadata key")
        meta[key] = line[idx + 1:].strip()
    if not meta:
        raise PlayerError("no metadata found")
    return meta


def seek_plan(current, target, duration):
    """Validate a seek target and describe the resulting mpv seek."""
    for name, v in (("current", current), ("target", target), ("duration", duration)):
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise PlayerError(f"{name} must be a number")
        if v < 0:
            raise PlayerError(f"{name} must be >= 0")
    current, target, duration = float(current), float(target), float(duration)
    if duration <= 0:
        raise PlayerError("duration must be > 0")
    if target > duration:
        raise PlayerError(f"target {target:g}s is beyond duration {duration:g}s")
    delta = round(target - current, 3)
    if delta > 0:
        op = "seek-forward"
    elif delta < 0:
        op = "seek-back"
    else:
        op = "noop"
    return {"op": op, "delta": delta, "target": target,
            "percent": round(100.0 * target / duration, 2)}


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("play-plan", help="build an mpv invocation")
    pp.add_argument("path", nargs="+", help="media file(s) or URL(s)")
    pp.add_argument("--fullscreen", action="store_true")
    pp.add_argument("--loop", action="store_true")
    pp.add_argument("--paused", action="store_true")
    pl = sub.add_parser("playlist", help="parse an M3U playlist")
    pl.add_argument("file")
    md = sub.add_parser("metadata", help="parse a key/value metadata dump")
    md.add_argument("file")
    sk = sub.add_parser("seek-plan", help="validate a seek target")
    sk.add_argument("--current", type=float, required=True)
    sk.add_argument("--target", type=float, required=True)
    sk.add_argument("--duration", type=float, required=True)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "play-plan":
            plan = play_plan(args.path, fullscreen=args.fullscreen,
                             loop=args.loop, paused=args.paused)
            print(" ".join(shlex.quote(a) for a in plan))
        elif args.cmd == "playlist":
            items = parse_playlist(_read(args.file))
            for i, it in enumerate(items, 1):
                d = "-" if it["duration"] is None else f'{it["duration"]:.1f}s'
                print(f'{i}. {it["title"]} ({d}) {it["url"]}')
            print(f"{len(items)} track(s)", file=sys.stderr)
        elif args.cmd == "metadata":
            for k, v in parse_metadata(_read(args.file)).items():
                print(f"{k} = {v}")
        elif args.cmd == "seek-plan":
            plan = seek_plan(args.current, args.target, args.duration)
            print(f'{plan["op"]} {plan["delta"]:+.3f}s '
                  f'({plan["percent"]}% of {args.duration:g}s)')
        return 0
    except (PlayerError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# --------------------------------------------------------------------------- #
#  Tests (plan/parse layer only -- no subprocess, no network)
# --------------------------------------------------------------------------- #
def self_test() -> None:
    argv = play_plan(["movie.mkv"], fullscreen=True, loop=True)
    assert argv == ["mpv", "--really-quiet", "--fullscreen",
                    "--loop-playlist=inf", "--", "movie.mkv"], argv
    assert play_plan(["a.mp4", "b.mkv"]) [-1] == "b.mkv"
    try:
        play_plan([])
    except PlayerError:
        pass
    else:
        raise AssertionError("empty path list not rejected")

    sample = ('#EXTM3U\n'
              '#EXTINF:-1 tvg-id="Ridge.uk" group-title="Docs",Sunrise Over the Ridge\n'
              'https://cdn.example.com/ridge.mp4\n'
              '#EXTINF:612.3,Deep Focus\n'
              'file:///media/focus.mkv\n'
              '# a comment\n\n')
    items = parse_playlist(sample)
    assert len(items) == 2, items
    assert items[0]["title"] == "Sunrise Over the Ridge"
    assert items[0]["duration"] is None
    assert items[0]["url"] == "https://cdn.example.com/ridge.mp4"
    assert items[1]["duration"] == 612.3
    assert items[1]["title"] == "Deep Focus"
    # name containing a comma inside quotes must not break parsing
    comma = ('#EXTM3U\n#EXTINF:-1 tvg-logo="http://x/a,b.png",News, 24x7\n'
             'https://cdn.example.com/news.m3u8\n')
    assert parse_playlist(comma)[0]["title"] == "News, 24x7"
    for bad in ("#EXTM3U\n", "#EXTM3U\n#EXTINF:-1,Only title\n",
                "#EXTM3U\n#EXTINF:xx,Bad\nhttps://x/y\n"):
        try:
            parse_playlist(bad)
        except PlayerError:
            pass
        else:
            raise AssertionError(f"bad playlist not rejected: {bad!r}")

    tags = ("title = Sunrise Over the Ridge\n"
            "artist: Marta Lind\n"
            "DATE: 2024\n"
            "genre=Ambient\n"
            "# comment line\n")
    meta = parse_metadata(tags)
    assert meta == {"title": "Sunrise Over the Ridge", "artist": "Marta Lind",
                    "date": "2024", "genre": "Ambient"}, meta
    for bad in ("", "no separator here\n"):
        try:
            parse_metadata(bad)
        except PlayerError:
            pass
        else:
            raise AssertionError(f"bad metadata not rejected: {bad!r}")

    plan = seek_plan(12, 90, 600)
    assert plan["op"] == "seek-forward" and plan["delta"] == 78.0, plan
    assert plan["percent"] == 15.0
    assert seek_plan(500, 100, 600)["op"] == "seek-back"
    assert seek_plan(5, 5, 600)["op"] == "noop"
    for bad in ((12, 900, 600), (-1, 10, 600), (0, 0, 0), (0, 10, -5)):
        try:
            seek_plan(*bad)
        except PlayerError:
            pass
        else:
            raise AssertionError(f"bad seek not rejected: {bad!r}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
