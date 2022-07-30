import copy
from typing import Optional, Generator, Any
from uuid import uuid4

import requests
from bs4 import BeautifulSoup
from ratelimit import sleep_and_retry, limits
from requests import Response

from pychan.logger import PychanLogger, LogLevel
from pychan.models import File
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


def _parse_post_from_html(thread: Thread, post: Any) -> Optional[Post]:
    op = "op" in post["class"]
    uid = _text(_find_first(post, "span.posteruid span"))

    file = None
    file_soup = _find_first(post, ".fileText a")
    if file_soup is not None:
        href = file_soup["href"]
        href = "https:" + href if href.startswith("//") else href
        file = File(href, name=file_soup.text)

    message = _find_first(post, "blockquote.postMessage")

    if message is not None:
        line_break_placeholder = str(uuid4())

        # The following approach to preserve HTML line breaks in the final post text is
        # based on this: https://stackoverflow.com/a/61423104
        for line_break in message.select("br"):
            line_break.replaceWith(line_break_placeholder)

        text = message.text.replace(line_break_placeholder, "\n").strip()

        if len(text) > 0:
            return Post(
                thread, int(message["id"][1:]), text, is_original_post=op, poster_id=uid, file=file
            )

    return None


class FourChan:
    def __init__(self, logger: Optional[PychanLogger] = None):
        self._agent = str(uuid4())
        self._logger = logger if logger is not None else PychanLogger(LogLevel.OFF)

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
            self._logger.warn(f"Received a 404 status from {url}")
            return None
        else:
            self._logger.error(f"Unexpected status code {response.status_code} when fetching {url}")
            return None

    def get_boards(self) -> list[str]:
        """
        Fetches all the boards within 4chan.

        :return: The board names (without slashes in their names) currently available on 4chan.
        """

        board_blacklist = ["f"]

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
                    if board not in board_blacklist:
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

        def get(page_number: int) -> Optional[Response]:
            suffix = f"/{page_number}" if page_number > 1 else ""
            return self._request_helper(f"https://boards.4channel.org/{sanitized_board}" + suffix)

        p = 0
        response = None
        while p == 0 or response is not None:
            p += 1

            self._logger.info(f"Fetching page {p} of /{sanitized_board}/...")
            response = get(p)

            if response is not None:
                soup = BeautifulSoup(response.text, "html.parser")
                if len(soup.select(".board > .thread")) == 0:
                    raise ValueError("shit")
                for thread in soup.select(".board > .thread"):
                    title = _text(_find_first(thread, ".subject"))
                    thread_number = int(thread["id"][1:])
                    yield Thread(board, thread_number, title=title)
            else:
                self._logger.info((
                    f"Page {p} of /{sanitized_board}/ could not be fetched, so no further threads "
                    f"will be returned"
                ))

    def get_posts(self, thread: Thread) -> list[Post]:
        """
        Fetches all the posts (includes the original post and all replies) within a thread.

        :param thread: The thread from which to fetch posts.
        :return: The list of posts currently in the thread. If there are no replies on the thread,
                 the returned list can be expected to have a single element (the original post).
        """
        t = copy.deepcopy(thread)
        t.board = _sanitize_board(t.board)

        self._logger.debug(f"Fetching posts for {t}...")
        response = self._request_helper(f"https://boards.4channel.org/{t.board}/thread/{t.number}/")
        if response is None:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        ret = []
        for post in soup.select("div.post"):
            p = _parse_post_from_html(t, post)
            if p is not None:
                if p.is_original_post and thread.title is None:
                    title = _text(_find_first(post, ".subject"))
                    if title is not None:
                        t.title = title

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
        query = text.strip()

        def get(o: int) -> Optional[Response]:
            return self._request_helper(
                "https://find.4channel.org/api",
                headers={"Accept": "application/json"},
                params={
                    "o": str(o), "q": query, "b": sanitized_board
                }
            )

        # The search results pages tend to overlap with one another, so this method requires
        # additional book-keeping in order to ensure duplicate threads are not returned
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
                    op = t.get("posts", [])
                    if len(number) > 1 and len(op) > 0:
                        title = op[0].get("sub", "")
                        title = title if len(title.strip()) > 0 else None
                        thread = Thread(
                            t.get("board", sanitized_board), int(number[1:]), title=title
                        )
                        if thread.number not in seen_thread_numbers:
                            new_this_iteration = True
                            seen_thread_numbers.add(thread.number)
                            yield thread
