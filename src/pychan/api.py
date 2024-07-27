import copy
import json
import re
from datetime import datetime, timezone
from typing import Optional, Generator, TypedDict, cast
from uuid import uuid4

import requests
from bs4 import BeautifulSoup, Tag
from pyrate_limiter import Limiter, Rate, Duration
from requests import Response

from pychan.logger import PychanLogger, LogLevel
from pychan.models import File, Poster
from pychan.models import Post, Thread

# Note: using a max_delay of 2000 below should make it so that this rate limiter will block the
# current thread until the request can be issued again. Note that using a delay greater than the
# actual throttle (1 second per request) will ensure we always wait long enough for the request to
# be issued.
# See: https://pyratelimiter.readthedocs.io/en/latest/index.html?highlight=wait#rate-limit-delays
_limiter = Limiter(Rate(1, Duration.SECOND), max_delay=2000)


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
    # containing just the raw ID number. Refer to the unit tests to see expected inputs/outputs.
    if text is not None and len(text) > offset:
        try:
            return int(text[offset:])
        except Exception:
            return None
    else:
        return None


def _text(element: Optional[Tag]) -> Optional[str]:
    return element.text if element is not None and len(element.text.strip()) > 0 else None


def _sanitize_board(board: str) -> str:
    return board.lower().replace("/", "").strip()


JSONThread = TypedDict(
    "JSONThread", {
        "sub": Optional[str | bool], "sticky": Optional[int], "closed": Optional[int]
    }
)
JSONCatalog = TypedDict("JSONCatalog", {"threads": dict[str, JSONThread]})


class ParsingError(Exception):
    pass


class FourChan:
    _UNPARSABLE_BOARDS = ["f"]
    _POST_TEXT_SELECTOR = "blockquote.postMessage"
    _USER_AGENT_HEADER_NAME = "User-Agent"

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
                return File(
                    href,
                    file_anchor.text,
                    size, (int(dimensions[0]), int(dimensions[1])),
                    is_spoiler=_find_first(post_html_element, ".imgspoiler") is not None
                )
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

    def _parse_catalog_json_from_javascript(self, javascript_text: str) -> Optional[JSONCatalog]:
        text = javascript_text
        result = re.search(r"var\s*catalog\s*=\s*({.+};)", text)
        if result is None:
            return None

        while result is not None:
            candidate = result.group(1).removesuffix(";")
            try:
                return cast(JSONCatalog, json.loads(candidate))
            except:
                text = candidate[:-1]
                # We already removed the "var catalog" portion above, so now we just check the JSON
                result = re.search(r"({.+};)", text)

        message = (
            f"Unable to parse the catalog JSON out of the following JavaScript: {javascript_text}"
        )
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

    def _throttle_request(self) -> None:
        # The throttling mechanism is defined as a dedicated function like this so that it can be
        # mocked in unit tests in a straightforward manner
        _limiter.try_acquire("4chan")
        return

    def _request_helper(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None
    ) -> Optional[Response]:
        self._throttle_request()

        h = {} if headers is None else headers
        response = requests.get(
            url, headers={
                self._USER_AGENT_HEADER_NAME: self._agent, **h
            }, params=params
        )
        if response.status_code == 200:
            return response
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

        # Below, we just choose a random 4chan page which includes the header/footer containing the
        # list of boards
        response = self._request_helper("https://boards.4chan.org/pol/catalog")
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

    def get_threads(self, board: str) -> list[Thread]:
        """
        Fetches all threads from a given board's catalog.

        :param board: The board name to fetch threads for. You may include slashes. Examples: "/b/",
                      "b", "vg/", "/vg"
        :return: A list of threads currently in the board.
        """
        sanitized_board = _sanitize_board(board)
        if self._is_unparsable_board(sanitized_board):
            return []

        self._logger.info(f"Fetching threads for board /{sanitized_board}/...")

        response = self._request_helper(f"https://boards.4chan.org/{sanitized_board}/catalog")
        if response is not None:
            soup = BeautifulSoup(response.text, "html.parser")
            for script in soup.select('script[type="text/javascript"]'):
                json_data = self._parse_catalog_json_from_javascript(script.text)
                if json_data is not None and "threads" in json_data and \
                        isinstance(json_data["threads"], dict):
                    ret = []
                    for id, thread in json_data["threads"].items():
                        parsed_id = _safe_id_parse(id, offset=0)
                        if parsed_id is not None:
                            title = thread.get("sub")
                            if isinstance(title, bool):
                                # The title will only be a boolean if no title exists (False)
                                title = None
                            title = title if title is not None and len(title.strip()) > 0 else None
                            ret.append(
                                Thread(
                                    sanitized_board,
                                    parsed_id,
                                    title=title,
                                    is_stickied=thread.get("sticky") == 1,
                                    is_closed=thread.get("closed") == 1,
                                    is_archived=False
                                )
                            )

                    if len(ret) > 0:
                        return ret
        message = (
            f"No thread data could be parsed out of the HTML for the catalog page of the board "
            f"/{sanitized_board}/"
        )
        self._logger.error(message)
        self._parse_error(message)
        return []

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

        self._logger.info(f"Fetching archived threads for board /{sanitized_board}/...")

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

        self._logger.info(f"Fetching posts for {t}...")

        response = self._request_helper(
            "https://boards.4chan.org/{}/thread/{}/".format(t.board, t.number)
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
                        quoted_post_number = _safe_id_parse(href, offset=len("#p"))
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

    def search(self, *, board: str, text: str, user_agent: str,
               cloudflare_cookies: dict[str, str]) -> Generator[Thread, None, None]:
        """
        Executes a given text query in a given board. This method leverages 4chan's native search
        functionality.

        :param board: The board within which to perform the search. You may include slashes.
                      Examples: "/b/", "b", "vg/", "/vg"
        :param text: The text against which to search.
        :param user_agent: The User-Agent header value to use in the HTTP request. If this value is
                           not the same as the one that is "associated" with the provided
                           cloudflare_cookies, you will receive HTTP 403 errors.
        :param cloudflare_cookies: A dictionary mapping cookie names to their values, where these
                                   cookies are appropriate for bypassing the Cloudflare checks in
                                   front of the 4chan API. If this value is not the same one that is
                                   "associated" with the provided user_agent, you will receive HTTP
                                   403 errors.
        :return: A Generator which yields threads one at a time until every thread in the search
                 results has been returned.
        """
        sanitized_board = _sanitize_board(board)
        if self._is_unparsable_board(sanitized_board):
            return

        query = text.strip()

        def get(o: int) -> Optional[Response]:
            cookie = "; ".join([f"{k}={v}" for k, v in cloudflare_cookies.items()])
            return self._request_helper(
                "https://find.4chan.org/api",
                headers={
                    "Accept": "application/json",
                    "Origin": "https://boards.4chan.org",
                    "Referer": "https://boards.4chan.org/",
                    self._USER_AGENT_HEADER_NAME: user_agent,
                    "Cookie": cookie
                },
                params={
                    "o": str(o), "q": query, "b": sanitized_board
                }
            )

        seen_thread_numbers = set()

        offset = 0
        new_this_iteration = True
        while new_this_iteration:
            new_this_iteration = False

            self._logger.info((
                f"Searching offset {offset} for threads in board /{sanitized_board}/ matching text "
                f'"{text}"...'
            ))

            response = get(offset)
            offset += 10

            if response is not None:
                threads = response.json().get("threads", [])
                if isinstance(threads, list):
                    for t in threads:
                        try:
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
                        except Exception as e:
                            self._parse_error(str(e))
                else:
                    self._parse_error(
                        f'Detected an unexpected structure in the "threads" JSON field: {threads}'
                    )
