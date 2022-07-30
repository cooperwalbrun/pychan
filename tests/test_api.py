import os
from urllib import parse

import pytest
import responses

from pychan.api import FourChan
from pychan.logger import LogLevel, PychanLogger
from pychan.models import Thread, Post, File


@pytest.fixture
def fourchan() -> FourChan:
    fourchan = FourChan(PychanLogger(LogLevel.INFO))
    fourchan._request_throttle = lambda: None
    return fourchan


@responses.activate
def test_get_boards(fourchan: FourChan) -> None:
    with open(f"{os.path.dirname(__file__)}/html/search_page.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(responses.GET, "https://boards.4channel.org/search", status=200, body=test_data)
    boards = fourchan.get_boards()

    assert "tv" in boards
    assert "b" in boards
    assert len(boards) > 20
    assert "f" not in boards  # Random blacklisted board


@responses.activate
def test_get_threads(fourchan: FourChan) -> None:
    board = "n"

    with open(f"{os.path.dirname(__file__)}/html/n_threads.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET, url=f"https://boards.4channel.org/{board}", status=200, body=test_data
    )
    responses.add(
        # This response terminates the iteration within the generator (normally a 404 would not
        # happen until page 11, but for testing purposes we do it on page 2)
        responses.GET,
        url=f"https://boards.4channel.org/{board}/2",
        status=404
    )

    expected = [
        Thread(board, 1808861),
        Thread(board, 1813725, title="/bqg/ Bike Questions General"),
        Thread(board, 1808469),
        Thread(board, 1802381),
        Thread(board, 1804964, title="post your bike threda - /pybt/(...)"),
        Thread(board, 1802146),
        Thread(board, 1812284),
        Thread(board, 1807310, title="/EMC/ - Electric Mobility Gene(...)"),
        Thread(board, 1811932),
        Thread(board, 1804716, title="daily ride thread - /drt/ 2.0 (...)"),
        Thread(board, 1805194, title="I still dont get why we dont t(...)"),
        Thread(board, 1813843),
        Thread(board, 1813856),
        Thread(board, 1813713, title="Foam tire inserts"),
        Thread(board, 1813946)
    ]
    actual = list(fourchan.get_threads(board))
    assert len(expected) == len(actual)
    for i, thread in enumerate(expected):
        assert tuple(thread) == tuple(actual[i])


def test_get_threads_http_errors(fourchan: FourChan) -> None:
    board = "n"

    @responses.activate
    def helper(status: int) -> None:
        # The method should only attempt to fetch the first page, because the generator should
        # terminate once it reaches a page that was not retrievable
        responses.add(responses.GET, url=f"https://boards.4channel.org/{board}", status=status)

        actual = list(fourchan.get_threads(board))
        assert len(actual) == 0
        responses.assert_call_count(url=f"https://boards.4channel.org/{board}", count=1)
        responses.assert_call_count(url=f"https://boards.4channel.org/{board}/2", count=0)

    helper(403)
    helper(404)
    helper(500)


@responses.activate
def test_get_posts(fourchan: FourChan) -> None:
    with open(f"{os.path.dirname(__file__)}/html/pol_thread_posts.html", "r",
              encoding="utf-8") as file:
        test_data = file.read()

    # The two thread objects below should be representations of the same thread where the first is
    # the user-specified version of the thread and the latter is the one that pychan automatically
    # assembles based on 4chan remote data
    thread = Thread("/Pol ", 388462123)
    processed_thread = Thread("pol", 388462123, title="No.1 Hitler movie in Germany?")

    responses.add(
        responses.GET,
        f"https://boards.4channel.org/{processed_thread.board}/thread/{processed_thread.number}/",
        status=200,
        body=test_data
    )

    expected_posts = [
        Post(
            processed_thread,
            388462123,
            "Apparently this movie smashed German box office records, and all the dialogue is ..NOT.. scripted.",
            is_original_post=True,
            poster_id="BYagKQXI",
            file=File(
                "https://i.4cdn.org/pol/1658892700380132.jpg", name="hitler miss kromier.jpg"
            )
        ),
        Post(processed_thread, 388462302, ">>388462123\nwhat movie?", poster_id="yzu2QJHE"),
        Post(
            processed_thread,
            388462314,
            ">>388462123\nFunny movie but there was agenda with this film",
            poster_id="xF49FJaT"
        ),
        Post(processed_thread, 388462450, ">>388462302\nLook who's back.", poster_id="e8uCKNk1")
    ]
    actual_posts = fourchan.get_posts(thread)
    for i, post in enumerate(expected_posts):
        assert tuple(post) == tuple(actual_posts[i])
        assert tuple(post.thread) == tuple(actual_posts[i].thread)
        if post.file is None:
            assert post.file == actual_posts[i].file
        else:
            assert tuple(post.file) == tuple(actual_posts[i].file)


def test_get_posts_http_errors(fourchan: FourChan) -> None:
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


@responses.activate
def test_search(fourchan: FourChan) -> None:
    with open(f"{os.path.dirname(__file__)}/json/search_results.json", "r",
              encoding="utf-8") as file:
        test_data = file.read()

    board = "news"
    search_text = "democrat"

    responses.add(
        responses.GET,
        f"https://find.4channel.org/api?q={parse.quote(search_text)}&b={board}&o=0",
        status=200,
        body=test_data
    )
    responses.add(
        # This response terminates the iteration within the generator (the generator halts when it
        # encounters a "page" of results which have all already been seen, so we simply mock the
        # results on the second "page" as being identical to the results on the first "page" above)
        responses.GET,
        f"https://find.4channel.org/api?q={parse.quote(search_text)}&b={board}&o=10",
        status=200,
        body=test_data
    )

    expected = [
        Thread(board, 1077597, title="Democrat corruption and grooming."),
        Thread(board, 1077143, title="In Reality, All The Actual Groomers Are Republicans")
    ]
    actual = list(fourchan.search(board=board, text=search_text))
    assert len(expected) == len(actual)
    for i, thread in enumerate(expected):
        assert tuple(thread) == tuple(actual[i])


def test_search_http_errors(fourchan: FourChan) -> None:
    board = "news"
    search_text = "democrat"

    @responses.activate
    def helper(status: int) -> None:
        responses.add(
            responses.GET,
            f"https://find.4channel.org/api?q={parse.quote(search_text)}&b={board}&o=0",
            status=status,
        )

        actual = list(fourchan.search(board=board, text=search_text))
        assert len(actual) == 0

    helper(403)
    helper(404)
    helper(500)
