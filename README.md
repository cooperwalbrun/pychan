# pychan ![master](https://github.com/cooperwalbrun/pychan/workflows/master/badge.svg) ![PyPI](https://img.shields.io/pypi/v/pychan) [![codecov](https://codecov.io/gh/cooperwalbrun/pychan/branch/master/graph/badge.svg?token=BJEJOMIYWY)](https://codecov.io/gh/cooperwalbrun/pychan)

1. [Overview](#overview)
2. [Usage](#usage)
   1. [Setup](#setup)
   2. [Iterating](#iterating)
      1. [Single Board](#single-board)
      2. [All Boards](#all-boards)
   3. [Data Available on Threads and Posts](#data-available-on-threads-and-posts)
   4. [Other Features](#other-features)
      1. [Get All Boards](#get-all-boards)
      2. [Fetch Posts for a Specific Thread](#fetch-posts-for-a-specific-thread)
3. [Installation](#installation)
4. [Contributing](#contributing)

## Overview

`pychan` is a Python client for interacting with 4chan. 4chan does not have an official API, and
attempts to implement one have been less maintained than desired, so instead, this library provides
abstractions over interacting with (scraping) 4chan directly. `pychan` is object-oriented and its
implementation is lazy wherever possible (using Python Generators) in order to optimize performance
and minimize unnecessary blocking I/O operations.

## Usage

### Setup

```python
from pychan.api import FourChan
from pychan.logger import LogLevel, PychanLogger

# With all logging disabled (default)
fourchan = FourChan()

# Configure logging explicitly
logger = PychanLogger(LogLevel.INFO)
fourchan = FourChan(logger)
```

### Iterating

For all thread-level iteration, the generators this library returns will maintain internal state
about which page of 4chan you are currently on. Threads are fetched one page at a time, up to page
10 (which is the highest page at which 4chan renders threads for any given board). Once page 10 is
reached internally by the generator, it stops returning threads.

#### Single Board

```python
# Iterate over all threads in /b/ lazily (Python Generator)
for thread in fourchan.get_threads_for_board("b"):
    # Iterate over all posts in each thread
    for post in fourchan.get_posts(thread):
        # Do stuff with the post
        print(post.text)
```

#### All Boards

Boards are visited in random order. For example, this function may perform the following sequence
of operations:

1. Query page 1 of /b/
2. Query page 1 of /pol/
3. Query page 2 of /b/ (because page 1 was visited already)
4. Query page 1 of /int/
5. *(and so on)*

```python
# Iterate over all threads across all boards
for thread in fourchan.get_all_threads():
   # Iterate over all posts in each thread
   for post in fourchan.get_posts(thread):
      # Do stuff with the post
      print(post.text)
```

## Data Available on Threads and Posts

The following table enumerates all the kinds of data that are available on the various models used
by this library.

| Entity | Field | Example Values |
| ------ | ----- | -------------- |
| `pychan.models.Thread` | `thread.board` | `"b"`, `"int"`
| `pychan.models.Thread` | `thread.number` | `882774935`, `168484869`
| `pychan.models.Thread` | `thread.title` | `None`, `"YLYL thread"`
| `pychan.models.Post` | `post.thread` | `pychan.models.Thread`
| `pychan.models.Post` | `post.number` | `882774935`, `882774974`
| `pychan.models.Post` | `post.is_original_post` | `True`, `False`
| `pychan.models.Post` | `post.poster_id` | `None`, `"BYagKQXI"`
| `pychan.models.Post` | `post.file` | `None`, `pychan.models.File`
| `pychan.models.File` | `file.url` | `"https://i.4cdn.org/pol/1658892700380132.jpg"`
| `pychan.models.File` | `file.name` | `None`, `"wojak.jpg"`

### Other Features

#### Get All Boards

This function fetches dynamically from 4chan. It is *not* a hard-coded list within `pychan`.

```python
boards = fourchan.get_boards()
# Sample return value:
# ['a', 'b', 'c', 'd', 'e', 'g', 'gif', 'h', 'hr', 'k', 'm', 'o', 'p', 'r', 's', 't', 'u', 'v', 'vg', 'vm', 'vmg', 'vr', 'vrpg', 'vst', 'w', 'wg', 'i', 'ic', 'r9k', 's4s', 'vip', 'qa', 'cm', 'hm', 'lgbt', 'y', '3', 'aco', 'adv', 'an', 'bant', 'biz', 'cgl', 'ck', 'co', 'diy', 'fa', 'fit', 'gd', 'hc', 'his', 'int', 'jp', 'lit', 'mlp', 'mu', 'n', 'news', 'out', 'po', 'pol', 'pw', 'qst', 'sci', 'soc', 'sp', 'tg', 'toy', 'trv', 'tv', 'vp', 'vt', 'wsg', 'wsr', 'x', 'xs']
```

#### Fetch Posts for a Specific Thread

>Warning: this will NOT work if the thread has become "stale" in 4chan and has entered an "expired"
>or "archived" state. This happens to almost all threads after they have gone inactive long enough.
>Therefore, it is recommended to use the iterating-based functionality shown above instead of doing
>this.

```python
from pychan.models import Thread

thread = Thread("int", 168484869)
posts = fourchan.get_posts(thread)
```

## Installation

If you have Python >=3.10 and <4.0 installed, `pychan` can be installed from PyPI using
something like

```bash
pip install pychan
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for developer-oriented information.
