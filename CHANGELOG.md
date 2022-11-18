# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

Nothing currently!

## v0.4.1 - 2022-11-18

### Changed

* The `FourChan` class will no longer output any warnings when 4chan's pages for a given board have
  been exhausted by the `get_threads()` generator (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.4.0 - 2022-11-16

### Added

* The `FourChan` class now supports the optional exception-oriented arguments
  `raise_http_exceptions` and `raise_parsing_exceptions` (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))
* There are now integration tests in the project that will actually connect to 4chan instead of
  relying on mocks (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* Added project configuration for using `mypy` to statically type-check code during development and
  in the GitHub Actions pipeline (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* Implemented proper typing throughout the source code and added a `py.typed` file per PEP 561 (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Changed

* The `Thread` class's `board` field will now always feature the "sanitized" version of the board
  (e.g. `a` instead of `/a/`, `/a`, or `a/`) (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* The `ratelimit` module was replaced by the `pyrate-limiter` module within the internal request
  throttler (by [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.5 - 2022-11-08

### Added

* Added support for Python 3.11 to the pipeline and project configuration (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.4 - 2022-10-12

### Changed

* The author email address in the wheel's metadata is now set to a real email address (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.3 - 2022-08-05

### Added

* `pychan` now supports Python 3.9 in addition to Python 3.10+ (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.2 - 2022-08-05

### Added

* The `Post` model now includes replies to the given post in a `replies` field (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.1 - 2022-08-04

### Fixed

* The `get_threads()` method will no longer return duplicate threads, even when waiting long periods
  of time between `yield`s (by [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.3.0 - 2022-07-31

### Added

* Implemented the `get_archived_threads()` method (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Changed

* Changed the `stickied` and `closed` fields on the `Thread` model to `is_stickied` and `is_closed`
  (by [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.2.3 - 2022-07-30

### Added

* The `FourChan`, `LogLevel`, and `PychanLogger` entities can now be imported directly from `pychan`
  (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* Added the `name` and `is_moderator` fields to the `Poster` model (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Changed

* The `poster` field on the `Post` model is no longer optional (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.2.2 - 2022-07-30

### Added

* The `File` model now includes the file's size and dimensions (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))
* Added more logging to the `FourChan` class (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Changed

* All methods in the `FourChan` class now properly handle "unparsable" boards (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.2.1 - 2022-07-30

### Added

* The `Post` model now includes the post's timestamp in the `timestamp` field (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))
* The `Thread` model now has `stickied` and `closed` boolean fields (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))
* Created the `Poster` model and updated the `Post` model to use it (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Fixed

* Fixed thread titles being truncated and ellipsized (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.2.0 - 2022-07-29

### Added

* Implemented the `search()` method, which leverages 4chan's native search functionality internally
  (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* Added docstrings to all user-facing functions (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Changed

* Changed the `get_all_threads_for_board()` method name to `get_threads()` (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

### Removed

* Removed the opinionated `get_all_threads()` method to simplify the code base and keep its scope
  more appropriate for its desired intent (by [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.1.1 - 2022-07-27

### Changed

* The `File` model's `name` field will no longer ever be `None` (to correspond to 4chan's real
  behavior) (by [@cooperwalbrun](https://github.com/cooperwalbrun))

### Fixed

* Fixed file names not being properly discovered on posts from the `get_posts()` operation (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))

## v0.1.0 - 2022-07-27

### Added

* Created the project (by [@cooperwalbrun](https://github.com/cooperwalbrun))
* Implemented the initial functionality for fetching threads, posts, and boards (by
  [@cooperwalbrun](https://github.com/cooperwalbrun))
