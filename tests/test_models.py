import copy

from pychan.models import Thread, Post, File


def test_thread_equality() -> None:
    t1 = Thread("b", 1337)
    t2 = Thread("b", 1338)
    t3 = Thread("int", 1337)
    assert t1 == t1
    assert t1 != t2
    assert t1 != t3

    # Test comparisons with non-Thread data types
    post = Post(t1, 1337, "test")
    file = File("test", "test")
    assert t1 != post
    assert t1 != file


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
    file = File("test", "test")
    assert p1 != t1
    assert p1 != file


def test_file_equality() -> None:
    f1 = File("test", "test")
    f2 = File("test", "test2")
    f3 = File("test2", "test")
    assert f1 == f1
    assert f1 == f2
    assert f1 != f3

    # Test comparisons with non-File data types
    thread = Thread("b", 1337)
    post = Post(thread, 1337, "test")
    assert f1 != thread
    assert f1 != post


def test_serialization() -> None:
    for text in [None, "test"]:
        thread = Thread("b", 1337, title=text)
        assert tuple(thread) == ("b", 1337, text)

        file = File("test", text)
        assert tuple(file) == ("test", text)

        post = Post(thread, 1337, "test", poster_id=text)
        assert tuple(post) == (thread.board, thread.number, 1337, "test", False, text, None)

        post = Post(thread, 1337, "test", poster_id=text, file=file)
        assert tuple(post) == (thread.board, thread.number, 1337, "test", False, text, file.url)


def test_copying() -> None:
    thread = Thread("b", 1337, title="test")
    thread_copy = copy.copy(thread)
    thread_deepcopy = copy.deepcopy(thread)
    assert thread == thread_copy == thread_deepcopy
    assert thread is not thread_copy
    assert thread is not thread_deepcopy

    file = File("test", name="test")
    file_copy = copy.copy(file)
    file_deepcopy = copy.deepcopy(file)
    assert file == file_copy == file_deepcopy
    assert file is not file_copy
    assert file is not file_deepcopy

    post = Post(thread, 1337, "test", poster_id="test")
    post_copy = copy.copy(post)
    post_deepcopy = copy.deepcopy(post)
    assert post == post_copy == post_deepcopy
    assert post is not post_copy
    assert post is not post_deepcopy
    assert post.thread == post_copy.thread == post_deepcopy.thread
    assert post.thread is post_copy.thread
    assert post.thread is not post_deepcopy.thread
