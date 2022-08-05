import copy
from datetime import datetime, timezone

from pychan.models import Thread, Post, File, Poster

_TIMESTAMP = datetime.fromtimestamp(0, timezone.utc)


def test_thread_equality() -> None:
    t1 = Thread("b", 1337)
    t2 = Thread("b", 1338)
    t3 = Thread("int", 1337)
    assert t1 == t1
    assert t1 != t2
    assert t1 != t3

    # Test comparisons with non-Thread data types
    poster = Poster("test")
    post = Post(t1, 1337, _TIMESTAMP, poster, "test")
    file = File("test", "test", "1337 KB", (1920, 1080))
    assert t1 != post
    assert t1 != file
    assert t1 != poster


def test_post_equality() -> None:
    t1 = Thread("b", 1337)
    t2 = Thread("b", 1338)
    poster = Poster("test")
    p1 = Post(t1, 1337, _TIMESTAMP, poster, "test")
    p2 = Post(t1, 1338, _TIMESTAMP, poster, "test")
    p3 = Post(t2, 1337, _TIMESTAMP, poster, "test")
    assert p1 == p1
    assert p1 != p2
    assert p1 != p3

    # Test comparisons with non-Post data types
    file = File("test", "test", "1337 KB", (1920, 1080))
    assert p1 != t1
    assert p1 != file
    assert p1 != poster


def test_file_equality() -> None:
    f1 = File("test", "test", "1337 KB", (1920, 1080))
    f2 = File("test", "test2", "1337 KB", (1920, 1080))
    f3 = File("test2", "test", "1337 KB", (1920, 1080))
    assert f1 == f1
    assert f1 == f2
    assert f1 != f3

    # Test comparisons with non-File data types
    thread = Thread("b", 1337)
    poster = Poster("test")
    post = Post(thread, 1337, _TIMESTAMP, poster, "test")
    assert f1 != thread
    assert f1 != post
    assert f1 != poster


def test_poster_equality() -> None:
    p1 = Poster("test")
    p2 = Poster("test", flag="test2")
    p3 = Poster("test", id="test2")
    p4 = Poster("test2")
    assert p1 == p1
    assert p1 == p2
    assert p1 != p3
    assert p1 != p4

    # Test comparisons with non-Poster data types
    thread = Thread("b", 1337)
    post = Post(thread, 1337, _TIMESTAMP, p1, "test")
    file = File("test", "test", "1337 KB", (1920, 1080))
    assert p1 != thread
    assert p1 != post
    assert p1 != file


def test_poster_properties() -> None:
    poster = Poster("test", mod_indicator=False)
    assert poster.is_moderator

    poster = Poster("Anonymous", mod_indicator=False)
    assert not poster.is_moderator

    poster = Poster("Anonymous", mod_indicator=True)
    assert poster.is_moderator


def test_serialization() -> None:
    file = File("test", "test", "1337 KB", (1920, 1080))
    assert tuple(file) == ("test", "test", "1337 KB", (1920, 1080))

    poster = Poster("test")
    assert tuple(poster) == ("test", False, None, None)

    for text in [None, "test"]:
        thread = Thread("b", 1337, title=text)
        assert tuple(thread) == ("b", 1337, text, False, False, False)

        post = Post(thread, 1337, _TIMESTAMP, poster, "test")
        # yapf: disable
        assert tuple(post) == tuple(thread) + (
            1337, _TIMESTAMP,
            poster.name,
            poster._mod_indicator,
            poster.id,
            poster.flag,
            "test",
            False,
            None,
            None,
            None,
            None,
            0
        )
        # yapf: enable

        post = Post(thread, 1337, _TIMESTAMP, poster, "test", file=file)
        assert tuple(post) == tuple(thread) + (
            1337,
            _TIMESTAMP,
            poster.name,
            poster._mod_indicator,
            poster.id,
            poster.flag,
            "test",
            False,
            file.url,
            file.name,
            file.size,
            file.dimensions,
            0
        )


def test_copying() -> None:
    thread = Thread("b", 1337, title="test")
    thread_copy = copy.copy(thread)
    thread_deepcopy = copy.deepcopy(thread)
    assert thread == thread_copy == thread_deepcopy
    assert thread is not thread_copy
    assert thread is not thread_deepcopy

    file = File("test", "test", "1337 KB", (1920, 1080))
    file_copy = copy.copy(file)
    file_deepcopy = copy.deepcopy(file)
    assert file == file_copy == file_deepcopy
    assert file is not file_copy
    assert file is not file_deepcopy

    poster = Poster("test")
    poster_copy = copy.copy(poster)
    poster_deepcopy = copy.deepcopy(poster)
    assert poster == poster_copy == poster_deepcopy
    assert poster is not poster_copy
    assert poster is not poster_deepcopy

    post = Post(thread, 1337, _TIMESTAMP, poster, "test", file=file)
    post_copy = copy.copy(post)
    post_deepcopy = copy.deepcopy(post)
    assert post == post_copy == post_deepcopy
    assert post is not post_copy
    assert post is not post_deepcopy
