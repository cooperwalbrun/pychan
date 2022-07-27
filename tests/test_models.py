from pychan.models import Thread, Post, File


def test_thread_equality() -> None:
    t1 = Thread("b", 1337)
    t2 = Thread("b", 1338)
    t3 = Thread("int", 1337)
    assert t1 == t1
    assert t1 != t2
    assert t1 != t3

    # Test comparisons with non-Thread data types
    p1 = Post(t1, 1337, "test")
    f1 = File("test")
    assert t1 != p1
    assert t1 != f1


def test_post_equality() -> None:
    t1 = Thread("b", 1337)
    t2 = Thread("b", 1338)
    p1 = Post(t1, 1337, "test")
    p2 = Post(t1, 1338, "test")
    p3 = Post(t2, 1337, "test")
    assert p1 == p1
    assert p1 != p2
    assert p1 != p3

    # Test comparisons with non-Post data types
    f1 = File("test")
    assert p1 != t1
    assert p1 != f1


def test_file_equality() -> None:
    f1 = File("test")
    f2 = File("test", name="test")
    f3 = File("test2")
    assert f1 == f1
    assert f1 == f2
    assert f1 != f3

    # Test comparisons with non-File data types
    t1 = Thread("b", 1337)
    p1 = Post(t1, 1337, "test")
    assert f1 != t1
    assert f1 != p1


def test_serialization() -> None:
    for text in [None, "test"]:
        thread = Thread("b", 1337, title=text)
        assert tuple(thread) == ("b", 1337, text)

        file = File("test", name=text)
        assert tuple(file) == ("test", text)

        post = Post(thread, 1337, "test", poster_id=text)
        assert tuple(post) == (thread.board, thread.number, 1337, "test", False, text, None)

        post = Post(thread, 1337, "test", poster_id=text, file=file)
        assert tuple(post) == (thread.board, thread.number, 1337, "test", False, text, file.url)
