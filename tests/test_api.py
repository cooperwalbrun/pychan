import itertools
import os

import responses

from pychan.api import FourChan
from pychan.models import Thread, Post, File


@responses.activate
def test_get_boards() -> None:
    fourchan = FourChan()

    with open(f"{os.path.dirname(__file__)}/html/search_page.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(responses.GET, "https://boards.4channel.org/search", status=200, body=test_data)
    boards = fourchan.get_boards()

    assert "tv" in boards
    assert "b" in boards
    assert len(boards) > 20
    assert "f" not in boards  # Random blacklisted board


@responses.activate
def test_get_threads() -> None:
    fourchan = FourChan()
    board = "n"
    fourchan.get_boards = lambda: [board]

    with open(f"{os.path.dirname(__file__)}/html/n_threads.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET, url=f"https://boards.4channel.org/{board}", status=200, body=test_data
    )

    for method in [fourchan.get_all_threads, lambda: fourchan.get_threads_for_board(board)]:
        expected_first_5_threads = [
            Thread(board, 1808861),
            Thread(board, 1813725, title="/bqg/ Bike Questions General"),
            Thread(board, 1808469),
            Thread(board, 1802381),
            Thread(board, 1804964, title="post your bike threda - /pybt/(...)")
        ]
        actual_first_5_threads = list(itertools.islice(method(), 5))
        for i, thread in enumerate(expected_first_5_threads):
            assert tuple(thread) == tuple(actual_first_5_threads[i])


def test_get_threads_http_errors() -> None:
    fourchan = FourChan()
    fourchan._request_throttle = lambda: None
    board = "n"
    fourchan.get_boards = lambda: [board]

    @responses.activate
    def helper(status: int) -> None:
        responses.add(responses.GET, url=f"https://boards.4channel.org/{board}", status=status)
        for i in range(1, 10):
            responses.add(
                responses.GET, url=f"https://boards.4channel.org/{board}/{i + 1}", status=status
            )

        for method in [fourchan.get_all_threads, lambda: fourchan.get_threads_for_board(board)]:
            actual = list(method())
            assert len(actual) == 0

    helper(403)
    helper(404)
    helper(500)


@responses.activate
def test_get_posts() -> None:
    fourchan = FourChan()

    with open(f"{os.path.dirname(__file__)}/html/pol_thread_posts.html", "r",
              encoding="utf-8") as file:
        test_data = file.read()

    thread = Thread("pol", 388462123, title="No.1 Hitler movie in Germany?")

    responses.add(
        responses.GET,
        f"https://boards.4channel.org/{thread.board}/thread/{thread.number}/",
        status=200,
        body=test_data
    )

    expected_posts = [
        Post(
            thread,
            388462123,
            "Apparently this movie smashed German box office records, and all the dialogue is ..NOT.. scripted.",
            is_original_post=True,
            poster_id="BYagKQXI",
            file=File(
                "https://i.4cdn.org/pol/1658892700380132.jpg", name="hitler_miss_kromier.jpg"
            )
        ),
        Post(thread, 388462302, ">>388462123\nwhat movie?", poster_id="yzu2QJHE"),
        Post(
            thread,
            388462314,
            ">>388462123\nFunny movie but there was agenda with this film",
            poster_id="xF49FJaT"
        ),
        Post(thread, 388462450, ">>388462302\nLook who's back.", poster_id="e8uCKNk1")
    ]
    actual_posts = list(fourchan.get_posts(thread))
    for i, post in enumerate(expected_posts):
        assert tuple(post) == tuple(actual_posts[i])
        assert post.file == actual_posts[i].file


def test_get_posts_http_errors() -> None:
    fourchan = FourChan()
    fourchan._request_throttle = lambda: None
    board = "n"
    fourchan.get_boards = lambda: [board]

    thread = Thread("pol", 388462123, title="No.1 Hitler movie in Germany?")

    @responses.activate
    def helper(status: int) -> None:
        responses.add(
            responses.GET,
            f"https://boards.4channel.org/{thread.board}/thread/{thread.number}/",
            status=status,
        )

        actual = list(fourchan.get_posts(thread))
        assert len(actual) == 0

    helper(403)
    helper(404)
    helper(500)
