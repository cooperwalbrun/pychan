import os
from datetime import timezone, datetime
from urllib import parse

import pytest
import responses

from pychan import FourChan, LogLevel, PychanLogger
from pychan.models import Thread, Post, File, Poster


@pytest.fixture
def fourchan() -> FourChan:
    fourchan = FourChan(PychanLogger(LogLevel.DEBUG))
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
    board = "pol"

    with open(f"{os.path.dirname(__file__)}/html/pol_threads.html", "r", encoding="utf-8") as file:
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
        Thread(
            board,
            124205675,
            title="Welcome to /pol/ - Politically Incorrect",
            is_stickied=True,
            is_closed=True
        ),
        Thread(board, 259848258, is_stickied=True, is_closed=True),
        Thread(board, 388895332, title="What is her end game?"),
        Thread(board, 388890794, title="I really truly deeply don't get it"),
        Thread(board, 388890337, title="/tg/ - Taiwan General"),
        Thread(board, 388895822),
        Thread(board, 388895815),
        Thread(board, 388893920, title="What exactly is the problem with being trans?"),
        Thread(board, 388894042, title="Monkeypox General"),
        Thread(board, 388883227, title="Crusades are underrated"),
        Thread(board, 388892393, title="Doesnt eat Insects but eats Honey, hypocrisy?"),
        Thread(board, 388895633),
        Thread(board, 388895430),
        Thread(board, 388895780),
        Thread(board, 388894935),
        Thread(
            board,
            388871008,
            title="/MOG/ - Monkeypox Outbreak General #128 - First Deaths Brazil/Spain"
        ),
        Thread(board, 388892859, title="Detransitioning"),
        Thread(board, 388894121),
        Thread(board, 388890979, title="/chug/ - Comfy Happening in Ukraine General #4740"),
        Thread(board, 388891424)
    ]
    actual = list(fourchan.get_threads(board))
    assert len(expected) == len(actual)
    for i, thread in enumerate(expected):
        assert tuple(thread) == tuple(actual[i])


def test_get_thread_unparsable_board(fourchan: FourChan) -> None:
    assert len(list(fourchan.get_threads("f"))) == 0


def test_get_threads_http_errors(fourchan: FourChan) -> None:
    board = "pol"

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
def test_get_archived_threads(fourchan: FourChan) -> None:
    board = "pol"

    with open(f"{os.path.dirname(__file__)}/html/pol_archive.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET, url=f"https://boards.4chan.org/{board}/archive", status=200, body=test_data
    )

    threads = fourchan.get_archived_threads(board)
    assert len(threads) == 3000
    for thread in threads:
        assert thread.title is not None
        assert thread.is_archived


def test_get_archived_threads_http_errors(fourchan: FourChan) -> None:
    board = "pol"
    url = f"https://boards.4chan.org/{board}/archive"

    @responses.activate
    def helper(status: int) -> None:
        # The method should only attempt to fetch the first page, because the generator should
        # terminate once it reaches a page that was not retrievable
        responses.add(responses.GET, url=url, status=status)

        actual = list(fourchan.get_archived_threads(board))
        assert len(actual) == 0
        responses.assert_call_count(url=url, count=1)

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

    reply1 = Post(
        processed_thread,
        388462302,
        datetime.fromtimestamp(1658892803, timezone.utc),
        Poster("Anonymous", id="yzu2QJHE", flag="United States"),
        ">>388462123\n>>388462123\n>>388462123\nwhat movie?"
    )
    reply2 = Post(
        processed_thread,
        388462314,
        datetime.fromtimestamp(1658892808, timezone.utc),
        Poster("Anonymous", id="xF49FJaT", flag="United States"),
        ">>388462123\nFunny movie but there was agenda with this film"
    )

    expected = [
        Post(
            processed_thread,
            388462123,
            datetime.fromtimestamp(1658892700, timezone.utc),
            Poster("Anonymous", id="BYagKQXI", flag="United States"),
            "Apparently this movie smashed German box office records, and all the dialogue is ..NOT.. scripted.",
            is_original_post=True,
            file=File(
                "https://i.4cdn.org/pol/1658892700380132.jpg",
                "hitler miss kromier.jpg",
                "106 KB", (800, 600)
            ),
            replies=[reply1, reply2]
        ),
        reply1,
        reply2,
        Post(
            processed_thread,
            388462450,
            datetime.fromtimestamp(1658892887, timezone.utc),
            Poster("Anonymous", id="e8uCKNk1", flag="Canada"),
            ">>389829992 →\nLook who's back."
        )
    ]
    actual = fourchan.get_posts(thread)
    assert len(expected) == len(actual)
    for i, post in enumerate(expected):
        assert tuple(post) == tuple(actual[i])


@responses.activate
def test_get_post_from_moderator(fourchan: FourChan) -> None:
    with open(f"{os.path.dirname(__file__)}/html/pol_moderator_post.html", "r",
              encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET,
        f"https://boards.4channel.org/pol/thread/259848258/",
        status=200,
        body=test_data
    )

    actual = fourchan.get_posts(Thread("pol", 259848258))
    assert len(actual) == 1
    assert actual[0].poster.name == "Anonymous"
    assert actual[0].poster.is_moderator


def test_get_posts_unparsable_board(fourchan: FourChan) -> None:
    thread = Thread("f", 0)
    assert len(fourchan.get_posts(thread)) == 0


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


def test_search_unparsable_board(fourchan: FourChan) -> None:
    assert len(list(fourchan.search(board="f", text=""))) == 0


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
