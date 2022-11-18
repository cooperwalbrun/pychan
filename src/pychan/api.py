import copy
import re
from datetime import datetime, timezone
from typing import Optional, Generator, Any
from uuid import uuid4

import requests
from bs4 import BeautifulSoup, Tag
from pyrate_limiter import Limiter, RequestRate, Duration
from requests import Response

from pychan.logger import PychanLogger, LogLevel
from pychan.models import File, Poster
from pychan.models import Post, Thread

_limiter = Limiter(RequestRate(1, Duration.SECOND))


def _find_first(selectable_entity: Tag, selector: str) -> Optional[Tag]:
    ret = selectable_entity.select(selector)
    if ret is not None and len(ret) > 0:
        return ret[0]
    else:
        return None


def _get_attribute(tag: Optional[Tag], attribute: str) -> Optional[str]:
    # Below, it is imperative that we use hasattr() instead of "x in y" syntax because these do not
    # mean the same thing in BeautifulSoup's API (only the former behaves as expected)
    if tag is not None and hasattr(tag, attribute):
        ret = tag[attribute]
        return ret[0] if isinstance(ret, list) else ret
    else:
        return None


def _safe_id_parse(text: Optional[str], *, offset: int) -> Optional[int]:
    # This function is meant to parse ID attribute values from 4chan's HTML into numeric values
    # containing just the raw ID number. For example, _safe_id_parse("t-12345678", offset=1) should
    # return 12345678.
    if text is not None and len(text) > offset:
        try:
            return int(text[offset:])
        except Exception:
            return None
    else:
        return None


def _text(element: Optional[Any]) -> Optional[str]:
    return element.text if element is not None and len(element.text.strip()) > 0 else None


def _sanitize_board(board: str) -> str:
    return board.lower().replace("/", "").strip()


class ParsingError(Exception):
    pass


class FourChan:
    _UNPARSABLE_BOARDS = ["f"]
    _POST_TEXT_SELECTOR = "blockquote.postMessage"

    def __init__(
        self,
        *,
        logger: Optional[PychanLogger] = None,
        raise_http_exceptions: bool = True,
        raise_parsing_exceptions: bool = True
    ):
        """

        :param logger: The logger instance to read for logging configuration, if any.
        :param raise_http_exceptions: Whether internal exceptions related to HTTP errors (e.g. HTTP
                                      500) should be raised so that users of this FourChan instance
                                      will see them.
        :param raise_parsing_exceptions: Whether internal exceptions related to parsing errors (e.g.
                                         due to invalid/unrecognized HTML on HTTP responses) should
                                         be raised so that users of this FourChan instance will see
                                         them.
        """

        self._agent = str(uuid4())
        self._logger = logger if logger is not None else PychanLogger(LogLevel.OFF)
        self._raise_http_exceptions = raise_http_exceptions
        self._raise_parsing_exceptions = raise_parsing_exceptions

    def _parse_error(self, message: str) -> None:
        if self._raise_parsing_exceptions:
            raise ParsingError(message)

    def _parse_file_from_html(self, post_html_element: Tag) -> Optional[File]:
        self._logger.debug(f"Attempting to parse a File out of {post_html_element}...")
        file_text = _find_first(post_html_element, ".fileText")
        file_anchor = _find_first(post_html_element, ".fileText a")
        href = _get_attribute(file_anchor, "href")
        if file_text is not None and file_anchor is not None and href is not None:
            href = "https:" + href if href.startswith("//") else href
            metadata = re.search(r"\((.+), ([0-9]+x[0-9]+)\)", file_text.text)
            if metadata is not None and len(metadata.groups()) > 1:
                size = metadata.group(1)
                dimensions = metadata.group(2).split("x")
                return File(href, file_anchor.text, size, (int(dimensions[0]), int(dimensions[1])))
            else:
                message = f"No file metadata could not be parsed from {file_text.text}"
                self._logger.error(message)
                self._parse_error(message)
                return None
        else:
            self._logger.debug(f"No file was discovered in {post_html_element}")
            return None

    def _parse_poster_from_html(self, post_html_element: Tag) -> Optional[Poster]:
        self._logger.debug(f"Attempting to parse a Poster out of {post_html_element}...")
        name = _text(_find_first(post_html_element, ".nameBlock > .name"))
        mod = _find_first(post_html_element, ".nameBlock > .id_mod") is not None
        uid = _text(_find_first(post_html_element, ".posteruid span"))
        flag = _get_attribute(_find_first(post_html_element, ".flag"), "title")
        if name is not None:
            return Poster(name, mod_indicator=mod, id=uid, flag=flag)
        else:
            self._logger.debug(f"No poster was discovered in {post_html_element}")
            return None

    def _parse_post_from_html(self, thread: Thread, post_html_element: Tag) -> Optional[Post]:
        self._logger.debug(f"Attempting to parse a Post out of {post_html_element}...")
        timestamp = _get_attribute(_find_first(post_html_element, ".dateTime"), "data-utc")
        if timestamp is None:
            message = f"No post timestamp was discovered in {post_html_element}"
            self._logger.error(message)
            self._parse_error(message)
            return None

        parsed_timestamp = datetime.fromtimestamp(int(timestamp), timezone.utc)
        poster = self._parse_poster_from_html(post_html_element)
        if poster is None:
            message = f"No poster was discovered in {post_html_element}"
            self._logger.error(message)
            self._parse_error(message)
            return None

        message_tag = _find_first(post_html_element, self._POST_TEXT_SELECTOR)
        if message_tag is not None:
            line_break_placeholder = str(uuid4())
            # The following approach to preserve HTML line breaks in the final post text is
            # based on this: https://stackoverflow.com/a/61423104
            for line_break in message_tag.select("br"):
                line_break.replaceWith(line_break_placeholder)
            text = message_tag.text.replace(line_break_placeholder, "\n")

            id = _safe_id_parse(_get_attribute(message_tag, "id"), offset=1)
            op = hasattr(post_html_element, "class") and "op" in post_html_element["class"]

            if id is not None and len(text) > 0:
                return Post(
                    thread,
                    id,
                    parsed_timestamp,
                    poster,
                    text,
                    is_original_post=op,
                    file=self._parse_file_from_html(post_html_element)
                )
            else:
                return None
        else:
            message = f"No post text was discovered in {post_html_element}"
            self._logger.error(message)
            self._parse_error(message)
            return None

    def _is_unparsable_board(self, board: str) -> bool:
        if board in self._UNPARSABLE_BOARDS:
            self._logger.warn((
                f"Detected that you are trying to interact with an unparsable board: {board}. "
                f"To avoid errors and undefined behavior, pychan will not attempt to interact with "
                f"this board."
            ))
            return True
        else:
            return False

    @_limiter.ratelimit("4chan", delay=True)
    def _throttle_request(self) -> None:
        # The throttling mechanism is defined as a dedicated function like this so that it can be
        # mocked in unit tests in a straightforward manner
        return

    def _request_helper(
        self,
        url: str,
        *,
        expect_404: bool = False,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None
    ) -> Optional[Response]:
        self._throttle_request()

        h = {} if headers is None else headers
        response = requests.get(url, headers={"User-Agent": self._agent, **h}, params=params)
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            if not expect_404:
                self._logger.warn(f"Received a 404 status code from {url}")
                if self._raise_http_exceptions:
                    response.raise_for_status()
            return None
        else:
            self._logger.error(f"Unexpected status code {response.status_code} when fetching {url}")
            if self._raise_http_exceptions:
                response.raise_for_status()
            return None

    def get_boards(self) -> list[str]:
        """
        Fetches all the boards within 4chan.

        :return: The board names (without slashes in their names) currently available on 4chan.
        """

        ret = []
        self._logger.info("Fetching all boards from 4chan...")

        # Below, we use https://boards.4channel.org/search instead of the homepage of 4chan due to
        # CloudFlare (and at the time of this writing, the VeNoMouS/cloudscraper repository on
        # GitHub does not work and seems to have disabled GitHub issues entirely)
        response = self._request_helper("https://boards.4channel.org/search")
        if response is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            board_list = _find_first(soup, ".boardList")
            if board_list is not None:
                for anchor in board_list.select("a"):
                    board = anchor.text
                    if board not in self._UNPARSABLE_BOARDS:
                        ret.append(board)

        self._logger.info(f"Fetched {len(ret)} board(s) from 4chan")
        return ret

    def get_threads(self, board: str) -> Generator[Thread, None, None]:
        """
        Fetches threads for a specific board. Only the first 10 pages of the given board will be
        returned, because 4chan does not keep any further threads readily-retrievable outside the
        archive.

        :param board: The board name to fetch threads for. You may include slashes. Examples: "/b/",
                      "b", "vg/", "/vg"
        :return: A Generator which yields threads one at a time until every thread in the given
                 board has been returned.
        """
        sanitized_board = _sanitize_board(board)
        if self._is_unparsable_board(sanitized_board):
            return

        def get(page_number: int) -> Optional[Response]:
            suffix = f"/{page_number}" if page_number > 1 else ""
            return self._request_helper(
                f"https://boards.4channel.org/{sanitized_board}" + suffix,
                expect_404=page_number != 1
            )

        seen_thread_numbers = set()

        p = 0
        response = None
        while p == 0 or response is not None:
            p += 1

            self._logger.info(f"Fetching page {p} of /{sanitized_board}/...")
            response = get(p)

            if response is not None:
                soup = BeautifulSoup(response.text, "html.parser")
                for thread in soup.select(".board > .thread"):
                    id = _safe_id_parse(_get_attribute(thread, "id"), offset=1)
                    if id is not None:
                        t = Thread(
                            sanitized_board,
                            id,
                            title=_text(_find_first(thread, ".desktop .subject")),
                            is_stickied=_find_first(thread, ".op .desktop .stickyIcon") is not None,
                            is_closed=_find_first(thread, ".op .desktop .closedIcon") is not None,
                            is_archived=_find_first(thread, ".op .desktop .archivedIcon")
                            is not None
                        )
                        if t.number not in seen_thread_numbers:
                            seen_thread_numbers.add(t.number)
                            yield t
                    else:
                        message = f"No thread ID was discovered in {thread}"
                        self._logger.error(message)
                        self._parse_error(message)
            else:
                self._logger.info((
                    f"Page {p} of /{sanitized_board}/ could not be fetched, so no further threads "
                    f"will be returned"
                ))

    def get_archived_threads(self, board: str) -> list[Thread]:
        """
        Fetches archived threads for a specific board. The titles of the returned threads will be
        the "excerpt" shown in 4chan, which could be either the thread's real title or a preview of
        the original post's text.

        :param board: The board name to fetch threads for. You may include slashes. Examples: "/b/",
                      "b", "vg/", "/vg"
        :return: The list of threads currently in the archive.
        """
        sanitized_board = _sanitize_board(board)
        if self._is_unparsable_board(sanitized_board):
            return []

        response = self._request_helper(f"https://boards.4chan.org/{sanitized_board}/archive")
        ret = []
        if response is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            for table_row in soup.select("#arc-list tbody tr"):
                id = _text(_find_first(table_row, "td"))
                if id is not None:
                    ret.append(
                        Thread(
                            sanitized_board,
                            int(id),
                            title=_text(_find_first(table_row, ".teaser-col")),
                            is_stickied=False,
                            is_closed=False,
                            is_archived=True
                        )
                    )

        return ret

    def get_posts(self, thread: Thread) -> list[Post]:
        """
        Fetches all the posts (includes the original post and all replies) within a thread.

        :param thread: The thread from which to fetch posts.
        :return: The list of posts currently in the thread. If there are no replies on the thread,
                 the returned list can be expected to have a single element (the original post).
        """
        t = copy.deepcopy(thread)
        t.board = _sanitize_board(t.board)

        if self._is_unparsable_board(t.board):
            return []

        self._logger.debug(f"Fetching posts for {t}...")
        response = self._request_helper(
            "https://boards.4channel.org/{}/thread/{}/".format(t.board, t.number)
        )
        if response is None:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        ret: list[Post] = []
        for post in soup.select(".post"):
            p = self._parse_post_from_html(t, post)
            if p is not None:
                for quote_link in post.select(f"{self._POST_TEXT_SELECTOR} a.quotelink"):
                    href = _get_attribute(quote_link, "href")
                    if href is not None and href.startswith("#p"):
                        # The #p check in the href above also guards against the situation where
                        # a post is quote-linking to a post in a different thread, which is
                        # currently beyond the scope of this function's implementation
                        quoted_post_number = _safe_id_parse(href, offset=2)
                        for ret_post in ret:
                            if ret_post.number == quoted_post_number and \
                                    not any([r.number == p.number for r in ret_post.replies]):
                                ret_post.replies.append(p)
                                break

                if p.is_original_post:
                    t.title = _text(_find_first(post, ".desktop .subject"))
                    t.is_stickied = _find_first(post, ".desktop .stickyIcon") is not None
                    t.is_closed = _find_first(post, ".desktop .closedIcon") is not None
                    t.is_archived = _find_first(post, ".desktop .archivedIcon") is not None
                    p.thread = t

                ret.append(p)

        return ret

    def search(self, *, board: str, text: str) -> Generator[Thread, None, None]:
        """
        Executes a given text query in a given board. This method leverages 4chan's native search
        functionality.

        :param board: The board within which to perform the search. You may include slashes.
                      Examples: "/b/", "b", "vg/", "/vg"
        :param text: The text against which to search.
        :return: A Generator which yields threads one at a time until every thread in the search
                 results has been returned.
        """
        sanitized_board = _sanitize_board(board)
        if self._is_unparsable_board(sanitized_board):
            return

        query = text.strip()

        def get(o: int) -> Optional[Response]:
            return self._request_helper(
                "https://find.4channel.org/api",
                headers={"Accept": "application/json"},
                params={
                    "o": str(o), "q": query, "b": sanitized_board
                }
            )

        seen_thread_numbers = set()

        offset = 0
        new_this_iteration = True
        while new_this_iteration:
            new_this_iteration = False

            response = get(offset)
            offset += 10

            if response is not None:
                for t in response.json().get("threads", []):
                    number = t.get("thread", "")
                    posts = t.get("posts", [])
                    if len(number) > 1 and len(posts) > 0:
                        title = posts[0].get("sub", "")
                        title = title if len(title.strip()) > 0 else None
                        thread = Thread(
                            t.get("board", sanitized_board),
                            int(number[1:]),
                            title=title,
                            # Closed/stickied/archived threads are not returned in search results
                            is_stickied=False,
                            is_closed=False,
                            is_archived=False
                        )
                        if thread.number not in seen_thread_numbers:
                            new_this_iteration = True
                            seen_thread_numbers.add(thread.number)
                            yield thread
                        else:
                            self._logger.debug(
                                f"Skipping a duplicate thread in the search results: {thread}"
                            )
