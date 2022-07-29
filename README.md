# pychan ![master](https://github.com/cooperwalbrun/pychan/workflows/master/badge.svg) ![PyPI](https://img.shields.io/pypi/v/pychan) [![codecov](https://codecov.io/gh/cooperwalbrun/pychan/branch/master/graph/badge.svg?token=BJEJOMIYWY)](https://codecov.io/gh/cooperwalbrun/pychan)

1. [Overview](#overview)
2. [Installation](#installation)
3. [Usage](#usage)
   1. [General Notes](#general-notes)
   2. [Setup](#setup)
   3. [Data Available on pychan's Models](#data-available-on-pychans-models)
   4. [Iterating Over Threads](#iterating-over-threads)
   5. [Search 4chan](#search-4chan)
   6. [Get All Boards](#get-all-boards)
   7. [Fetch Posts for a Specific Thread](#fetch-posts-for-a-specific-thread)
4. [Contributing](#contributing)

## Overview

`pychan` is a Python client for interacting with 4chan. 4chan does not have an official API, and
attempts to implement one by third parties have tended to languish, so instead, this library
provides abstractions over interacting with (scraping) 4chan directly. `pychan` is object-oriented
and its implementation is lazy where reasonable (using Python Generators) in order to optimize
performance and minimize superfluous blocking I/O operations.

## Installation

If you have Python >=3.10 and <4.0 installed, `pychan` can be installed from PyPI using
something like

```bash
pip install pychan
```

## Usage

### General Notes

All 4chan interactions are throttled internally by sleeping the executing thread. If you execute
`pychan` in a multithreaded way, you will not get the benefits of this throttling. `pychan` does not
take responsibility for the consequences of excessive HTTP requests in such cases.

For all thread-level iteration shown below, the generators returned  will maintain internal state
about which page of 4chan you are currently on. Threads are fetched one page at a time up to page 10
(which is the highest page at which 4chan renders threads for any given board). Once page 10 is
reached internally by the generator, it stops returning threads.

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

The rest of the examples in this `README` assume that you have already created an instance of the
`FourChan` class as shown above.

### Data Available on pychan's Models

The following table enumerates all the kinds of data that are available on the various models used
by this library.

| Entity | Field | Example Value(s) |
| ------ | ----- | ---------------- |
| `pychan.models.Thread` | `thread.board` | `"b"`, `"int"`
| `pychan.models.Thread` | `thread.number` | `882774935`, `168484869`
| `pychan.models.Thread` | `thread.title` | `None`, `"YLYL thread"`
| `pychan.models.Post` | `post.thread` | `pychan.models.Thread`
| `pychan.models.Post` | `post.number` | `882774935`, `882774974`
| `pychan.models.Post` | `post.is_original_post` | `True`, `False`
| `pychan.models.Post` | `post.poster_id` | `None`, `"BYagKQXI"`
| `pychan.models.Post` | `post.file` | `None`, `pychan.models.File`
| `pychan.models.File` | `file.url` | `"https://i.4cdn.org/pol/1658892700380132.jpg"`
| `pychan.models.File` | `file.name` | `"wojak.jpg"`, `"i feel alone.jpg"`

### Iterating Over Threads

```python
# Iterate over all threads in /b/ lazily (Python Generator)
for thread in fourchan.get_threads("b"):
    # Iterate over all posts in each thread
    for post in fourchan.get_posts(thread):
        # Do stuff with the post
        print(post.text)
```

### Search 4chan

```python
# Iterate over all threads returned in the search results lazily (Python Generator)
for thread in fourchan.search(board="b", text="ylyl"):
    # The thread object is the same class as the one returned by get_threads()
    ...
```

### Get All Boards

This function dynamically fetches boards from 4chan at call time.

```python
boards = fourchan.get_boards()
# Sample return value:
# ['a', 'b', 'c', 'd', 'e', 'g', 'gif', 'h', 'hr', 'k', 'm', 'o', 'p', 'r', 's', 't', 'u', 'v', 'vg', 'vm', 'vmg', 'vr', 'vrpg', 'vst', 'w', 'wg', 'i', 'ic', 'r9k', 's4s', 'vip', 'qa', 'cm', 'hm', 'lgbt', 'y', '3', 'aco', 'adv', 'an', 'bant', 'biz', 'cgl', 'ck', 'co', 'diy', 'fa', 'fit', 'gd', 'hc', 'his', 'int', 'jp', 'lit', 'mlp', 'mu', 'n', 'news', 'out', 'po', 'pol', 'pw', 'qst', 'sci', 'soc', 'sp', 'tg', 'toy', 'trv', 'tv', 'vp', 'vt', 'wsg', 'wsr', 'x', 'xs']
```

### Fetch Posts for a Specific Thread

>Warning: this will NOT work if the thread has become "stale" in 4chan and has entered an "archived"
>state. This happens to almost all threads after they have gone inactive long enough. Therefore, it
>is recommended to use the iterating-based functionality shown above instead of doing what is shown
>below.

```python
from pychan.models import Thread

# Instantiate a Thread instance with which to query for posts
thread = Thread("int", 168484869)

# Note: the thread contained within the returned posts will have a title if the thread had a title,
# regardless of whether you provided the title above - pychan will "auto-discover" the title and
# include it in the post models
posts = fourchan.get_posts(thread)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for developer-oriented information.
