    # SigmaOS-player-library

    Media playlist / metadata library

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/xplayer-plparser

    ## Design principles applied
    - **Separation of Concerns**
- **Defensive Programming**
- **Fail-Fast**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `play-plan, playlist, metadata, seek-plan`

    ```
    $ sigma-player play-plan movie.mkv --fullscreen --loop
mpv --really-quiet --fullscreen --loop-playlist=inf -- movie.mkv
$ sigma-player playlist show.m3u
1. Sunrise Over the Ridge (612.3s) https://cdn.example.com/ridge.mp4
$ sigma-player metadata tags.txt
title = Sunrise Over the Ridge
$ sigma-player seek-plan --current 12 --target 90 --duration 600
seek-forward +78.000s (15% of 600s)

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
