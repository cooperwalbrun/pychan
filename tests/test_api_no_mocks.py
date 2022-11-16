import itertools

import pytest

from pychan import FourChan


@pytest.fixture
def fourchan() -> FourChan:
    # Below, we specify raise_*_exceptions=True because we want to raise all exceptions so that our
    # tests fail if anything does not work properly
    return FourChan(raise_http_exceptions=True, raise_parsing_exceptions=True)


def test_get_boards_no_mocks(fourchan: FourChan) -> None:
    boards = fourchan.get_boards()
    assert len(boards) > 10


def test_get_threads_and_get_posts_no_mocks(fourchan: FourChan) -> None:
    # Test fetching threads
    threads = fourchan.get_threads("/a")
    first_ten_threads = list(itertools.islice(threads, 10))
    for thread in first_ten_threads:
        assert thread.number > 0
        assert thread.board == "a"
        assert not thread.is_archived
        if thread.title is not None:
            assert len(thread.title) > 0  # Titles should be None instead of "" when empty

    # Test fetching posts using one of the threads from above
    posts = fourchan.get_posts(first_ten_threads[0])
    assert posts[0].is_original_post  # There will always be at least 1 post (the original post)
    assert posts[0].file is not None  # Original posts must always include a file
    (file_x, file_y) = posts[0].file.dimensions
    assert file_x > 0
    assert file_y > 0
    for post in posts:
        assert post.number > 0
        assert post.thread == first_ten_threads[0]
        assert len(post.text) > 0


def test_get_archived_threads_no_mocks(fourchan: FourChan) -> None:
    threads = fourchan.get_archived_threads("/a/")
    assert len(threads) > 100
    for thread in threads:
        assert thread.number > 0
        assert thread.board == "a"
        assert thread.is_archived
        if thread.title is not None:
            assert len(thread.title) > 0  # Titles should be None instead of "" when empty
