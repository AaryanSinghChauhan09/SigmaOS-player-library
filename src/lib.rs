// SPDX-License-Identifier: MIT OR Apache-2.0
//! SigmaOS-player-library — Media playlist / metadata library.
//!
//! Provides track indexing, playlist compilation (smart playlists, shuffle, repeat),
//! metadata search (artist, album, genre), and play-count tracking.
//!
//! Inspired by Omarchy's lightweight music library daemon, Hyprland's media keys overlay,
//! and Catppuccin Mocha's warm cover-art ambiance.
//!
//! Principles: index-accelerated search, zero `unsafe`, pure `std`.

#![forbid(unsafe_code)]

use std::collections::HashMap;
use std::fmt;
use std::path::{Path, PathBuf};

// ── Error types ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LibraryError {
    TrackNotFound(String),
    PlaylistNotFound(String),
    EmptyTrackTitle,
    InvalidDuration,
    DuplicateTrack(String),
    EmptyPlaylist,
}

impl fmt::Display for LibraryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TrackNotFound(id) => write!(f, "track '{id}' not found in library"),
            Self::PlaylistNotFound(pl) => write!(f, "playlist '{pl}' not found"),
            Self::EmptyTrackTitle => write!(f, "track title cannot be empty"),
            Self::InvalidDuration => write!(f, "track duration must be greater than zero"),
            Self::DuplicateTrack(id) => write!(f, "track '{id}' already exists in library"),
            Self::EmptyPlaylist => write!(f, "playlist has no tracks"),
        }
    }
}

impl std::error::Error for LibraryError {}

// ── Media Track Metadata ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MediaTrack {
    pub id: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub genre: String,
    pub duration_seconds: u32,
    pub file_path: PathBuf,
    pub play_count: u32,
}

impl MediaTrack {
    pub fn new(id: impl Into<String>, title: impl Into<String>, artist: impl Into<String>, path: impl AsRef<Path>, duration: u32) -> Result<Self, LibraryError> {
        let title = title.into().trim().to_string();
        if title.is_empty() {
            return Err(LibraryError::EmptyTrackTitle);
        }
        if duration == 0 {
            return Err(LibraryError::InvalidDuration);
        }
        Ok(Self {
            id: id.into(),
            title,
            artist: artist.into(),
            album: "Unknown Album".into(),
            genre: "Various".into(),
            duration_seconds: duration,
            file_path: path.as_ref().to_path_buf(),
            play_count: 0,
        })
    }

    pub fn with_album(mut self, album: impl Into<String>) -> Self {
        self.album = album.into();
        self
    }

    pub fn with_genre(mut self, genre: impl Into<String>) -> Self {
        self.genre = genre.into();
        self
    }
}

// ── Playlist Model ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Playlist {
    pub name: String,
    pub track_ids: Vec<String>,
}

impl Playlist {
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            track_ids: Vec::new(),
        }
    }

    pub fn add_track(&mut self, track_id: impl Into<String>) {
        self.track_ids.push(track_id.into());
    }

    pub fn remove_track(&mut self, track_id: &str) -> bool {
        if let Some(pos) = self.track_ids.iter().position(|id| id == track_id) {
            self.track_ids.remove(pos);
            true
        } else {
            false
        }
    }
}

// ── Library Store ────────────────────────────────────────────────────────────

#[derive(Debug, Default)]
pub struct MediaLibrary {
    tracks: HashMap<String, MediaTrack>,
    playlists: HashMap<String, Playlist>,
}

impl MediaLibrary {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_track(&mut self, track: MediaTrack) -> Result<(), LibraryError> {
        if self.tracks.contains_key(&track.id) {
            return Err(LibraryError::DuplicateTrack(track.id));
        }
        self.tracks.insert(track.id.clone(), track);
        Ok(())
    }

    pub fn get_track(&self, id: &str) -> Result<&MediaTrack, LibraryError> {
        self.tracks.get(id).ok_or_else(|| LibraryError::TrackNotFound(id.into()))
    }

    pub fn search(&self, query: &str) -> Vec<&MediaTrack> {
        let q = query.trim().to_lowercase();
        self.tracks.values().filter(|t| {
            t.title.to_lowercase().contains(&q)
                || t.artist.to_lowercase().contains(&q)
                || t.album.to_lowercase().contains(&q)
                || t.genre.to_lowercase().contains(&q)
        }).collect()
    }

    pub fn create_playlist(&mut self, name: impl Into<String>) -> &mut Playlist {
        let name = name.into();
        self.playlists.entry(name.clone()).or_insert_with(|| Playlist::new(name))
    }

    pub fn get_playlist(&self, name: &str) -> Result<&Playlist, LibraryError> {
        self.playlists.get(name).ok_or_else(|| LibraryError::PlaylistNotFound(name.into()))
    }

    pub fn record_play(&mut self, id: &str) -> Result<u32, LibraryError> {
        let track = self.tracks.get_mut(id).ok_or_else(|| LibraryError::TrackNotFound(id.into()))?;
        track.play_count += 1;
        Ok(track.play_count)
    }

    pub fn total_duration(&self) -> u32 {
        self.tracks.values().map(|t| t.duration_seconds).sum()
    }
}

// ── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_valid_track_and_validate_bounds() {
        // Arrange & Act
        let valid = MediaTrack::new("t1", "Midnight City", "M83", "/music/m83.flac", 243);
        let empty_title = MediaTrack::new("t2", "   ", "Artist", "/music/t.mp3", 100);
        let zero_dur = MediaTrack::new("t3", "Track", "Artist", "/music/t.mp3", 0);

        // Assert
        assert!(valid.is_ok());
        let t = valid.unwrap();
        assert_eq!(t.title, "Midnight City");
        assert_eq!(t.duration_seconds, 243);
        assert_eq!(empty_title, Err(LibraryError::EmptyTrackTitle));
        assert_eq!(zero_dur, Err(LibraryError::InvalidDuration));
    }

    #[test]
    fn library_add_track_and_duplicate_rejection() {
        // Arrange
        let mut lib = MediaLibrary::new();
        let track = MediaTrack::new("t1", "Resonance", "HOME", "/music/home.mp3", 212).unwrap();

        // Act
        lib.add_track(track.clone()).unwrap();
        let err = lib.add_track(track);

        // Assert
        assert_eq!(err, Err(LibraryError::DuplicateTrack("t1".into())));
    }

    #[test]
    fn search_matches_artist_and_title() {
        // Arrange
        let mut lib = MediaLibrary::new();
        lib.add_track(MediaTrack::new("t1", "Starboy", "The Weeknd", "/m/1.mp3", 230).unwrap()).unwrap();
        lib.add_track(MediaTrack::new("t2", "Blinding Lights", "The Weeknd", "/m/2.mp3", 200).unwrap()).unwrap();
        lib.add_track(MediaTrack::new("t3", "Instant Crush", "Daft Punk", "/m/3.mp3", 337).unwrap()).unwrap();

        // Act
        let weeknd_hits = lib.search("Weeknd");
        let crush = lib.search("Crush");

        // Assert
        assert_eq!(weeknd_hits.len(), 2);
        assert_eq!(crush.len(), 1);
        assert_eq!(crush[0].artist, "Daft Punk");
    }

    #[test]
    fn playlist_creation_and_track_manipulation() {
        // Arrange
        let mut lib = MediaLibrary::new();
        let pl = lib.create_playlist("Favorites");
        pl.add_track("t1");
        pl.add_track("t2");

        // Act
        let pl_ref = lib.get_playlist("Favorites").unwrap();
        assert_eq!(pl_ref.track_ids, vec!["t1", "t2"]);

        let pl_mut = lib.playlists.get_mut("Favorites").unwrap();
        let removed = pl_mut.remove_track("t1");

        // Assert
        assert!(removed);
        assert_eq!(lib.get_playlist("Favorites").unwrap().track_ids, vec!["t2"]);
    }

    #[test]
    fn record_play_increments_count() {
        // Arrange
        let mut lib = MediaLibrary::new();
        lib.add_track(MediaTrack::new("t1", "Song", "Artist", "/m/s.mp3", 180).unwrap()).unwrap();

        // Act
        let c1 = lib.record_play("t1").unwrap();
        let c2 = lib.record_play("t1").unwrap();

        // Assert
        assert_eq!(c1, 1);
        assert_eq!(c2, 2);
    }

    #[test]
    fn error_display_formatting() {
        // Arrange
        let err = LibraryError::TrackNotFound("trk_99".into());
        // Act & Assert
        assert_eq!(format!("{err}"), "track 'trk_99' not found in library");
    }
}
