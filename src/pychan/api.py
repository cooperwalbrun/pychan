import copy
import re
from datetime import datetime, timezone
from typing import Optional, Generator, Any
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from ratelimit import sleep_and_retry, limits
from requests import Response

from pychan.logger import PychanLogger, LogLevel
from pychan.models import File, Poster
from pychan.models import Post, Thread


def _find_first(selectable_entity: Any, selector: str) -> Optional[Any]:
    ret = selectable_entity.select(selector)
    if ret is not None and len(ret) > 0:
        return ret[0]
    else:
        return None


def _text(element: Optional[Any]) -> Optional[str]:
    return element.text if element is not None and len(element.text.strip()) > 0 else None


def _sanitize_board(board: str) -> str:
    return board.lower().replace("/", "").strip()


class FourChan:
    _UNPARSABLE_BOARDS = ["f"]
    _POST_TEXT_SELECTOR = "blockquote.postMessage"

    def __init__(self, logger: Optional[PychanLogger] = None):
        self._agent = str(uuid4())
        self._logger = logger if logger is not None else PychanLogger(LogLevel.OFF)

    def _parse_file_from_html(self, post_html_element: Any) -> Optional[File]:
        self._logger.debug(f"Attempting to parse a File out of {post_html_element}...")
        file_text = _find_first(post_html_element, ".fileText")
        file_anchor = _find_first(post_html_element, ".fileText a")
        if file_text is not None and file_anchor is not None:
            href = file_anchor["href"]
            href = "https:" + href if href.startswith("//") else href
            print(file_text.text)
            metadata = re.search(r"\((.+), ([0-9]+x[0-9]+)\)", file_text.text)
            if len(metadata.groups()) > 1:
                size = metadata.group(1)
                dimensions = metadata.group(2).split("x")
                return File(href, file_anchor.text, size, (int(dimensions[0]), int(dimensions[1])))
            else:
                self._logger.error(f"No file metadata could not be parsed from {file_text.text}")
                return None
        else:
            self._logger.debug(f"No file was discovered in {post_html_element}")
            return None

    def _parse_poster_from_html(self, post_html_element: Any) -> Optional[Poster]:
        self._logger.debug(f"Attempting to parse a Poster out of {post_html_element}...")
        name = _text(_find_first(post_html_element, ".nameBlock > .name"))
        mod = _find_first(post_html_element, ".nameBlock > .id_mod") is not None
        uid = _text(_find_first(post_html_element, ".posteruid span"))
        flag = _find_first(post_html_element, ".flag")
        flag = flag["title"] if flag is not None and hasattr(flag, "title") else None
        if name is not None:
            return Poster(name, mod_indicator=mod, id=uid, flag=flag)
        else:
            self._logger.debug(f"No poster was discovered in {post_html_element}")
            return None

    def _parse_post_from_html(self, thread: Thread, post_html_element: Any) -> Optional[Post]:
        self._logger.debug(f"Attempting to parse a Post out of {post_html_element}...")
        timestamp = _find_first(post_html_element, ".dateTime")
        if timestamp is not None and hasattr(timestamp, "data-utc"):
            timestamp = datetime.fromtimestamp(int(timestamp["data-utc"]), timezone.utc)
        else:
            self._logger.error(f"No post timestamp was discovered in {post_html_element}")
            return None

        poster = self._parse_poster_from_html(post_html_element)
        if poster is None:
            self._logger.error(f"No poster was discovered in {post_html_element}")
            return None

        message = _find_first(post_html_element, self._POST_TEXT_SELECTOR)
        if message is not None:
            line_break_placeholder = str(uuid4())
            # The following approach to preserve HTML line breaks in the final post text is
            # based on this: https://stackoverflow.com/a/61423104
            for line_break in message.select("br"):
                line_break.replaceWith(line_break_placeholder)
            text = message.text.replace(line_break_placeholder, "\n")

            op = hasattr(post_html_element, "class") and "op" in post_html_element["class"]

            if len(text) > 0:
                return Post(
                    thread,
                    int(message["id"][1:]),
                    timestamp,
                    poster,
                    text,
                    is_original_post=op,
                    file=self._parse_file_from_html(post_html_element)
                )
        else:
            self._logger.error(f"No post text was discovered in {post_html_element}")
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

    @sleep_and_retry
    @limits(calls=1, period=0.75)
    def _request_throttle(self) -> None:
        # This is a separate function primarily to allow us to unit test _request_helper() without
        # doing a lot of work to bypass/mock the rate-limiting annotations
        return

    def _request_helper(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None
    ) -> Optional[Response]:
        self._request_throttle()

        h = {} if headers is None else headers
        response = requests.get(url, headers={"User-Agent": self._agent, **h}, params=params)
        if response.status_code == 200:
            return response
        elif response.status_code == 404:
            # We have to swallow 404 errors because threads can be deleted in real-time between
            # HTTP requests pychan sends, and we do not want to choke when that happens. Imagine the
            # following scenario for example: you fetch the threads for a board, then one of those
            # threads gets deleted, then you try to fetch the posts for that thread; this would lead
            # to a 404.
            self._logger.warn(f"Received a 404 status code from {url}")
            return None
        else:
            self._logger.error(f"Unexpected status code {response.status_code} when fetching {url}")
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
        returned, because 4chan does not keep any further threads readily-retrievable.

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
            return self._request_helper(f"https://boards.4channel.org/{sanitized_board}" + suffix)

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
                    t = Thread(
                        board,
                        int(thread["id"][1:]),
                        title=_text(_find_first(thread, ".desktop .subject")),
                        is_stickied=_find_first(thread, ".op .desktop .stickyIcon") is not None,
                        is_closed=_find_first(thread, ".op .desktop .closedIcon") is not None,
                        is_archived=_find_first(thread, ".op .desktop .archivedIcon") is not None
                    )
                    if t.number not in seen_thread_numbers:
                        seen_thread_numbers.add(t.number)
                        yield t
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
        ret = []
        for post in soup.select(".post"):
            p = self._parse_post_from_html(t, post)
            if p is not None:
                for quote_link in post.select(f"{self._POST_TEXT_SELECTOR} a.quotelink"):
                    if hasattr(quote_link, "href") and quote_link["href"].startswith("#p"):
                        # The #p check in the href above also guards against the situation where
                        # a post is quote-linking to a post in a different thread, which is
                        # currently beyond the scope of this function's implementation
                        quoted_post_number = int(quote_link["href"][2:])
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
        Searches a given text query in a given board. This method leverages 4chan's native search
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
