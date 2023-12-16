import os
from datetime import timezone, datetime
from typing import Callable
from urllib import parse

import pytest
import responses
from requests import HTTPError

from pychan import FourChan, LogLevel, PychanLogger
from pychan.api import _safe_id_parse, ParsingError
from pychan.models import Thread, Post, File, Poster


@pytest.fixture
def fourchan() -> FourChan:
    fourchan = FourChan(
        logger=PychanLogger(LogLevel.DEBUG),
        raise_http_exceptions=True,
        raise_parsing_exceptions=True
    )
    fourchan._throttle_request = lambda: None
    return fourchan


@pytest.fixture
def fourchan_no_raises() -> FourChan:
    fourchan = FourChan(
        logger=PychanLogger(LogLevel.DEBUG),
        raise_http_exceptions=False,
        raise_parsing_exceptions=False
    )
    fourchan._throttle_request = lambda: None
    return fourchan


def test_safe_id_parse() -> None:
    assert _safe_id_parse(None, offset=1) is None
    assert _safe_id_parse("", offset=1) is None
    assert _safe_id_parse("t", offset=1) is None
    assert _safe_id_parse("test", offset=1) is None
    assert _safe_id_parse("t1", offset=1) == 1


def test_parse_error(fourchan: FourChan) -> None:
    with pytest.raises(ParsingError):
        fourchan._parse_error("test")


def test_parse_catalog_json_from_javascript(fourchan: FourChan) -> None:
    # yapf: disable
    tests = {
        'var catalog = {"test": "test"};': {"test": "test"},
        'var catalog = {"t1": "t1"};var x = {"t2": "t2"};': {"t1": "t1"},
        'var x = {"t2": "t2"};var catalog = {"t1": "t1"};': {"t1": "t1"},
        'var catalog = {"te};st": "te};st"};': {"te};st": "te};st"}
    }
    # yapf: enable
    for input, expected_json in tests.items():
        assert fourchan._parse_catalog_json_from_javascript(input) == expected_json


@responses.activate
def test_get_boards(fourchan: FourChan) -> None:
    with open(f"{os.path.dirname(__file__)}/html/pol_catalog.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(responses.GET, "https://boards.4chan.org/pol/catalog", status=200, body=test_data)
    boards = fourchan.get_boards()

    assert "tv" in boards
    assert "b" in boards
    assert len(boards) > 20
    assert "f" not in boards  # Random blacklisted board


@responses.activate
def test_get_threads(fourchan: FourChan) -> None:
    board = "pol"

    with open(f"{os.path.dirname(__file__)}/html/pol_catalog.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET, f"https://boards.4chan.org/{board}/catalog", status=200, body=test_data
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
        Thread(board, 422352356, title="Who is “The Market”?"),
        Thread(board, 422343879, title="ITS OVER"),
        Thread(board, 422321472, title="jewess steals 175 million from chase bank through fraud"),
    ]
    actual = fourchan.get_threads(board)
    assert len(actual) == 202
    for i, thread in enumerate(expected):
        assert tuple(thread) == tuple(actual[i])


def test_get_thread_unparsable_board(fourchan: FourChan) -> None:
    assert len(list(fourchan.get_threads("f"))) == 0


def test_get_threads_http_errors(fourchan: FourChan, fourchan_no_raises: FourChan) -> None:
    board = "pol"

    @responses.activate
    def with_mocks(status: int, function: Callable[[], None]) -> None:
        # The method should only attempt to fetch the first page, because the generator should
        # terminate once it reaches a page that was not retrievable
        responses.add(responses.GET, f"https://boards.4chan.org/{board}/catalog", status=status)
        function()

    def helper_without_raises() -> None:
        actual = list(fourchan_no_raises.get_threads(board))
        assert len(actual) == 0
        responses.assert_call_count(f"https://boards.4chan.org/{board}/catalog", count=1)

    def helper() -> None:
        with pytest.raises(HTTPError):
            fourchan.get_threads(board)

    with_mocks(403, helper_without_raises)
    with_mocks(404, helper_without_raises)
    with_mocks(500, helper_without_raises)
    with_mocks(403, helper)
    with_mocks(404, helper)
    with_mocks(500, helper)


@responses.activate
def test_get_archived_threads(fourchan: FourChan) -> None:
    board = "pol"

    with open(f"{os.path.dirname(__file__)}/html/pol_archive.html", "r", encoding="utf-8") as file:
        test_data = file.read()

    responses.add(
        responses.GET, f"https://boards.4chan.org/{board}/archive", status=200, body=test_data
    )

    threads = fourchan.get_archived_threads(board)
    assert len(threads) == 3000
    for thread in threads:
        assert thread.title is not None
        assert thread.is_archived


def test_get_archived_threads_http_errors(fourchan: FourChan, fourchan_no_raises: FourChan) -> None:
    board = "pol"
    url = f"https://boards.4chan.org/{board}/archive"

    @responses.activate
    def with_mocks(status: int, function: Callable[[], None]) -> None:
        # The method should only attempt to fetch the first page, because the generator should
        # terminate once it reaches a page that was not retrievable
        responses.add(responses.GET, url, status=status)
        function()

    def helper_no_raises() -> None:
        actual = list(fourchan_no_raises.get_archived_threads(board))
        assert len(actual) == 0
        responses.assert_call_count(url, count=1)

    def helper() -> None:
        with pytest.raises(HTTPError):
            fourchan.get_archived_threads(board)

    with_mocks(403, helper_no_raises)
    with_mocks(404, helper_no_raises)
    with_mocks(500, helper_no_raises)
    with_mocks(403, helper)
    with_mocks(404, helper)
    with_mocks(500, helper)


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
        f"https://boards.4chan.org/{processed_thread.board}/thread/{processed_thread.number}/",
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
                "106 KB", (800, 600),
                is_spoiler=False
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
        f"https://boards.4chan.org/pol/thread/259848258/",
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


def test_get_posts_http_errors(fourchan: FourChan, fourchan_no_raises: FourChan) -> None:
    thread = Thread("pol", 388462123, title="No.1 Hitler movie in Germany?")

    @responses.activate
    def with_mocks(status: int, function: Callable[[], None]) -> None:
        responses.add(
            responses.GET,
            f"https://boards.4chan.org/{thread.board}/thread/{thread.number}/",
            status=status,
        )
        function()

    def helper_no_raises() -> None:
        actual = list(fourchan_no_raises.get_posts(thread))
        assert len(actual) == 0

    def helper() -> None:
        with pytest.raises(HTTPError):
            fourchan.get_posts(thread)

    with_mocks(403, helper_no_raises)
    with_mocks(404, helper_no_raises)
    with_mocks(500, helper_no_raises)
    with_mocks(403, helper)
    with_mocks(404, helper)
    with_mocks(500, helper)


def test_search(fourchan_no_raises: FourChan) -> None:
    board = "news"
    search_text = "democrat"

    @responses.activate
    def helper(file_name: str, *, expected_threads: list[Thread]) -> None:
        with open(f"{os.path.dirname(__file__)}/json/{file_name}", "r", encoding="utf-8") as file:
            test_data = file.read()

        responses.add(
            responses.GET,
            f"https://find.4chan.org/api?q={parse.quote(search_text)}&b={board}&o=0",
            status=200,
            body=test_data
        )
        responses.add(
            # This response terminates the iteration within the generator (the generator halts when
            # it encounters a "page" of results which have all already been seen, so we simply mock
            # the results on the second "page" as being identical to the results on the first "page"
            # above)
            responses.GET,
            f"https://find.4chan.org/api?q={parse.quote(search_text)}&b={board}&o=10",
            status=200,
            body=test_data
        )

        actual = list(
            fourchan_no_raises.search(
                board=board, text=search_text, user_agent="test", cloudflare_cookies={}
            )
        )
        assert len(expected_threads) == len(actual)
        for i, thread in enumerate(expected_threads):
            assert tuple(thread) == tuple(actual[i])

    helper(
        "search_results.json",
        expected_threads=[
            Thread(board, 1077597, title="Democrat corruption and grooming."),
            Thread(board, 1077143, title="In Reality, All The Actual Groomers Are Republicans")
        ]
    )
    helper(
        "search_results_unparsable_partial.json",
        expected_threads=[
            Thread(board, 1077143, title="In Reality, All The Actual Groomers Are Republicans")
        ]
    )
    helper("search_results_unparsable_whole.json", expected_threads=[])


def test_search_unparsable_board(fourchan: FourChan) -> None:
    assert len(list(fourchan.get_threads("f"))) == 0


def test_search_http_errors(fourchan: FourChan, fourchan_no_raises: FourChan) -> None:
    board = "news"
    search_text = "democrat"

    @responses.activate
    def with_mocks(status: int, function: Callable[[], None]) -> None:
        responses.add(
            responses.GET,
            f"https://find.4chan.org/api?q={parse.quote(search_text)}&b={board}&o=0",
            status=status,
        )
        function()

    def helper_no_raises() -> None:
        actual = list(
            fourchan_no_raises.search(
                board=board, text=search_text, user_agent="test", cloudflare_cookies={}
            )
        )
        assert len(actual) == 0

    def helper() -> None:
        with pytest.raises(HTTPError):
            # The call to list() below forces the generator to execute; without it, the actual HTTP
            # call never happens
            list(
                fourchan.search(
                    board=board, text=search_text, user_agent="test", cloudflare_cookies={}
                )
            )

    with_mocks(403, helper_no_raises)
    with_mocks(404, helper_no_raises)
    with_mocks(500, helper_no_raises)
    with_mocks(403, helper)
    with_mocks(404, helper)
    with_mocks(500, helper)
